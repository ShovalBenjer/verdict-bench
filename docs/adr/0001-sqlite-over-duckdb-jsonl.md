# ADR-0001: SQLite as the run ledger, over DuckDB or JSONL

Status: accepted, 2026-08-17.

## Context

Every (prompt version, model, case, repeat) run needs to be recorded and
later queried: for a report table, for flip-rate over repeats, for the UI
export, and for the expected-loss composite. Options considered: a JSONL
append log, DuckDB, or SQLite.

## Decision

SQLite. `engine/schema.sql` defines the `cases`, `prompts`, `models`,
`runs`, and `judgments` tables with foreign keys and a UNIQUE constraint
on `(case_id, prompt_version, model_id, repeat_idx, prompt_sha)`.

## Consequences

Won on:
- Transactional appends from what can be concurrent run invocations
  (`--case X` reruns, batch runs), where a JSONL append log has no
  built-in guard against a torn write or a silent duplicate row. The
  actual dupe-guard bug found 2026-08-19 (two independent API calls
  colliding on `repeat_idx=0`) was caught BECAUSE the UNIQUE constraint
  turned a silent double-row into a hard integrity error; a JSONL log
  would have let it pass silently.
- One file, stdlib driver (`sqlite3`), zero install friction for a
  reviewer cloning the repo to inspect it.
- Foreign keys catch a referential mistake (a run against a case that
  was never seeded) at write time, not at report time.

Lost to the alternatives, accepted as a real cost:
- DuckDB wins for OLAP-scale analytical queries (window functions,
  larger-than-memory joins). This repo's actual scale (139-150 rows
  across the whole run) never approaches that threshold; DuckDB's
  columnar engine would be unused capability, not a benefit.
- JSONL is simpler to `tail -f` and diff in git, and needs no schema
  migration discipline. Rejected because the FK discipline and the
  UNIQUE constraint are load-bearing: they are what caught two real
  bugs (the dupe-guard collision, and an earlier silent-skip in a batch
  wrapper), not defensive boilerplate.

Known cost paid: `engine/schema.sql` uses `CREATE TABLE IF NOT EXISTS`,
which never re-applies a column change to an existing table. This
silently let the live DB and the schema file drift (the `retired`
column existed live via an untracked `ALTER TABLE` with no migration on
record, found 2026-08-19). Fixed with an explicit `migrate()` step in
`runner.py`'s `db()`, not by switching engines.
