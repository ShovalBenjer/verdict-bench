# ADR-0003: Tauri desktop shell, over a web-only UI

Status: accepted, 2026-08-17. Design directions considered per the
out-of-distribution rule before this was locked (dark-ops/terminal-
adjacent register, not the default LLM-dashboard look).

## Context

The benchmark matrix, power curve, and case-compare screens need to be
presented live during the interview. Options: a web app served over
localhost (or deployed), or a native desktop shell.

## Decision

Tauri, launched as a debug binary under WSLg for the presentation. Both
the Tauri shell and a plain browser tab read the SAME built `ui/dist/`
output (`make ui`), so the web path is never abandoned, only demoted to
fallback.

## Consequences

Won on:
- One binary to launch on the presentation machine, no dev server to
  keep alive, no "is the port still bound" failure mode mid-interview.
- Genuinely interactive live demo (click a matrix tile, drill into a
  case) beats looping video embedded in slides for the "we'll dig into a
  couple of cases together" part of the interview format Aviv described.

Lost to the alternative, accepted as a real cost:
- `tauri dev` hot-reload does not work under this harness's background-
  task model (documented in STATUS.md, not silently worked around); the
  reliable path is `make ui` then launching the built debug binary, which
  costs an explicit rebuild step after every UI change instead of
  live-reload.
- A pure web build would deploy to a shareable URL with zero extra
  tooling; Tauri's binary is local-machine-only by design. Accepted
  because the deliverable is an interview demo, not a hosted product; if
  a shareable link is ever needed, `ui/dist/` already builds for that
  path with no separate code.

## Fallback decided

If the Tauri binary fails to launch on presentation day, the web build in
a browser tab, same `dist/`, is the named fallback (decided per PLAN.md's
"standing risks" section), not an improvised recovery.
