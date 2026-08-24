# verdict-bench architecture

PRD: docs/prd/SPEC.md. Status: active. Companion: PRODUCT.md, PLAN.md.

## System shape: one data plane, three consumers

```
                    +---------------------+
  engine/runner.py  |                     |   notebooks/analysis.ipynb
  (writes runs) --> |  state/verdict.     | <-- (reads, analyst surface)
                    |  sqlite3            |
  engine/graders/   |  single source of   | --> engine/export.py
  (writes judgments)|  truth              |     --> ui/public/benchmark.json
                    +---------------------+          --> React UI / Tauri
```

Every experiment is a row. Nothing is derived state except benchmark.json,
which is regenerated from SQLite on demand and never edited by hand. The UI
is read-only over the export; runs are launched from the CLI. This keeps
one write path (runner/graders), one audit trail, and no server process.

## Boundaries and their contracts

1. Provider boundary (engine/providers.py). Every model call returns a
typed DecisionResult (decision, reasoning, confidence, raw\_output,
contract\_ok, tokens, latency, error). Every parse or IO failure becomes
a recorded row, never a silent skip; upstream garbage is a
contract-violation row, not a crash. One retry on transient CLI flake,
the retry itself visible in latency.
2. Contract parser (parse\_contract). Strict first (whole output is one
JSON object), extraction fallback second, and the strict/fallback
distinction IS the contract\_ok metric. Grading and contract measurement
are deliberately separated: a fenced JSON is a wrong-format
right-answer, and both facts are recorded.
3. Case boundary (data/cases/\*.json + runner.EXPECTED). Labels carry their
source class (expert / adjudicated / construction), mirroring the
calibrated-claims rule: an expert label and my own adjudication are not
the same evidence class and the analysis can weight them differently.
4. Judge boundary (engine/graders/, S2). Judges are providers too: same
DecisionResult discipline, plus the cross-judging rule (a judge never
scores its own family) enforced in the assignment table, not by
convention.

## Decisions and their rejected alternatives

* SQLite over DuckDB/JSONL: transactional appends from concurrent runs,
one file, stdlib driver. DuckDB wins for OLAP scale we don't have; JSONL
loses the FK discipline that caught the silent-skip incident.
* Hand-rolled provider clients over LiteLLM/promptfoo: 3 providers with
2 API shapes (openai-compat, gemini) is under the abstraction threshold;
a dependency that owns the request path would also own the failure
modes, and the failure modes are part of what we measure. promptfoo is
named in SPEC.md prior art as the production CI alternative.
* Static JSON export to the UI over FastAPI: no live process to babysit in
a presentation; the one live feature (run-case demo button) gets a tiny
local endpoint in S4 only when it exists.
* Tauri over web-only: operator decision 2026-08-17 (presentation from
local machine, one binary). Web build remains the fallback; both consume
the same dist/.
* claude CLI over Anthropic SDK: subscription auth, no API key handling in
this repo. Cost: CLI startup latency (\~10-40s p95) pollutes the latency
metric for Claude columns; recorded as a known measurement caveat rather
than engineered away before the deadline.

## Failure modes designed against (premortem)

1. Silent data loss in batch runs: caught once already (wrapper dropped a
case while reporting success). Defense: per-case rows + count checks
against the case table; report prints per-case lines, not a summary.
2. Judge self-preference: cross-family judging matrix (S2), literature
cited in SPEC.md.
3. Perturbation leakage: perturbed/synthetic cases carry kind + label
source construction; they never mix into golden accuracy.
4. Metric saturation misread as quality: the labeled suite saturates
(v1 naive scores 11/12); the analysis notebook must always show n and
separate the suites, and flip-rate/contract carry the discrimination
the accuracy metric lost.
5. Stale UI data at demo time: export + rebuild is one make target
(make ui); the demo checklist in PLAN.md names it.

```


