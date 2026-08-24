# X3-R2 — VLAN Missing Runtime

Date: 2026-08-17

Status: ACCEPTED — REAL CONTAINERLAB VERIFIED

## Scope

The accepted `X3_TOP_01_L2_VLAN` topology is reused unchanged. The controlled
fault removes VLAN 10 from both SW1 `eth1` access membership and SW1 `eth3`
tagged trunk membership. SW2 and native VLAN 99 are preserved.

## Evidence and rule

`l2_vlan_state_collector:v2` records VLAN and FDB inventories from both
switches, relevant link state and tagged/native probes. Rule
`R_X3_L2_VLAN_002` requires access false, VLAN existence false, trunk allowance
false, native peer agreement true and expected FDB location false. The
combined engine preserves X3-R1; connectivity is effectiveness evidence only.

## Safety and boundary

Recovery intent precedes both deletions. Restoration is best-effort on every
error, idempotent after confirmation and restores exact VLAN 10 PVID/untagged
access plus tagged trunk membership before the full baseline is rerun. The
slice creates Evidence v4 and a Rule-Based v2 result only. Dataset, ML/Hybrid,
metrics, multiple faults, API v2 and P9-R1 remain outside scope.

## Acceptance

The real lifecycle produced the exact false/false/false/true/false signature,
diagnosed `vlan_missing`, preserved native VLAN 99, restored both exact VLAN
10 memberships and the complete baseline, and left zero active Containerlab
containers. Clean and materialized regressions passed before public commit
`36c9747`.
