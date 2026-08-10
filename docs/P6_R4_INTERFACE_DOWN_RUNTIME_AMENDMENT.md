# P6-R4 Interface-Down Runtime Amendment

Date: 2026-08-10

Status: D-081 APPROVED; IMPLEMENTATION AND RE-SMOKE VERIFIED

## 1. Purpose

This document records the runtime evidence that invalidated one
pre-execution assumption in D-077 and defines the smallest amendment
required before P6-R4 may be re-smoked.

The amendment changes no class label, feature name, schema version,
context, split, mask, topology, or historical P2-P5 artifact. It changes
only the expected route-family state of `interface_down` and the exact
restoration procedure for routes bound to the disabled interface.

## 2. Conflict with the original design

D-077 expected the destination route to remain installed while R1
`eth2` was administratively down. The first real P6-R4 runtime disproved
that expectation:

- runtime: `p6_r4_new_class_smoke-20260810T114903Z`;
- `ip link set dev eth2 down`: return code 0;
- `ip -j link show dev eth2`: `operstate=DOWN`;
- exact route query for `10.10.2.0/24`: return code 0 and `[]`;
- R1-to-`10.10.12.2` ping: return code 1;
- HostA-to-HostB ping: return code 1; and
- R2-to-HostB ping: return code 0.

The first recovery correctly identified the kernel route removal but
attempted to preserve the two routes with `onlink` after the interface
was already down. The second runtime disproved that mechanism:

- runtime: `p6_r4_interface_recovery_smoke-20260810T122212Z`;
- both `ip route replace ... dev eth2 onlink` commands: return code 2;
- stderr: `Error: Nexthop device is not up.`; and
- interface, both routes, complete baseline, and healthy Evidence v3
  were safely restored before cleanup.

The collector did not run during either failed fault gate. No failed
runtime was accepted as a class signature or dataset result.

## 3. Amended interface-down contract

The expected ten-feature vector is now:

| Feature | Value |
| --- | --- |
| `source_expected_gateway_reachable` | `true` |
| `source_default_gateway_matches_expected` | `true` |
| `destination_reachable` | `false` |
| `route_to_destination_exists_on_observer` | `false` |
| `route_next_hop_matches_expected` | `unavailable` |
| `route_next_hop_reachable_from_observer` | `unavailable` |
| `expected_next_hop_reachable_from_observer` | `false` |
| `observer_egress_interface_oper_up` | `false` |
| `destination_reachable_from_transit` | `true` |
| `flow_blocked_by_policy` | `false` |

The exact observer route query remains an observed probe. Because that
probe observes an absent route, the two installed-next-hop features are
structurally unavailable under the existing Evidence v3 contract. The
collector therefore produces eight raw artifacts, eight observed
features, and two structurally unavailable features for this class.

Injection performs only the approved `eth2 down` mutation and verifies
that every explicitly recorded baseline route bound to that device was
removed by the kernel. It does not attempt to add routes through a down
device.

Restoration first raises `eth2`, then replaces each exact recorded
baseline route without `onlink`, verifies neighbor and end-to-end
reachability, and finally requires the complete 13-check TOP-01
baseline plus healthy Evidence v3.

## 4. Six-class separability

The amended vector remains unique. The two absent-route classes differ
as follows:

| Discriminator | `missing_static_route` | `interface_down` |
| --- | --- | --- |
| Expected next-hop reachable | `true` | `false` |
| Observer egress interface operational | `true` | `false` |

Route absence is the injected root cause for `missing_static_route`.
For `interface_down`, route absence is a deterministic consequence of
the link fault. Ground truth remains `interface_down`; neither the
collector nor the rule engine receives the scenario label.

## 5. Plan identity and audit boundary

The original D-077 canonical plan SHA-256 remains recorded as:

`f2cf0feced412af5fa76f1ffa861b3500389c430209d8e5b09a4d9e985f1b4f9`

The runtime-amended canonical plan SHA-256 is:

`571cc26518d81a1768261970fb2d3847587fc4bbc1a9c62678c8f97f3e524746`

Git history preserves the original bytes. D-081 authorizes the amended
hash for all later Phase 6 work and prohibits use of the superseded
interface-down signature.

## 6. Runtime confirmation

Runtime `p6_r4_d081_amended_smoke-20260810T130119Z` verified the amended
contract. The `interface_down` injector confirmed the interface-down
state and removal of both recorded routes without any `onlink` attempt.
Evidence v3 contained eight raw artifacts, eight observed features, and
the two required structurally unavailable installed-next-hop features.
Rule `R_P6_LINK_001` was the sole exact match.

Restoration raised `eth2`, recreated both exact routes without
`onlink`, restored the healthy Evidence v3 signature, and returned
TOP-01 to a 13/13 valid baseline. The same runtime subsequently accepted
the independent `acl_block` smoke. Together with the saved
`wrong_default_gateway` result, D-082 closed P6-R4 at 3/3 exact rule
matches, 3/3 restorations, and 3/3 restored healthy signatures.

Dataset Row v3 aggregation, E01-E06, the 72-row campaign, model fitting,
prediction, and metrics were not executed in P6-R4.
