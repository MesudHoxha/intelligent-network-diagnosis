# X2-R2 — Wrong Subnet Mask Runtime Slice

Date: 2026-08-17

Status: IMPLEMENTED — TRANSACTIONAL INFRASTRUCTURE ACCEPTANCE REQUIRED

## Objective

X2-R2 activates only `wrong_subnet_mask`. It reuses the verified X2-R1
topology and baseline while adding new append-only runtime files. No X2-R1
hash-bound source is edited.

## Exact fault signature

| Feature | Wrong subnet mask value |
| --- | --- |
| `source_address_matches_expected` | `true` |
| `source_prefix_matches_expected` | `false` |
| `source_default_route_present` | `true` |
| `duplicate_address_detected` | `false` |

The controlled mutation changes `10.20.1.10/24` to `10.20.1.10/25` on HostA.
The IPv4 address and default route through `10.20.1.1` remain unchanged.

## Runtime and safety

`recovery_intent.json` is written atomically before the first mutating command.
It binds the scenario hash, target, interface, healthy prefix, wrong prefix,
and gateway. A surviving intent authorizes exact restoration even if execution
fails after the real mutation and before `injection_record.json` exists.

Restoration tolerantly removes only the reviewed `/25`, replaces the healthy
`/24` and default route, verifies address/route/reachability state, and returns
the existing confirmed record on retry. The lifecycle validates the baseline
before mutation and after restoration.

## Evidence and diagnosis

`addressing_state_collector:v2` collects address state, default-route state,
and a three-sample active duplicate check for the preserved address. Native
Evidence v4 binds every raw artifact by SHA-256. Temporal MAC churn remains
`not_requested` until X2-R4.

The combined Rule-Based v2 engine preserves X2-R1 Rule
`R_X2_ADDRESSING_001` and adds only `R_X2_ADDRESSING_002`. Missing required
evidence returns `insufficient_evidence`; an unreviewed complete signature
returns `abstained`.

## Compatibility and scientific boundary

Evidence v3, Dataset Row v3, accepted Phase 6/7/8 results, X2-R1, Phase 7
`/api/v1`, and Phase 8 claims are unchanged. X2-R2 creates no dataset row,
model operation, ML/Hybrid result, metric, report-only access, multiple-fault
execution, or extended API.

## Acceptance gate

Before commit, the transactional package must prove:

- 15/15 X2-R2 unit and integration tests;
- the combined X0-through-X2-R2 gate regression;
- green clean-checkout and materialized full suites;
- unchanged Phase 6/H1 and Phase 7-through-9 regressions;
- all three real Containerlab lifecycles;
- exact restoration and baseline validation;
- preserved real X2-R2 Evidence v4; and
- zero remaining `clab-*` containers.

The next release is X2-R3 Missing Default Route. Runtime authorization is not
inherited.
