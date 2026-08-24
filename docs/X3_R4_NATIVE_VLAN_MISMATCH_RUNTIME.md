# X3-R4 — Native VLAN Mismatch Runtime

Status: IMPLEMENTED — TRANSACTIONAL ACCEPTANCE PENDING

This append-only slice observes the distinct HostC-to-HostD native VLAN 99
context. It changes only SW1 `eth3` by retaining VLAN 99 as tagged carriage
and assigning controlled VLAN 98 as the PVID/untagged native VLAN. The tagged
HostA-to-HostB VLAN 10 control remains healthy.

`l2_vlan_state_collector:v4` records both trunk endpoints, source FDB state,
link state, and native/tagged effectiveness probes. `R_X3_L2_VLAN_004` accepts
only `true/true/true/false/true`; connectivity is effectiveness evidence, not
the classifier.

Recovery intent precedes mutation. Every failure path attempts exact removal
of VLAN 98 and restoration of VLAN 99 PVID/untagged membership, then reruns the
complete baseline. The slice creates Evidence v4 and one Rule-Based v2 result;
it creates no dataset, ML/Hybrid output, metric, API change, or multi-fault
claim. Real E2E acceptance requires restoration and zero-container cleanup.
