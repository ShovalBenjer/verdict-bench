# ADR-0004: stdlib-only engine core, analysis extras kept separate

Status: accepted, 2026-08-23 (written retroactively; the code choice
predates this file, per STATUS.md's named gap).

## Context

`pyproject.toml` declares `dependencies = []` for the core engine
(`engine/runner.py`, `providers.py`, `oec.py`, `export.py`): only
`urllib`, `sqlite3`, `json`, `hashlib`, `argparse` from the standard
library. `polars`, `matplotlib`, and `jupyter` are pushed into an
`[project.optional-dependencies] analysis` extra instead of the base
install.

`repo-stack-reasoning.md`'s 2026-08-13 correction is explicit: stdlib is
one candidate among several, never the default, and a session that
silently defaults to it repeats a named drift. This ADR exists to show
the comparison that correction requires, not to assert stdlib as
self-evidently right.

## Decision

Keep the engine core stdlib-only. Keep `polars`/`matplotlib`/`jupyter`
as an opt-in extra for the notebook and static chart export only.

## Comparison actually made

Modern candidates considered, per the correction's requirement that at
least two real alternatives get checked before defaulting:

- **httpx + pydantic** for the provider layer (typed HTTP, validated
  response models instead of hand-checked dicts). Would clean up
  `providers.py`'s manual JSON parsing. Rejected for THIS repo's
  lifespan: a 2-week take-home lab that a reviewer clones once and never
  maintains does not amortize the dependency-pinning and version-drift
  cost; `urllib.request` plus the existing `parse_contract()` strict/
  fallback logic already does the one thing needed (call an HTTP
  endpoint, parse JSON, handle a malformed response as data not an
  exception).
- **DuckDB with its Python client** instead of raw `sqlite3` for the
  ledger. Already compared and rejected in ADR-0001 on different
  grounds (OLAP scale not reached); restated here because it would also
  have added a dependency the stdlib choice avoids.

## Consequences

Won on:
- Zero install friction: `git clone && python3 engine/runner.py --report`
  works with no `pip install` step, which matters for a submission a
  reviewer opens once, not a service anyone runs long-term.
- No version drift risk over the 2-week window this repo is actively
  worked in; a pinned `httpx`/`pydantic` version has a real (if small)
  chance of a breaking release landing mid-project.
- The provider abstraction is already covered by ADR-0002's reasoning
  (owning the request path is the point, not a workaround); a typed
  HTTP client would not remove that ownership, only restyle it.

Lost, accepted as a real cost:
- `providers.py`'s manual JSON extraction (`re.search(r"\{.*\}", ...)`
  plus `json.loads`) is less robust than a schema-validating library
  would be against a genuinely adversarial malformed response. Mitigated
  by `contract_ok` being tracked as its own metric specifically because
  this parsing is fragile by design and the fragility itself is data
  worth reporting, not hiding behind a library that silently coerces.
- Analysis extras (`polars`, `matplotlib`, `jupyter`) DO pull real
  dependencies; the "stdlib-only" claim is scoped to the engine core
  that runs the benchmark, not the analyst surface that reads its
  output, and this file says so rather than letting the pyproject.toml
  comment imply a broader claim than the repo actually keeps.
