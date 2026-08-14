# X2-R0 — Addressing Design and Runtime Gate

Date: 2026-08-14

Status: COMPLETE DESIGN GATE — X2-R1 IS NEXT; RUNTIME REMAINS UNAUTHORIZED

## 1. Objective

X2-R0 freezes the safe implementation boundary for four addressing vertical
slices without executing Containerlab, mutating a network, collecting new
evidence, generating a dataset, or creating an empirical claim.

The four slices are `wrong_ip_address`, `wrong_subnet_mask`,
`missing_default_route`, and `duplicate_ip`. They extend the frozen six-class
baseline append-only and remain single-fault work.

## 2. Why a separate gate is required

The addressing faults can look similar if diagnosis relies only on failed
connectivity. X2-R0 therefore freezes configuration-state signatures before
runtime:

| Fault | Address | Prefix | Default route | Duplicate | Temporal churn |
| --- | --- | --- | --- | --- | --- |
| Wrong IP | mismatch | match | present | false | not required |
| Wrong subnet mask | match | mismatch | present | false | not required |
| Missing default route | match | match | absent | false | not required |
| Duplicate IP | match | match | present | true | true |

These signatures are disjoint. Connectivity remains supporting evidence, not
the only class discriminator. The frozen `wrong_default_gateway` class remains
separate: it has a default route with the wrong gateway, while
`missing_default_route` has no default route.

## 3. Evidence boundary

The five planned X1 addressing features remain normative:

- `source_address_matches_expected`;
- `source_prefix_matches_expected`;
- `source_default_route_present`;
- `duplicate_address_detected`; and
- `duplicate_address_mac_churn_detected`.

`addressing_state_collector:v1` remains `DESIGN_ONLY` at X2-R0. Each later
runtime slice must produce Evidence v4 with collector provenance and raw-byte
SHA-256 bindings.

Duplicate IP requires two evidence modes: an active duplicate-address check
and temporal neighbor observation. A stale neighbor entry alone is explicitly
insufficient.

## 4. Safety boundary

Every runtime slice must persist a scenario-bound recovery intent before
mutation, write mutation records atomically, attempt restoration on every
partial failure, treat confirmed restoration as idempotent, verify the exact
healthy final state, validate the baseline before and after, and leave zero
Containerlab containers after cleanup.

Each slice requires a real infrastructure E2E cycle before acceptance. Runtime
authorization is not inherited from this gate or from a previous slice.

## 5. Incremental release sequence

1. X2-R0: design and runtime gate;
2. X2-R1: isolated runtime foundation and wrong IP;
3. X2-R2: wrong subnet mask;
4. X2-R3: missing default route;
5. X2-R4: duplicate IP with active and temporal evidence; and
6. X2-R5: addressing closeout and handoff to X3.

X2 does not generate the extended dataset or fit Rule/ML/Hybrid v2 models.
Those remain X7 and X8 work.

## 6. Compatibility

Phase 6 Evidence v3, Dataset Row v3, method contracts, accepted artifacts and
results, consumed report-only test, Phase 7 `/api/v1`, and Phase 8 claims remain
unchanged. P9-R1 remains paused by explicit user request.

All ten X2-R0 runtime authorization flags are false.

## 7. Acceptance gate

X2-R0 requires schema and semantic tests, X0/X1/X2 read-only composition,
source SHA-256 binding, full regression, unchanged protected artifacts, and
the existing infrastructure lifecycle as a regression only. It creates no new
addressing runtime evidence.

Local verification passed 28/28 X2-R0 tests, 75/75 combined X0-through-X2
tests, 191/191 combined Phase 6 and H1 tests, and 682 passed with three explicit
clean-checkout skips. The transactional commit package must additionally
materialize the accepted 15-source projection, re-run the protected gates, and
pass the existing 1/1 Containerlab lifecycle before applying this payload.

Limitation: X2-R0 proves only that the addressing plan is explicit,
disambiguated, safety-gated, and backward compatible. It does not prove any new
injector, collector output, rule result, restoration, topology, or real fault.
