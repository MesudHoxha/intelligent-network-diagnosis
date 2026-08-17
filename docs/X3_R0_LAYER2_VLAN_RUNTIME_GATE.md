# X3-R0 — Layer 2 and VLAN Design/Runtime Gate

Date: 2026-08-17

Status: ACCEPTED DESIGN ONLY — NO X3 RUNTIME AUTHORIZED

## Purpose

X3-R0 turns the four Layer 2/VLAN items frozen by X0 into a concrete,
testable release design. It binds the design to the X1 feature catalog and to
the accepted X2-R5 closeout, but it does not deploy a topology, mutate a
network or collect X3 evidence.

P9-R1 remains paused by user request. Frozen Phase 6/7/8 results and Phase 7
`/api/v1` remain unchanged.

## Planned real topology

`X3_TOP_01_L2_VLAN` uses six Linux containers:

- `sw1` and `sw2` implement Linux bridges with VLAN filtering enabled;
- `hosta` and `hostb` form the tagged VLAN 10 test flow;
- `hostc` and `hostd` form the untagged native VLAN 99 test flow;
- the inter-switch trunk carries VLAN 10 tagged and VLAN 99 as native;
- VLAN 20 is reserved as the controlled wrong access VLAN;
- VLAN 98 is reserved as the controlled mismatched native VLAN.

The separate VLAN 10 and VLAN 99 flows are intentional. A native-VLAN
mismatch must affect a native flow without changing the tagged-VLAN evidence
used for the other three slices.

## Disjoint fault signatures

| Fault | Access | VLAN exists | Trunk allows | Native peers match | Local FDB |
| --- | --- | --- | --- | --- | --- |
| Healthy baseline | true | true | true | true | true |
| Wrong access VLAN | false | true | true | true | false |
| VLAN missing | false | false | false | true | false |
| VLAN not allowed on trunk | true | true | false | true | true |
| Native VLAN mismatch | true | true | true | false | true |

Connectivity failure is never enough to select a root cause. Runtime slices
must collect the relevant `bridge -j vlan`, `bridge -j fdb`, interface-state
and active-flow artifacts. The native mismatch additionally requires an
explicit comparison of both trunk endpoints.

## Runtime sequence

1. X3-R1 — Wrong Access VLAN and the first real topology implementation;
2. X3-R2 — VLAN Missing;
3. X3-R3 — VLAN Not Allowed on Trunk;
4. X3-R4 — Native VLAN Mismatch;
5. X3-R5 — Layer 2/VLAN closeout and evidence receipt.

Every slice requires its own non-inherited gate, durable recovery intent,
atomic mutation record, best-effort and idempotent restoration, exact VLAN
membership recovery, baseline verification, real Evidence v4, real E2E and
zero-container cleanup.

## Authorization and claim boundary

All ten runtime/scientific authorization flags are false. X3-R0 proves only
that the design is internally consistent, hash-bound, contract-valid and
disjoint. It does not prove that the topology has run, that a fault is
effective or diagnosable, that X3 evidence exists, or that Rule-Based, ML or
Hybrid performance has improved.

## Next step

X3-R1 may implement the topology and the controlled Wrong Access VLAN slice
only after this transactional design gate is committed and published.
