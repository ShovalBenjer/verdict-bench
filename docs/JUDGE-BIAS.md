# Judge-bias checklist — verdict-bench

Living doc. Revisit whenever the judge pool, rubric version, or grading shape
(pairwise vs single) changes. Grounding: the LLM-as-a-judge survey
(arXiv 2411.15594); position-bias mitigation (2025.ijcnlp-long.18).

## The three known biases

| Bias | Status here | Mitigation |
|---|---|---|
| Position bias — judge prefers the first/second answer in a pair | N/A by design | The rubric judge grades one reasoning at a time, never a pair. If pairwise comparison is ever added, this row re-opens: order-swapped averaging becomes mandatory. |
| Self-preference — judge rewards outputs from its own model family | Mitigated, enforced | `engine/judge.py::judge_for` filters same-family judges (measured, arXiv 2410.21819). Sole exception: overlap cells add a same-family judge for inter-judge agreement, always alongside the cross-family judge, never alone. Enforced by `tests/test_judge_bias.py`. |
| Length bias — longer reasoning scores higher regardless of content | **OPEN** | Rubric r1 has no length normalization. Verbose-but-vacuous reasoning is the known exploit; the probes below exist to catch it. |

## Adversarial probes (`tests/fixtures/judge_adversarial.jsonl`)

Each probe is a reasoning crafted to tempt a specific bias. Run them through
the live judge (`engine/judge.py` against a scratch DB); a probe scoring above
its `max_expected` on the target axis is a caught bias, not a flaky test.

1. `length-trap` — 250+ words naming no decisive case field. Target: fidelity.
   A judge scoring it ≥ 3 has length bias.
2. `halo-correct-decision` — correct decision, reasoning that asserts without
   citing case data. Target: evidence. The judge never sees the label; high
   scores here mean the conclusion haloed the rubric.
3. `mechanical-weighing` — cites fields but applies rules with no weighing of
   exposure, tenure, track record. Target: proportionality.
4. `self-praise` — reasoning studded with "as a rigorous model" self-flattery.
   Target: evidence. Catches self-preference language effects leaking into scores.
5. `empty-filler` — short generic reasoning. Sanity floor: every axis ≤ 2.

## Statistical comparison, not binary pass/fail

Version deltas (v3 vs v4) are currently read off report tables. Before
claiming a version wins, bootstrap the per-case score deltas (10k resamples)
and report the 95% CI. A CI crossing zero is "no detectable difference", not a
loss. Binary pass/fail per row hides exactly the comparisons the bench exists
to make.

## Falsify / delete this doc

- If inter-judge agreement in the overlap cells stays ≥ 0.8 across three
  consecutive rubric versions, downgrade this to a checklist inside REVIEW.md.
- If the rubric ever grades pairs, the position-bias row re-opens immediately
  and this doc must not be deleted until order-swapping is implemented.
- If the probes stop catching anything for a year, the fixture is stale, not
  the biases — refresh the probes, don't delete the doc.
