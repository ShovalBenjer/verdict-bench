<div align="center">

<img src="docs/assets/logo.jpg" alt="verdict-bench" width="520" />

**Every prompt version ran against every model, and no claim ships without the runs behind it.**

![runs](https://img.shields.io/badge/runs_banked-1215_protocol_of_1275_banked-333?style=flat-square&labelColor=1a1d24)
![models](https://img.shields.io/badge/models-8_wired_7_decided-333?style=flat-square&labelColor=1a1d24)
![cases](https://img.shields.io/badge/cases-88_active_of_89-333?style=flat-square&labelColor=1a1d24)
![coverage](https://img.shields.io/badge/policy_coverage-8_of_8_clauses-333?style=flat-square&labelColor=1a1d24)

**[Live benchmark UI](https://verdict-bench.pages.dev)** &nbsp;&middot;&nbsp; **[Analysis notebook](https://verdict-bench.pages.dev/notebook)** &nbsp;&middot;&nbsp; reachable by link, deliberately unindexed

</div>

An account-review agent decides flagged merchant accounts: APPROVE, HOLD,
or REJECT, driven by a plain-text prompt. This repository treats that
prompt the way a risk team should: versioned one change at a time,
benchmarked across 8 wired (7 decided) models on a frozen case suite,
attacked with planted instructions, repeated until stability is a number,
and gated so an untrustworthy cell cannot show a headline figure.

It is not a general eval platform (promptfoo is the production-grade
alternative and is named as prior art), not a fraud model, and not a
prediction of money: the dollar figures are stated exchange rates between
error types, sensitivity-swept, with the one partially-grounded figure
marked as such.

## The three deliverables

1. **The prompt**: `engine/prompts/v5.md`, the shipped rung of an
   ablation ladder (`engine/prompts/v1..v6b`, one change per rung, each
   with its hypothesis); `engine/prompts/CHANGELOG.md` carries the gate
   record of the one edit a loop proposed and a pre-registered gate
   accepted after N=5 repeats refuted a false regression.
2. **The writeup**: `docs/WRITEUP.md`, what was chosen, why, and what
   would convince a reviewer the prompt is ready or not.
3. **The transcript**: three depths of the same record. `TRANSCRIPT.md`
   (the curated narrative, dead ends kept);
   `submission/sessions/*-full.md`, the COMPLETE build session, all 445
   turns verbatim (only a logged personal-content screen removed 73
   off-scope segments); and the sibling 93-turn readability cut with
   every drop marked.

## Sixty seconds

```bash
git clone https://github.com/ShovalBenjer/verdict-bench && cd verdict-bench
python3 engine/runner.py --report      # the gated benchmark matrix, no keys needed
python3 engine/runner.py --coverage    # does every policy clause have a test
pip install -e '.[dev]'                # ruff + mypy + pytest for the line below
make check                             # compile, lint, types, full test suite, report smoke
```

No API keys needed to read the checked-in ledger
(`state/verdict.sqlite3`); running new cases against live providers
needs credentials per `engine/providers.py`. Zero-install reproduction:
`make docker && make docker-run` builds the two-stage image (build
VERIFIED 2026-08-24: 15/15 steps, live smoke on :8080) and serves the
full benchmark UI with the ledger mounted.

## Where it landed

**v5 on gemini-flash**: 100% decision accuracy, 100% contract adherence, $0 weighted loss per 1,000 cases

| rung | model | accuracy | contract | weighted loss /1k [95% CI] |
|---|---|---|---|---|
| v5 | gemini-flash | 100% | 100% | $0 [0 to 0] |
| v6b | gemini-flash | 100% | 100% | $0 [0 to 0] |
| v1 | qwen3.8-max | 92% | 100% | $41,667 [0 to 125,000] |
| v4 | gemini-flash | 92% | 100% | $50,000 [0 to 150,000] |
| v4b | gemini-flash | 92% | 100% | $50,000 [0 to 150,000] |

Rankable cells only; a cell that fails the trust gate (n, contract rate,
CI width, repeat-run flip, or a zero-tolerance miss) hides its own number.
Loss prices are assumptions: three stated (missed fraud $2,000, needless
hold $45, lost customer $600) plus one derived cell, a fraudster merely
held instead of rejected at $2,000/4 = $500 (partial containment). The
interval is case-resampling variability only. For scale, deciding every
case the same way costs $189k (always HOLD) to $674k (always APPROVE)
per 1,000 cases.

## Structure

```
engine/           runner, provider clients, cost model (oec.py), export
  prompts/        the ablation ladder v1..v6b + CHANGELOG.md (deliverable 1)
data/             case JSON (synthetic, no real PII) + labels.json
state/            verdict.sqlite3, the run ledger (checked in; every number regenerates from it)
tests/            pytest suite, boundary tests over real sqlite fixtures, no mocks
notebooks/        analysis.ipynb, the analyst surface over the ledger
ui/               web + Tauri UI behind verdict-bench.pages.dev
tools/            deck builders, synthetic-case factory, plots, annotation ingest
docs/
  WRITEUP.md      deliverable 2
  prd/SPEC.md     the spec this lab implements
  ARCHITECTURE.md, PRODUCT.md, PLAN.md, STATUS.md, adr/
  PROCESS-LOG.txt all 107 lab commit subjects with timestamps, the week's arc
TRANSCRIPT.md     deliverable 3, curated, dead ends kept
submission/       the assignment's own material and the raw work evidence:
  case-study/     the assignment input as received (the company's material,
                  reproduced for reference; not covered by this repo's MIT license)
  sessions/       verbatim session extract behind TRANSCRIPT.md
  early-prompts/  the pre-repo drafts (prompt_v1..v11) the first sessions iterate
  verification/   perturbed cases built to break the early prompts
```

Version-name map, because two numbering schemes coexist:
`submission/early-prompts/prompt_v1..v11` are the PRE-REPO drafts the
transcript's first sessions iterate (rich procedure from day one), while
the ladder's `v1` in `engine/prompts/` is the deliberately minimal
no-policy BASELINE built later so ablations had a floor. Transcript
sections about "prompt_v1" refer to the former; every benchmark number
refers to the latter.

## Tech stack, reasoned (not defaulted)

Every non-obvious choice is an ADR with the alternative actually
compared: `docs/adr/0001..0004`. SQLite over DuckDB/JSONL for the run
ledger; hand-rolled provider clients over LiteLLM/promptfoo because the
request-path failure modes (retry, contract parsing, latency) are the
thing being measured; Tauri shell with the web build as a same-`dist/`
fallback; stdlib-only engine core (`urllib`, `sqlite3`, `json`) with
analysis extras kept separate for clone-once install friction.

## How it stays honest

Every run is pinned to its prompt by content hash. Accuracy never blends
label tiers (4 expert labels, 5 adjudicated, the rest constructed and
saying so; see `docs/WRITEUP.md` for what each tier supports) or suites
(robustness cases score in their own columns). 511 blocklist-kept
conversation turns ship as 93, every drop marked. A verdict that depends
on one temperature-0.2 sample is repeated to N=5 before it is believed;
that protocol reversed one gate decision and revoked one perfect score.
`make check` fails on any real failure (a prior Makefile swallowed test
failures with `2>/dev/null || true`; found and fixed 2026-08-23, and the
fix is in the transcript).

## Fits and does not fit

| question | answer |
|---|---|
| Rank prompts for this decisioning task | yes, gated matrix |
| Certify production readiness | no: 4 expert labels bound everything at Wilson [0.51, 1.00] |
| Predict fraud losses in dollars | no: prices are stated assumptions |
| Resist adversarial notes | measured, not achieved: resistance is a coin flip at every rung, named |
| Replace promptfoo in CI | no, and the writeup says why |
