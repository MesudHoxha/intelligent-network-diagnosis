# HANDOFF X3-R3 — VLAN Not Allowed on Trunk

Date: 2026-08-18

Status: IMPLEMENTED — REAL ACCEPTANCE PENDING

## Implemented boundary

- exact parent binding to public X3-R2 commit `36c9747`;
- unchanged accepted X3 topology, context and tagged/native baseline;
- controlled removal of VLAN 10 only from the SW1 `eth3` trunk endpoint;
- preserved SW1 access VLAN, SW2 trunk state and native VLAN 99;
- durable recovery intent and exact tagged-trunk restoration;
- native Evidence v4 from `l2_vlan_state_collector:v3`;
- combined engine preserving `R_X3_L2_VLAN_001/002` and adding
  `R_X3_L2_VLAN_003`;
- unit, integration and opt-in real E2E coverage.

## Acceptance still required

Run the full transactional package in the reviewed WSL environment. Acceptance
requires all regressions, the real X3-R3 lifecycle, exact
true/true/false/true/true diagnosis, preserved native flow, restored baseline
and zero active Containerlab containers.

## Scientific boundary

No Dataset Row v4, ML/Hybrid output, metric, API change or multiple-fault claim
is created. Frozen Phase 6/7/8, accepted X2/X3-R1/X3-R2, API v1 and P9-R1
remain unchanged.

## Next step

X3-R4 Native VLAN Mismatch begins only after X3-R3 is committed and published
from a fully passing real acceptance run. Before its Evidence v4 collection,
X3-R4 must add the planned HostC-to-HostD Topology Context v1 variant.
