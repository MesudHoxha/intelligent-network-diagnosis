# HANDOFF P8-R1

Date: 2026-08-12

Status: COMPLETED — FINAL EVIDENCE ARCHIVE VERIFIED

## 1. What was completed

P8-R1 implemented a fail-closed final-evidence registry and a
deterministic private archive for the accepted P6-R5 through P6-R6
experimental chain. The exact runtime artifact count and byte total are
generated from the accepted local repository and frozen in the tracked
registry. A separate tracked receipt binds the archive SHA-256, size,
member count, registry, and source checkpoint.

The archive contains the accepted raw campaign, context datasets,
merged and split Dataset Row v3 artifacts, method gate, development
freeze/model artifacts, and report-only evaluation artifacts. The
selected estimator is hashed and copied only as opaque bytes.

## 2. What was decided

D-092 accepts the P8-R1 registry/archive model. The tracked Git tree is
the public source archive; the deterministic external bundle is the
private runtime archive. P1-P5 runtime remains developmental history
bound by tracked HANDOFFs, while the private final numerical archive is
limited to the D-091 P6-R5/P6-R6 chain.

Archival reading is not test re-evaluation. No Containerlab process,
diagnosis, estimator deserialization, refit, policy reselection, metric
calculation, new metric, artifact mutation, or empirical claim is
authorized or performed.

## 3. Files created or changed

- `src/phase8/archive.py` implements strict inventory, hashing,
  deterministic archive creation, verification, and receipt generation;
- two P8-R1 JSON Schemas freeze registry and receipt contracts;
- two generated tracked JSON files bind the real registry and archive;
- `tests/unit/test_p8_r1_evidence_archive.py` verifies success and
  fail-closed behavior;
- `docs/P8_R1_FINAL_EVIDENCE_ARCHIVE.md` records the complete boundary;
- this HANDOFF records the milestone; and
- `docs/DECISIONS.md`, `docs/MASTER_CONTEXT.md`, `docs/ROADMAP.md`, and
  `docs/STATUS.md` record D-092 and advance to P8-R2.

No accepted P1-P7 runtime artifact, source contract, API route,
Dashboard asset, prediction, report value, or metric is changed.

## 4. Open issues

- P8-R2 must create thesis-ready tables, figures, and
  claim-to-evidence references from accepted values only;
- P8-R3 must perform the final Phase 8 acceptance and Phase 9 handoff;
- the private archive and its tracked receipt must be backed up
  together; and
- external replication, production deployment, multiple faults, OSPF,
  statistical superiority, and automatic remediation remain outside
  scope.

## 5. Next step

P8-R2 is next. It may read hash-verified accepted metrics and format
them for the thesis. It may not deserialize the estimator, reopen the
test protocol, rerun any method, calculate a new empirical metric, or
introduce a claim not authorized by D-091.

## 6. Impact on central documents

- `DECISIONS.md`: adds D-092 and accepts the public/private archive
  separation and final-chain scope;
- `MASTER_CONTEXT.md`: records the registry, deterministic archive,
  opaque-estimator rule, and preservation boundary;
- `STATUS.md`: marks P8-R1 complete and P8-R2 next;
- `ROADMAP.md`: advances Phase 8 to thesis-ready synthesis; and
- no P6 empirical identity or P7 interface boundary is reopened.
