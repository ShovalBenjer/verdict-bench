"""Rubric judge: cross-family LLM judging of decision REASONING quality.

Fills the judgments table (schema.sql) that sat empty since S2 was planned.
Three axes, scored 1-5, rubric_version r1:
  fidelity        does the reasoning cite the actually-decisive fields of the case
  evidence        are claims grounded in case data rather than asserted
  proportionality does it weigh exposure and track record the way POLICY.md does

Design choices, on the record:
- Cross-family assignment (SPEC.md: the judge is never in the contestant pool
  for that cell, and never the same family): claude cells are judged by
  gemini-flash, gemini cells by claude-haiku, open-model cells (llama,
  nemotron, qwen) by gemini-flash. Grounding: self-preference bias is
  measured, not folklore (arXiv 2410.21819).
- The judge does NOT see the expected label. It grades reasoning quality;
  handing it the answer would halo correct decisions into high rubric scores
  and make the column redundant with accuracy.
- Only decision-suite kinds are judged (golden, perturbation): robustness
  cases measure resistance, not reasoning craft.
- A dual-judge overlap runs BOTH judges over the v4/gemini-flash cell so
  inter-judge agreement is a measured number, not an assumption.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from providers import call_claude_cli, call_gemini

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "state" / "verdict.sqlite3"
POLICY = (ROOT / "assignment" / "case-study" / "case-study" / "POLICY.md").read_text()

RUBRIC_VERSION = "r1"

JUDGE_SYSTEM = f"""You are grading the quality of another model's account-review reasoning
against the policy below. You are NOT deciding the case and you are NOT told
the correct answer; grade the reasoning's craft, not its conclusion.

POLICY:
{POLICY}

Score three axes, each an integer 1-5:
- fidelity: does the reasoning cite the fields of the case that actually
  drive the decision under this policy (5 = names the decisive fields
  precisely; 1 = generic talk, decisive fields never mentioned)?
- evidence: are its claims grounded in specific case data (5 = every claim
  traceable to a field; 1 = assertions with no anchor)?
- proportionality: does it weigh exposure, tenure and track record the way
  the policy's weighing section requires (5 = explicit, correct weighing;
  1 = mechanical rule-matching with no weighing)?

Output EXACTLY one JSON object, first character {{, no markdown fences:
{{"fidelity": n, "evidence": n, "proportionality": n, "rationale": "<one sentence>"}}"""


def judge_for(model_id: str, overlap: bool = False) -> list[str]:
    """Cross-family judge id(s). `overlap` adds the second-family judge."""
    if model_id.startswith("claude"):
        judges = ["gemini-flash"]
    elif model_id.startswith("gemini"):
        judges = ["claude-haiku"]
    else:
        judges = ["gemini-flash"]
    if overlap:
        judges = ["gemini-flash", "claude-haiku"]
    return judges


def call_judge(judge_id: str, content: str) -> tuple[dict | None, str]:
    if judge_id == "gemini-flash":
        r = call_gemini("gemini-2.5-flash", JUDGE_SYSTEM, content)
    elif judge_id == "claude-haiku":
        r = call_claude_cli("claude-haiku-4-5-20251001", JUDGE_SYSTEM, content)
    else:
        raise ValueError(f"unknown judge {judge_id}")
    raw = r.raw_output
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None, raw
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None, raw
    try:
        scores = {k: float(obj[k]) for k in ("fidelity", "evidence", "proportionality")}
    except (KeyError, TypeError, ValueError):
        return None, raw
    if not all(1.0 <= v <= 5.0 for v in scores.values()):
        return None, raw
    return scores, raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", nargs="+", default=["v3", "v4", "v4b"])
    ap.add_argument("--limit", type=int, default=None, help="max judge calls (smoke)")
    a = ap.parse_args()
    con = sqlite3.connect(DB)
    placeholders = ",".join("?" for _ in a.versions)
    rows = con.execute(
        f"""SELECT r.run_id, r.case_id, r.prompt_version, r.model_id,
                   r.decision, r.reasoning, c.path
            FROM runs r JOIN cases c USING(case_id)
            WHERE r.prompt_version IN ({placeholders})
              AND c.kind IN ('golden','perturbation')
              AND r.reasoning IS NOT NULL AND r.decision IS NOT NULL
            ORDER BY r.run_id""", a.versions).fetchall()
    # first run per (cell, case)
    first: dict[tuple[str, str, str], tuple] = {}
    for row in rows:
        first.setdefault((row[2], row[3], row[1]), row)
    already = {(j, r) for r, j in con.execute(
        "SELECT run_id, judge_model FROM judgments WHERE rubric_version=?",
        (RUBRIC_VERSION,))}
    done = 0
    for (pv, mid, cid), (run_id, _, _, _, decision, reasoning, path) in sorted(first.items()):
        overlap = (pv, mid) == ("v4", "gemini-flash")
        for judge_id in judge_for(mid, overlap=overlap):
            if (run_id, judge_id) in already:
                continue
            if a.limit is not None and done >= a.limit:
                print(f"limit {a.limit} reached")
                return
            case_json = Path(path).read_text()
            content = (f"CASE:\n{case_json}\n\nMODEL DECISION: {decision}\n"
                       f"MODEL REASONING:\n{reasoning}")
            scores, raw = call_judge(judge_id, content)
            if scores is None:
                # recorded as a judge contract failure, never silently skipped
                con.execute(
                    "INSERT INTO judgments (run_id,judge_model,rubric_version,raw) "
                    "VALUES (?,?,?,?)", (run_id, judge_id, RUBRIC_VERSION, raw[:4000]))
                con.commit()
                print(f"{cid} x {mid} [{pv}] judged by {judge_id} -> PARSE FAIL")
                done += 1
                continue
            con.execute(
                "INSERT INTO judgments (run_id,judge_model,rubric_version,"
                "fidelity,evidence,proportionality,raw) VALUES (?,?,?,?,?,?,?)",
                (run_id, judge_id, RUBRIC_VERSION, scores["fidelity"],
                 scores["evidence"], scores["proportionality"], raw[:4000]))
            con.commit()
            print(f"{cid} x {mid} [{pv}] judged by {judge_id} -> "
                  f"f={scores['fidelity']:.0f} e={scores['evidence']:.0f} "
                  f"p={scores['proportionality']:.0f}")
            done += 1
    print(f"judged {done} run(s)")


if __name__ == "__main__":
    main()
