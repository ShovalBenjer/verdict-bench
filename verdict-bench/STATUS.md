# Implementation status audit

Dated snapshot, 2026-08-19 morning. Verified against running code/tests/DB,
not against plan-doc claims. Rubric: FULL (built, tested, demoed) / PARTIAL
(built, gaps named) / STUB (exists but mock/thin) / PLANNED (doc only, no
code). Companion: docs/PLAN.md (the forward plan this audit feeds).

## The canonical 4-file set: verified adequate for this repo's shape

Per docs-control-plane.md's full taxonomy (docs/prd/, docs/specs/, docs/adr/,
TODO.md, INDEX.md), this repo has PRD (docs/prd/SPEC.md) and 3 top-level
docs (ARCHITECTURE/PRODUCT/PLAN) but no specs/, adr/, TODO.md, or INDEX.md.
Consulted claude-setup: pending reply at time of writing; the working
judgment call: docs-control-plane's full taxonomy is sized for a
multi-surface repo accumulating decisions over months. A single-purpose
2-week eval lab with 4 living docs and PLAN.md's own coverage-register
serving as the de facto TODO is a reasonable right-sized adaptation, AS
LONG AS no fifth planning doc gets created (already the standing rule).
One real gap: no ADR for the SQLite-vs-DuckDB / hand-rolled-vs-LiteLLM /
Tauri-vs-web calls, which currently live as prose in ARCHITECTURE.md's
"rejected alternatives" section. Given the deadline, that's an acceptable
substitute, not a defect to fix.

## FULL: built, tested, evidenced

- **SQLite schema + runner** (engine/schema.sql, runner.py, 136 lines).
  139 runs banked, sha-pinned (prompt_sha/case_sha/temperature/batch_id),
  9/9 planted-defect tests green.
- **Provider boundary** (providers.py, 182 lines): 3 of the ~8 planned
  providers actually implemented: claude CLI, Gemini, NVIDIA
  openai-compat. Every call returns typed DecisionResult; retry-once on
  CLI flake; contract parsing strict-then-fallback, both states recorded.
- **Report with Wilson CIs + flip rate** (runner.py report()): honest
  uncertainty at n=12, first-run/repeat separation (the bug the
  peer-reviewer's item 7 predicted and this session's own repeats then
  triggered, now fixed).
- **Ablation ladder, verified by diff**: v1 -> v2 -> v3 -> v3c -> v4 -> v4b,
  each rung one element, v4=v3c+one-bullet checked by machine diff (not
  just asserted). CHANGELOG.md documents the ladder AND its own
  correction history (v4 was originally 2 changes, caught and fixed).
- **UI matrix + power curve + case-compare** (App.jsx, verified in
  browser, screenshots sent 3x across the session): version-labeled rows,
  annotated curve with delta ticks and value labels, split-pane case view
  with all-models comparison, discrepancy banners, auto-expand on miss.
- **Tauri native shell**: built, launched under WSLg, verified running.
  `tauri dev` hot-reload fails under this harness's background-task model
  (documented, not a code defect); `make ui` + launch the debug binary is
  the reliable path.
- **Assignment core**: prompt v4/v4b, 9/9 golden+adjudicated, 3/3
  perturbations + 1 regression, TRANSCRIPT.md sections 1-17 (intake
  through operator corrections), all with dead ends kept (the 101-P1
  inconsistent perturbation, the --bare misdiagnosis, the wrapper
  silent-skip, the v3 stability-repeat pollution).
- **Dist/submission pipeline** (build_dist.py): manifest-based ship list,
  verbatim-operator-text session extraction, blocklist exclusion with a
  human-reviewed EXCLUDED.md gate, leak check. Ran once, 42/87 turns
  excluded on a keyword filter that over-caught (named as a known
  refinement need, not silently accepted).

## PARTIAL: built, real gaps named

- **Model roster**: 5 of ~8 planned columns have ANY data (sonnet, haiku,
  flash, pro, llama). Qwen and GLM: keys exist in .env, zero code written.
  Roster-honesty correction already logged (llama-3.3-70b framed as
  deliberate legacy baseline, not silently included).
- **Stability (flip rate)**: N=5 exists for exactly 3 (case, prompt)
  pairs (113-P3 on v3 and v4, 104 on v4). Not run across the matrix; the
  flip column is real where populated, blank everywhere else.
- **Packaging**: pyproject/requirements/Makefile/Dockerfile all written
  and internally consistent. `docker build` has NEVER been executed, and
  checked just now: `docker` is not installed in this WSL environment at
  all (`command not found`). This downgrades the item from "unverified"
  to "unverifiable from this machine"; the Dockerfile is a hypothesis
  until it's built on a host that has Docker (the operator's Windows
  Docker Desktop, if linked to WSL, or any CI runner). Flagging this as a
  needs-operator item: either install/link Docker here, or accept the
  Dockerfile as untested and cut it from the submission's verified claims.
- **Books/domain grounding**: 34 files copied into docs/research/books/
  (gitignored, local-only) after TWO passes: first pass filename-grepped
  and missed 22 relevant files (llm_*, context_eng_*, prob_product*, dq),
  caught only because the operator asked "why aren't the others
  relevant" and forced a content-read pass. Zero of these 34 files have
  actually been READ into the writeup or prompt design yet; they are
  copied, not yet used.
- **Hamel-alignment (error analysis / annotation)**: gap named 2026-08-18
  (annotate control in case-view UI, judge-vs-operator-agreement metric).
  Zero implementation. This is the single highest-value gap against the
  explicit "eval is a product job" framing a peer surfaced (hamel.dev), and it is
  still just a paragraph in this file's predecessor conversation, not
  code.

## STUB: exists in name/schema only, no working content

- **judgments table** (schema.sql): defined, zero rows. S2 rubric judge
  never called.
- **notebooks/** directory: EMPTY. This was flagged twice as an explicit,
  repeated operator ask (the .ipynb-on-local-Jupyter requirement from
  the "next-gen approach" prompt) and still does not exist. This is the
  most overdue item in the whole plan relative to how clearly it was
  asked for.
- **HF/embeddings/LR-baseline tools**: named in SPEC.md, zero code.
- **prompt-eval skill extraction**: named in PLAN.md item 6, zero files
  under ~/.claude/skills/.
- **Project memory beyond one file**: project_verdict-bench.md exists;
  no per-decision memory entries (e.g. the --bare misdiagnosis, the
  ablation-discipline correction) that would help a cold session avoid
  repeating the same mistakes.

## PLANNED: doc only, zero code, zero data

- Injection case set (0 of >=4 planned).
- Metamorphic case set (0 of >=4 planned).
- Synthetic factory (factory.py does not exist; no seeded generator).
- v5 / autoresearch-style gated loop.
- DSPy comparison arm (a peer's pointer, cited not built).
- Data-source fetch scripts (IEEE-CIS/PaySim distributions).
- Calibration analysis, expected-loss sensitivity.
- Writeup.md, deck.
- ADR file(s) for the 3 named architecture decisions.

## The honest one-paragraph summary

The engine core (schema, providers, runner, tests, ablation ladder) and
the UI are genuinely FULL and demo-ready today. Everything downstream of
"run more cells" (more models, more repeats, docker proof) is PARTIAL,
correctly designed, partially executed. Everything requiring NEW
mechanisms not yet touched (rubric judge, annotation UI, synthetic
factory, notebook) is STUB or PLANNED. The two most consequential gaps
relative to explicit operator asks are the missing notebook (asked twice,
still absent) and the never-run `docker build` (a packaging claim nobody
has verified). Both are cheap, both should be first on Tuesday.

## Books, second pass (2026-08-19, operator-directed)
37 files now under docs/research/books/ (gitignored). New this pass, read
by content/abstract before copying, not by filename:
- "Foundations of Large Language Models" (Xiao & Zhu, arXiv:2501.09223):
  full chapter coverage of prompting/alignment/inference; feeds the
  writeup's grounding section.
- "CTRL-ALT-DECEIT: Sabotage Evaluations for Automated AI R&D"
  (arXiv:2511.09904): adjacent eval methodology (adversarial-pressure
  testing), useful for the injection-set design even though its target
  domain (autonomous AI R&D agents) differs from ours.
- Docker Deep Dive (Poulton, 2025): directly load-bearing, since docker
  is confirmed NOT INSTALLED on this machine (see packaging section
  above). This is the fix-path reading for the single largest unverified
  claim in the repo, not background material.
Left out on content grounds (math/physics theory, no connection to fraud
decisioning, prompt evals, or product LLM work): tensor networks,
polynomial functors, categorical deep learning, interpretability-in-
scientific-ML, topos theory, geometric deep learning, TDA, deep learning
theory, MARL. Correction on method: first Downloads pass (2026-08-18)
filename-grepped and missed 22 relevant harness-corpus files; this pass
used arXiv-ID lookups and abstracts before deciding, per the
search-query-discipline standing correction.

## Grill-me stress test (2026-08-19): fabricated answer caught, real audit run

The operator forwarded a fluent, fully-fabricated response to the grill
questions (invented CASE-104 content, invented prompt files
`prompts/v3.txt`, invented `run_batch()` function, invented matrix
numbers). Flagged and rejected wholesale rather than partially credited.
Re-ran all 8 questions against the real repo. Findings from that pass:

1. Real CASE-104 (KYB ownership change, not the fabricated ATO/Tor
   scenario) run_id=6, v4/gemini-flash: model said REJECT, expert label
   is HOLD. Reproducible model miss, not a data artifact.
2. Real v3->v3c diff has TWO changes (stricter contract block AND a
   trailing "final reminder"), not one atomically isolated line as
   CHANGELOG.md's ladder claims. Ablation-purity gap, logged as a defect
   in the ladder documentation, not fixed retroactively (would need a
   v3c-2 rung to actually isolate).
3. **New bug found while verifying claim 4**: CASE-101 and CASE-104 each
   have a DUPLICATE repeat_idx=0 row for v4/gemini-flash (two separate
   run_id's both tagged repeat_idx=0). This is exactly peer-review item 7
   (no dupe guard) manifesting for real. runner.py report()'s dict-based
   first-run dedup happens to mask it (correct n=13); a naive
   repeat_idx=0 filter does not (wrong n=15). Root cause: re-running
   `--case CASE-101` and `--case CASE-104` singly (done during earlier
   debugging) always writes repeat_idx=0, colliding with the case's
   existing row. FIX NEEDED: schema UNIQUE(case_id, prompt_version,
   model_id, repeat_idx, prompt_sha) or repeat_idx computed as
   MAX(existing)+1 at insert time.
4. Real worst cell (report()'s correct dedup logic): v3c/gemini-flash,
   10/12 (83.3%), driven by the same CASE-104 miss.

## Dupe-guard fix applied (2026-08-19, same session as the fabrication catch)

Root cause confirmed: `runner.py run()` always started `repeat_idx` at 0
per invocation instead of offsetting from what already existed for that
(case, prompt, model). Fixed: `repeat_idx` now starts at
`MAX(existing)+1`. Schema gained `UNIQUE(case_id, prompt_version,
model_id, repeat_idx, prompt_sha)` (SQLite table rebuilt in place, all
139 rows preserved and verified by count before/after).

Data repair: found 7 dupe groups (not 2), across CASE-101/104/106/113-P3
on v3 and v4, multiple models. These were genuine independent API calls
that had collided on repeat_idx=0, not literal duplicate inserts (each
pair has a different run_id, timestamp, and raw_output). Repaired by
RENUMBERING the later row to the next free repeat_idx, never by deleting
data. Verified: 0 remaining dupe groups, 139/139 rows still present.

**Known limitation, disclosed not hidden**: 115 of 139 rows predate the
prompt_sha column and carry `prompt_sha=NULL`. SQLite's UNIQUE treats
NULL as distinct from every other value, so the new constraint protects
only rows written after this fix; it cannot retroactively guard the
legacy 115. This was caught by checking the constraint's actual behavior
against a real rerun (CASE-101, run_id=145) rather than assumed to work
after writing it.

Corrected report after the fix: v4/gemini-flash n=24 (was ambiguous
between 23/24/15 across three different measurement attempts this
session, the exact "trust the command, not the memory" lesson this
whole incident teaches). Numbers below are the current authoritative
state, all commands re-run:
```
prompt model              n    acc         ci95  flip contract   p50ms
v1     gemini-flash      12  11/12  [0.65,0.99]     -     0.08    7650
v2     gemini-flash      12  12/12  [0.76,1.00]     -     0.00    8771
v3     gemini-flash      17  11/12  [0.65,0.99]  0.17     0.00   10696
v3c    gemini-flash      12  10/12  [0.55,0.95]     -     1.00    9704
v4     claude-haiku      13  11/12  [0.65,0.99]  0.00     0.00   18063
v4     claude-sonnet     12  12/12  [0.76,1.00]     -      n/a   17742
v4     gemini-flash      24  11/12  [0.65,0.99]  0.06     1.00    8397
v4     gemini-pro        12  11/12  [0.65,0.99]     -     0.00   18372
v4     llama-3.3-70b     14   9/10  [0.60,0.98]     -     0.83   72453
v4b    gemini-flash      12  11/12  [0.65,0.99]     -     1.00    8121
```

## v4c ablation: card-testing counting scaffold, tested not just diagnosed

Grill-me item 6 asked whether the llama/haiku CASE-102 miss was a
capability boundary or a prompt artifact. Built v4c = v4b + ONE explicit
"count distinct instruments before deciding" scaffold, tested on the two
models that missed it plus gemini-flash as a control.

Result: MIXED, and the honest mixed result is the finding.
- llama-3.3-70b: still HOLD (still wrong, expected REJECT). The scaffold
  did NOT fix it. This model's miss on CASE-102 is not a "didn't count"
  problem; something else in its policy application is off. Open
  question, not closed by this test.
- claude-haiku: first attempt threw a JSON parse error (a NEW contract
  failure mode, not seen before on this case); retry produced REJECT
  (correct). So haiku DOES benefit from explicit counting, but its
  contract adherence on this case is unstable (0/1 then correct decision
  on retry), consistent with its 0% contract rate across the whole
  matrix, not a new problem.
- gemini-flash: REJECT, correct, no regression (control held).
Conclusion: the capability-boundary question from item 6 does not have
one answer across models. llama's miss looks like a genuine policy-
application gap the scaffold didn't touch; haiku's miss looks like it
WAS partly a compute/scaffold gap. This nuance would have been lost if
the fabricated response's confident single-cause diagnosis had been
accepted instead of tested.

## Status delta, 2026-08-23 night (append-only; the 08-19 audit above stands as written)

Rows above that are no longer current, each with tonight's artifact:
- "no adr/": docs/adr/0001-0004 exist, one per named architecture call,
  each with the rejected alternative.
- "Writeup.md, deck" under PLANNED: docs/WRITEUP.md written and shipped;
  the deck's spine is PRODUCT.md's beat sheet (2026-08-23) including the
  one-page workflow slide.
- notebooks/ EMPTY: notebooks/analysis.ipynb exists.
- Packaging / "docker is not installed at all": docker IS installed now
  (/usr/bin/docker); the build is blocked on docker-group membership
  (/var/run/docker.sock is root:docker), a one-command operator action.
  The Dockerfile remains an untested hypothesis; the cause is narrowed.
- Dist pipeline row ("ran once, 42/87 turns, over-catching blocklist"):
  superseded by turn-level curation (assignment/curation.json, content-
  hash keys, DROP/TRIM with markers, per-session cutoff), two agent
  review rounds (leak, orphan, readability), and fail-closed bundle
  checks (machine paths, dashes outside frozen/verbatim files, citation
  resolution, secrets). 511 blocklist-kept turns ship as 93 after two
  curation rounds and the final review (the machine-path check was
  extended to the verbatim extract after that review found three
  path-carrying turns; each was dropped or paragraph-trimmed);
  EXCLUDED.md moved outside the bundle.
- "Stability (flip rate): N=5" row: the CASE-113-P3 pairs are N=6 in the
  ledger as of 2026-08-23 (v3 is 5/6 wrong, v4 is 5/6 right).
- New since 08-19, not audited above: LICENSE, AGENTS.md + CLAUDE.md
  pointer, .claude/rules/ inherited from claude-setup (six rules,
  provenance README), mypy+ruff wired into make check (were declared but
  never run), benchmark.json shipped in the bundle as the readable form
  of the ledger.

## Status delta, 2026-08-24 (submission day; append-only, prior sections stand)

The operator un-cut the whole open register at 00:15; this delta records
what changed on disk by ~03:00. PLAN.md's "Register re-opened and RUN"
section is the item-by-item account; this is the audit-shaped summary.

Rows above that are no longer current:
- "judgments table: defined, zero rows": engine/judge.py exists and the
  table is filling (cross-family, label-blind, r1 rubric, dual-judge
  overlap on v4/flash). Finding already stable in aggregate: flash as
  judge saturates near 5.0 on every axis, haiku as judge spreads
  (3.1-3.95); the harsher judge carries the signal.
- "Injection case set (0 of >=4)" and "Metamorphic case set (0 of >=4)"
  under PLANNED: 4+4 authored and run on flash (v1 and v4b), nemotron,
  qwen; plus CASE-115 (kind=coverage, data_quality_flag). Coverage 8/8.
- "HF/embeddings/LR-baseline tools: zero code": experiments/lr_baseline
  exists and ran (LOO 8/12; misses concentrate on policy-reasoning
  cases). Embeddings arm still zero code, unchanged.
- "DSPy comparison arm: cited not built": experiments/dspy_arm built and
  run (ceiling effect at 12/12; 34KB rendered prompt vs 7KB procedure).
- "v5 / autoresearch-style gated loop" under PLANNED: run in full,
  ACCEPTED; engine/prompts/CHANGELOG.md carries the pre-registered gate,
  the false single-run regression, and the N=5 refutation. v5 is the
  submitted prompt (WRITEUP updated).
- "prompt-eval skill extraction: zero files": ~/.claude/skills/prompt-eval
  written, plus the single-run-claims-dissolve memory row.
- Model roster PARTIAL row: qwen3.8-max and nemotron-super-49b columns
  live; GLM wired and money-blocked on both routes (error rows banked).

New defects found and fixed this delta, each with its oracle:
- schema CHECK lacked the 'coverage' kind: live-DB table rebuild in
  runner.migrate(), row-count asserted before/after.
- claude CLI calls all dying prompt_too_long (~450k tokens of MCP
  connector tool definitions): --strict-mcp-config added to
  call_claude_cli; caught by the judge smoke reading the recorded error
  envelope.
- 429s on openai-compat providers were terminal: bounded Retry-After
  backoff added, mirroring the CLI retry discipline.
- First-run accuracy could sit on a coin-flip case (v4b/qwen 12/12 over
  an unstable CASE-108): flip guardrail (>0.25) added to report trust.
- Suite blending: oec/report/export/notebook all filtered to
  DECISION_SUITE_KINDS; new test
  test_injection_and_metamorphic_never_blend_into_el_or_guardrails.
`make check` green after all of it: ruff, mypy, a test suite counted live by `python3 -m pytest -q tests/` (59 at last gate), report smoke.
