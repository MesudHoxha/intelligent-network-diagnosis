# HANDOFF X1 — Extended Contracts and Modular Collection

Date: 2026-08-14

Status: COMPLETE — X2 IS NEXT; NEW FAULT RUNTIME REMAINS UNAUTHORIZED

## Outcome

X1 implements the versioned contract and modular collection boundary required
by the X0 ambitious expansion roadmap. It remains contract-first and creates no
new empirical result.

The release adds eight schemas, a 39-feature catalog, Evidence Mask Plan v2, a
seven-spec design-only collector registry, semantic validators, a read-only
Evidence v3 to v4 adapter, and an in-memory Feature Vector v2 projector.

## Frozen baseline

The Phase 6 class order, Evidence v3, Dataset Row v3, method schemas, method
protocol, accepted hashes/results, Phase 7 `/api/v1`, and Phase 8 claim scope
remain unchanged. P9-R1 remains paused.

## Runtime boundary

No X1 collector executor is registered. All ten runtime authorization flags
remain false. The existing Containerlab smoke is required only as a regression
of deploy, baseline, injection, evidence, diagnosis, restoration, restored
baseline, and cleanup.

## Acceptance evidence

- X1 unit and integration tests: 29/29;
- X0: 18/18; H1: 6/6; Phase 6: 185/185; Phase 7–9: 175/175;
- materialized full suite: 656 passed, 1 explicit infrastructure skip;
- clean-checkout suite: 654 passed, 3 explicit skips;
- existing real infrastructure lifecycle: 1/1 passed;
- protected hashes: unchanged; and
- X1 gate: verified, X2 next.

## Next milestone

X2 — Addressing Vertical Slices. Runtime is not inherited automatically from
this handoff; X2 requires a separate design and execution gate.
