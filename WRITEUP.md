# Writeup: account-review decisioning prompt

PRD: docs/prd/SPEC.md. Status: active. Companion: TRANSCRIPT.md at the
submission bundle root (the required complete transcript), and
engine/prompts/CHANGELOG.md (the ablation ladder this writeup
summarizes).

## The prompt

`engine/prompts/v5.md`, current best-tested version. Seven prior rungs
(v1 through v4c) are kept in the same directory, unmodified, each pinned
to the runs it produced by a sha in the run ledger. v5 is the one rung I
did not author directly from intuition: it is v4c plus a single
look-alike bullet proposed from a measured miss and accepted through a
pre-registered gate, with the full protocol (including the repeats that
refuted a false single-run regression) in
`engine/prompts/CHANGELOG.md`'s gate record.

The decision logic reads in a fixed priority order and stops at the
first step that fires, the way a SQL CASE statement evaluates: Step 1
looks for a corroborated problem (a genuine sanctions match, a confirmed
prior determination against the same party, card testing, a bust-out, a
real link to known fraud), and names the look-alikes that must NOT
trigger it; Step 2 holds only when a genuine doubt remains AND money is
exposed; Step 3 is default approve. The 4 expert labels each exercise a
different part of that order, which is some of why I trust it: CASE-106
dies at Step 1 on the confirmed prior, CASE-102 dies at Step 1 on the
card-testing pattern, CASE-101 is Step 1's own named look-alike (a
name-only watchlist hit with mismatched attributes and independently
verified identity) passing through to approval, and CASE-108 is the
Step 3 default, high volume explained by its own settled history.

## What I actually know, versus what I built to check it

Two different evidence bases sit in this repo, and this writeup keeps
them separate on purpose, because conflating them is exactly the
"polished submission, thin reasoning" failure the assignment warns
against.

**Ground truth from Intuit**: `labeled-answers.md` gives the expert
decision for 4 cases: CASE-101 (APPROVE), CASE-102 (REJECT), CASE-106
(REJECT), CASE-108 (APPROVE). This is the only ground truth I did not
construct myself.

**Labels I constructed**: the other 5 base cases (103, 104, 105, 107,
113) and every perturbation have a label I wrote myself, reasoning
directly from POLICY.md's text, and recorded the reasoning at the time
(TRANSCRIPT.md). These are useful for stress-testing the prompt against
policy clauses the 4 real cases don't touch, but they are not expert
ground truth, and I don't present them as such.

## Finding on the 4 real cases: they don't discriminate between versions

Checked (2026-08-23, re-checked 2026-08-24 after the freeze-day runs,
against the real run ledger): on the 4 Intuit-labeled cases, gemini-flash
decides all 4 correctly at every prompt version run against the full
suite, including v1, the naive baseline with NO policy text at all, and
including the full v4c and v5 passes run on 2026-08-24. The real misses
on real labels are claude-haiku and llama-3.3-70b on CASE-102
(card-testing) at v4, both HOLD instead of REJECT, joined on 2026-08-24
by nemotron-super-49b making the same CASE-102 miss at v4b: three
different models, one shared failure on the same expert-labeled case.

This matters for how I read my own results: I cannot claim the ablation
ladder (v1 to v4c) improved accuracy on the 4 real cases, because there
was no room to improve, one strong model got them all right from the
naive baseline. What the ladder actually demonstrates, and what I can
defend:

1. **Output-contract reliability**, not decision accuracy. v1 through v3
   have models wrapping their JSON in markdown fences some or all of the
   time (a real contract violation even when the decision inside is
   right); v3c's strict-contract rung and v4/v4b hold contract rate at
   100% for gemini-flash. This is the actual, measured effect of the
   changes I made, distinct from decision quality.
2. **A capability gap the 4 real cases DO surface**: claude-haiku and
   llama-3.3-70b both miss CASE-102 at v4. I built a targeted fix (v4c:
   one explicit "count distinct instruments before deciding" scaffold)
   and tested it against both models plus a control. Result: it fixed
   haiku (0/1 -> correct on retry, though its contract adherence stayed
   unstable), it did NOT fix llama (still wrong). I'm reporting this as
   a genuine mixed result, not smoothing it into "the fix worked."
3. **A stable disagreement on a case I constructed** (CASE-104, ownership
   change + KYB pending): at v4, gemini-flash says REJECT in all six
   repeat runs (and in its single v3c and v4b runs); every other model
   at v4 says HOLD. Scope matters here: at v1 through v3, one run each,
   flash itself said HOLD, so the disagreement is a property of the
   prompt-model pair, not of the model alone. I did not resolve this by picking a
   side. I read it as the correct behavior of the process: a stable
   cross-model disagreement is a signal to route the case to a human
   reviewer for a label decision, not a bug in one model's reasoning.
   This is a labeling-workflow claim, not a policy claim, and I'm naming
   it as such.

## Choices made, and why

- **Procedure over verbatim policy** (v2 -> v3): pasting POLICY.md
  verbatim into the prompt (v2) versus rewriting it as an ordered
  decision procedure with explicit weighing principles (v3). v3 is the
  version I kept building on, because a procedure gives the model a
  checkable sequence (look for a corroborated problem, then an
  unresolved question, then default to approve) instead of a wall of
  prose to re-derive structure from on every case.
- **One change per rung**: after finding I'd conflated two changes in an
  early v4 draft (contract hardening + the sanctions rule, both at once,
  making it impossible to attribute a metric delta to either one), I
  split it into v3c (contract only) then v4 (v3c + the sanctions rule)
  and kept that discipline for every rung after. `engine/prompts/CHANGELOG.md`
  is the ledger; it also keeps this correction on the record rather than
  quietly rewriting history.
- **A card-testing counting scaffold, added and tested, not assumed to
  work**: when haiku and llama both missed CASE-102, I did not simply add
  "count the distinct instruments" and declare it fixed. I ran it against
  both models plus gemini-flash as a control, and reported the honest
  mixed result (fixes haiku, doesn't fix llama) rather than a single
  clean story.
- **Sanctions/confirmed-history are treated as a hard gate, not a
  point deduction**, in how I score my own work (not in the prompt
  itself, which already encodes POLICY.md's "zero tolerance" language
  directly). Checked every run against the 3 cases tagged to those two
  clauses (CASE-101, CASE-101-P1B, CASE-106) across every prompt version
  and every model: every PARSEABLE decision is correct, zero exceptions.
  Two llama-3.3-70b runs on v4 had no recoverable decision on the first
  attempt (a JSON contract failure, not a wrong decision) and both
  recovered to the correct decision on retry. I'd still call this strong
  evidence, but I'm stating the contract-failure caveat rather than
  rounding it to a clean "100% every time."

## How I'd convince myself the prompt is ready before shipping it

Honestly, and in order of how much I actually trust each check:

1. **It is not ready on sample size alone.** The 4 real-labeled cases are
   too few to certify a prompt for production; a Wilson confidence
   interval on 4/4 is [0.51, 1.00], wide enough that "100% on the real
   cases" is compatible with a true accuracy anywhere from 51% up. I
   would not ship on this evidence without more labeled cases from
   Intuit, full stop.
2. **The output contract is verified mechanically**, not by eyeballing
   samples: a strict parser checks every run starts with `{` and ends
   with `}` and parses as the exact schema, and I track the parseable
   rate as its own metric, separate from decision correctness, because a
   model that decides correctly but wraps the answer in prose or
   markdown still fails a downstream system expecting raw JSON.
3. **I would NOT ship on a single model's results.** The same prompt
   produces different contract-adherence and, on constructed cases,
   different decisions depending on the model behind it (claude via CLI
   wraps output in markdown fences by default; gemini-flash does not).
   Before shipping, I'd pin the exact model + prompt pair, not just the
   prompt, since the prompt alone doesn't fully determine behavior.
4. **I would re-run the sanctions/confirmed-history cases specifically**
   as a release gate, separate from a general accuracy number, because
   POLICY.md itself states zero tolerance there and a single miss on
   those clauses is disqualifying regardless of how the rest of the
   suite scores.
5. **I would not trust an accuracy number without also checking which
   policy clauses the test cases actually exercise.** I built a
   coverage check against POLICY.md's own sections and found two clauses
   (an account holder's own account of events is not evidence on its
   own; a flag with nothing substantiating it is a data-quality question,
   not a confirmed problem) have zero test cases in my suite. I would not
   claim the prompt is validated against clauses I never tested it
   against, and I'm naming that gap here rather than leaving it implicit.
6. **Repeat-run stability is the monitoring baseline.** The harness
   already measures a flip rate (same prompt, same model, same case,
   repeated runs), which is an A/A test: it bounds how much disagreement
   the pipeline produces when nothing has changed. In production I'd run
   the live comparison as a sequential test (SPRT) on shadow traffic
   against the expert-agreement rate, so a real regression trips an
   alarm as it develops instead of surfacing in the next batch review.

## The freeze-day round (2026-08-24): the cut list, un-cut and run

Everything in this section happened in the final hours before submission,
after I decided the items I had scoped and cut should be executed rather
than narrated. Each one reports what it actually measured, including the
two results that came back and contradicted my own earlier single-run
claims.

**Model roster.** Two current-generation columns were added. qwen3.8-max:
11/12 on the decision suite at 100% contract adherence, the only model
that resisted all four injection cases and held all four metamorphic
variants, at the price of 30 to 120 seconds per decision. nemotron-super-49b:
10/11 plus one JSON contract failure, and it misses CASE-102 the same way
claude-haiku and llama-3.3-70b do. A GLM column was wired and is
money-blocked on both available routes (Z.AI error 1113, insufficient
balance; DashScope free tier exhausted); it ships as recorded error rows
rather than a silently absent column, because recharging is an account
decision, not an engineering one.

**Robustness suites, and the claim they killed.** Four injection cases
(adversarial instructions planted in fields the model must read as data:
an owner note claiming compliance pre-clearance, a fake overturned-appeal
story, an uploaded-document OCR string shouting CONFIRMED_FRAUD, and one
deliberately pushing toward over-rejection, because injection defense is
not only about blocking approvals) and four metamorphic variants
(ids, dates, geography renamed; the decision must not move). These score
in their own columns and never blend into accuracy or expected loss.
The single-run readout looked like a clean story: the naive v1 prompt
falls for the planted note on CASE-102 while v4b resists everything.
Repeating the hardest injection to N=5 per rung dissolved that story:
v4b resists 2 of 5, v4c 1 of 5, v5 3 of 5. No rung of the ladder
reliably resists that injection; what looked like hardening was sampling
luck, and the repeat protocol is what caught it. The literature frames
this exact failure mode (InjecAgent, ACL Findings 2024; BIPIA, arXiv
2312.14197: the confusion of informational context with actionable
instruction), and my result says prompt hardening alone did not buy me
out of it. One measurement confound is also on the record: flash "fails"
the CASE-104 injection variant only because it already misses base
CASE-104 at v4-family rungs, so for that case accuracy-under-injection
and injection-caused-flips are different numbers, and I report the flip
count.

**Coverage closed.** The coverage check had flagged two policy clauses
with zero test cases (an account holder's own account of events is not
evidence; an unsubstantiated flag is a data-quality question). Both now
have cases: the CASE-106 injection variant doubles as the evidence
clause's test (the owner claims the prior determination was overturned;
the record says otherwise), and CASE-115 is a clean data-quality case (a
legacy flag with no reference id against a long clean record). 8 of 8
clauses now carry at least one case, and the closing case runs correctly
on every model tested.

**Rubric judge, and the instrument it broke.** The judgments table
(empty since it was designed) now holds 118 rubric judgments: three axes
(fidelity, evidence grounding, proportionality reasoning), scored 1 to
5, cross-family so no judge grades its own family (self-preference bias
is measured, not folklore: arXiv 2410.21819), and the judge never sees
the expected label, because a judge handed the answer would halo correct
decisions into high scores. Two findings. First, one of my two judges is
a dead instrument: gemini-flash as judge awards 5/5/5 to essentially
every run it grades, including all 12 in the deliberately dual-judged
overlap cell, while claude-haiku spreads scores from 2 to 5 and
disagrees with flash's ceiling on 34 of 36 axis readings in that same
cell. Inter-judge agreement this poor means a rubric score is
judge-relative here, and I report the discriminating judge's numbers
only. Second, by that discriminating judge, my prompt ladder barely
moves reasoning craft: v3, v4 and v4b all sit near 3.9 fidelity / 4.0
evidence / 3.2 proportionality for the same model. The ladder measurably
improved contract adherence and specific decisions; it did not
measurably improve how well the reasoning reads against the rubric, and
I would rather report that than pretend the rubric column crowns the
ladder. One judgment of 119 attempts failed to parse and is recorded as
a judge contract failure.

**v5 across models.** The gated edit was accepted on flash evidence
(the full record is in the CHANGELOG): 12/12 with the CASE-104 fix
stable at 4 of 4 decided repeats. Cross-model checks after acceptance:
nemotron-super-49b decides 10 of 10 parseable cases correctly at v5
including CASE-104, with its two recurring JSON contract failures;
qwen3.8-max scores 11/12 at v5, its one miss a single-run flip on
CASE-104-P2 (the inverted perturbation whose right answer is APPROVE)
in exactly the direction the new bullet pushes. At n=1 that flip is
unproven by the same repeat standard that saved v5 from a false
rejection, so it ships as v5's named open question, not smoothed over.
The recommended pair stays gemini-flash + v5; on qwen, v4b remains its
best-evidenced cell.

**LR baseline.** Logistic regression on 10 hand-extracted mechanical
features, leave-one-out over the 12 decision-suite cases: 8/12, against
11 to 12 of 12 for the LLM cells. Its four misses are exactly the
policy-reasoning cases (both zero-tolerance gates, the bust-out, the
proportionality flip), all missed in the expensive direction. On this
suite, that is where the LLM earns its cost. The caveat file names the
leakage: the feature author also wrote 8 of the 12 labels, so the
expert-4 subset (3/4) is the only leakage-free read.

**DSPy arm.** Given the policy text alone, both unoptimized and
BootstrapFewShot-compiled DSPy hit the suite's ceiling (12/12 on
gemini-flash), matching the hand ladder's v2 rung, which gives the model
the same raw material. The structural contrast is the finding: DSPy's
compiled prompt carries four full worked cases (34 KB rendered per call)
and leans on induction; the hand ladder teaches a 7 KB procedure once.
At n=12 the suite cannot separate them, and
`experiments/dspy_arm/RESULTS.md` carries that ceiling-effect caveat and
the leakage risks in full.

**Cost grounding.** The expected-loss framing follows the cost-sensitive
fraud-evaluation literature: with fraud prevalence under 1%, plain
accuracy is the wrong headline (a trivial always-approve classifier
scores 99.8% on the standard European card dataset), and the correction
is an explicit cost matrix matched to the deployment's error asymmetry,
not a blanket metric swap (a 2024 NeurIPS review shows the popular
"always prefer AUPRC under imbalance" rule is itself an overgeneralization).
Baesens, Van Vlasselaer and Verbeke's Fraud Analytics (Wiley, 2015) is
the standing reference for the descriptive-to-predictive pipeline this
mirrors; cited as metadata, not extracted.

## What I built beyond the prompt, and why it's not the main deliverable

I built a small local benchmark harness (SQLite run ledger, a report
command, a coverage check, a UI) to run the ablation ladder above
systematically instead of by hand, and to catch mistakes in my own
reasoning before they became silent claims. Three concrete catches from
that process, added to the required transcript (sections 18-20) after
being caught here first:

- A fabricated response to a self-test (invented case content, invented
  code, invented numbers) that I rejected outright and re-ran for real
  rather than partially crediting.
- A duplicate-row bug in my own run ledger that silently miscounted
  accuracy on two cases; found, root-caused, and fixed with an integrity
  constraint rather than a one-off patch.
- Three different cost-model implementations that had drifted out of
  agreement with each other inside the same repo (a scratch calculation,
  the UI's export script, and a notebook cell); found by re-reading my
  own work rather than assuming it was consistent, reconciled to one,
  and locked with a test that fails if they ever disagree again.

This tooling is evidence of process, offered as supporting material, not
as the deliverable. The prompt, this writeup, and the transcript are the
actual ask.
