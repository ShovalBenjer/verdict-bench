# Submission bundle: AI workflow case study

95 files including this index. Suggested reading order, with
honest time estimates:

1. `WRITEUP.md`, the required short writeup (about 5 minutes).
2. `prompts/`, the prompt ablation ladder v1..v4c with `CHANGELOG.md`, one
   change per version. `early-prompts/` holds the two pre-repo drafts the
   transcript's first sections walk through.
3. `TRANSCRIPT.md`, the curated work log (about 15 minutes).
4. `sessions/`, the verbatim session extract behind it (9256 words, about
   37 minutes). Operator messages are word-for-word;
   removed segments are counted markers, shortened assistant turns are marked.
   Nothing was reworded.
5. `verdict-bench/`, the eval lab built behind the deliverables: engine,
   tests (`make check`), docs, ADRs (each with the rejected alternative),
   `benchmark.json` (the benchmark matrix the numbers in the writeup come
   from), and `data/labels.json` with its label-tier disclosure.

Punctuation note: `prompts/`, `early-prompts/`, `case-study/` (your input)
and `verification/` are frozen artifacts shipped byte-identical; the session
extract is verbatim conversation. Prose style rules were applied only to the
authored documents.

Path mapping: the docs were written repo-relative. `docs/prd/SPEC.md` is
`verdict-bench/SPEC.md` here; `docs/WRITEUP.md` is `WRITEUP.md` at the
bundle root; `ui/public/benchmark.json` is `verdict-bench/benchmark.json`;
`engine/prompts/` is also mirrored at `prompts/` at the root.

benchmark.json note: each cell's `accuracy` and `contract` are computed
over the FIRST run per case; repeat rows in `cases` feed only the `flip`
(repeat-run stability) metric. `kind` is the suite tag; `label_source`
is the label tier (expert / adjudicated / construction), per SPEC.md's
"Label tiers" section.

Not included, deliberately: `state/verdict.sqlite3` (raw run ledger,
available on request; `benchmark.json` is generated from it), the
`Dockerfile` and `ui/`/`notebooks/` build surfaces (repo components, see
`verdict-bench/README.md`), `docs/power_curve.png` (regenerable), and the
internal planning docs (`docs/PLAN.md`, `docs/PRODUCT.md`, the deck's
working notes; the deck itself is presented live). Removal markers in the
session extract refer to an exclusion log that is reviewed by the author
and not part of this bundle.
