# Data source provenance

Per-source record for the three external datasets named in
`docs/prd/SPEC.md`, section "Data sources". Each entry states the canonical
URL, the license as verified on the source page, what this project uses the
source to inform, and the no-raw-rows rule that applies to all three.

Verification method: the dataset pages were fetched directly
(`curl -L`) on 2026-08-24 and the embedded schema.org `CreativeWork` JSON-LD
metadata that Kaggle itself renders into the page was read for the license
field. Where that metadata was not present (the IEEE-CIS competition page),
no license is stated here; the entry instead points to where to check,
per this project's rule to never invent a license.

## IEEE-CIS Fraud Detection

- Canonical URL: https://www.kaggle.com/c/ieee-fraud-detection
- License: check at https://www.kaggle.com/c/ieee-fraud-detection/rules.
  This is a Kaggle COMPETITION, not a plain dataset: competitions are
  governed by rules an account must explicitly accept, not by a fixed
  CC/ODbL license tag. Both the competition page and its `/rules` subpage
  were fetched on 2026-08-24 and both returned the same 5550-byte
  client-rendered shell (no server-side rules text, no schema.org license
  metadata), so the actual rules text was never retrieved and no license
  string is verified here. The rules must be read and accepted directly
  on the page above before download.
- Distribution this informs: amount, decline, and chargeback shapes for the
  synthetic case factory (real e-commerce transaction fraud, the richest
  open analogue to merchant risk available for this project).
- Fetch script: `tools/fetch_data/fetch_ieee_cis.py`.

## PaySim

- Canonical URL: https://www.kaggle.com/datasets/ealaxi/paysim1
- License: CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/).
  Verified 2026-08-24 from the dataset page's embedded schema.org
  `CreativeWork` JSON-LD: `"license":{"@type":"CreativeWork","name":"CC
  BY-SA 4.0","url":"https://creativecommons.org/licenses/by-sa/4.0/"}`.
- Distribution this informs: transfer-out, bust-out-like patterns
  (TRANSFER / CASH_OUT sequences in synthetic mobile money flows) for the
  synthetic case factory.
- Fetch script: `tools/fetch_data/fetch_paysim.py`.

## ULB Credit Card Fraud

- Canonical URL: https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
- License: Kaggle's page metadata names it verbatim as "Database: Open
  Database, Contents: Database Contents", url
  http://opendatacommons.org/licenses/dbcl/1.0/. Verified 2026-08-24 from
  the dataset page's embedded schema.org `CreativeWork` JSON-LD:
  `"license":{"@type":"CreativeWork","name":"Database: Open Database,
  Contents: Database Contents","url":"http://opendatacommons.org/licenses/dbcl/1.0/"}`.
  The URL itself was independently fetched the same day and
  resolves to "Database Contents License (DbCL) v1.0" on Open Data
  Commons; Kaggle's compound label names a database-rights half ("Open
  Database") without giving it a separate URL, so this note states both
  the verbatim Kaggle label and the one URL's independently confirmed
  target rather than inventing a name for the unlinked half.
- Distribution this informs: the class-imbalance framing used in this
  project's writeup (fraud is roughly 0.17% of transactions in this
  dataset), i.e. why accuracy is the wrong headline metric for a rare-event
  decision task.
- Fetch script: `tools/fetch_data/fetch_ulb_ccf.py`.

## No raw rows ship or reach a model

None of these three datasets ship in this repository, in any form, at any
commit. Each fetch script downloads (or prints instructions to download)
into `data/raw/<source>/`, which is gitignored territory (`data/raw/` is in
`.gitignore`). No row from any of these sources is ever passed to an LLM
provider in this project: only aggregate, locally-derived distribution
shapes (amount/decline/chargeback shapes, transfer-out pattern shapes, and
the class-imbalance ratio) inform the parametric synthetic case factory
described in `docs/prd/SPEC.md`. The factory itself generates cases from a
seeded grid; it does not replay or resample source rows.
