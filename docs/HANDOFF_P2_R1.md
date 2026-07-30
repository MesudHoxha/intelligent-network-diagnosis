# HANDOFF — P2-R1 Role-Neutral Dataset Contract

Date: 2026-07-30
Status: COMPLETED

## 1. What was completed

- Added the Dataset Row v2 runtime contract and JSON Schema.
- Defined seven tri-state role-neutral diagnostic feature names.
- Added direction, route_observer_node, and transit_node to v2
  observation-context metadata.
- Preserved topology_id, variant_id, split_group_id, labels, and
  quality fields.
- Kept concrete IP addresses, ground truth, rule outputs, and
  evaluation results outside model features.
- Added dedicated Dataset Row v1 and v2 validators and builders.
- Made the generic builder produce Dataset Row v2 for new
  experiments.
- Preserved explicit Dataset Row v1 output when schema version 1 is
  requested.
- Added explicit Dataset Row v1 to v2 migration for the historical
  TOP_01, hosta_to_hostb, r1/r2 context.
- Preserved sample identity, split_group_id, labels, and quality
  during migration.
- Updated Batch Runner to produce v2 by default, persist the dataset
  row schema version, and reject mixed-version aggregation.
- Updated the group-aware splitter to accept homogeneous v1 or v2
  sources, record source_dataset_schema_version, and reject mixed
  versions.
- Verified 126/126 automated tests, compileall, and git diff checks.
- Executed the real B0 regression for N0, C1, and C2.
- Verified three Dataset Row v2 records with seven role-neutral
  features each, three exact rule-based matches, and valid TOP-01
  13/13 baselines before and after the batch.

## 2. What was decided

- Dataset Row v2 is the canonical dataset contract for new
  experiments.
- Dataset Row v1 remains an immutable historical P1 contract.
- Historical rows are not silently reinterpreted as v2.
- V1 to v2 migration is explicit and limited to the known historical
  TOP-01, hosta_to_hostb, r1/r2 semantics.
- Dataset metadata may record topology and observation roles, but
  topology-specific identifiers and IP addresses are not model
  features.
- Batch datasets and split-source datasets must each contain one
  Dataset Row schema version.
- Ground-truth isolation and the exclusion of rule/evaluation outputs
  from features remain unchanged.
- P2-R1 does not claim that TOP-02 or an ML-training dataset has been
  implemented.

## 3. Files created or changed

Implementation:

- schemas/dataset_row_v2.schema.json
- src/dataset/contract.py
- src/batch/runner.py
- src/dataset/splitter.py

Tests:

- tests/unit/test_batch_runner.py
- tests/unit/test_contract_schemas.py
- tests/unit/test_dataset_contract.py
- tests/unit/test_dataset_splitter.py
- tests/unit/test_normal_experiment.py

Central documentation:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/HANDOFF_P2_R1.md

Verified regression artifacts:

- data/metadata/b0_smoke_canonical-
  20260730T115517979203Z-24c80549d03d4e84ad7e066f19409ecb.json
- data/processed/b0_smoke_canonical-
  20260730T115517979203Z-24c80549d03d4e84ad7e066f19409ecb.jsonl
- data/raw/n0_normal_operation-
  20260730T115517981898Z-e70c5eb6c730468ebe85d141017f3e3f/
- data/raw/c1_missing_static_route-
  20260730T115538237435Z-6220642b985e4495ae9d81bf4381c186/
- data/raw/c2_wrong_next_hop-
  20260730T115605222163Z-acb6d03f2ca74969a27854e5d3de936f/

## 4. Open issues

- Design and implement a real TOP-02 laboratory.
- Add and verify a TOP-02 baseline validator and controlled scenario
  bindings.
- Define genuinely independent split groups across topology and
  observation contexts.
- Execute the expanded campaign and produce the first valid
  train/validation/test split.
- Implement and evaluate the Machine Learning method.
- Implement and evaluate the hybrid method.

## 5. Next step

Design and validate TOP-02 as the first real non-TOP-01 laboratory
context. Verify its Evidence v2 and Dataset Row v2 artifacts before
adding it to the controlled dataset campaign.

## 6. Impact on central documents

- MASTER_CONTEXT records Dataset Row v2 as canonical, explicit v1
  compatibility and migration boundaries, version-homogeneous batch
  and split behavior, and the real P2-R1 regression.
- DECISIONS updates D-049, D-051, D-055, and D-056 and adds D-057.
- STATUS records 126 passing tests, the verified Dataset Row v2
  regression, current limitations, and TOP-02 as the next milestone.
