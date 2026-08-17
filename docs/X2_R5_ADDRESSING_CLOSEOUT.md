# X2-R5 — Addressing Closeout

Date: 2026-08-17

Status: ACCEPTED — RECEIPT COMMITTED BY TRANSACTIONAL CLOSEOUT

## Closed scope

X2 contains four isolated single-fault addressing slices on the verified
`X2_TOP_01_ADDRESSING` topology:

1. Wrong IP Address — `R_X2_ADDRESSING_001`;
2. Wrong Subnet Mask — `R_X2_ADDRESSING_002`;
3. Missing Default Route — `R_X2_ADDRESSING_003`;
4. Duplicate IP — `R_X2_ADDRESSING_004`.

Each slice has a disjoint reviewed signature, Evidence v4, a real Containerlab
lifecycle, durable recovery intent, confirmed restoration, baseline recovery
and zero-container cleanup.

## Evidence receipt

The transactional closeout reads the already accepted real run directories,
revalidates manifest, diagnosis, restoration, before/after baseline and raw
artifact hashes, and commits one receipt containing per-file SHA-256 bindings.
It also creates a private local archive. X2-R5 performs no new network mutation
or evidence collection.

## Scientific claim boundary

X2 proves four controlled variants on one known topology and exact Rule-Based
discrimination for those variants. It does not establish arbitrary addressing
coverage, unseen-topology generalization, dataset expansion, ML/Hybrid
performance, multiple-fault diagnosis or production readiness.

## Handoff

The next authorized milestone is X3-R0, a design-only gate for Layer 2 and VLAN
faults. No X3 runtime is inherited from X2.
