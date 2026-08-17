# HANDOFF X2-R2 — Wrong Subnet Mask

Date: 2026-08-17

Status: IMPLEMENTED — X2-R3 IS NEXT AFTER TRANSACTIONAL ACCEPTANCE

## Outcome

X2-R2 provides one complete controlled vertical slice:

- exact prefix-only `/24` to `/25` mutation on the verified X2 topology;
- durable recovery intent and idempotent exact restoration;
- native hash-bound Evidence v4 from `addressing_state_collector:v2`;
- Feature Vector v2 and combined Rule-Based Diagnosis Result v2;
- explicit preservation of the X2-R1 Wrong IP rule; and
- an opt-in real deploy-to-cleanup E2E test.

## Verified local boundary

- X2-R2 tests: 15/15;
- X2-R1 plus X2-R2 tests: 30/30; and
- X2-R2 gate: verified with the complete X2-R1 parent gate unchanged; and
- clean-checkout full regression: 712 passed, five explicit skips.

The transactional package must still re-prove full clean/materialized suites,
frozen gates, all three real Containerlab lifecycles, exact hashes, preserved
real evidence, and zero-container cleanup before creating the commit.

## Frozen boundary

No accepted Phase 6/7/8 artifact, result, metric, contract, class order, API,
or X2-R1 hash-bound file is changed. X2-R2 creates no extended dataset and
runs no ML/Hybrid method. P9-R1 remains paused.

## Next release

X2-R3 — Missing Default Route. It requires a fresh, non-inherited runtime gate
and must preserve the exact source address and prefix while removing only the
default route.
