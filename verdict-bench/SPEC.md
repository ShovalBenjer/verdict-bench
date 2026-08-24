# verdict-bench: eval-driven prompt improvement for the Intuit case study

PRD: this file. Ticket: Intuit take-home (submit 2026-08-24).
Status: active.

## One sentence
A local benchmark lab that treats each prompt version as a model release:
every version runs against every available model on a frozen case suite,
scored by deterministic tests plus rubric judges, with the whole history in
SQLite and a web UI to present the power curve from v1 to v5.

## Audience calibration (the reason this exists)
The screening round pointed the follow-up at analytical craft: predictions,
feedback loops, evals, rather than engineering internals. So the product is
the BENCHMARK and its charts, not the runner. Every slice ends in an
analyst artifact.

## KPIs

### Business KPIs (what a risk org actually buys)
| KPI | Definition | Proxy in this project |
|---|---|---|
| Expected loss per 1k cases | sum(cost[error_type] x rate) using an explicit cost matrix | Cost matrix: FA=$2,000 (realized fraud loss, avg of case exposures), FH=$45 (support touch + churn risk), FR=$600 (lost LTV), plus ONE derived cell: a fraudster held instead of rejected costs FA/4=$500 (partial containment; the fourth price is derived, not a fourth assumption). Stated as assumptions, sensitivity-analyzed in the notebook |
| Auto-decision rate | share of cases decided without human review at target precision | share of cases where decision is stable (N-run agreement = 100%) AND confidence >= threshold |
| Hold queue burden | holds created per 1k cases x avg resolution cost | HOLD rate on the suite, weighted by exposure |
| Sanctions recall | missed genuine sanctions matches | must be 1.0; a single miss is disqualifying (zero-tolerance mirror of the policy) |
| Cost to serve | $ per decided case | tokens x provider price per cell |

### Technical KPIs
| KPI | Definition |
|---|---|
| Golden accuracy | correct decisions / labeled+adjudicated cases |
| Flip rate | 1 - modal-decision agreement over N=5 repeats per case |
| Invariance rate | metamorphic cases (irrelevant field changed) that do NOT flip |
| Causal sensitivity | perturbation cases (causal field flipped) that DO flip |
| Contract adherence | outputs that parse as the exact JSON contract, first char { |
| Injection resistance | poisoned-note cases where the decision ignores the injection |
| Reasoning fidelity (rubric) | judge score: does the reasoning cite the actually-decisive fields |
| Calibration error | |stated confidence - empirical accuracy| binned |
| Latency p50/p95 | wall-clock per decision, per provider |

Latency: we CARE but as a reported dimension, not an optimization target.
Account review is human-in-the-loop back-office; anything under ~30s is fine.
It matters for the benchmark because it prices the auto-decision path and
because p95 blowups reveal provider throttling. Report it, never tune for it.

## How a prompt becomes solvable / testable / benchmarkable
Each prompt version is an immutable artifact: `engine/prompts/v{n}.md` +
a changelog entry naming the hypothesis it encodes ("v3: conflicted sanctions
signal resolves to HOLD"). A version is benchmarkable because:
1. Input space is frozen: the case suite (golden + perturbation + metamorphic
   + injection + synthetic) is versioned data, not regenerated per run.
2. Output space is a 3-class decision + JSON contract: deterministically
   gradeable.
3. Reasoning quality is rubric-gradeable: fixed judge prompt, fixed rubric
   questions, scored by a judge model that is NEVER in the contestant pool
   for that cell (cross-judging to avoid self-preference).
So each (prompt, model) cell = deterministic layer (accuracy, flip, contract,
invariance, sensitivity, injection, latency, cost) + hybrid layer (rubric
scores on reasoning fidelity, evidence citation, proportionality reasoning).

## The benchmark matrix (the centerpiece screen)
Rows: prompt v1 (baseline "just decide"), v2 (policy-quoting naive), v3
(policy-teaching, today's work), v4 (+sanctions conflict rule + contract
hardening), v5 (+expected-loss weighing / whatever the feedback loop
proposes). Columns: claude-sonnet, claude-haiku, gemini-flash, gemini-pro,
llama-3.3-70b (NVIDIA), nemotron (NVIDIA), qwen-max, glm (Z.AI).

Each cell renders as a small stacked tile:
```
+--------------------------------------+
| v3 x gemini-flash                    |
| golden 9/9   flip 0.04   inj 5/6     |
| rubric 4.2/5   $0.0011   p95 3.1s    |
| EL/1k: $8,400                        |
+--------------------------------------+
```
Clicking a cell opens the run drill-down: per-case decisions, reasoning,
judge scores, diffs vs the expert label. The demo arc: walk left-to-right
(models) then top-to-bottom (versions) and watch expected loss fall.

## Data sources (Intuit-adjacent, open)
- IEEE-CIS Fraud Detection (Vesta, Kaggle): real e-commerce transaction
  fraud, richest open analogue to merchant risk. Use: feature distributions
  to make synthetic cases realistic (amount/decline/chargeback shapes).
- PaySim (Kaggle): synthetic mobile-money flows; bust-out-like
  transfer-out patterns.
- ULB Credit Card Fraud (Kaggle): class-imbalance benchmark; use for the
  imbalance framing in the writeup (fraud is rare, accuracy is the wrong
  headline metric).
- Elliptic (Bitcoin) dataset: linked-account graph patterns for the
  linkage cases.
- Sparkov / IBM TabFormer generators: reference implementations for
  synthetic transaction generation.
- Competitor documentation as domain ground truth: Stripe Radar docs,
  Adyen risk rules, Sift/Ravelin fraud-pattern glossaries, FATF and FinCEN
  typology reports. These calibrate what realistic signals look like.
None of these ship in the repo (size/licenses); a fetch script + provenance
note per source. Distributions inform the simulator; no raw rows go to models.

## Synthetic data: yes, and this IS the flight simulator
Generate cases parametrically, not by asking an LLM to "make a fraud case"
(LLM-generated cases inherit the same priors as the LLM judge; correlated
errors). The factory: sample (archetype, tenure, exposure, signal strength,
conflict presence, injection presence) from a grid; render deterministic
JSON with seeded randomness; label BY CONSTRUCTION (the archetype is the
label). LLMs are allowed only to paraphrase note text on top of the
deterministic skeleton. This gives labeled ground truth at scale with zero
labeling cost, and the decision-surface heatmap falls straight out.

## HF / open models as tools (not contestants)
- Judge diversity: a small open judge (Qwen or Llama via NVIDIA) alongside
  Gemini judging Claude cells and vice versa.
- Embeddings (sentence-transformers, local or HF inference): cluster
  reasoning texts to find failure MODES not visible in accuracy ("all
  errors mention tenure").
- A tiny classifier baseline (logistic regression on hand-extracted case
  features): the analyst move that lands hardest, because if XGBoost-lite
  on 8 features matches the LLM on the golden suite, that is a finding
  about where LLMs earn their cost.

## Architecture
```
verdict-bench/
  engine/            python, uv-managed
    providers/       one client per provider behind one typed interface
                     (claude_sdk, gemini, nvidia_openai_compat, qwen, zai)
    prompts/         v1.md ... v5.md, immutable + CHANGELOG
    factory.py       synthetic case generator (seeded, archetype->label)
    runner.py        (prompt, model, case, n_repeats) -> rows in sqlite
    graders/         deterministic.py, rubric_judge.py (cross-judging)
    schema.sql       runs, cases, prompts, models, judgments, costs
  data/              golden cases (from the zip), perturbations, injections,
                     synthetic batches (versioned by seed)
  notebooks/         analysis.ipynb: matrices, calibration, cost frontier,
                     expected-loss sensitivity
  ui/                Vite + React, reads FastAPI (engine/api.py) over sqlite
  state/verdict.sqlite3
```
Boundary contracts rule applies: every provider client returns a typed
DecisionResult (decision, reasoning, raw, tokens, latency, error) and every
parse failure is a recorded contract-violation row, never a silent skip.

## Product design (UI)
Three screens, no more:
1. Matrix (the tile grid above) with version/model filters.
2. Case drill-down: case JSON left, per-model decisions+reasoning right,
   expert label banner, judge scores.
3. Power curve: line chart of expected loss + golden accuracy per prompt
   version, one line per model. This is the "incremental increase of power"
   screen and the deck's money shot.
UI is read-only over the DB; runs are launched from CLI/notebook. A demo
button that runs ONE live case through 3 models on stage is the only write.

## Program design: vertical slices (no debt, each shippable)
Assumed calendar: today Mon 2026-08-17. Fly Wed 19. Remote Wed-Fri.
Submit Mon 2026-08-24.
- S0 (today): repo, schema, provider interface + 2 providers (claude-sdk,
  gemini), golden suite loaded, runner writes rows, CLI report. DONE = one
  command reruns the 9-case suite on 2 models.
- S1 (Mon-Tue): deterministic graders complete (flip, invariance,
  sensitivity, contract, injection set authored), + NVIDIA + Qwen/GLM
  providers. DONE = full deterministic layer on 4+ models.
- S2 (Tue): rubric judge with cross-judging + notebook v1 (matrix,
  flip-rate, cost). DONE = first full benchmark matrix as a dataframe.
- S3 (Tue-Wed am, pre-flight): FastAPI + React matrix screen + drill-down.
  DONE = presentable local demo of v3 vs v4 across models.
- S4 (remote, Bucharest): synthetic factory + 100-case batch + decision
  surface + power-curve screen; prompt v5 from the disagreement loop.
- S5 (weekend): calibration, expected-loss sensitivity, deck, writeup,
  freeze. Submission Sunday night.
Debt rule: a slice merges only with its tests green and schema migrations
forward-only; UI never reads anything but the DB, so engine and UI cannot
block each other.

## Rejected alternatives
- Tauri shell: Rust build chain + packaging debt, zero benefit for a
  localhost presentation. Web UI wins on the deadline constraint.
- Azure runtime: excluded per operator (unavailable).
- LLM-authored synthetic cases as ground truth: correlated with judges,
  rejected; deterministic factory with LLM paraphrase only.
- One shared judge model: self-preference bias; cross-judging instead.

## Prior art (searched 2026-08-17, queries logged per prior-art-gate)
Queries: "prompt regression testing matrix multiple models eval framework
promptfoo" / "LLM-as-judge self-preference bias cross-judging evaluation
survey" / "synthetic fraud case generation benchmark LLM fraud detection
evaluation".
- The versions x models matrix is a solved category: promptfoo (MIT,
  acquired by OpenAI 2026-03) does matrix regression testing, golden
  datasets, red teaming, cost/latency across providers. This project's
  matrix is an APPLICATION of that pattern, not an invention.
- Cross-judging is literature, not our trick: arXiv 2410.21819
  (self-preference bias), family-favoritism findings, ensemble-of-judges
  mitigation. Cite, don't claim.
- Fraud eval prior art: PaySim, the CCF/ccFraud/IEEE-CIS/PaySim four-dataset
  convention, Fraud-R1 benchmark.
Our actual contribution: policy-clause-tied causal perturbation suites, the
expected-loss layer with an explicit cost matrix, and the analyst-facing
notebook/UI over one SQLite ledger. Why not promptfoo directly: it does not
carry the expected-loss/calibration/decision-surface analytics that ARE the
deliverable here; a thin runner writing the same SQLite the notebook reads
keeps one data plane. Divergence is a deadline+analytics call, and the deck
names promptfoo as the production-grade alternative for CI.

## Label tiers (golden / silver / construction), added 2026-08-17
- GOLDEN: the 4 expert-labeled cases (101, 102, 106, 108). The only tier
  that can falsify the adjudicator.
- SILVER: the 5 cases adjudicated by this project's own full-power
  reasoning pass (103, 104, 105, 107, 113). Weaker evidence class by
  definition; CASE-104's stable model disagreement is exactly a silver
  label under challenge, and the report/notebook must show tiers
  separately, never blended silently.
- CONSTRUCTION: perturbation/metamorphic/injection/synthetic cases whose
  label is true by construction. They measure sensitivity and robustness,
  never "accuracy".
label_source in the cases table carries the tier; blending tiers in one
accuracy number is the anti-pattern this section exists to forbid.

## Testing-pyramid mapping (state, honest), added 2026-08-17
| layer | instance here | state |
|---|---|---|
| static | py_compile in make check; ruff in dev extra | partial (ruff not wired into check) |
| unit | tests/test_graders.py planted-defect suite (9) | done |
| property | randomized contract-fuzz of parse_contract | MISSING (cheap, Mon) |
| contract/boundary | DecisionResult discipline; provider error-row tests | partial (discipline yes, tests of providers no) |
| integration | test_report_runs_clean over the real DB | done |
| E2E | browser screenshot of the UI over real export | done manually, not automated |
| trajectory | N=5 repeat stability runs | done (pilot) |
| adversarial | injection case set | MISSING (Mon, S1b) |

## Model roster: rationale and correction, added 2026-08-17
Correction on the record: llama-3.3-70b was chosen as a familiar NVIDIA
Build slug, not by reasoning; it is a Dec-2024-generation model and its
column measures a PREVIOUS generation of open weights. Kept deliberately
as the "yesterday's open model" reference point, and labeled as such in
the deck. Roster policy going forward: one frontier closed (sonnet), one
cheap closed (haiku, gemini-flash), one strong closed (gemini-pro), one
CURRENT open (add: qwen3 or nemotron via NVIDIA/Qwen keys, Mon), one
legacy open (llama-3.3-70b, explicitly framed as the generation baseline).
Every column must state why it is in the matrix or leave.
