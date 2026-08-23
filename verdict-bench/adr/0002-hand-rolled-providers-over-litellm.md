# ADR-0002: Hand-rolled provider clients, over LiteLLM or promptfoo

Status: accepted, 2026-08-17.

## Context

The benchmark needs to call multiple model providers (Claude via CLI,
Gemini, NVIDIA-hosted Llama) with a uniform typed return shape. LiteLLM
and promptfoo both exist as off-the-shelf abstraction layers over exactly
this problem, and promptfoo is a direct prior-art competitor to this
whole repo (named in `docs/prd/SPEC.md`).

## Decision

Hand-rolled clients in `engine/providers.py`: one function per provider
(`call_claude_cli`, plus openai-compat and Gemini HTTP calls), all
returning the same typed `DecisionResult` dataclass, with a shared
`parse_contract()` for the strict-then-fallback JSON parsing.

## Consequences

Won on:
- 3 providers with really 2 distinct API shapes (openai-compat, Gemini's
  own schema) is under the threshold where an abstraction layer earns
  its complexity cost. `repo-stack-reasoning.md`'s standing test applies:
  stdlib/hand-rolled has to WIN the comparison, not be defaulted to, and
  here it wins on a specific, checkable reason: a dependency that owns
  the request path would also own the retry, timeout, and error-parsing
  behavior, and those behaviors are literally what this benchmark
  measures (contract adherence, latency, retry-once-on-flake). Owning
  the client means owning the metric's own definition.
- Every provider failure mode (a claude CLI `rc=1` flake, a Gemini
  timeout, a malformed-JSON response) is caught and recorded as a typed
  `DecisionResult(error=...)` row, never swallowed, matching
  `boundary-contracts.md`'s no-raw-passthrough rule.

Lost to the alternative, accepted as a real cost:
- LiteLLM would have handled provider-specific quirks (rate limits,
  streaming, auth) that are currently hand-maintained per provider. The
  claude CLI route in particular carries a real, disclosed cost: ~10-40s
  p95 startup latency that pollutes the latency metric for Claude
  columns, recorded as a known measurement caveat in ARCHITECTURE.md
  rather than engineered around before the deadline.
- promptfoo is the production-grade version of this whole idea and is
  named explicitly as prior art this repo does not attempt to replace;
  this repo is the analyst layer over exactly one decision task that
  promptfoo does not provide out of the box (the policy-clause coverage
  check, the disqualifying-clause gate, the dollar-denominated OEC), not
  a general eval platform.
