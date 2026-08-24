# verdict-bench

Eval-driven prompt improvement lab for an account-review decisioning agent.
Prompt versions are treated as model releases: each runs against every
available model on a frozen case suite, graded by deterministic tests plus
a dollar-denominated expected-loss composite, history in SQLite, native UI
for the benchmark matrix.

Built as supporting evidence for an Intuit take-home assignment (the
required deliverables (prompt, writeup, transcript) are the actual ask;
this repo is the process behind them, not a substitute for them).

## Quickstart

```bash
git clone <this-repo> && cd verdict-bench
pip install -r requirements.txt        # analysis extras (polars, jupyter); engine core is stdlib-only
pip install -e '.[dev]'                # ruff + mypy + pytest, needed by `make check` below
python3 engine/runner.py --report      # print the benchmark table from the checked-in DB
python3 engine/runner.py --coverage    # policy-clause coverage: which POLICY.md sections have zero test cases
python3 engine/runner.py --sweep --models gemini-flash   # sensitivity sweep on the FA cost assumption
make check                             # compile + ruff + mypy + full test suite + report smoke test
```

No API keys needed to read the existing ledger (`state/verdict.sqlite3`
is checked in). Running new cases against live providers needs
`~/.env` credentials per `engine/providers.py`.

Zero-install reproduction: `make docker && make docker-run` builds the
two-stage image (node builds the UI from the lockfile, python:3.12-slim
serves it; the engine is stdlib-only so the container needs no pip
installs) and serves the full benchmark UI on :8080 with the ledger
mounted.

## Structure

The tree below describes this WORKING repo. In the submission bundle,
`docs/` flattens to the repo root (`SPEC.md`, `STATUS.md`, `adr/`), the
writeup moves to the bundle root, and `PRODUCT.md`, `PLAN.md`, and
`notebooks/` stay local by design (the bundle README's path note says so
explicitly).

```
engine/         runner, provider clients, cost model (oec.py), export
  prompts/      the ablation ladder (v1..v4c) + CHANGELOG.md
data/           case JSON (synthetic, no real PII) + labels.json
state/          verdict.sqlite3, the run ledger (checked in)
tests/          pytest suite, boundary tests over real sqlite fixtures
notebooks/      analysis.ipynb, analyst surface over the ledger
ui/             Tauri + web UI (matrix / power curve / case compare)
docs/
  prd/SPEC.md         the spec this repo implements
  ARCHITECTURE.md     system design + decision summary
  PRODUCT.md          UI/demo design, beat sheet
  PLAN.md             calendar-scoped work plan, coverage register
  STATUS.md           dated implementation-status audit (FULL/PARTIAL/STUB/PLANNED)
  WRITEUP.md          the assignment's required short writeup
  adr/                architecture decision records (Nygard shape)
```

Docs taxonomy is a deliberate, reasoned deviation from this estate's
default `docs/prd + specs + adr + TODO.md + INDEX.md` taxonomy: STATUS.md
(2026-08-19) reasoned that taxonomy is sized for a multi-surface repo
accumulating decisions over months, and a single-purpose 2-week eval lab
with 4 living docs plus `PLAN.md`'s own coverage register as the de facto
TODO is a right-sized adaptation, on the condition that no fifth planning
doc gets created. `docs/specs/` and `TODO.md`/`INDEX.md` are intentionally
absent; `docs/adr/` was the one named gap in that call and is now filled.

## Tech stack, reasoned (not defaulted)

Every non-obvious choice below is written up as an ADR with the
alternative actually compared, not asserted: `docs/adr/0001` through
`0004`.

- **SQLite** for the run ledger, over DuckDB (OLAP scale not reached) or
  JSONL (no FK/uniqueness discipline; would have missed 2 real bugs this
  repo actually hit).
- **Hand-rolled provider clients**, over LiteLLM/promptfoo, because the
  request-path failure modes (retry, contract parsing, latency) are
  themselves the thing being measured, not incidental plumbing to hide
  behind a dependency.
- **Tauri** desktop shell for the live demo, over web-only, with the web
  build kept as a same-`dist/` fallback, not abandoned.
- **stdlib-only engine core** (`urllib`, `sqlite3`, `json`), analysis
  extras (`polars`, `matplotlib`, `jupyter`) kept separate, chosen for a
  clone-once-read-once submission's install friction, not as a default.

## Docker

`Dockerfile` builds the UI (Node stage) and serves it from a Python
stdlib HTTP server. **Build status: VERIFIED 2026-08-24** after the
one-time group fix below: image built clean (15/15 steps, tagged
`verdict-bench:latest`), and a live smoke served the UI from the
container (HTTP 200 on :8080, `benchmark.json` served with every cell
including v5). The 2026-08-23 blocker was the group membership, not the
code. To build:

```bash
sudo usermod -aG docker $USER && newgrp docker   # one-time, this machine
make docker        # docker build -t verdict-bench .
make docker-run     # serves the UI on :8080, mounts ./state read-write
```

## Code style

A standing personal engineering rule: "prefer strict type checking
where the language supports it... Python type hints checked by
mypy/pyright." `pyproject.toml` had `mypy` and `ruff` declared as dev
deps but neither was ever actually run (checked 2026-08-23; mypy found 3
untyped-dict findings, ruff found 4, all fixed). Both now run in
`make check`, so "declared but unused" can't recur silently.

## Tests

`make check` runs `py_compile` + `ruff check` + `mypy` + the full pytest
suite (count it live: `python3 -m pytest -q tests/`; real-sqlite boundary
tests, no mocks) + a live report
smoke test against the checked-in ledger. All steps fail the target on a
real failure
(no swallowed errors; a prior version of this Makefile silently ignored
test failures with `2>/dev/null || true`; fixed 2026-08-23).

## Ground truth vs. constructed labels

Only 4 cases (CASE-101, 102, 106, 108) have real expert labels from the
assignment's `labeled-answers.md`. Every other label in `data/labels.json`
was constructed by this project, reasoning from `POLICY.md`'s text, and
is documented as such, never presented as expert ground truth. See
`docs/WRITEUP.md` for what each evidence tier actually supports.
