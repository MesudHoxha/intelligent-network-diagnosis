# HANDOFF — P4-R0 Leakage-Safe ML Feature Matrix

Date: 2026-08-05
Status: COMPLETED

## 1. What was completed

- Froze Leakage-Safe Machine Learning Baseline Protocol v1 before
  fitting any estimator.
- Implemented ML Feature Matrix v1 and its JSON Schema.
- Restricted predictors to the seven ordered Dataset Row v2
  diagnostic features and kept fault_type as a separate target.
- Implemented the lossless tri-state available/true encoding with 14
  ordered binary columns and no learned preprocessing.
- Excluded labels, metadata, quality, ground truth, rule outputs,
  evaluations, identifiers, paths, hashes, and explanation text from
  predictors.
- Froze six bounded logistic-regression and shallow-tree candidates,
  deterministic selection tie-breakers, and seed 20260730.
- Preserved train-only fitting, validation-only selection, no
  train-plus-validation refit, and G02 test as report_only.
- Executed the builder against the accepted D-067 runtime artifacts.
- Verified 30/30 source-row references, partition/hash binding,
  balanced class coverage, and the predictor-leakage audit.
- Passed 10/10 targeted tests and 195/195 full regression tests.

Accepted result:

- matrix ID: p4_r0_ml_feature_matrix_v1
- artifact path:
  reports/experiments/p4_r0_ml_feature_matrix_v1.json
- artifact SHA-256:
  9193b4b8c676bf94ef9af05562d9d0047faef61bc94c9d81b0485b88bf599730
- rows: 30
- partition rows: 18/6/6
- partition groups: 3/1/1
- raw features: 7
- encoded features: 14
- structural unavailable values: 10
- source-row references: 30/30 SHA-256 PASS
- test use: report_only
- ML fitting, predictions, and metrics: absent

## 2. What was decided

- D-070 establishes the immutable leakage-safe preprocessing,
  candidate, fitting, selection, and test boundary.
- D-071 accepts the real feature matrix as the deterministic pre-fit
  input for the first ML baseline.
- The available/true pair is the only approved tri-state encoding for
  this baseline; no learned imputation or partition-derived statistic
  is permitted.
- The six candidates and their parameters cannot be changed after
  seeing validation or test results.
- The selected estimator remains fitted on train only and is not
  refitted on train plus validation.
- G02 test may be evaluated once only after the winning pipeline is
  frozen and persisted.
- The generated matrix remains a local ignored runtime artifact; its
  matrix ID, path, and SHA-256 are the recorded binding.
- Matrix acceptance is an input-integrity result, not an ML
  performance or generalization result.

## 3. Files created or changed

Created implementation and contract files:

- docs/ML_BASELINE_PROTOCOL.md
- schemas/ml_feature_matrix_v1.schema.json
- src/ml/__init__.py
- src/ml/feature_matrix.py
- tests/unit/test_p4_r0_ml_feature_matrix.py

Created closeout document:

- docs/HANDOFF_P4_R0.md

Changed central documents:

- docs/DECISIONS.md
- docs/MASTER_CONTEXT.md
- docs/ROADMAP.md
- docs/STATUS.md

Runtime artifact created locally and intentionally excluded from the
implementation commit:

- reports/experiments/p4_r0_ml_feature_matrix_v1.json

## 4. Open issues

- Implement the six frozen estimator configurations without changing
  the accepted matrix or protocol.
- Fit only on train and produce candidate metrics only for train and
  validation before selection.
- Select the winner with the precommitted validation-only rule and
  persist its full identity, parameters, software versions, and
  artifact hash.
- Open G02 test exactly once only after the pipeline freeze and emit
  the ML Method Evaluation Result v1.
- Implement the hybrid policy only after the independent ML baseline
  is complete.
- Add broader contexts, repetitions, fault classes, and missing-
  evidence experiments before making generalization claims.
- Define reproducible backup or publication policy for generated
  runtime artifacts before final thesis archiving.

## 5. Next step

Start P4-R1 — Train, Select, Freeze, and Report the ML Baseline.

P4-R1 must:

- consume only the accepted D-071 matrix and preserve its SHA-256;
- implement exactly the six D-070 candidate configurations;
- fit candidate parameters only on train;
- use validation macro F1, validation accuracy, complexity rank, and
  candidate ID as the only selection order;
- persist and verify the winning train-only pipeline before any test
  prediction or metric is produced;
- evaluate G02 test once as report_only after the freeze;
- emit Method Evaluation Result v1 for machine_learning; and
- stop before designing or evaluating the hybrid method.

## 6. Impact on central documents

- MASTER_CONTEXT records the accepted matrix, dimensions, SHA-256,
  leakage audit, and interpretation boundary.
- DECISIONS updates D-070 to runtime-verified and adds D-071.
- STATUS closes P4-R0 and names P4-R1 as the next milestone.
- ROADMAP records the real feature matrix and P4-R0 closeout.
- ML_BASELINE_PROTOCOL records the accepted runtime artifact and its
  cryptographic binding.
