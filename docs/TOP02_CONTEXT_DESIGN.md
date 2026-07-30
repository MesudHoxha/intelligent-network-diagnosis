# TOP-02 Context Design Review

Version: 1
Date: 2026-07-30
Status: G02 IMPLEMENTED AND VERIFIED; G03/G04 DESIGN FROZEN

## 1. Purpose

This document converts the G02, G03, and G04 coverage slots from
Evaluation Group Protocol v1 into concrete, reviewable TOP-02
laboratory designs.

It freezes the causal distinctions, logical graphs, baseline
forwarding intent, observation roles, fault locations, evidence
producers, and split-group bindings before implementation.

P2-R4 now records the verified G02 implementation against this frozen
design. G03 and G04 remain design artifacts and do not yet claim a
topology, validator, scenario, experiment, Evidence v2 artifact, or
Dataset Row v2 artifact.

## 2. Design constraints

All three contexts:

- use Linux static routing so C1 and C2 preserve their current
  semantics;
- use the existing Observation Profile v1 contract with one source,
  one route observer, and one transit role;
- use the existing Evidence v2 and Dataset Row v2 contracts;
- contain the complete current class set: no_fault,
  missing_static_route, and wrong_next_hop;
- use one shared split_group_id across N0, C1, and C2 inside the
  context;
- keep repetitions and address-only variants inside the same group;
- isolate ground truth from evidence collection and diagnosis;
- require explicit baseline validation before and after execution;
  and
- remain separate from historical P1 and P2-R1 metadata.

OSPF remains proposed under D-034 and is not introduced by this
review. Adding dynamic routing while validating the first real
role-neutral topology would confound protocol variation with topology
variation.

## 3. Frozen group identifiers

| Slot | topology_id | split_group_id | State |
| --- | --- | --- | --- |
| G01 | TOP_01 | CTX_G01_TOP01_LINEAR_2R | Binding frozen for future campaign rows; historical rows unchanged |
| G02 | TOP_02_CHAIN | CTX_G02_TOP02_CHAIN_3R | Implemented and smoke-verified |
| G03 | TOP_02_BRANCH | CTX_G03_TOP02_BRANCH_MID | Design frozen; laboratory pending |
| G04 | TOP_02_DUAL_TRANSIT | CTX_G04_TOP02_DUAL_TRANSIT | Design frozen; laboratory pending |
| G05 | Pending TOP-03 design | Pending | Planned |

The identifiers are fixed before deterministic splitting. They must
not be renamed to influence partition allocation.

## 4. Fingerprint method

Each design has a semantic fingerprint descriptor with the following
ordered fields:

1. descriptor version;
2. topology_id;
3. directed graph;
4. forwarding intent;
5. diagnostic direction;
6. route-observer and transit binding;
7. logical C1/C2 target; and
8. evidence-producing components.

The descriptor is the design fingerprint. During implementation, a
normalized bundle of the topology, validator, and scenario files
receives a SHA-256 value recorded alongside the descriptor. G02 now
has that real artifact fingerprint. G03 and G04 do not, because their
files do not yet exist. No placeholder hash is treated as a real
artifact fingerprint.

## 5. G02 — Three-router chain

### 5.1 Identity and graph

- topology_id: TOP_02_CHAIN
- split_group_id: CTX_G02_TOP02_CHAIN_3R
- laboratory name: top02chain
- diagnostic direction: hosta_to_hostb

Graph:

```text
hosta -- r1 -- r2 -- r3 -- hostb
```

This is a directed three-router forwarding chain. R3 extends the
destination-side path beyond the directly observed transit R2.

### 5.2 Baseline addressing and forwarding intent

| Link | Prefix | Endpoint addresses |
| --- | --- | --- |
| hosta-r1 | 10.20.1.0/24 | hosta 10.20.1.10, r1 10.20.1.1 |
| r1-r2 | 10.20.12.0/29 | r1 10.20.12.1, r2 10.20.12.2 |
| r2-r3 | 10.20.23.0/29 | r2 10.20.23.1, r3 10.20.23.2 |
| r3-hostb | 10.20.3.0/24 | r3 10.20.3.1, hostb 10.20.3.10 |

Forward path:

- hosta sends 10.20.3.0/24 through r1;
- r1 sends 10.20.3.0/24 through 10.20.12.2;
- r2 sends 10.20.3.0/24 through 10.20.23.2; and
- r3 delivers the connected destination network.

The reverse path uses hostb -> r3 -> r2 -> r1 -> hosta with explicit
static routes toward 10.20.1.0/24. HostB also uses
10.20.23.0/29 via 10.20.3.1 so replies to the r2 transit probe return
through r3.

### 5.3 Observation and fault binding

| Role | Binding |
| --- | --- |
| source | hosta |
| source gateway | r1, 10.20.1.1 |
| route observer | r1 |
| expected transit | r2, 10.20.12.2 |
| destination | hostb, 10.20.3.10 |
| destination prefix | 10.20.3.0/24 |
| C1 target | route on r1 toward 10.20.3.0/24 |
| C2 correct next hop | 10.20.12.2 |
| C2 wrong next hop | unassigned 10.20.12.6 through the r1-r2 interface |

N0 observes the intact route. C1 removes the destination route from
r1. C2 replaces it with the unreachable next hop 10.20.12.6 while
the correct r2 neighbor remains reachable.

### 5.4 Evidence producers

- hosta produces gateway and end-to-end reachability results;
- r1 produces the destination-route lookup and expected/configured
  next-hop reachability results;
- r2 produces destination reachability from the transit role; and
- r3 and hostb causally contribute to the r2-to-destination result.

The current collector can represent this context without a schema
change.

### 5.5 Design fingerprint

`ctx-v1|TOP_02_CHAIN|hosta-r1-r2-r3-hostb|static-forward-and-return|`
`hosta_to_hostb|observer=r1|transit=r2|fault=r1-destination-route|`
`evidence=hosta,r1,r2,r3,hostb`

The three physical lines above form one logical descriptor.

### 5.6 Material distinction

G02 differs from G01 because the forwarding path contains a third
router after the transit observer. Destination reachability from the
transit role now depends on an additional forwarding component rather
than on a directly connected destination network.

G02 is the first implementation target because it tests real
role-neutral execution with the smallest controlled increase in
laboratory complexity.

### 5.7 Real artifact and verification

The normalized bundle contains:

- labs/topologies/top02_chain/topology.clab.yml;
- labs/topologies/top02_chain/scripts/validate_baseline.sh;
- scenarios/routing/N0_NORMAL_OPERATION_TOP02_CHAIN.yml;
- scenarios/routing/C1_MISSING_STATIC_ROUTE_TOP02_CHAIN.yml; and
- scenarios/routing/C2_WRONG_NEXT_HOP_TOP02_CHAIN.yml.

Its SHA-256 fingerprint is:

fa411079e19fa7047a467ae46ff1ba7edd54657daee254f74f6c57cd58e4adc3

The real P2_G02_SMOKE batch completed one N0, one C1, and one C2
experiment. Evidence v2, Dataset Row v2, exact-match, restoration, and
the initial and final 28/28 baselines passed their separate audits.
The complete automated suite passed 134 tests.

The first baseline attempt exposed the need for the explicit HostB
return route for 10.20.23.0/29. The correction enables the frozen r2
transit-to-destination evidence probe and does not change the G02
semantic fingerprint.

## 6. G03 — Interior branched observer

### 6.1 Identity and graph

- topology_id: TOP_02_BRANCH
- split_group_id: CTX_G03_TOP02_BRANCH_MID
- proposed laboratory name: top02branch
- diagnostic direction: hosta_to_hostc

Graph:

```text
                         r3 -- hostb
                        /
hosta -- r1 -- r2
                        \
                         r4 -- hostc
```

R2 is an interior branch point. The observed destination path uses
r4-hostc, while r3-hostb remains a separate active destination arm.

### 6.2 Baseline addressing and forwarding intent

| Link | Prefix | Endpoint addresses |
| --- | --- | --- |
| hosta-r1 | 10.30.1.0/24 | hosta 10.30.1.10, r1 10.30.1.1 |
| r1-r2 | 10.30.12.0/29 | r1 10.30.12.1, r2 10.30.12.2 |
| r2-r3 | 10.30.23.0/29 | r2 10.30.23.1, r3 10.30.23.2 |
| r3-hostb | 10.30.3.0/24 | r3 10.30.3.1, hostb 10.30.3.10 |
| r2-r4 | 10.30.24.0/29 | r2 10.30.24.1, r4 10.30.24.2 |
| r4-hostc | 10.30.4.0/24 | r4 10.30.4.1, hostc 10.30.4.10 |

R1 forwards both destination networks toward r2. R2 selects r3 for
10.30.3.0/24 and r4 for 10.30.4.0/24. Both arms have explicit return
routes toward 10.30.1.0/24.

### 6.3 Observation and fault binding

| Role | Binding |
| --- | --- |
| source | hosta |
| source gateway | r1, 10.30.1.1 |
| route observer | r2 |
| expected transit | r4, 10.30.24.2 |
| destination | hostc, 10.30.4.10 |
| destination prefix | 10.30.4.0/24 |
| C1 target | route on r2 toward 10.30.4.0/24 |
| C2 correct next hop | 10.30.24.2 |
| C2 wrong next hop | unassigned 10.30.24.6 through the r2-r4 interface |

The source gateway and route observer are deliberately different.
C1 and C2 occur at the interior branch router r2, after traffic has
already crossed r1.

### 6.4 Evidence producers

- hosta produces gateway and end-to-end reachability results;
- r1 is the upstream forwarding component between the source and
  observer;
- r2 produces the route and next-hop evidence;
- r4 produces destination reachability from the selected transit
  role;
- hostc terminates the observed path; and
- the separately validated r3-hostb arm proves that the graph is a
  real branch rather than a renamed linear chain.

The existing collector supports the selected observation path. The
baseline validator, not the Evidence v2 row, is responsible for
confirming the independent r3-hostb arm.

### 6.5 Design fingerprint

`ctx-v1|TOP_02_BRANCH|hosta-r1-r2-{r3-hostb,r4-hostc}|`
`static-two-destination-branch|hosta_to_hostc|observer=r2|`
`transit=r4|fault=r2-hostc-route|`
`evidence=hosta,r1,r2,r4,hostc;baseline-arm=r3,hostb`

The four physical lines above form one logical descriptor.

### 6.6 Material distinction

G03 differs from G01 and G02 in three causal properties:

- the route observer is an interior node rather than the source
  gateway;
- the fault is injected after an upstream forwarding hop; and
- the observer selects between two active destination-side branches.

Removing the unused branch would change the frozen graph and
fingerprint, so a linear implementation cannot be labelled G03.

## 7. G04 — Dual-transit cross-segment next hop

### 7.1 Identity and graph

- topology_id: TOP_02_DUAL_TRANSIT
- split_group_id: CTX_G04_TOP02_DUAL_TRANSIT
- proposed laboratory name: top02dual
- diagnostic direction: hosta_to_hostc

Graph:

```text
                 r2 -- hostb
                /
hosta -- r1
                \
                 r3 -- hostc
```

R1 is the route observer and has two live transit neighbors. The
observed path uses r3-hostc. The r2-hostb arm remains valid and is
used to define a cross-segment C2 fault.

### 7.2 Baseline addressing and forwarding intent

| Link | Prefix | Endpoint addresses |
| --- | --- | --- |
| hosta-r1 | 10.40.1.0/24 | hosta 10.40.1.10, r1 10.40.1.1 |
| r1-r2 | 10.40.12.0/29 | r1 10.40.12.1, r2 10.40.12.2 |
| r2-hostb | 10.40.2.0/24 | r2 10.40.2.1, hostb 10.40.2.10 |
| r1-r3 | 10.40.13.0/29 | r1 10.40.13.1, r3 10.40.13.2 |
| r3-hostc | 10.40.3.0/24 | r3 10.40.3.1, hostc 10.40.3.10 |

R1 sends 10.40.2.0/24 through r2 and 10.40.3.0/24 through r3.
Both transit arms have explicit return routes toward 10.40.1.0/24.

### 7.3 Observation and fault binding

| Role | Binding |
| --- | --- |
| source | hosta |
| source gateway | r1, 10.40.1.1 |
| route observer | r1 |
| expected transit | r3, 10.40.13.2 |
| destination | hostc, 10.40.3.10 |
| destination prefix | 10.40.3.0/24 |
| C1 target | route on r1 toward 10.40.3.0/24 |
| C2 correct next hop | 10.40.13.2 through the r1-r3 interface |
| C2 wrong next hop | unassigned 10.40.12.6 through the r1-r2 interface |

For C2, the route to hostc is deliberately moved from the correct
r3 segment to an unreachable address on the separate, otherwise live
r2 transit segment. The correct r3 next hop and the real r2 neighbor
must remain reachable.

This preserves the wrong_next_hop label and the existing rule
signature while varying both next-hop segment and egress interface.

### 7.4 Evidence producers

- hosta produces gateway and destination reachability;
- r1 produces route and next-hop evidence across two live transit
  domains;
- r3 produces destination reachability for the selected transit
  path;
- hostc terminates the selected path; and
- r2-hostb is separately validated as the live alternate transit arm
  used by the C2 cross-segment context.

The current evidence schema still records only the selected transit
role. The baseline and injector preconditions must prove that the
alternate r2 arm is healthy; Dataset Row v2 must not gain an
unreviewed feature for it.

### 7.5 Design fingerprint

`ctx-v1|TOP_02_DUAL_TRANSIT|hosta-r1-{r2-hostb,r3-hostc}|`
`static-two-live-transits|hosta_to_hostc|observer=r1|transit=r3|`
`fault=r1-hostc-route;wrong-nh=r2-segment|`
`evidence=hosta,r1,r3,hostc;baseline-arm=r2,hostb`

The four physical lines above form one logical descriptor.

### 7.6 Material distinction

G04 differs from G03 because the branch and route observer are at the
source gateway rather than after an upstream forwarding hop. It also
uses a C2 next hop on a different active transit segment and egress
interface. A same-link unreachable address would not satisfy the
frozen G04 design.

## 8. Distinction audit

| Property | G01 | G02 | G03 | G04 |
| --- | --- | --- | --- | --- |
| Router structure | Two-router line | Three-router line | Interior two-arm branch | Source-gateway dual transit |
| Observer equals source gateway | Yes | Yes | No | Yes |
| Selected transit | r2 | r2 | r4 | r3 |
| Logical fault location | Edge r1 | Edge r1 | Interior r2 | Dual-transit edge r1 |
| Downstream after transit | Direct destination LAN | r3 then destination LAN | Direct selected destination LAN | Direct selected destination LAN |
| Additional active arm | No | No | r3-hostb | r2-hostb |
| C2 wrong-next-hop context | Same observer-transit segment | Same observer-transit segment | Same selected branch segment | Different live transit segment and egress |

The designs do not collapse to one causal context. Their differences
affect forwarding structure, observation roles, injection location,
or the network component that receives the incorrect next-hop
configuration.

## 9. Required baseline assertions

Every implementation must validate:

- all required interfaces and IPv4 addresses;
- IPv4 forwarding on every router;
- every forward and reverse static route used by the context;
- source-to-destination and destination-to-source reachability;
- observer-to-expected-transit reachability;
- transit-to-destination reachability;
- absence of the selected C2 wrong next hop before injection; and
- both active destination arms for G03 and G04.

The validator must fail if a supposedly material branch is absent or
unreachable.

## 10. Scenario acceptance rules

For each of G02, G03, and G04:

- N0, C1, and C2 must declare the same frozen split_group_id;
- every scenario must reference the correct topology_id and laboratory
  file;
- Observation Profile v1 must match the frozen role binding;
- C1 and C2 fault targets must equal the route observer;
- C1 must remove only the selected destination route;
- C2 must preserve a route entry while using the frozen unreachable
  next hop;
- the expected transit must remain reachable during C1 and C2;
- the selected destination must become unreachable during C1 and C2;
- the rule diagnosis and evaluator exact match must be reported
  separately from batch completion;
- restoration must return the complete baseline to VALID; and
- new rows must validate as Dataset Row v2.

## 11. Implementation order and readiness gate

P2-R4 implemented and verified G02 only:

1. create the TOP_02_CHAIN Containerlab topology;
2. create its baseline validator;
3. add N0, C1, and C2 scenario bindings with the shared G02 group;
4. add static contract and helper tests;
5. run the full automated regression suite;
6. execute the real G02 three-scenario smoke batch;
7. verify Evidence v2, Dataset Row v2, rule evaluation, and final
   restoration; and
8. record the real artifact SHA-256 fingerprint and HANDOFF.

G02 has now proved the first real TOP-02 pipeline. G03 is the next
implementation target; G04 remains design-frozen behind it. G05
remains a separate TOP-03 design task.

ML training remains blocked. P2-R4 created three G02 smoke rows, but
it did not create the two-repetition campaign or a valid
train/validation/test split.
