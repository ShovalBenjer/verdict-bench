# UI backlog (operator review 2026-08-17, against SPEC.md)

PRD: SPEC.md. Status: active. Ordered by presentation value.

## P0 (blocks the demo story)
1. Prompt version rows v1-v5 in the matrix. Requires authoring v1 (naive
   baseline "just decide"), v2 (policy-quoting verbatim) and running them;
   v5 lands with the autoresearch loop (S4).
2. Power-curve screen: line chart, expected loss + golden accuracy per
   prompt version, one line per model. The incremental-power money shot.
3. Drill-down split-pane: case JSON viewer left, MULTI-model decisions and
   reasoning for the same case right (current pane is single-model).
4. Ground-truth discrepancy banner per case run: expected vs decided and
   which policy clause the miss violates.

## P1 (stronger matrix)
5. Tile KPIs: flip rate (needs N=5 repeat runs), injection resistance
   (needs the injection case set), rubric score (needs S2 judge).
6. Filters: prompt version, provider, suite kind (golden / perturbation /
   metamorphic / injection / synthetic).
7. Reasoning default-visible on wrong cases (auto-expand misses).

## P2 (live-demo interactivity)
8. "Run case" stage action: paste/select a case, execute live across 2-3
   selected models concurrently (the only write path in the UI).
9. Cost-matrix sliders (FA/FH/FR) with live expected-loss recalculation;
   also fixes the misleading $46k/1k display by making the assumption
   visible and adjustable.
10. Rubric dimension breakdown in drill-down: evidence citation,
    proportionality, policy alignment (needs S2).

## Dependency truth
Rows before curves (1 -> 2), suites before their KPIs (graders -> 5),
judge before rubric surfaces (S2 -> 5, 10). UI-only items: 3, 4, 6, 7, 9.
