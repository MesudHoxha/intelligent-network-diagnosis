# HANDOFF X2-R0 — Addressing Design and Runtime Gate

Date: 2026-08-14

Status: COMPLETE DESIGN GATE — X2-R1 IS NEXT

## Outcome

X2-R0 freezes four disjoint single-fault addressing signatures, their exact
X1 feature dependencies, safety invariants, real-evidence requirements, and
the X2-R1 through X2-R5 release sequence.

No collector executor, injector, rule, topology, dataset row, model, metric,
or empirical artifact is created by this release.

## Runtime boundary

All ten runtime authorization flags remain false. Every future slice requires
its own scoped authorization and must prove:

- durable recovery intent before mutation;
- best-effort and idempotent restoration;
- Evidence v4 with raw hashes and collector provenance;
- exact rule signature and confounder exclusion;
- baseline before and after;
- real Containerlab E2E; and
- zero containers after cleanup.

Duplicate IP additionally requires active and temporal MAC evidence.

## Acceptance evidence

- X2-R0 unit and integration tests: 28/28;
- combined X0 through X2 contract tests: 75/75;
- combined Phase 6 and H1 safety tests: 191/191;
- clean-checkout full suite: 682 passed, 3 explicit skips; and
- transactional package must still re-prove materialized runtime integrity and
  the existing 1/1 Containerlab lifecycle before commit.

## Frozen baseline

The Phase 6/7/8 accepted baseline, `/api/v1`, protected v3 contracts, accepted
results, and report-only boundary remain unchanged. P9-R1 remains paused.

## Next release

X2-R1 — Wrong IP Address. It will introduce the isolated addressing runtime
foundation and only the first vertical slice; runtime is not inherited from
X2-R0.
