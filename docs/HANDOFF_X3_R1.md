# HANDOFF X3-R1 — Wrong Access VLAN

Date: 2026-08-17

Status: ACCEPTED — REAL RUNTIME VERIFIED

## Completed locally

- exact parent binding to public `f59af55`;
- real six-node, five-link VLAN-filtering Containerlab topology;
- tagged VLAN 10 and native VLAN 99 baseline validation;
- controlled SW1 access VLAN 10-to-20 mutation;
- durable recovery intent and idempotent exact restoration;
- native Evidence v4 with both-switch VLAN/FDB provenance;
- exact `R_X3_L2_VLAN_001` Diagnosis Result v2;
- unit, integration and opt-in real E2E coverage.

## Acceptance completed

The transactional WSL run passed clean and materialized regressions, all prior
real lifecycles and the real X3-R1 lifecycle. Exact diagnosis, preserved native
flow, restored baseline and zero active Containerlab containers were confirmed.
The accepted public boundary is `0563fcd`.

## Scientific boundary

No Dataset Row v4, ML/Hybrid output, metric, API change or multiple-fault claim
is created. Frozen Phase 6/7/8, accepted X2, API v1 and P9-R1 remain unchanged.

## Next step

X3-R2 VLAN Missing is the next separately authorized runtime slice.
