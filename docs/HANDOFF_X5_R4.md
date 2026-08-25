# HANDOFF X5-R4 — Targeted OSPF Correction and Revalidation

Status: ACCEPTED LOCAL SUCCESSOR CLOSEOUT — awaiting publication only.

X5-R4 is append-only from published X5-R3. The original X5-R1 C4 tree remains
unchanged as historical evidence, but is not authoritative for targeted-C4
scientific use after the later aggregate-neighbor/convergence audit.

The new C4 tree is
`data/raw/x5_r4/x5-r4-targeted-c4-20260825T140611741533Z-4d050e04f7334ed0a4cf8782b579f793`.
It identifies R2--R3 by router ID `3.3.3.3`, address `10.51.23.2`, and
interface `eth2:10.51.23.1`, separately proves R1--R2 is `Full`, and uses a
bounded state-based postcondition. Command acceptance and observed mutation
effectiveness are separate records. Restoration, both baselines, and
zero-container cleanup passed.

The successor receipt binds corrected C4 and unchanged accepted C5. C5 remains
`true,false,false,false` with `R_X5_OSPF_002`; `X5-R2-SUPPRESS` is provenance
metadata and the accepted mechanism is removal of R3's OSPF network statement,
not an attached prefix-list filter. Corrected C5 compatibility handling fails
closed for unavailable evidence.

Claims remain limited to two controlled single-fault OSPF variants on the
accepted topology. No generalized OSPF, ML/Hybrid, dataset, metric, API,
unseen-topology, performance, or multiple-fault claim is made. X4 audit
observations are non-blocking limitations for a later robustness track. X6 and
P9-R2 remain paused.

## Next milestone

`X6_R0_PERFORMANCE_FAULT_DESIGN_GATE` — explicit authorization required.
