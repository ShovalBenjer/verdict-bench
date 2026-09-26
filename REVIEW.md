# REVIEW.md — judging policy for verdict-bench

Kilo Code reads this file when reviewing pull requests. Base branch: `main`.
A branch must not alter the criteria by which it is judged.

## What this repo is

An LLM-decision benchmark. `engine/` (stdlib-only per ADR-0004) runs cases
through models, grades reasoning quality with a rubric judge
(`engine/judge.py`), and stores everything in `state/verdict.sqlite3` — the
committed run ledger, which is the product's data plane. `tools/` and
`ui/` present the numbers. Review the instruments, not their output.

## Severity calibration

- **Blocking.** A weakened oracle: a test that passes whatever the code does
  (the antipattern retired in `tests/test_graders.py`, 2026-08-24). A judge
  assignment that lets a model judge its own family — the cross-family
  invariant in `engine/judge.py::judge_for` is load-bearing, not style. A
  `RUBRIC_VERSION` bump with no migration of the `judgments` table. The runner
  accepting contract-violating model output silently. A test that mutates the
  tracked ledger instead of a snapshot (the shared-SUT antipattern). Secrets or
  `.env` committed. A new non-stdlib engine dependency (violates ADR-0004).
- **Major.** New provider call paths that bypass `engine/providers.py`. Prompt
  changes to `JUDGE_SYSTEM` without a rubric-version bump. Report numbers that
  cannot be reproduced from the DB the PR ships.
- **Minor.** Formatting, naming, comment drift, doc typos. Say it once.

## Paths to skip — never style-comment these

- `state/verdict.sqlite3` — binary ledger; comment on `engine/schema.sql` or
  the code that writes it, never on the file.
- `ui/dist/`, `engine/__pycache__/`, `data/raw/` — build output / ignored.
- `notebooks/analysis.ipynb` cell outputs, `docs/assets/`, `TRANSCRIPT.md`
  (a verbatim record), `ui/public/benchmark.json` — generated exports;
  review the exporter.

## Verification expected

- `make check` (py_compile, ruff, mypy, pytest, report smoke). CI green is the
  floor; quote the log, not a claim of green.
- Oracle or judge changes: a planted-defect demonstration, per the convention
  in `tests/test_graders.py` — show the new check failing before, passing
  after.
- Prompt changes: a `--limit` smoke run before/after, with the numbers in the
  PR. Not vibes.
- Never trust a benchmark number quoted in a PR description; it must reproduce
  from the committed DB.

## Summary style

Terse, defect-first. `path:line` references. No praise paragraphs. One line per
finding: severity, what's wrong, what's expected. Close with mergeable /
not mergeable and the single blocking item, if any.

## Sub-agent budget

Diffs under ~300 lines: review inline, no sub-agents. Larger diffs: one
sub-agent per top-level directory touched, each reporting findings against
this file. No sub-agent approves; they report, a human merges.

## Relationship to AGENTS.md

AGENTS.md is how to build here; this file is how to judge a change. Where they
overlap, AGENTS.md wins on build facts, this file wins on the bar.
