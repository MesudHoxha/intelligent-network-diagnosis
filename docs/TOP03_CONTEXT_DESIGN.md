# TOP-03 Asymmetric Context Design Review

Version: 1
Date: 2026-07-31
Status: G05 IMPLEMENTED AND RUNTIME VERIFIED

## 1. Purpose and scope

This document converts the G05 coverage slot from Evaluation Group
Protocol v1 into one concrete TOP-03 asymmetric static-routing
context.

P2-R7 froze the graph, forwarding asymmetry, addressing,
observation roles, logical C1/C2 fault target, evidence producers,
split-group binding, baseline requirements, runtime distinction
proof, and semantic design fingerprint before implementation.

P2-R8 implemented and runtime-verified that frozen design. It created
the Containerlab topology, validator, N0/C1/C2 scenarios, smoke plan,
tests, Evidence v2 artifacts, Dataset Row v2 records, and a real
artifact SHA-256. It did not create an expanded campaign, grouped
split, ML result, or hybrid result.

## 2. Design constraints

G05:

- uses Linux static routing and the current N0/C1/C2 semantics;
- uses one physical routed cycle with deliberately different forward
  and return forwarding paths;
- uses Observation Profile v1 with one source, one route observer,
  and one selected transit role;
- uses Evidence v2 and Dataset Row v2 without adding a reverse-path
  feature;
- uses one split_group_id for all N0, C1, and C2 executions;
- keeps repetitions and address-only variants inside that group;
- requires reverse-path filtering to be disabled where strict source
  validation would reject the intended asymmetric forwarding;
- isolates ground truth from collection and diagnosis;
- requires explicit baseline validation before and after every
  execution; and
- remains separate from historical P1 and P2-R1 metadata.

OSPF remains proposed under D-034. Introducing OSPF in G05 would mix
forwarding-protocol variation with the first asymmetric-context test,
so it is outside this design.

## 3. Frozen identity

| Field | Frozen value |
| --- | --- |
| Group slot | G05 |
| topology_id | TOP_03_ASYMMETRIC_RETURN |
| split_group_id | CTX_G05_TOP03_ASYMMETRIC_RETURN |
| Planned laboratory name | top03asym |
| Diagnostic direction | hosta_to_hostb |
| Forward route observer | r2 |
| Selected transit | r3 |

These identifiers are frozen before deterministic splitting. They
must not be renamed to influence partition allocation.

## 4. Physical graph and directed forwarding

Physical graph:

```text
                  r2
                 /  \
hosta -- r1           r3 -- hostb
           \          /
             r4 -----
```

The router cycle is r1-r2-r3-r4-r1.

Selected forward path:

```text
hosta -> r1 -> r2 -> r3 -> hostb
```

Selected return path:

```text
hostb -> r3 -> r4 -> r1 -> hosta
```

The paths share r1 and r3 but use different middle routers. R2 is the
forward route observer and is deliberately absent from the selected
return path. R4 is deliberately absent from the selected forward
path. Static routes, not node names alone, enforce this asymmetry.

No ECMP, default-route ambiguity, or policy-routing dependency is
part of the frozen design.

## 5. Baseline addressing and routing intent

| Link | Prefix | Endpoint addresses |
| --- | --- | --- |
| hosta-r1 | 10.50.1.0/24 | hosta 10.50.1.10, r1 10.50.1.1 |
| r1-r2 | 10.50.12.0/29 | r1 10.50.12.1, r2 10.50.12.2 |
| r2-r3 | 10.50.23.0/29 | r2 10.50.23.1, r3 10.50.23.2 |
| r3-hostb | 10.50.3.0/24 | r3 10.50.3.1, hostb 10.50.3.10 |
| r3-r4 | 10.50.34.0/29 | r3 10.50.34.1, r4 10.50.34.2 |
| r4-r1 | 10.50.14.0/29 | r4 10.50.14.2, r1 10.50.14.1 |

Forward routes toward 10.50.3.0/24:

- hosta uses 10.50.1.1 on r1;
- r1 uses 10.50.12.2 on r2;
- r2 uses 10.50.23.2 on r3; and
- r3 delivers the connected HostB network.

Return routes toward 10.50.1.0/24:

- hostb uses 10.50.3.1 on r3;
- r3 uses 10.50.34.2 on r4;
- r4 uses 10.50.14.1 on r1; and
- r1 delivers the connected HostA network.

R2 also retains an explicit route toward 10.50.1.0/24 through r1,
and r4 retains an explicit route toward 10.50.3.0/24 through r3.
These support deterministic local routing and validation but do not
change the selected end-to-end return path.

IPv4 forwarding is required on r1, r2, r3, and r4. Reverse-path
filtering must be disabled on the routed interfaces used by the
asymmetric path, because r3 receives HostA-sourced forward traffic
from r2 while its route back to HostA uses r4, and r1 receives
HostB-sourced return traffic from r4 while its route toward HostB
uses r2.

## 6. Observation and fault binding

| Role | Binding |
| --- | --- |
| source | hosta |
| source gateway | r1, 10.50.1.1 |
| route observer | r2 |
| expected transit | r3, 10.50.23.2 |
| destination | hostb, 10.50.3.10 |
| destination prefix | 10.50.3.0/24 |
| C1 target | route on r2 toward 10.50.3.0/24 |
| C2 correct next hop | 10.50.23.2 through the r2-r3 interface |
| C2 wrong next hop | unassigned 10.50.23.6 through the r2-r3 interface |

C1 removes only the r2 destination route. C2 preserves the route but
replaces the correct r3 next hop with unreachable 10.50.23.6.

The fault remains on the selected forward path. The asymmetric
return corridor is configuration and runtime distinction evidence,
not another fault target and not another evaluation group.

## 7. Evidence producers and contract boundary

- hosta produces source-gateway and end-to-end reachability;
- r1 is the upstream forward component and final return router;
- r2 produces destination-route and next-hop evidence;
- r3 is the selected transit, reaches HostB directly, and starts the
  selected return path;
- r4 is the return-only intermediate router; and
- hostb terminates the forward path and originates return traffic.

The current Evidence v2 row records the selected forward observer and
transit roles. The baseline validator and runtime distinction audit,
not Dataset Row v2, prove the asymmetric return corridor.

The existing seven features remain unchanged. Topology identity,
direction, observer/transit binding, and split_group_id remain
metadata rather than model features.

## 8. Required baseline and runtime assertions

The G05 implementation must validate:

- every frozen interface and IPv4 address;
- IPv4 forwarding on r1-r4;
- disabled reverse-path filtering on the asymmetric routed path;
- every frozen forward, return, and support route;
- HostA-to-HostB and HostB-to-HostA baseline reachability;
- route lookups proving the forward sequence through r1, r2, and r3;
- route lookups proving that r3 returns toward HostA through r4 and
  that r4 continues through r1;
- absence of a selected return route from r3 through r2;
- observer r2 reachability to expected transit r3;
- transit r3 reachability to HostB;
- adjacency health on r3-r4 and r4-r1;
- absence and unreachability of 10.50.23.6 before injection; and
- exclusion of 10.50.23.6 from the baseline r2 destination route.

Separate C1 and C2 runtime audits must prove:

- HostA can still reach local gateway r1;
- HostA cannot reach HostB after the selected r2 fault;
- r2 can still reach correct next hop r3;
- r3 can still reach HostB;
- r3 still resolves 10.50.1.0/24 through r4;
- r4 still resolves 10.50.1.0/24 through r1;
- the r3-r4 and r4-r1 adjacencies remain healthy;
- reverse-path filtering remains disabled; and
- only for C2, r2 resolves 10.50.3.0/24 through
  10.50.23.6 on the r2-r3 interface while 10.50.23.2 remains
  reachable.

An end-to-end HostB-to-HostA ping during C1 or C2 is not a valid
standalone return-corridor assertion: its echo reply must traverse
the intentionally faulty HostA-to-HostB direction. The fault-state
audit therefore uses frozen route lookups and adjacent-hop
reachability to isolate the return corridor from the failed forward
direction.

## 9. Scenario acceptance rules

All three scenarios must reference TOP_03_ASYMMETRIC_RETURN,
hosta_to_hostb, observer r2, transit r3, and
CTX_G05_TOP03_ASYMMETRIC_RETURN.

N0 must:

- preserve the frozen forward and return routes;
- produce seven true diagnostic features; and
- produce NO_FAULT_DETECTED with exact_match true.

C1 must:

- remove only the r2 route toward 10.50.3.0/24;
- keep expected transit r3 and the r3-HostB segment healthy;
- keep the asymmetric return corridor configured and healthy under
  the fault-state audit;
- produce the approved missing_static_route feature semantics; and
- match R_ROUTING_001.

C2 must:

- retain the r2 route toward 10.50.3.0/24;
- replace 10.50.23.2 with unreachable 10.50.23.6 on the same
  r2-r3 segment;
- keep correct neighbor 10.50.23.2 reachable;
- keep r3-to-HostB and the asymmetric return corridor healthy;
- produce the approved wrong_next_hop feature semantics; and
- match R_ROUTING_002.

For C1 and C2, restoration must recover the complete frozen baseline.
Rule-based exact-match evaluation remains separate from Batch Runner
completion, and every new row must validate as Dataset Row v2.

## 10. Semantic design fingerprint

The normative descriptor is:

`ctx-v1|TOP_03_ASYMMETRIC_RETURN|`
`forward=hosta-r1-r2-r3-hostb;return=hostb-r3-r4-r1-hosta|`
`static-forward-return-divergence|hosta_to_hostb|`
`observer=r2|transit=r3|fault=r2-hostb-route;`
`wrong-nh=r2-r3-segment|`
`evidence=hosta,r1,r2,r3,hostb;return-path=r3,r4,r1`

The six physical lines above form one logical descriptor.

This is a semantic design fingerprint, not a cryptographic artifact
hash. P2-R8 created and verified the normalized topology, validator,
and N0/C1/C2 scenario bundle. Its real SHA-256 is:

`6bd4de9818ba0c3b589e5a17cf47553f523fc743d6feb12334bd525ea79ca870`

## 11. Distinction audit

| Property | G01 | G02 | G03 | G04 | G05 |
| --- | --- | --- | --- | --- | --- |
| Physical router structure | Two-router line | Three-router line | Interior two-arm branch | Source-gateway dual transit | Four-router cycle |
| Observer equals source gateway | Yes | Yes | No | Yes | No |
| Forward-only middle router | No | No | No | No | r2 |
| Return-only middle router | No | No | No | No | r4 |
| Selected return path mirrors forward path | Yes | Yes | Yes | Yes | No |
| Additional active arm | No | No | r3-hostb | r2-hostb | Dedicated return corridor |
| Logical fault location | Edge r1 | Edge r1 | Interior r2 | Dual-transit edge r1 | Forward-only interior r2 |
| C2 context | Same segment | Same segment | Selected branch segment | Other live transit segment | Forward observer-transit segment |

G05 does not claim novelty from its IP addresses, node names, or a
nominal reverse direction. Its material distinction is the frozen
forward/return divergence: the fault observer r2 is traversed only in
the diagnosed forward direction, while return traffic uses r4.

Removing r4, routing r3 back through r2, or placing both directions
on the same router sequence collapses G05 toward a G02/G03-style
context and is not compliant with this design.

## 12. Implementation and verification record

P2-R8 completed the required implementation sequence:

1. create the frozen Containerlab graph and static forwarding;
2. add a baseline validator covering asymmetry and reverse-path
   filtering;
3. add N0, C1, and C2 with the frozen shared group;
4. add static contract, topology, and G01-G04 distinction tests;
5. run the complete regression suite;
6. prove the forward/return distinction at runtime;
7. execute one real three-scenario smoke batch;
8. audit Evidence v2, Dataset Row v2, role binding, feature
   semantics, exact match, restoration, and final baseline; and
9. record the real normalized artifact SHA-256 and HANDOFF.

The accepted batch is P2_G05_SMOKE with batch run ID
p2_g05_smoke-20260731T083408705159Z-
4badf5fdf6da4141af74af11d4b5f1a2. All three experiments completed.
Evidence v2, Dataset Row v2, role binding, feature semantics,
rule-based exact match, restoration, and semantic artifact audits
passed. The initial and final baselines passed 52/52 checks, the
targeted suite passed 7/7 tests, the complete suite passed 155/155
tests, and laboratory cleanup passed.

G05 now satisfies the implementation portion of the fifth-context
gate. G01 future campaign bindings must still be created, and the full
two-repetition campaign and grouped split must still succeed before
ML training begins.
