# X5-R1 — OSPF Adjacency Failure

Status: IMPLEMENTED AND REAL-E2E-VERIFIED — controlled single fault only.

X5-R1 mutates only OSPF on R2 `eth2` with `passive-interface eth2`, preserving
the link, addressing, no static route override and no ACL control block. The
real Evidence v4 signature is false/false/false/true for adjacency,
advertisement, installed route and policy allowance. `R_X5_OSPF_001` returns
`dynamic_routing_adjacency_failure` at `r2:eth2`; exact OSPF state is restored
and the healthy baseline passes before and after cleanup.

No dataset, ML/Hybrid result, metric, API change, multi-fault behavior, BGP,
or generalized claim is created. C5 remains design-only. P9-R2 remains paused.
