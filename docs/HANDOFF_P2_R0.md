# HANDOFF — P2-R0 Role-Neutral Observation Contract

Date: 2026-07-30
Status: COMPLETED

## 1. What was completed

- Removed fixed TOP-01, hosta_to_hostb, r1, and r2 requirements from
  Observation Profile v1 validation.
- Derived topology_id from topology.id and preserved validated
  direction, route-observer, and transit roles in the observation
  profile.
- Added the role-neutral Evidence v2 runtime contract and JSON Schema.
- Updated the collector to emit and validate Evidence v2 before
  writing it.
- Updated raw probe and parsed evidence names to use source,
  destination, route-observer, and transit semantics.
- Added Rule Engine validation for collected Evidence v2.
- Added a compatibility adapter for historical Evidence v1.
- Made diagnosis locations, explanations, and recommendations derive
  from actual observation roles.
- Preserved Dataset Row v1 through an Evidence v2 compatibility
  adapter limited to the legacy TOP-01 r1/r2 binding.
- Added automated coverage for generic topology/node identifiers,
  Evidence v2 validation, collection, diagnosis, compatibility, and
  Dataset Row v1 boundary enforcement.
- Verified 114/114 automated tests, compileall, and git diff checks.
- Executed the real B0 regression for N0, C1, and C2.
- Verified three Evidence v2 artifacts, three exact rule-based
  matches, and valid TOP-01 13/13 baselines before and after the
  batch.

## 2. What was decided

- Evidence v2 is the canonical evidence contract for new
  experiments.
- Diagnostic evidence uses network roles rather than topology-specific
  node names.
- Historical Evidence v1 remains readable for backward compatibility.
- Dataset Row v1 is not silently renamed or reinterpreted.
- Dataset Row v1 accepts Evidence v2 only for the legacy TOP-01 r1/r2
  binding.
- Dataset Row v2 must be defined before TOP-02 evidence is exported
  for Machine Learning.
- P2-R0 does not claim that TOP-02 has been implemented or tested in
  the real laboratory.

## 3. Files created or changed

Implementation:

- schemas/evidence_v2.schema.json
- src/contracts/evidence.py
- src/contracts/observation_profile.py
- src/collection/evidence_collector.py
- src/dataset/contract.py
- src/rules/rule_engine.py

Tests:

- tests/unit/test_evidence_contract.py
- tests/unit/test_contract_schemas.py
- tests/unit/test_dataset_contract.py
- tests/unit/test_evidence_collector.py
- tests/unit/test_missing_route_helpers.py
- tests/unit/test_observation_profile.py
- tests/unit/test_rule_engine.py
- tests/unit/test_wrong_next_hop_helpers.py

Central documentation:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/HANDOFF_P2_R0.md

Verified regression artifacts:

- data/metadata/b0_smoke_canonical-
  20260730T112109248368Z-e589527badc546feb1426f41b78fdb1a.json
- data/processed/b0_smoke_canonical-
  20260730T112109248368Z-e589527badc546feb1426f41b78fdb1a.jsonl
- Three corresponding experiment directories under data/raw/

## 4. Open issues

- Define Dataset Row v2 with role-neutral feature names and explicit
  v1 migration behavior.
- Implement and validate a real TOP-02 laboratory.
- Define independent split groups across topology and observation
  contexts.
- Execute the expanded campaign and produce the first valid
  train/validation/test split.
- Implement and evaluate the Machine Learning method.
- Implement and evaluate the hybrid method.

## 5. Next step

Implement and test Dataset Row v2 without changing historical Dataset
Row v1 artifacts. After that contract is verified, design TOP-02 and
its scenarios, validator, and batch entries before executing the next
dataset campaign.

## 6. Impact on central documents

- MASTER_CONTEXT records Evidence v2, role-neutral observation and
  diagnosis behavior, compatibility boundaries, and the real P2-R0
  regression.
- DECISIONS adds D-056 and updates Dataset Row v1 compatibility
  status.
- STATUS records 114 passing tests, the verified real regression,
  current limitations, and Dataset Row v2 as the next milestone.
