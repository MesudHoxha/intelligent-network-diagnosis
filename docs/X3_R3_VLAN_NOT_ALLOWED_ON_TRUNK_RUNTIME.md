# X3-R3 — VLAN Not Allowed on Trunk Runtime

Date: 2026-08-18

Status: IMPLEMENTED — TRANSACTIONAL ACCEPTANCE PENDING

## Scope

The accepted `X3_TOP_01_L2_VLAN` topology and HostA-to-HostB observation
roles are reused unchanged. The controlled fault removes tagged VLAN 10 only
from the SW1 `eth3` trunk endpoint. SW1 access VLAN 10, the peer trunk
endpoint and native VLAN 99 remain intact.

## Evidence and rule

`l2_vlan_state_collector:v3` records both-switch VLAN/FDB inventories, link
state and tagged/native probes. Rule `R_X3_L2_VLAN_003` requires access true,
VLAN existence true, trunk allowance false, native peer agreement true and
expected FDB location true. The combined engine preserves X3-R1 and X3-R2;
connectivity remains effectiveness evidence only.

The FDB port parser consumes the native iproute2 JSON field `ifname` and keeps
`dev` compatibility for normalized executor fixtures. This prevents a real
HostA MAC learned on SW1 `eth1`/VLAN 10 from being reported as a location
mismatch solely because of the JSON field name.

## Safety and boundary

Recovery intent precedes the single trunk mutation. Restoration is attempted
on every error, is idempotent after confirmation and restores exact tagged
VLAN 10 membership before the complete baseline is rerun. The slice creates
Evidence v4 and a Rule-Based v2 result only. Dataset, ML/Hybrid, metrics,
multiple faults, API v2 and P9-R1 remain outside scope.
