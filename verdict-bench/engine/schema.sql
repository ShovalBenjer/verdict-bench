CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY,
  -- 'coverage' added 2026-08-24: a hand-authored case whose job is closing a
  -- policy-clause coverage gap (CASE-115 / data_quality_flag). It is excluded
  -- from the decision suite (oec.DECISION_SUITE_KINDS) so old and new cells
  -- never compare different denominators; live DBs get the widened CHECK via
  -- runner.migrate()'s table rebuild.
  kind TEXT NOT NULL CHECK (kind IN ('golden','perturbation','metamorphic','injection','synthetic','coverage')),
  expected TEXT CHECK (expected IN ('APPROVE','HOLD','REJECT') OR expected IS NULL),
  label_source TEXT NOT NULL,          -- 'expert' | 'adjudicated' | 'construction'
  path TEXT NOT NULL,
  -- which POLICY.md section this case's decision turns on (added 2026-08-19,
  -- operator ask: metrics must trace to the policy, not an invented weight).
  -- One of: sanctions_watchlist | account_linkage | transaction_activity |
  -- identity_ownership | confirmed_history | weighing_proportionality |
  -- evidence_discipline | data_quality_flag. NULL for untagged legacy rows.
  policy_clause TEXT,
  -- kept out of state until 2026-08-19 (added live via ALTER TABLE, schema.sql
  -- had drifted from the real DB; CREATE TABLE IF NOT EXISTS never re-applies
  -- to an existing table, so this file alone cannot add a column to a DB that
  -- already exists — see runner.py's migrate() for the actual add-path).
  retired INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prompts (
  version TEXT PRIMARY KEY,            -- 'v1'..'v5'
  path TEXT NOT NULL,
  hypothesis TEXT NOT NULL             -- the change this version encodes
);

CREATE TABLE IF NOT EXISTS models (
  model_id TEXT PRIMARY KEY,           -- 'claude-sonnet', 'gemini-flash', ...
  provider TEXT NOT NULL,
  price_in_per_mtok REAL,
  price_out_per_mtok REAL
);

CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  case_id TEXT NOT NULL REFERENCES cases(case_id),
  prompt_version TEXT NOT NULL REFERENCES prompts(version),
  model_id TEXT NOT NULL REFERENCES models(model_id),
  repeat_idx INTEGER NOT NULL DEFAULT 0,
  decision TEXT,                       -- NULL when contract violated beyond repair
  reasoning TEXT,
  confidence REAL,
  raw_output TEXT NOT NULL,
  contract_ok INTEGER NOT NULL,        -- strict: raw starts with { and parses
  correct INTEGER,                     -- NULL when no expected label
  tokens_in INTEGER,
  tokens_out INTEGER,
  latency_ms INTEGER,
  error TEXT,
  prompt_sha TEXT,                     -- sha256[:12] of the prompt text that ran
  case_sha TEXT,                       -- sha256[:12] of the case JSON that ran
  temperature REAL,
  batch_id TEXT,                       -- groups rows from one `runner.py run()` call
  -- dupe guard: found 2026-08-19 via grill-me stress test (STATUS.md).
  -- Single-case reruns (--case X) always wrote repeat_idx=0, colliding
  -- with that case's existing row and silently corrupting n. This makes
  -- a genuine collision an integrity error instead of a silent double-row.
  UNIQUE (case_id, prompt_version, model_id, repeat_idx, prompt_sha)
);

CREATE TABLE IF NOT EXISTS judgments (
  judgment_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES runs(run_id),
  judge_model TEXT NOT NULL,
  rubric_version TEXT NOT NULL,
  fidelity REAL, evidence REAL, proportionality REAL,
  raw TEXT NOT NULL
);
