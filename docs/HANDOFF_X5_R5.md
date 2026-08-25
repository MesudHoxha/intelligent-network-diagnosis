# X5-R5 C5 operational-policy correction design handoff

X5-R5 is a source-only, append-only correction from published X5-R4 commit
`671ce01fcf5ee48e3cbd65aa1182d1e54a509792`. It creates no runtime evidence
and does not modify X5-R1 through X5-R4 evidence, receipts, hashes, or claims.

The future C5 runtime uses FRRouting OSPF `redistribute connected route-map
X5-R5-C5-EXPORT` on R3. The baseline route map matches a permit prefix-list
entry for `10.51.3.0/24`; direct `network 10.51.3.0/24 area 0` origination is
absent. The future fault changes only that attached active policy criterion to
deny the exact prefix. Raw running configuration must prove the attachment,
match and denial; a label alone is not evidence.

The unchanged X5-R4 C4 tree remains authoritative. X5-R2 C5 and the X5-R3/R4
receipts remain preserved historical artifacts, but are non-authoritative for
scientific use of C5's policy feature. A future X5-R6 lifecycle must create a
new durable C5 tree, then X5-R7 must bind it with authoritative C4 in a new
successor receipt. The only permitted prospective claim remains two controlled
single-fault OSPF variants on the accepted topology.

Required next milestone: `X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION`.
X6 and P9-R2 remain paused. The future lifecycle must validate structured
neighbor, LSDB and route observations, use bounded state-based effectiveness,
separate command acceptance from observed effectiveness, validate Feature
Vector v2 at rule entry, prove idempotent partial-mutation recovery, and leave
zero containers after cleanup.
