"""Run the DSPy comparison arm end to end:

1. Load the 12 active cases, split into 8 train (adjudicated + construction
   source) / 4 expert-labeled eval (CASE-101, 102, 106, 108).
2. Baseline (unoptimized dspy.Predict) accuracy on expert-4 and on all-12.
3. Compile with BootstrapFewShot (max_bootstrapped_demos=4,
   max_labeled_demos=4) using only the 8 train cases.
4. Optimized accuracy on the same two sets.
5. Extract the verbatim rendered prompt (system + demos + user) that the
   compiled program actually sent for one eval case, from lm.history.
6. Write experiments/dspy_arm/scores.json (per-case decisions, both phases,
   both sets, call counts) and experiments/dspy_arm/optimized_prompt.txt.

Never writes to state/verdict.sqlite3. All output lives in this directory.
"""
from __future__ import annotations

import json
from pathlib import Path

import dspy
from dspy.teleprompt import BootstrapFewShot

from arm import (
    build_program,
    build_split,
    configure_lm,
    decision_exact_match,
    load_active_cases,
    read_env_key,
)

OUT_DIR = Path(__file__).resolve().parent


def run_on(program: dspy.Module, examples: list[dspy.Example]) -> list[dict]:
    """Run program on each example, return per-case result records. A failed
    call (exception from the LM/adapter boundary) is recorded with
    decision=None and error=str(e), never silently dropped or coerced into a
    false 'correct'."""
    rows = []
    for ex in examples:
        try:
            pred = program(case_json=ex.case_json)
            predicted = getattr(pred, "decision", None)
            reasoning = getattr(pred, "reasoning", None)
            error = None
        except Exception as e:  # boundary: LM/adapter call, record don't swallow
            predicted, reasoning, error = None, None, str(e)
        correct = (
            error is None
            and predicted is not None
            and str(predicted).strip().upper() == ex.decision
        )
        rows.append({
            "case_id": ex.case_id,
            "expected": ex.decision,
            "predicted": predicted,
            "correct": correct,
            "error": error,
            "reasoning_snippet": (reasoning or "")[:300],
        })
    return rows


def accuracy(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum(1 for r in rows if r["correct"]) / len(rows)


def extract_rendered_prompt(program: dspy.Module, lm: dspy.LM, sample_case_json: str) -> str:
    """Runs one live call through the compiled program and returns the exact
    rendered message list DSPy/LiteLLM sent to the model (system + few-shot
    demos + the user turn), read from lm.history. This is the verbatim prompt,
    not a reconstruction from signature.instructions + demos."""
    before = len(lm.history)
    program(case_json=sample_case_json)
    assert len(lm.history) == before + 1, "expected exactly one LM call for prompt extraction"
    messages = lm.history[-1]["messages"]
    lines = []
    for msg in messages:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        lines.append(f"=== role: {role} ===\n{content}\n")
    return "\n".join(lines)


def main() -> None:
    api_key = read_env_key("GEMINI_API_KEY")
    lm = configure_lm(api_key)

    cases = load_active_cases()
    train, expert_eval = build_split(cases)
    all_examples = train + expert_eval
    assert len(all_examples) == 12, f"expected 12 active cases, got {len(all_examples)}"
    assert len(train) == 8 and len(expert_eval) == 4

    calls_before_baseline = len(lm.history)

    baseline = build_program()
    baseline_expert_rows = run_on(baseline, expert_eval)
    baseline_all_rows = run_on(baseline, all_examples)

    calls_after_baseline = len(lm.history)

    optimizer = BootstrapFewShot(
        metric=decision_exact_match,
        max_bootstrapped_demos=4,
        max_labeled_demos=4,
    )
    compiled = optimizer.compile(build_program(), trainset=train)

    calls_after_compile = len(lm.history)

    optimized_expert_rows = run_on(compiled, expert_eval)
    optimized_all_rows = run_on(compiled, all_examples)

    calls_after_optimized_eval = len(lm.history)

    prompt_text = extract_rendered_prompt(compiled, lm, expert_eval[0].case_json)
    calls_after_extraction = len(lm.history)

    (OUT_DIR / "optimized_prompt.txt").write_text(prompt_text)

    demo_case_ids = []
    try:
        predictor = compiled.predictors()[0]
        demo_case_ids = [
            next((ex.case_id for ex in train if ex.case_json == d.get("case_json")), "?")
            for d in predictor.demos
        ]
    except Exception:
        demo_case_ids = ["<could not introspect demos>"]

    scores = {
        "n_active_cases": 12,
        "n_train": len(train),
        "n_expert_eval": len(expert_eval),
        "expert_eval_case_ids": [ex.case_id for ex in expert_eval],
        "train_case_ids": [ex.case_id for ex in train],
        "baseline": {
            "expert_4_accuracy": accuracy(baseline_expert_rows),
            "all_12_accuracy": accuracy(baseline_all_rows),
            "expert_4_rows": baseline_expert_rows,
            "all_12_rows": baseline_all_rows,
        },
        "optimized": {
            "optimizer": "BootstrapFewShot(max_bootstrapped_demos=4, max_labeled_demos=4)",
            "demo_case_ids_used": demo_case_ids,
            "expert_4_accuracy": accuracy(optimized_expert_rows),
            "all_12_accuracy": accuracy(optimized_all_rows),
            "expert_4_rows": optimized_expert_rows,
            "all_12_rows": optimized_all_rows,
        },
        "api_calls": {
            "baseline_expert_and_all12_eval": calls_after_baseline - calls_before_baseline,
            "bootstrap_compile": calls_after_compile - calls_after_baseline,
            "optimized_expert_and_all12_eval": calls_after_optimized_eval - calls_after_compile,
            "prompt_extraction_sample": calls_after_extraction - calls_after_optimized_eval,
            "total": calls_after_extraction - calls_before_baseline,
        },
        "lm_config": {
            "model": "gemini/gemini-2.5-flash",
            "temperature": 0.2,
            "max_tokens": 4096,
        },
    }

    (OUT_DIR / "scores.json").write_text(json.dumps(scores, indent=2))

    print("baseline expert-4:", scores["baseline"]["expert_4_accuracy"])
    print("baseline all-12:  ", scores["baseline"]["all_12_accuracy"])
    print("optimized expert-4:", scores["optimized"]["expert_4_accuracy"])
    print("optimized all-12:  ", scores["optimized"]["all_12_accuracy"])
    print("total API calls:", scores["api_calls"]["total"])


if __name__ == "__main__":
    main()
