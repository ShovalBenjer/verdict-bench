<div align="center">

<img src="assets/logo.jpg" alt="verdict-bench" width="520" />

**Single runs lie. A prompt, treated as a model release.**

![runs](https://img.shields.io/badge/runs_banked-835-333?style=flat-square&labelColor=1a1d24)
![models](https://img.shields.io/badge/models-8-333?style=flat-square&labelColor=1a1d24)
![cases](https://img.shields.io/badge/cases-76-333?style=flat-square&labelColor=1a1d24)
![coverage](https://img.shields.io/badge/policy_coverage-8_of_8_clauses-333?style=flat-square&labelColor=1a1d24)

</div>

An account-review agent decides flagged merchant accounts: APPROVE, HOLD,
or REJECT, driven by a plain-text prompt. This repository treats that
prompt the way a risk team should: versioned one change at a time,
benchmarked across 8 models on a frozen case suite, attacked with
planted instructions, repeated until stability is a number, and gated so
an untrustworthy cell cannot show a headline figure.

It is not a general eval platform (promptfoo is the production-grade
alternative and is named as prior art), not a fraud model, and not a
prediction of money: the dollar figures are stated exchange rates between
error types, sensitivity-swept, with the one partially-grounded figure
marked as such.

## Sixty seconds

```bash
git clone https://github.com/ShovalBenjer/verdict-bench && cd verdict-bench/verdict-bench
python3 engine/runner.py --report      # the gated benchmark matrix, no keys needed
python3 engine/runner.py --coverage    # does every policy clause have a test
pip install -e '.[dev]'                # ruff + mypy + pytest for the line below
make check                             # compile, lint, types, full test suite, report smoke
```

## Where it landed

**v5 on gemini-flash**: 100% decision accuracy, 100% contract adherence, $0 weighted loss per 1,000 cases

| rung | model | accuracy | contract | weighted loss /1k [95% CI] |
|---|---|---|---|---|
| v5 | gemini-flash | 100% | 100% | $0 [0 to 0] |
| v1 | qwen3.8-max | 92% | 100% | $41,667 [0 to 125,000] |
| v4 | gemini-flash | 92% | 100% | $50,000 [0 to 150,000] |
| v4b | gemini-flash | 92% | 100% | $50,000 [0 to 150,000] |
| v4c | gemini-flash | 92% | 100% | $50,000 [0 to 150,000] |

Rankable cells only; a cell that fails the trust gate (n, contract rate,
CI width, repeat-run flip, or a zero-tolerance miss) hides its own number.
Loss prices are assumptions (missed fraud $2,000, needless hold $45, lost
customer $600); the interval is case-resampling variability only. For
scale, deciding every case the same way costs $189k (always HOLD) to
$674k (always APPROVE) per 1,000 cases.

## What is in here

1. `WRITEUP.md`: the required writeup, 5 minutes.
2. `prompts/`: the ablation ladder v1 to v5, one change per rung with its
   hypothesis; `CHANGELOG.md` carries the gate record of the one edit a
   loop proposed and a pre-registered gate accepted after N=5 repeats
   refuted a false regression.
3. `TRANSCRIPT.md`: the curated work log, dead ends kept.
4. `sessions/`: the verbatim extract behind it (0 words; operator
   messages word-for-word, every removal a counted marker).
5. `verdict-bench/`: the lab itself: engine, 28 tests over real SQLite,
   ADRs each carrying the rejected alternative, `benchmark.json` (every
   number in the writeup, regenerated from the run ledger), robustness
   suites, and three held-out cases authored from fraud archetypes the
   ladder never saw.

## How it stays honest

Every run is pinned to its prompt by content hash. Accuracy never blends
label tiers (4 expert labels, 5 adjudicated, the rest constructed and
saying so) or suites (robustness cases score in their own columns). 511
blocklist-kept conversation turns ship as 93, every drop marked. A
verdict that depends on one temperature-0.2 sample is repeated to N=5
before it is believed; that protocol reversed one gate decision and
revoked one perfect score.

## Fits and does not fit

| question | answer |
|---|---|
| Rank prompts for this decisioning task | yes, gated matrix |
| Certify production readiness | no: 4 expert labels bound everything at Wilson [0.51, 1.00] |
| Predict fraud losses in dollars | no: prices are stated assumptions |
| Resist adversarial notes | measured, not achieved: resistance is a coin flip at every rung, named |
| Replace promptfoo in CI | no, and the writeup says why |

Path note: repo-relative doc links map as `docs/prd/SPEC.md` to
`verdict-bench/SPEC.md`, `ui/public/benchmark.json` to
`verdict-bench/benchmark.json`. The raw run ledger and internal planning
docs stay out by design; the ledger is available on request.
