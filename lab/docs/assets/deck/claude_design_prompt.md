# claude-design prompt pack: verdict-bench deck

GENERATED 2026-08-24: the styled deck now lives at
the operator's Claude Design canvas (private) and is the
presentation deck of record. The python-pptx twin in this directory and the
HTML artifact stay as fallbacks; number verification against the ledger was
done on this pack's text, not on the generated deck itself.

Paste the prompt below into claude-design, then attach the 15 PNGs listed at the
end from `docs/assets/deck/`. The pptx twin in this directory is the fallback,
not the target; this pack is how the styled deck gets made. Every number in the
slide content came from `key_numbers.json` and the ledger and was verified
2026-08-24; do not let the design tool restate or round them.

---

## The prompt

Build a 23-slide 16:9 presentation deck named "verdict-bench" for a 45-minute
technical panel (3 panelists, engineering audience, projected in a room).

Design direction, fixed, not a suggestion:

- Palette: ink #08090c background, off-white text, indigo #828fff as the single
  accent, gold #cfa36c reserved for verdicts and money. No gradients, no purple
  washes, no third accent.
- Type: one geometric sans for display (not Inter, not Space Grotesk), tabular
  numerals wherever digits align. Big numbers get display size; their units and
  denominators stay small beside them.
- Charts arrive as attached PNGs on dark ground, one per slide, never two side
  by side. Captions are one sentence under the chart.
- Three slides are FLOW DIAGRAMS, not charts: draw them as rounded boxes joined
  by arrows in the accent color, dark panel fills, two-line labels (bold title,
  muted sub-line). Keep every diagram to at most seven boxes.
- No emoji, no em dashes, no icon grids, no rule-of-three bullet walls. Slides
  carry at most one idea. Slide numbers small in a corner. The Intuit wordmark
  appears once, on the cover, beside the verdict-bench name.

Slide content, verbatim where quoted:

1. COVER: "verdict-bench", sub-line "account-review decisioning prompt, the
   Intuit case study", byline "Shoval Benjer, August 2026". Wordmarks only,
   no body text.
2. "I run AI the way this benchmark runs prompts". Presenter, modest and
   short: Shoval Benjer, B.Sc. Data Science (Afeka, 2022-2025). Before this: seven months at an online-trading company in Herzliya, owning the quality, accuracy, and reliability of AI agents on three production surfaces (a chatbot, voice agents, and social content). Built a sales-training platform on voice agents and a four-language transcription-and-analysis pipeline for sales and retention calls; implemented a hybrid test pyramid and quality gates, evals beside deterministic checks, that raised agent quality on the company's internal benchmarks and block regressions before they reach a customer; and a real-time productivity dashboard (SQL, Next.js) over the CRM with query optimization and cache layers.
   DIAGRAM, the operating loop: operator -> rules + claim controls ->
   agents run -> evidence ledger -> gates decide -> back to operator.
   Caption: verdict-bench is the same loop pointed at one prompt.
3. "What the ledger showed": three findings, one line each. (a) The gate
   rejected my best fix: v6 resisted 19 of 20 planted-instruction attacks,
   then missed its pre-registered 12-of-12 decision bar; it stays rejected.
   (b) On 64 unseen generated cases the same prompt scores 100% on two models
   and 58% on the weakest. (c) Contested cases are routed to a human with the
   cross-model split attached, never scored.
4. "Accuracy is the wrong headline". Wrong decisions cost different dollars,
   so the headline metric is expected loss per 1,000 cases under a named cost
   matrix. Chart: funnel.png.
5. "The two-hour version exists inside this one". The minimal deliverable is
   intact and separable; the lab is the evidence behind it.
6. "Planned Sunday evening, re-planned at 00:15". The build story: the
   Sunday plan (engine + ladder + matrix standing that night, 115 runs), the
   cut list rejected at 00:15 on submission day, the 00:15-03:00 window that
   produced the qwen/nemotron columns, both robustness suites, the judge,
   the LR baseline, the DSPy arm, and v5 itself; glm-5.3 wired then
   money-blocked, shipped as recorded error rows.
7. "The work the deck does not show". Seven one-liners: LR baseline
   (LOO 8/12 vs LLM 11-12/12, all four misses expensive-direction), DSPy arm
   (12/12 ceiling, different artifact), self-consistency (11/12 unanimous at
   N=5), SPRT (p0=0.75, p1=0.92, a=0.05, b=0.10), beta-binomial ~3:1 odds,
   data provenance (PaySim/ULB verified, IEEE-CIS honestly unverifiable),
   Tauri shell + adjudication queue + number-grounding audit (81-98%).
8. "Six commitments, fixed before any analysis". The pre-registered gates:
   n >= 8, contract >= 0.5, Wilson CI width <= 0.5, max flip 0.25,
   zero-tolerance tripwire, suite separation. The tripwire disqualified 10 of
   38 cells.
9. "Expected loss, the actual model". The 3x3 cost matrix as a table ($0
   diagonal; false approve $2,000 in gold; false reject $600; false hold $45;
   caught-fraud containment $500, derived). Beside it, the notation:
   EL_1k = (1000/N) SUM_i (1/R) SUM_r C(y_i, yhat_ir); unparseable charged
   worst-case; case-clustered bootstrap B=1,000 seed 1789; Wilson 95% width
   <= 0.5 rankability; EL(pi) prevalence sweep 0.5-5%; queue cost = 1000 x
   p_HOLD x $35.
10. "One pipeline, every claim traceable to a run". DIAGRAM: 89 labeled
    cases + prompt ladder -> runner (7 providers, N=5 repeats) -> sqlite
    ledger -> trust gates -> export -> surfaces. Caption: every surface
    reads one differential-tested export.
11. "89 labeled cases, five suites, tiers kept apart". Chart: eda_corpus.png.
12. "Repeats dissolve stories". Chart: injection_repeats.png.
13. "The gate bites, and ranking survives". Chart: bootstrap_loss.png.
14. "Stated confidence is decorative; earned confidence is measured". Chart:
    reliability.png (claim pile-up + claimed-vs-earned; at stated 0.90 the
    model was right once in two).
15. "Triangulated across three families". gemini-flash saturated and
    excluded; claude-haiku and phi-4 discriminate; both discriminating
    families score proportionality lowest. Chart: judge_triangulation.png
    (three judges by three rubric axes, ceiling line drawn).
16. "64 generated cases found a policy ambiguity". Chart: synthetic_sweep.png.
17. "Is v5 overfit to nine cases? Three tests, one open risk". Transfer
    (tuned on flash only; 12/12 sonnet, 12/12 haiku, 11/12 gemini-pro),
    post-freeze generated data (56/56 flash, 48/48 qwen), weak columns fail
    for capacity (llama 8/12 on v1 before tuning, 9/12 at v5 with contract
    1.00), the v6 rejection as the discipline check, and the open risk: true
    holdout n=3 (v5 2/3), which is why gates carry the claim.
18. "A contested case is routed, not resolved". DIAGRAM: archetype -> seven
    models split 20 HOLD / 8 REJECT -> policy underdetermines -> no score ->
    policy owner gets the split. Caption: sanctions-partial fails closed,
    zero APPROVEs in 23 runs.
19. "A million-case simulation on measured kernels". Chart: population_sim.png.
20. "The gate does not bend on deadline day". The v6 story. Chart:
    holdout_funnel.png.
21. "Ship v5 + gemini-flash, and say what that means". CERTIFIED / SUGGESTED /
    DECORATIVE tiers. Chart: holdout.png.
22. "Out of scope, and what I'd do next given time". Two columns.
    Deliberately out of scope, each with its one-line why: tools and skills
    (no function calling or retrieval; tools change the eval surface, so
    they get their own arm), MCP integrations (frozen case file keeps runs
    reproducible), CLI vs API surfaces (claude columns ride the
    subscription CLI, no sampler control, stated; API rerun specced,
    blocked on a key), memory attached to models (stateless by design;
    repeats are the method and memory breaks repeats), fine-tuning (the
    prompt is the only movable part). Next given time, ranked: more expert
    labels (SPRT says how many), the v6 injection line, the claude API
    rerun with temperature control, the adjudication queue wired to a real
    reviewer, a tool-augmented variant as a new arm.
23. "What breaks, in order". Five production risks ranked. Close: the
    benchmark's job is to say when not to trust a good-looking answer.

## Attachments (from docs/assets/deck/)

bootstrap_loss.png, clause_citation.png, eda_corpus.png, eda_errorband.png,
eda_fingerprints.png, eda_landscape.png, eda_runs.png, eda_temperament.png,
funnel.png, holdout.png, holdout_funnel.png, injection_repeats.png,
judge_triangulation.png, population_sim.png, reliability.png,
synthetic_sweep.png. The Intuit wordmark is docs/assets/deck/intuit-mark.png.
