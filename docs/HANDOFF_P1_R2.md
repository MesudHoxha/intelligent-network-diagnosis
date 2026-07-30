# HANDOFF — P1-R2 Group-Aware Dataset Splitter

Date: 2026-07-30
Status: COMPLETED

## 1. What was completed

- Audited split_group_id across the accepted 12-row P1 dataset.
- Confirmed that all rows have a split group and that related
  repetitions and canonical/alternate variants remain grouped.
- Confirmed that P1 contains three independent groups in total, one
  for each fault_type.
- Implemented a deterministic, class-stratified, group-aware
  train/validation/test splitter using Python standard library only.
- Added validation for Dataset Row v1, duplicate sample identifiers,
  group-label consistency, ratios, seeds, and class-group
  feasibility.
- Added split outputs and a manifest with partition statistics and
  source/output SHA-256 hashes.
- Verified 11/11 targeted splitter tests and 91/91 total tests.
- Verified that P1 is rejected with return code 1 before any output
  directory is created.

## 2. What was decided

- No split_group_id may cross train, validation, and test
  partitions.
- Every split group must contain exactly one fault_type.
- A three-way split requires at least three independent groups per
  fault_type so every partition retains class coverage.
- The splitter is deterministic for a fixed seed and uses
  stratified_group_hash_v1 with default seed 20260730.
- P1 remains the accepted parameterized pipeline pilot and is not
  altered merely to force an ML split.
- Repeated rows and related variants sharing one split_group_id do
  not count as independent groups.
- ML training must wait for a larger controlled dataset campaign.

## 3. Files created or changed

Code checkpoint:

- Commit 25f5ba6 — feat: add group-aware dataset splitter
- src/dataset/splitter.py
- tests/unit/test_dataset_splitter.py

Central documentation:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/HANDOFF_P1_R2.md

No valid split artifacts were created from P1 because its group
structure is intentionally insufficient for three-way class
coverage.

## 4. Open issues

- Define the controlled dimensions that create genuinely independent
  split groups for every class.
- Decide the next campaign size beyond the minimum three groups per
  class.
- Execute the expanded dataset campaign and produce the first
  successful split manifest.
- Implement and evaluate the Machine Learning method.
- Implement and evaluate the hybrid method.
- Compare rule-based, Machine Learning, and hybrid performance.

## 5. Next step

Design the next controlled dataset expansion with at least three
independent split_group_id values per fault_type. Verify group
independence in the batch plan before laboratory execution, then
generate and audit the first successful train/validation/test split.

## 6. Impact on central documents

- MASTER_CONTEXT records the implemented splitter, its safety
  guarantees, and the P1 feasibility result.
- DECISIONS marks grouped splitting as implemented and adds D-055
  for the deterministic group-aware splitting contract.
- STATUS moves group-aware splitting to completed work and makes the
  controlled multi-group dataset expansion the next milestone.
