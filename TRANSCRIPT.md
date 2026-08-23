# Work transcript: Intuit take-home (account-review prompt)

Required deliverable: every prompt and response, in order, including dead ends.
This file is the running log; the raw Claude Code session transcript backs it.

## Session 1, 2026-08-17

### 1. Intake
- Received Aviv's email + `ai-workflow-case-study 2.zip`. Filed under
  the assignment zip, unzipped to `case-study/` (shipped in this bundle).
- Read README.md, POLICY.md, labeled-answers.md, all 9 case JSONs whole
  (no sampling), before forming any opinion.

### 2. Exploration findings (human + Claude joint pass)
- Case map with my reads before writing any prompt:
  101 APPROVE (labeled), 102 REJECT (labeled), 103 APPROVE (IP-only link on
  coffee-shop wifi; strong link is owner's own good account), 104 HOLD (ownership
  changed 5d ago, new owner unverified, Chicago->Lagos device shift, new
  unverified payout, $12k out in 3 days; unresolved not confirmed), 105 APPROVE
  (903d verified, one normal decline+retry, trivial 0.22 token), 106 REJECT
  (labeled), 107 REJECT (bust-out: 21d account, mechanical funding pattern,
  cash-out to 5d-old destination, chargebacks corroborate; policy says loss
  realized at extraction), 108 APPROVE (labeled), 113 APPROVE (4.5y merchant,
  3 chargebacks vs $2.4M lifetime, prior review cleared same issue).
- Insight: each unlabeled case is a trap for a naive rule. 103 punishes
  "link=bad", 104 punishes "tenure=good", 107 punishes "wait for chargebacks",
  113 punishes "above-average dispute rate=bad". Labeled pairs teach the same
  contrasts (101 vs real sanctions hit, 108 vs bust-out).
- Insight: policy is principles, not thresholds. Hardcoded numbers will fail
  held-out cases; the prompt must teach the weighing logic.
- Insight: analyst notes inside cases disagree (104 has both directions) and
  could themselves be traps in held-out cases. Prompt must treat notes as
  opinions to check against data, not verdicts.
- Insight: `precomputed.confirmed_problem_on_record` is a crutch; policy
  explicitly covers a flag that conflicts with the record (data-quality
  question, not confirmed problem). Prompt must not lean on the boolean blindly.

### 3. Decision: prompt architecture
- Chose policy-TEACHING (restate the decision logic as a procedure with the
  weighing principles explicit) over policy-QUOTING (embed POLICY.md verbatim
  + scaffold). Assumption: held-out cases test generalization of the weighing
  principles; a verbatim embed is exactly what the lazy one-shot submission
  does and gives the model no help on order of operations or trap patterns.
  Risk accepted: paraphrase can drift from the policy; mitigated by checking
  each prompt clause against a POLICY.md sentence.
- Wrote `prompt_v1.md`: 3-step procedure (REJECT triggers -> HOLD test ->
  APPROVE default), explicit look-alike table (false-positive watchlist,
  incidental links, unsubstantiated flags), weighing principles including
  "tenure attaches to the party in control" (the 104 lesson), output contract.

### 4. Planned verification (next)
- Run v1 on the 4 labeled cases: must go 4/4 with reasons matching the
  expert's one-liners.
- Perturbation tests (flip the causal feature, decision must flip):
  101 with matching DOB -> REJECT; 113 as a 30-day account -> HOLD;
  104 without the ownership change -> APPROVE; 107 without the cash-out ->
  not REJECT.
- Adversarial: feed a case with a misleading analyst note; check the model
  overrides it from data.

### 5. v1 results on labeled cases (fresh-context runs, Sonnet, one case each)
- 4/4 correct: 101 APPROVE (DOB/country mismatch + independent ID verify),
  102 REJECT (22 cards in 81s, $0 captured; discounted owner's "testing my
  integration" note per evidence discipline), 106 REJECT (same SSN/device/
  instrument to CLOSED_FRAUD account, prior adjudication CX-41990; protest
  overridden), 108 APPROVE (steady ramp, verified 900d payout destination,
  prior VOLUME_SPIKE cleared).
  [Correction 2026-08-23, final review: the 102 count was recounted
  directly from case-102.json: the 81-second burst is 28 transactions
  across 28 distinct instruments, 24 declined, $0 settled. This log's
  "22" was itself a miscount. The fabricated answer caught in section 18
  said "28", which happened to match the real count while everything
  around it was invented.]
- DEFECT FOUND: the 102 run violated the output contract, printing analysis
  prose before the fenced JSON instead of JSON-only starting with `{`.
  Fix for v2: harden the contract line ("your ENTIRE output is one JSON
  object; no preamble, no markdown fences") and repeat it at the end of the
  prompt, since contract adherence decays when the reasoning is long.
- Reasons matched the expert's one-liners in all four, not just the labels.

### 6. v1 results on unlabeled cases (predictions pre-registered in section 2)
- 5/5 match my pre-registered reads: 103 APPROVE, 104 HOLD, 105 APPROVE,
  107 REJECT, 113 APPROVE.
- 104 was the strongest output: it invoked tenure-attaches-to-the-party,
  credited analyst_jru over analyst_svo with a stated reason, and explained
  why HOLD not REJECT (destination unverified, not confirmed bad).
- Contract defect persists: 3/9 runs (102, 107, 113) emitted prose before
  the JSON, concentrated on long-reasoning REJECT cases even after the
  wrapper instruction was hardened, so the fix must live in the prompt.
- 107's reasoning contained a self-correcting arithmetic stumble
  ("totaling 3,000+... actually 4,300"). Sloppy for production output.

### 7. prompt_v2
- Same decision logic as v1. Changes: strict output-contract block up top
  (ENTIRE output is one JSON object, no preamble/fences/trailing text) and
  a closing "final reminder" section (recency helps adherence), plus an
  instruction to recompute cited numbers and resolve self-corrections
  before emitting.

### 8. Perturbation tests (flip the causal feature, decision must flip)
Built 3 perturbed cases under verification/:
- case-101-p1: sanctions hit now matches owner DOB+country, score 0.97.
  Expect REJECT (was APPROVE).
- case-104-p2: ownership change removed, KYB complete, US-only logins,
  payout destination long-established, no exposure. Expect APPROVE (was HOLD).
- case-113-p3: tenure 30 days, $22k exposed, payout destination 12 days old
  unverified, no prior clearing case. Expect HOLD (was APPROVE).
Runs launched on prompt_v2, fresh contexts.

### 9. Perturbation results (the useful failure)
- case-101-p1: FAILED, stayed APPROVE. Root cause split two ways:
  (a) my perturbation was internally inconsistent: I flipped the watchlist
  hit to full attribute match at 0.97 but left the original analyst note and
  prior case saying the attributes mismatch; the model weighed the conflict
  and credited the note. Dead end kept: perturbations must update ALL
  correlated evidence, not one field.
  (b) a real prompt vulnerability: an in-case analyst note was allowed to
  overrule an attribute-corroborated sanctions hit and RELEASE the account.
  Under zero tolerance, a conflicted sanctions signal should resolve to
  HOLD pending re-screen, never to release on the note's word.
  Fix: v2 sanctions bullet now says a conflicted attribute-match resolves
  to HOLD; a note can justify not-rejecting, never releasing past the hit.
  Rebuilt the perturbation cleanly as case-101-p1b (all sources consistent
  with a genuine match) and re-ran on patched v2, plus a regression run of
  the ORIGINAL case-101 to confirm the new rule does not flip the true
  false-positive to HOLD.
- case-104-p2: PASS, flipped to APPROVE. Bonus: I left two stale artifacts
  in the perturbed file (KYB_DOC_PENDING flag_reason, prior-case note about
  an ownership change) and the model correctly called both data-quality
  discrepancies contradicted by the record rather than holding on them.
- case-113-p3: PASS, flipped to HOLD, compounding exactly the intended
  signals (30-day tenure, unverified 12-day-old payout destination, $22k
  exposed, no own-history baseline).

### 10. Sanctions patch verified both directions
- case-101-p1b (clean genuine match, patched v2): REJECT. Correctly noted
  IDVerifyPlus confirming the identity CORROBORATES the sanctions match
  rather than disputing it.
- case-101 original (regression, patched v2): APPROVE. Correctly read the
  vendor's "attributes not compared" as no-conflict, so the new
  conflicted-match->HOLD rule does not fire on the true false positive.
- Perturbation suite final: 3/3 decision flips + 1/1 regression.

### 11. Open items for the writeup
- Contract adherence: 4 of 12 runs emitted prose before the JSON. Confound:
  runs went through an agent wrapper that can add its own commentary, so
  this measures the harness as much as the prompt. Clean measurement =
  direct API call, prompt as system message, case JSON as user message.
- Model variance: all runs were single-shot on one model (Sonnet). No
  repeat-sampling stability check yet.
- Readiness argument for the writeup: labeled 4/4, unlabeled 5/5 vs
  pre-registered predictions, causal perturbations flip decisions, and the
  one failure found was fixed and regression-tested. What would still make
  me nervous in production: contract adherence under long reasoning, and
  no measurement of behavior on genuinely ambiguous cases the policy
  underdetermines.

### 12. First cross-model matrix (v4, verdict-bench repo, direct APIs)
| model | acc | contract | p50 |
|---|---|---|---|
| gemini-flash | 12/13 (.923) | 1.00 | 8.4s |
| gemini-pro | 11/12 (.917) | 0.00 | 18.4s |
| llama-3.3-70b | 11/12 after 1 timeout retry (.917) | 0.86 | ~50s |
Findings: flash beats pro on contract adherence (12/12 vs 0/12, pro wraps
in fences); llama is the only model to miss a labeled expert case (102
card-testing -> HOLD); each model misses a DIFFERENT case (flash: 104,
pro: 113-P3, llama: 102), which is the ensemble/disagreement story.
Claude column blocked on CLI login (operator action pending).

### 13. Version axis lands, and falsifies the easy story
v1 (no policy) 11/12, v2 (verbatim policy) 12/12, v3 11/12, v4 12/13, all
on gemini-flash single runs. Finding: the labeled suite SATURATES; model
priors nearly solve it, so accuracy cannot separate prompt versions at
n=12 with 1 repeat. What does separate them: contract adherence (v4 100%
vs 0-8% for v1-v3; the strict-contract block demonstrably works) and,
prospectively, flip rate (N=5) + harder synthetic/injection cases. 113-P3
flip-flopped between runs (v3 HOLD earlier, REJECT now): direct evidence
single-run grading is noise at this n. This reframes the deck: the eval
has to get harder before the prompt can get better, which is the whole
argument for the simulator phase.

### 14. Claude column via wrapper, and a silent-skip catch
Subprocess claude CLI cannot read the credential store from this session's
sandbox (operator /login verified working interactively), so Claude cells
run through an agent wrapper: decisions valid, contract metric marked n/a.
The batch wrapper returned 11/12 cases, silently dropping CASE-105 while
reporting completion. Caught by counting against the case list; refilled
with a dedicated single-case run. Kept as a finding: batch agents can drop
items and still report success; per-case fresh contexts + count checks are
the defense. Sonnet v4: 11/11 correct on the cases it did return.

### 15. Sandbox diagnosis retracted; matrix complete at 100 runs
- The "sandbox blocks credentials" claim in section 14 was WRONG: the real
  cause was our own --bare flag, which skips credential loading. Fixed,
  auth-error rows purged, Claude columns now run native CLI with real
  contract + cost measurement. Calibration loss recorded: a confident
  infrastructure diagnosis stated without isolating the flag difference.
- Haiku v4 on retry decided HOLD on CASE-102 (card testing, expert REJECT):
  the SAME miss llama-3.3-70b made. Two small models independently
  underweight card-testing severity to a hold; sonnet/flash/pro all reject.
  Model-capability boundary, presentation material.
- v4 standings (single-run): sonnet 12/12, haiku 12/13, flash 12/13
  (miss: 104), pro 11/12 (miss: 113-P3), llama 11/12 (miss: 102).
  Every model misses a DIFFERENT case except the haiku/llama 102 overlap.
- Contract adherence: flash 100%, llama 86%, haiku/sonnet/pro 0% (markdown
  fences). CLI route also surfaces real cost: ~$0.15/case for haiku via
  CLI (77k-token system+context cache write dominates).
  [Note 2026-08-23: that figure is an early CLI-side estimate whose
  denominator includes cache-write tokens; export.py's flat per-token
  pricing over the same cells computes about $0.002/case. Two bases,
  both stated.]
- claude CLI flaked rc=1 on one case twice, then reproduced clean;
  provider now retries once and preserves stdout+stderr in the error row.

### 16. N=5 stability: the flip-rate and disagreement layers earn their place
- CASE-113-P3, gemini-flash: v3 = 4 REJECT / 1 HOLD (80% wrong), v4 =
  4 HOLD / 1 REJECT (80% right). Same case, same model, five repeats each.
  [Updated 2026-08-23: a sixth repeat per side exists in the ledger;
  v3 is 5/6 wrong (83%), v4 is 5/6 right, per benchmark.json.]
  The v4 edits shifted the whole decision DISTRIBUTION toward correct:
  causal evidence a prompt change worked, invisible to single-run grading.
- CASE-104, gemini-flash: REJECT 5/5, zero variance. Not noise: a stable,
  systematic cross-model disagreement (all four other models HOLD). A
  stable disagreement is a label-review trigger, the concrete mechanism of
  the disagreement feedback loop, and the strongest single exhibit for the
  "improve AI with AI, gated by adjudication" argument.

### 17. Operator correction: ablation discipline, label tiers, roster honesty
Operator flagged four gaps, all accepted:
1. Versions must change ONE element each. v4 had been authored as two
   changes (contract + sanctions). Fixed by inserting v3c (v3 + contract
   only); verified by machine diff that v4 = v3c + exactly the sanctions
   bullet. Ladder + per-version hypothesis now in engine/prompts/
   CHANGELOG.md; prompt_sha pins banked rows to their exact text.
2. Contestants/adjudicator split made explicit: frozen prompts at temp
   0.2 are contestants; this session's full-power reasoning is the
   adjudicator (silver labels, perturbation design) and is never a
   matrix column, because the grader must not compete in its own contest.
3. Golden/silver/construction label tiers documented in SPEC; blending
   tiers into one accuracy number named as the forbidden anti-pattern
   (CASE-104's stable disagreement is a silver label under challenge).
4. Roster honesty: llama-3.3-70b was picked by slug familiarity, not
   reasoning; it is Dec-2024 generation. Reframed as the deliberate
   legacy-open baseline; a current open model (qwen3/nemotron) joins Mon.
   Testing-pyramid mapping added to SPEC with MISSING rows named
   (property fuzz, injection set, automated E2E).

## Session 2, 2026-08-19, verdict-bench engine sessions (self-test discipline)

### 18. A fabricated self-check, rejected wholesale, and the real answers underneath it

Ran the 8 "grill me" questions against the harness as a self-test. The
first pass of answers came back fluent and fully fabricated: invented
CASE-104 content, an invented `prompts/v3.txt` file, an invented
`run_batch()` function, invented matrix numbers. None of it existed in
the repo. Rejected the whole response rather than partially crediting
any of it (a fluent wrong answer is worse than an obviously wrong one),
and re-ran all 8 questions against the real repo instead. What came back
for real:

1. Real CASE-104 (the KYB ownership-change case from section 2, not the
   fabricated ATO/Tor scenario the first pass invented) has a
   reproducible model miss: v4/gemini-flash decides REJECT, expert
   label is HOLD. Kept as the section 16 disagreement finding, not
   discarded.
2. The real v3->v3c diff has TWO changes (a stricter contract block AND
   a trailing "final reminder"), not the one cleanly isolated line
   CHANGELOG.md's ladder claims. Logged as a defect in the ladder
   documentation itself (ablation purity gap), not silently fixed
   retroactively: a genuine isolation would need a v3c-2 rung.
3. Checking claim 4 surfaced a NEW bug, not asked for: CASE-101 and
   CASE-104 each had a duplicate `repeat_idx=0` row for v4/gemini-flash
   (two different run_ids both tagged repeat 0). Section 19 covers the
   fix.
4. Real worst-scoring cell (correct dedup logic): v3c/gemini-flash,
   10/12, driven by the same CASE-104 miss as claim 1.

Lesson kept explicit: a self-check is only as good as the discipline to
reject a fluent wrong answer instead of accepting it because it sounds
complete.

### 19. Dupe-guard bug: found, root-caused, fixed with a constraint not a patch

Root cause: the run inserter always started `repeat_idx` at 0 per
invocation instead of offsetting from what already existed for that
(case, prompt, model). A single-case rerun (`--case CASE-101`) always
wrote `repeat_idx=0`, silently colliding with that case's existing row.
This is exactly what an earlier peer-review pass (section 17 area, item
7 in that review) predicted before it happened, and it manifested for
real here.

Fix: `repeat_idx` now computed as `MAX(existing)+1` at insert time, and
the schema gained `UNIQUE(case_id, prompt_version, model_id, repeat_idx,
prompt_sha)` so a future collision is a hard integrity error, not a
silent double-row. Data repair: found 7 dupe groups (not the 2 first
suspected), across 4 cases and both v3/v4. These were genuine
independent API calls that had collided on `repeat_idx=0`, not literal
duplicate inserts (each pair had a different run_id, timestamp, and raw
output), repaired by RENUMBERING the later row to the next free
`repeat_idx`, never by deleting data. Verified before/after row counts
matched (139/139) and zero dupe groups remained.

Known limitation, disclosed not hidden: rows written before the
`prompt_sha` column existed carry `prompt_sha=NULL`, and SQLite's UNIQUE
constraint treats NULL as distinct from every other value, so the new
constraint protects only rows written after this fix: it cannot
retroactively guard the 115 legacy rows. Checked this by triggering a
real rerun rather than assuming the constraint worked as written.

### 20. Three cost models, found by re-reading the notebook instead of trusting that it ran

Built an OEC (expected-loss) module using an invented unitless 0-10 cost
matrix with per-clause severity multipliers, before checking whether a
cost basis already existed elsewhere in the repo. It did: `docs/prd/SPEC.md`'s
KPI table already names FA=$2,000 (realized fraud loss) / FH=$45
(support touch) / FR=$600 (lost LTV), predating this work by months, plus
a hard rule ("Sanctions recall must be 1.0; a single miss is
disqualifying") that the invented multiplier system didn't honor as a
gate.

Caught only when asked directly whether the notebook was
presentation-ready. It ran clean end to end, which I had verified, but
running clean and being narratively ready are different questions, and
checking the second one meant actually reading the notebook's cells, not
re-confirming it executed. That read surfaced a THIRD, independent cost
formula already live in `engine/export.py` (the script that feeds the
UI's data file) and copied into the notebook itself, disagreeing with
both the invented multiplier system and, on two of nine cells, with each
other's assumptions about which HOLD/REJECT cells should carry which
cost.

Reconciled to one: matched the new module to `export.py`'s pre-existing,
UI-connected formula exactly (the older, load-bearing implementation
wins over a same-night invention), moved the sanctions/confirmed-history
"zero tolerance" language from a cost multiplier to a hard disqualifying
gate on the result, and added a regression test that imports
`export.py`'s real function and asserts every one of the 9 cost cells
agrees, so a future edit to either file breaks the test instead of
silently drifting into a fourth disagreeing cost model.

Checked whether the resulting $2,000 FA figure has any real grounding in
the case data: it does not: `SPEC.md`'s own comment claims "avg of case
exposures" but no code anywhere computed that average. Computed it for
real: mean `at_risk_usd` over the 4 cases actually labeled
`expected=REJECT` (the only cases where FA fires) is $4,251.63, roughly
2x the stated figure, but over only 4 cases including one with $0
exposure recorded, too thin a sample to treat as ground truth over the
stated $2,000. Recorded as an open, honest uncertainty rather than
resolved either direction; a sensitivity sweep over $1,000-$5,000
brackets the computed number on both sides and the ranking implication
of that range is checked, not assumed.

## Session 3, 2026-08-24 (00:15 to 03:00), the freeze-day round

The submission bundle had been declared done and gated the night before,
with eight open plan items cut to one line each. At 00:15 on submission
day I rejected those cuts and ran the register in full against a 15:00
deadline. This section is the curated log of that round; the verbatim
session extract in `sessions/` ends at its curation point the previous
evening, and the raw turns behind this section are available on request,
same as the rest.

### What ran

Two new model columns (qwen3.8-max, nemotron-super-49b; a GLM column is
wired and money-blocked on both available routes, shipped as recorded
error rows). Four injection cases with payloads in untrusted channels
pushing against the true label, four metamorphic variants, one coverage
case closing the two policy clauses my own coverage check had flagged as
untested. A cross-family rubric judge filling the judgments table that
had sat empty since it was designed. A logistic-regression baseline on
hand-extracted features. A DSPy comparison arm. Dataset fetch scripts
with verified provenance. One gated prompt iteration (v5).

### What the round caught, in the order it hurt

1. Every claude CLI call was dying with rc=0 and an is_error envelope:
   the CLI had started inheriting ~450k tokens of connector tool
   definitions, so every request exceeded the context limit before the
   case JSON even mattered. Found by reading the recorded error body of
   a failed judge call; fixed by isolating the eval subprocess from the
   account's connector surface. The boundary rule (record every failure,
   never swallow) is the only reason the cause was on disk to read.
2. My robustness headline died under repetition. Single runs said the
   hardened prompt resists the planted-note injection and the naive one
   does not. N=5 per rung says resistance on that case is a coin flip at
   EVERY rung (2/5, 1/5, 3/5). The clean story was sampling luck, and
   the repeat protocol is the only reason I know.
3. The v5 gate fired both ways before settling. Target chosen from the
   ledger (flash reads CASE-104's post-ownership-change extraction as a
   bust-out; the policy distinction is that a bust-out needs the rapid
   build-up half, and 104's balance predates the change). Single-run
   readout: the edit fixed 104 but regressed an injection case, so the
   pre-registered gate said revert. Repeats to N=5 on both sides showed
   the "regression" was the same coin flip as finding 2, while the 104
   fix held 4 of 4. Accepted. An accuracy-only gate would have shipped
   blind; a single-run robustness gate would have rejected wrong.
4. One of my two judges is a dead instrument. gemini-flash as judge
   awards top marks to essentially everything, including all 12 runs in
   the deliberately dual-judged overlap cell, where claude-haiku
   disagrees with it on 34 of 36 axis scores. And by the judge that does
   discriminate, my prompt ladder barely moves judged reasoning quality
   at all: the rungs improved contract adherence and specific decisions,
   not rubric scores.
5. A first-run accuracy was sitting on a coin flip: a smoke run's
   correct answer buried a full-run miss as a "repeat", leaving a 12/12
   cell whose flip rate was 0.50. The trust gate now flags any cell
   whose repeats disagree above 0.25.
6. The run ledger was never actually in git: a generic ignore pattern
   had kept it out, so the README's "checked in" claim was false and a
   fresh clone's quickstart failed. Found at freeze, fixed with an
   explicit negation.

### What v5 looks like across models

flash: 12/12, the ladder's first perfect decision-suite pass, expected
loss $0/1k on a trustworthy cell. nemotron: 10 of 10 parseable decisions
correct including the target case, two recurring JSON contract breaks.
qwen: 11/12, its one miss a single-run flip on the inverted perturbation
in exactly the direction the new bullet pushes; by the same repeat
standard that saved v5 from a false rejection, that flip is unproven at
n=1 and ships as v5's named open question.

### Still cut, named

The synthetic factory, the docker build proof (blocked on a one-line
host permission only the account owner can run), and the live run-case
demo button.
