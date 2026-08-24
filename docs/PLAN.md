# verdict-bench program plan: vertical slices

PRD: docs/prd/SPEC.md. Status: active. Companion: ARCHITECTURE.md, PRODUCT.md.
Calendar: today Sun 2026-08-17 evening. Fly Wed 08-19 (Bucharest, remote
Wed-Fri). Submit Sun 08-24 night for Monday.

Slice rule: every slice merges green (make check), leaves the repo
presentable, and ends in an analyst artifact. No slice depends on an
unmerged slice.

## Done (evidence: git log, state/verdict.sqlite3, TRANSCRIPT.md 1-16)
- S0 engine: schema, typed providers (claude CLI, gemini, nvidia), runner,
  golden+perturbation suite loaded, per-case reporting. 115 runs banked.
- S0.5 versions: v1 naive, v2 policy-quoting, v3 policy-teaching, v4
  hardened; version axis run on gemini-flash; saturation finding.
- S3a UI: matrix, power curve, case compare, discrepancy banners; verified
  in browser; Tauri debug shell built and launched under WSLg.
- Stability pilot: N=5 on 113-P3 (v3 vs v4 distribution shift) and 104
  (stable disagreement).

## Mon 08-18 (full day, the hard-work day)
- S1a packaging: pyproject + requirements, Makefile (run/report/export/ui/
  check/docker), Dockerfile (engine + built UI served statically),
  .dockerignore. Acceptance: `make check` green in a fresh clone;
  `docker build` succeeds; container runs the report against a mounted DB.
- S1b graders: injection case set (>=4 poisoned-note cases), metamorphic
  set (>=4 irrelevant-field variants), flip-rate computation into export;
  tiles show flip + injection. Acceptance: tiles render with real numbers.
- S2 rubric judge: judge prompt + rubric (evidence citation,
  proportionality, policy alignment), cross-family assignment (gemini
  judges claude+llama cells, claude judges gemini cells), judgments table
  filled for v3/v4 cells. Acceptance: rubric column in matrix; one
  disagreement between judges surfaced in TRANSCRIPT.
- S2b: sonnet native rerun (retire wrapper caveat rows).

## Tue 08-19 morning (pre-flight, presentation-critical only)
- S3b UI: filters (version/model/suite), flip+injection+rubric tiles wired,
  live "run case" button behind a local endpoint IF time allows, else cut.
- Deck skeleton: 10 slides following PRODUCT.md story arc.

## Wed-Fri (Bucharest, remote, laptop)
- S4 factory: seeded synthetic generator (archetype -> label by
  construction), 100-case batch, decision-surface heatmap in the notebook;
  v5 prompt from the autoresearch-style loop (propose edit -> golden gate
  -> accept/revert), each experiment a row.
- Writeup draft (the choices, the dead ends, the readiness argument).

## Sat-Sun 08-23/24 (freeze)
- Calibration + expected-loss sensitivity in the notebook.
- Final deck, writeup, transcript assembly (TRANSCRIPT.md + raw session
  logs), repo tag v1.0, submission bundle. Freeze Sunday 18:00, submit
  Sunday night.

## Cut lines (in order, if time runs out)
1. Live run-case button (demo can run from terminal).
2. v5 autoresearch loop (present the design + one manual iteration).
3. Synthetic batch shrinks 100 -> 30.
Never cut: packaging (Mon), rubric judge, writeup, transcript.

## Standing risks
- Provider flake burning presentation-morning time: all demo data is
  pre-run; the live button is a garnish, never the meal.
- WSLg window vs Windows-native binary for the actual presentation:
  decide Tue; fallback is the web build in a browser, same dist/.
- Operator travel days: Wed-Fri slices are laptop-only by design (no
  local model deps, all providers remote).

## Operator-ask coverage register (added 2026-08-17 night, after gap reread)

Single source of truth for plan-vs-ask; no further plan files get created.
plan_nextgen.md in the assignment folder is SUPERSEDED by this file.

Open gaps against explicit operator asks, priority order:
1. notebooks/analysis.ipynb on a local Jupyter server: ASKED EXPLICITLY,
   does not exist. Moves from weekend to Mon morning, before S1b. The
   notebook is the analyst surface; the UI is the presentation surface.
2. Model coverage: qwen (QWEN_API_KEY) and GLM (Z_AI_KEY) columns unwired;
   add both as openai-compat providers Mon. Second NVIDIA model optional.
3. LR-baseline (hand-extracted features): cheap, high analytical value,
   Mon with the notebook.
4. Domain research pass through connectors (Exa, alphaXiv, Consensus,
   O'Reilly for Baesens metadata): Mon, feeds the writeup's grounding
   section. Deep-research agent optional if time.
5. Data-source fetch scripts (IEEE-CIS/PaySim distributions): Wed, they
   gate the synthetic factory's realism.
6. prompt-eval skill extraction + project memory files: Tue, cheap.
7. docker build proof: Mon S1a acceptance, still unproven.
8. Autoresearch v5 + DSPy comparison: Wed-Fri as planned.

## Register reconciliation, 2026-08-23 night (freeze eve)

Closed since the rows above were written, with the artifact:
- Item 1 notebook: notebooks/analysis.ipynb exists.
- Writeup: docs/WRITEUP.md written, plus the decision-order paragraph and
  the A/A-to-SPRT readiness item added 2026-08-23.
- Transcript assembly: assignment/build_dist.py builds the full bundle;
  the session extract is curated turn-by-turn (curation.json, two review
  rounds, leak and orphan checked), EXCLUDED.md is the operator gate.
- ADRs: docs/adr/0001-0004 written (the three architecture calls STATUS.md
  named as prose-only, plus stdlib-core).
- Deck spine: PRODUCT.md beat sheet (2026-08-23) including the one-page
  "how I operate" slide.
- Item 7 docker: docker is now INSTALLED in this WSL (contra the 08-19
  audit); the build is blocked on docker-group membership, a one-command
  operator action recorded in README.md. Still unproven, cause narrowed.

Still open, unchanged priority: item 2 (qwen/GLM columns), item 3
(LR baseline), item 4 (research pass), item 5 (IEEE-CIS/PaySim), item 6
(skill extraction), item 8 (v5 loop, DSPy), plus S1b injection/metamorphic
sets and the S2 rubric judge from the Mon plan. None gates the submission.

## Register re-opened and RUN, 2026-08-24 (submission day, 00:15 to 03:00)

Operator decision 00:15: the cut list above was never accepted; all items
un-cut. Deadline restated: submit by 15:00 today. Every open row above is
now closed, each with its artifact:

- Item 2 qwen/GLM: qwen3.8-max wired and run (11-12/12, contract 1.00,
  4/4 injection, 4/4 metamorphic; 30-120s latency; its 12/12 first-run
  cell is gated unrankable by the new flip guardrail, CASE-108 coin
  flip). GLM wired and money-blocked on its one route (Z.AI 429, body
  error 1113 insufficient balance, banked verbatim); operator action
  to unblock; ships as recorded error rows. nemotron-super-49b fills
  SPEC's current-open roster slot (10/11 + contract failures; misses
  CASE-102 like haiku and llama).
- S1b injection + metamorphic: 4+4 cases authored (untrusted channels,
  payloads push against the label, one pushes over-rejection), plus
  CASE-115 (kind=coverage). Coverage table now 8/8 clauses. Suite
  separation enforced in oec/report/export/notebook; inj/inv columns.
  Headline finding: 102-INJ resistance is a coin flip at every v4-family
  rung (N=5: v4b 2/5, v4c 1/5, v5 3/5); the single-run "v4b resists
  everything" claim was noise.
- S2 rubric judge: engine/judge.py, cross-family, judge blind to the
  expected label, dual-judge overlap on v4/flash. Judgments table
  filling as this row is written; flash-as-judge saturates (~5.0 means),
  haiku-as-judge discriminates (~3.1-3.95): the disagreement finding.
- Item 3 LR baseline: experiments/lr_baseline, LOO 8/12 vs LLM 11-12/12;
  all four misses are policy-reasoning cases in the expensive direction.
- Item 4 research pass: per-claim verification (promptfoo/OpenAI
  acquisition CONFIRMED 2026-03-09; arXiv 2410.21819 CONFIRMED; Fraud-R1
  CONFIRMED); grounding folded into WRITEUP.
- Item 5 fetch scripts: tools/fetch_data + PROVENANCE.md (kaggle CLI
  absent here, scripts print exact manual steps and exit 0; PaySim/ULB
  licenses verified from source pages, IEEE-CIS honestly unverifiable).
- Item 6 skill extraction: ~/.claude/skills/prompt-eval/SKILL.md written
  (live tree, stated openly) + per-decision memory rows.
- Item 8: DSPy arm in experiments/dspy_arm (ceiling 12/12, structural
  contrast vs the hand ladder, honest caveats). v5 gated iteration run
  IN FULL: ACCEPTED (first 12/12 flash pass; the apparent injection
  regression refuted at N=5; CASE-104 fix stable 4/4); v5 is now the
  submitted prompt, CHANGELOG carries the gate record.

Still cut after the re-run, named: synthetic factory, live run-case
button.

Delivery switch, operator decision ~02:00 2026-08-24: the bundle ships
as a GitHub repo, not a zip. Renamed ~07:00 to
https://github.com/ShovalBenjer/verdict-bench (the lab's own name; a
second name fragmented the brand; tagline "single runs lie..."; the old
account-review-case-study URL redirects). The private repo carries
exactly the gated dist content (PRODUCT/PLAN stay out, per the recorded
exclusion); refreshed post-freeze with the measured v5 resolution and
the docker proof. The 01:44 zip on disk is superseded. Deck: operator
builds a .pptx via claude-design; the beat sheet here is its spine. The docker proof closed post-freeze (2026-08-24 ~02:00): the
operator ran the group one-liner, the image built 15/15, and a live
smoke served the UI from the container (HTTP 200 on :8080, 19-cell
benchmark.json with v5). The 01:44 submission zip predates this and
deliberately keeps its conservative "blocked, not a code defect" claim;
rebuilding it would regenerate EXCLUDED.md, which the operator reviewed
and deleted.
