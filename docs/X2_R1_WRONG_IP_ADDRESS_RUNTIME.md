# X2-R1 — Wrong IP Address Runtime Slice

Date: 2026-08-14

Status: IMPLEMENTED — TRANSACTIONAL INFRASTRUCTURE ACCEPTANCE REQUIRED

## Objective

X2-R1 activates only `wrong_ip_address`, the first of four X2 addressing
slices. It adds the minimum reusable addressing runtime foundation without
changing the frozen Phase 6/7/8 baseline.

## Exact fault signature

| Feature | Wrong IP value |
| --- | --- |
| `source_address_matches_expected` | `false` |
| `source_prefix_matches_expected` | `true` |
| `source_default_route_present` | `true` |
| `duplicate_address_detected` | `false` |

The controlled mutation changes `10.20.1.10/24` to `10.20.1.11/24` on HostA.
The /24 and default route through `10.20.1.1` remain correct. End-to-end
reachability is supporting lifecycle evidence, not the class discriminator.

## Runtime and safety

The injector writes `recovery_intent.json` atomically before mutation. The
journal contains the exact scenario hash, target, healthy address, injected
address, interface, and gateway. If execution fails after the real mutation
but before `injection_record.json`, the intent still authorizes restoration.

Restoration removes the controlled wrong address, restores the exact healthy
address and default route, validates destination reachability, persists an
atomic record, and returns the existing confirmed record on retry.

## Evidence and diagnosis

`addressing_state_collector:v1` collects local address state, default-route
state, and three active neighbor-refresh samples. Every raw JSON artifact is
bound by SHA-256 in native Evidence v4. The temporal MAC-churn feature remains
`not_requested` until the separate duplicate-IP slice X2-R4.

Feature Vector v2 feeds the exact deterministic Rule
`R_X2_ADDRESSING_001`. Unexpected complete signatures abstain; unavailable
required evidence returns `insufficient_evidence`. No alternative class is
guessed.

## Compatibility and scientific boundary

Evidence v3, Dataset Row v3, accepted Phase 6 results, Phase 7 `/api/v1`, and
Phase 8 claims are unchanged. X2-R1 creates no dataset row, ML/Hybrid result,
metric, report-only test access, multiple-fault execution, or extended API.

## Acceptance gate

Before commit, the transactional package must prove:

- 15/15 X2-R1 unit and integration tests;
- 90/90 combined X0-through-X2 tests;
- 191/191 Phase 6 plus H1 safety tests;
- green clean-checkout and materialized full suites;
- the existing Phase 6 real Containerlab regression;
- the new real X2-R1 deploy-to-cleanup lifecycle;
- exact restoration and baseline validation after mutation;
- zero remaining `clab-*` containers; and
- unchanged frozen artifacts and gates.

The next release is X2-R2 Wrong Subnet Mask. Runtime authorization is not
inherited.

