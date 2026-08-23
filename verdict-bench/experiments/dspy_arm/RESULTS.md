Location: experiments/dspy_arm/. Everything here is isolated from engine/, state/, assignment/, docs/, tests/, Makefile, and pyproject. No write to state/verdict.sqlite3 happened at any point (verified by inspection of run.py and by not opening that file for writing anywhere in this arm).

## What ran

Files:
- arm.py: signature, program, data loading (keyed by the case_id field inside each JSON file, not the filename), train/eval split, exact-match metric, LM config, key reading.
- run.py: baseline eval, BootstrapFewShot compile, optimized eval, prompt extraction, writes scores.json and optimized_prompt.txt.
- smoke_test.py: the one-off check that confirmed dspy.LM("gemini/gemini-2.5-flash", ...) returns a parseable field before the full run was built. Kept for reference, not part of the scored pipeline.
- scores.json: full per-case results for both phases and both evaluation sets, plus call counts.
- optimized_prompt.txt: the verbatim rendered message list DSPy/LiteLLM sent for one live call through the compiled program (system + 4 few-shot demos + the user turn for CASE-101), read directly from lm.history, not reconstructed from signature.instructions plus a demo list printed separately.

Model: gemini-2.5-flash through DSPy's LiteLLM integration ("gemini/gemini-2.5-flash"), temperature 0.2, max_tokens 4096. API key read from ~/.env (GEMINI_API_KEY), same env-first-then-~/.env-fallback shape as engine/providers.py:_env, never printed or logged.

Data: 12 active cases from data/cases/*.json, matched to data/labels.json by the case_id field found inside each case file. The one retired label (CASE-101-P1, "internally inconsistent perturbation") was excluded, matching the 12-case suite the hand ladder scores against.

Split (as specified in the task): the 4 expert-labeled cases (CASE-101, CASE-102, CASE-106, CASE-108, source "expert" in labels.json) are the held-out eval set. The other 8 active cases (source "adjudicated" or "construction": CASE-103, 104, 105, 107, 113, and the perturbation twins CASE-101-P1B, CASE-104-P2, CASE-113-P3) are what BootstrapFewShot saw during compilation.

Signature: one dspy.Signature (case_json -> decision, reasoning). The docstring carries a de-dashed transcription of the policy in assignment/case-study/case-study/POLICY.md (dashes removed per this repo's writing-style rule; the wording is otherwise a close paraphrase, not a byte-identical copy of POLICY.md). This gives DSPy the same raw material the hand ladder's v2 rung gives the model (policy verbatim plus the output contract), not the hand-engineered decision procedure that v3 and later rungs add on top (the ordered REJECT/HOLD/APPROVE steps, the look-alike counterexamples, the worked proportionality and card-testing examples).

Optimizer: BootstrapFewShot(max_bootstrapped_demos=4, max_labeled_demos=4), MIPROv2 skipped, both per the task's own steer given the 90-minute box and n=8 trainset.

Metric: exact match on the decision field vs the expected label. A missing or out-of-set decision counts as incorrect, never raises.

## Scores

All numbers are decision accuracy only. Contract strictness is not compared: the hand ladder's parse_contract in engine/providers.py gates on the raw output being a single parseable JSON object with the two required keys; DSPy's ChatAdapter parses named `[[ ## field ## ]]` sections and has no equivalent strict/loose distinction, so the two systems are not measuring the same thing on that axis. Decision accuracy is the only comparable number.

| Phase | Expert-4 (101/102/106/108) | All-12 |
|---|---|---|
| DSPy baseline (unoptimized dspy.Predict, policy in signature, zero demos) | 4/4 (100%) | 12/12 (100%) |
| DSPy optimized (BootstrapFewShot, 4 demos) | 4/4 (100%) | 12/12 (100%) |

Both DSPy phases hit 12/12 on all 12 active cases and 4/4 on the expert-labeled subset. The expert-4 numbers were computed twice (once standalone, once as a subset of the all-12 pass) and the two readings agree on every case (checked programmatically, zero mismatches), so this is not an artifact of run-to-run nondeterminism at temperature 0.2 on this suite.

Hand-ladder comparator, read from state/verdict.sqlite3 (read-only, not modified): the only complete single-pass gemini-flash runs on all 12 active cases are v2 and v3.

| Hand prompt | gemini-flash, all 12 (single clean pass) |
|---|---|
| v1 (naive, no policy) | 11/12 (91.7%) |
| v2 (policy verbatim + contract, no procedure) | 12/12 (100%) |
| v3 (v2 + hand-written weighing procedure) | 11/12 (91.7%), missed CASE-113-P3 |
| v4 / v4c (later ladder rungs) | not comparable: v4's stored gemini-flash rows include 5 repeated attempts at CASE-113-P3 rather than one clean 12-case pass, and v4c has exactly 1 stored gemini-flash row. The hand ladder's final rung was never run to completion against this model, so it cannot be used as the top-of-ladder comparator here. |

The honest framing: DSPy with only the policy document (no hand-written procedure) matched v2, which gives the model the same raw material (policy plus contract, no procedure) and also hit 12/12. It also matched, and on this run beat, v3, which adds the hand-engineered decision procedure on top of the same policy and still missed CASE-113-P3 (a perturbation case) in its one clean pass. That is the real comparison this arm supports: whether few-shot demos substitute for a hand-written procedure layered on the same policy text, not "DSPy vs the ladder" in general, since the ladder's own top rung has no complete run to compare against.

## What the optimized prompt looks like, qualitatively, vs the hand ladder

The compiled program used exactly 4 demos (max_bootstrapped_demos and max_labeled_demos were both 4, against an 8-case trainset, so the optimizer had room to use up to 8 and used half): CASE-103, CASE-104, CASE-105, CASE-107. None of the three perturbation twins in the trainset (CASE-101-P1B, CASE-104-P2, CASE-113-P3) ended up as a demo on this run, so the sharpest version of the leakage risk (a near-duplicate of an eval case, with the opposite label, sitting in a few-shot demo) did not materialize here; it could have, and would not have been visible from the accuracy number alone.

Structurally the optimized prompt (see optimized_prompt.txt, 1150 lines / 34.3 KB for the one-case sample it was extracted against) is DSPy's ChatAdapter format:
- A system message with a mechanical field-contract preamble (input/output field names and types, the `[[ ## field ## ]]` delimiter convention) followed by the policy text as the stated "objective."
- Four full worked demos, each a complete user turn (the raw case JSON) and assistant turn (decision plus a paragraph of policy-quoting reasoning), inserted as prior conversation turns rather than as inline text examples.
- The live case as the final user turn.

The hand ladder's v3/v4c prompts (engine/prompts/v3.md, 5.0 KB; v4c.md, 7.1 KB) are structured the opposite way: one static system-style document with an explicit numbered decision procedure (Step 1: look for REJECT triggers, with a named list of qualifying patterns and a separate named list of look-alikes that do NOT qualify; Step 2: HOLD conditions; Step 3: default APPROVE), a "weighing principles" section, and, in v4b/v4c, one or two worked examples embedded as prose inside the instructions rather than as full conversational turns. The hand ladder teaches a procedure once and asks the model to apply it; the DSPy optimized prompt shows worked instances and leans on the model to induce the procedure from them. Given the size (34.3 KB rendered for a single case vs 5-7 KB), the DSPy prompt is far more expensive per call: it carries four full case JSONs (some of them long, like CASE-107's ~30 transactions) as fixed overhead on every request, where the hand ladder's marginal cost per case is just that one case's JSON.

## Honest caveats

1. n=12 total, n=4 held out. This is a machinery demonstration, not a statistically valid optimization result. A single flipped decision on the 4-case eval set is a 25 percentage point swing; nothing here should be read as "DSPy beats the ladder" at any confidence.
2. The optimizer sees constructed labels. Three of the 8 training cases (CASE-101-P1B, CASE-104-P2, CASE-113-P3) are labeled "construction" in labels.json, meaning the label was authored to fit a deliberately constructed perturbation, not drawn from an independent adjudication. Two of those three are minimally-perturbed twins of eval-set cases with inverted labels (CASE-101-P1B mirrors eval CASE-101 with the sanctions match flipped from a false positive to a genuine one; CASE-113-P3 mirrors eval-adjacent CASE-113 with tenure collapsed). CASE-104-P2 is a construction twin of train-set CASE-104, not of an eval case. This makes the 8-case trainset thinner evidence than "8 independent adjudications" would be, and means a demo drawn from the trainset could in principle leak surface features of an eval case's twin. On this run, none of the three perturbation twins was selected as one of the 4 demos, so this risk is named rather than realized, but it would not necessarily be visible in the accuracy number if it had materialized (a demo can bias toward the correct decision by lucky twin resemblance as easily as away from it).
3. Correlated-judge risk: the DSPy signature's policy text and the hand ladder's v2/v3 prompts both quote or closely paraphrase the same POLICY.md, and both are graded by the same 12-case, hand-labeled suite. A prompt that memorizes surface patterns in this specific label set (all 12 cases, all sourced from one case-study author) could score well here without being a better policy-following prompt in general. 12/12 on both DSPy phases and on hand-ladder v2 is also a ceiling effect: with only 12 cases and multiple approaches already at 100%, this suite cannot currently distinguish "good" from "very good" prompting on this model.
4. Contract strictness is excluded from the comparison, stated above and repeated here because it is the most likely thing a reader would assume was compared and was not: DSPy's field-adapter parsing has no equivalent to the hand ladder's strict-JSON contract_ok gate.
5. The hand ladder's top rung (v4c) has no complete gemini-flash run to compare against (1 stored row). The comparison in this file is DSPy vs v2 and v3 only, not DSPy vs the ladder's best hand-written prompt.
6. Single run, no repeats. Temperature was pinned to 0.2, not 0.0, so a second run could disagree on a case or two; this was not re-run to check, given the time box.

## API calls

Logical LM calls, counted via len(lm.history) deltas around each phase (DSPy's LiteLLM layer appends to history on cache hits too, so this counts logical calls attempted, not necessarily billed calls; a rerun of this script would show cache hits and cost less than the totals below imply):

| Phase | Logical LM calls |
|---|---|
| Baseline eval (expert-4 standalone + all-12, which re-includes the same 4 cases) | 16 |
| BootstrapFewShot compile (attempts against the 8-case trainset) | 4 |
| Optimized eval (expert-4 standalone + all-12) | 16 |
| Prompt extraction (one live call through the compiled program) | 1 |
| Total | 37 |

The baseline and optimized eval counts (16 each) are higher than the strict minimum (12 unique cases) because the expert-4 set was evaluated twice, once alone and once as part of all-12, per the task's own ask for both numbers reported separately; this was checked above to confirm the two readings agree rather than silently trusting determinism.

## Verification

- python3 -m py_compile arm.py run.py smoke_test.py: passed, no output, exit 0.
- run.py executed once end to end against the live Gemini API, exit code 0, wrote both scores.json and optimized_prompt.txt.
- state/verdict.sqlite3 was opened read-only (file:...?mode=ro) for the hand-ladder comparison; no write occurred.
- No file outside experiments/dspy_arm/ was created or modified by this arm.
