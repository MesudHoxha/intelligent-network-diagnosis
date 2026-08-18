# X3-R1 — Wrong Access VLAN Runtime

Date: 2026-08-17

Status: ACCEPTED — REAL CONTAINERLAB VERIFIED

## Scope

The real `X3_TOP_01_L2_VLAN` topology uses four hosts and two Linux bridges
with VLAN filtering. HostA-to-HostB crosses the trunk as tagged VLAN 10;
HostC-to-HostD crosses it as native VLAN 99. The controlled fault moves only
SW1's HostA-facing access port from VLAN 10 to VLAN 20.

## Evidence and rule

`l2_vlan_state_collector:v1` records `bridge -j vlan` and `bridge -j fdb` from
both switches, relevant link state, and tagged/native active probes. Rule
`R_X3_L2_VLAN_001` requires access false, VLAN existence true, trunk allowance
true, native peer agreement true and expected FDB location false. Connectivity
failure proves effectiveness but is not a root-cause classifier.

## Safety and boundary

Recovery intent precedes mutation. Restoration is best-effort on every error,
idempotent after confirmation and restores exact VLAN 10 PVID/untagged
membership before the full tagged/native baseline is rerun. The slice creates
Evidence v4 and a Rule-Based v2 result only. Dataset, ML/Hybrid, metrics,
multiple faults, API v2 and P9-R1 remain outside scope.

## Acceptance

The real lifecycle produced the exact false/true/true/true/false signature,
diagnosed `wrong_access_vlan`, preserved the native VLAN 99 flow, restored the
complete baseline and left zero active Containerlab containers. Clean and
materialized regressions passed before public commit `0563fcd`.
