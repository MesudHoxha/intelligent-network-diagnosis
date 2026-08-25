# X5-R0 — OSPF Dynamic-Routing Design Gate

Status: ACCEPTED DESIGN ONLY — NO EMPIRICAL RUNTIME AUTHORIZED

X5-R0 begins the append-only OSPF expansion from the accepted X4-R6 source
boundary at commit `50f0624679d7b1577d88d66ba87eb1c7390e80f0`. It also
hash-binds the accepted P9-R1 traceability plan, which remains accepted while
`P9_R2_CONTROLLED_CHAPTER_DRAFTING` is intentionally paused.

## Scope and release sequence

The design uses a five-node FRRouting OSPFv2 path:
`HostA -- R1 -- R2 -- R3 -- HostB`. R1 and R2 are the observation roles;
R2--R3 is the controlled adjacency and policy boundary. No topology is
deployed by this release.

The exact release sequence is:

1. `X5_R0_OSPF_DYNAMIC_ROUTING_DESIGN_GATE` — this design-only release.
2. `X5_R1_OSPF_ADJACENCY_FAILURE` — one isolated adjacency failure.
3. `X5_R2_ROUTE_FILTERING_OR_ADVERTISEMENT_PROBLEM` — one controlled prefix
   suppression/filtering fault.
4. `X5_R3_OSPF_DYNAMIC_ROUTING_CLOSEOUT` — hash-bind only accepted X5 slices.

The two X0-planned, single-fault signatures use the four X1-owned OSPF
features. C4 requires adjacency false, advertisement false, route absent, and
policy allowance true. C5 requires adjacency true, advertisement false, route
absent, and policy allowance false. They are disjoint.

`ospf_state_collector:v1` is the only design-time owner of those four
features. OSPF neighbor, database, route-table, policy and interface-state
records are required raw evidence. Static-route-override, policy-block and
connectivity controls are mandatory exclusion evidence, not classifier inputs.
Thus end-to-end reachability alone cannot select an OSPF diagnosis.

## Safety and scientific boundary

Each later runtime slice must receive separate authorization and require a
durable pre-mutation recovery intent, atomic mutation journal, best-effort and
idempotent restoration, exact OSPF/policy restoration, baseline checks before
and after, zero-container cleanup, Evidence v4 raw hashes, collector
provenance, and a real E2E lifecycle.

All ten runtime/scientific flags are false in X5-R0. It performs no Containerlab
deployment, network mutation, evidence collection, rule prediction, dataset
generation, model operation, metric calculation, report-only access, API
change, BGP work, or multiple-fault execution. It establishes neither OSPF
effectiveness nor diagnosis accuracy, ML/Hybrid behavior, generalization, or
production readiness.

Phase 6–8 results, P8 claim limitations, API v1, X2–X4 evidence and hashes,
and P9-R1 remain frozen. X7/X8 are separately planned extended-scientific
tracks; X5 does not create inputs or claims for them.

Next release: `X5_R1_OSPF_ADJACENCY_FAILURE` only, after separate
authorization.
