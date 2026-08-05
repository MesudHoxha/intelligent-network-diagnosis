# HANDOFF — P3-R0 Formal Rule-Based Baseline

Date: 2026-08-05
Status: COMPLETED

## 1. What was completed

- Froze Formal Method Evaluation Protocol v1 for rule-based, Machine
  Learning, and hybrid diagnostic methods.
- Implemented Method Evaluation Result v1 and its JSON Schema.
- Implemented the partition-aware adapter over the separate P2-R10
  rule audit without modifying the Rule Engine.
- Preserved the D-067 campaign, dataset, groups, split, features,
  labels, predictions, and test role unchanged.
- Recalculated accuracy, per-class precision/recall/F1, macro
  metrics, fixed-order confusion matrices, exact diagnosis match,
  and fault-only affected-prefix correctness.
- Bound every sample to its Manifest, ground truth, Evidence v2,
  prediction, and per-experiment evaluation with path and SHA-256.
- Executed the adapter against the accepted runtime artifacts and
  generated the first real 30-record rule-based baseline report.
- Verified 30/30 split mappings and 150/150 artifact references.
- Passed 10/10 targeted tests and 185/185 full regression tests.

Accepted result:

- result ID: p3_r0_rule_based_baseline_v1
- report path:
  reports/experiments/p3_r0_rule_based_baseline_v1.json
- report SHA-256:
  7158f1de31a892779bbce2eaad8f5c5e5bb7c2fc08e0766b49a55047ddc56424
- rows: 30
- partition rows: 18/6/6
- partition groups: 3/1/1
- train accuracy / macro F1: 1.0 / 1.0
- validation accuracy / macro F1: 1.0 / 1.0
- test accuracy / macro F1: 1.0 / 1.0
- exact diagnosis match: 30/30
- fault-only affected-prefix correctness: 20/20
- source-artifact references: 150/150 SHA-256 PASS

## 2. What was decided

- D-068 establishes Method Evaluation Result v1 as the shared
  comparison contract and macro F1 as the primary metric.
- D-069 accepts the real P3-R0 result as the traditional baseline for
  the frozen controlled campaign.
- Train remains development, validation remains selection, and G02
  test remains report_only.
- The overall 30-row result remains descriptive_only.
- The generated report remains a local ignored runtime artifact; its
  result ID, path, and SHA-256 are the recorded binding.
- Classification metrics remain distinct from full-diagnosis and
  fault-localization checks.
- The perfect values are not evidence of real-world generalization,
  statistical superiority, or ML/hybrid performance.

## 3. Files created or changed

Created implementation and contract files:

- docs/METHOD_EVALUATION_PROTOCOL.md
- schemas/method_evaluation_result_v1.schema.json
- src/evaluation/reporting.py
- tests/unit/test_p3_r0_evaluation_reporting.py

Created closeout document:

- docs/HANDOFF_P3_R0.md

Changed central documents:

- docs/DECISIONS.md
- docs/MASTER_CONTEXT.md
- docs/ROADMAP.md
- docs/STATUS.md

Runtime artifact created locally and intentionally excluded from the
implementation commit:

- reports/experiments/p3_r0_rule_based_baseline_v1.json

## 4. Open issues

- Freeze the leakage-safe ML feature transformation and experiment
  protocol before fitting a model.
- Select a small interpretable supervised baseline appropriate for
  18 training rows and seven tri-state features.
- Fit only on train and use validation only for model/pipeline
  selection.
- Evaluate G02 test once after the ML pipeline is frozen and emit the
  same Method Evaluation Result v1 contract.
- Implement the hybrid policy only after the independent ML baseline
  exists.
- Add broader contexts, repetitions, fault classes, and missing-
  evidence experiments before making generalization claims.
- Define reproducible backup or publication policy for generated
  runtime artifacts before final thesis archiving.

## 5. Next step

Start P4-R0 — Leakage-Safe ML Baseline Protocol and Feature Matrix.

P4-R0 must:

- preserve D-067, D-068, and D-069 unchanged;
- use fault_type as the supervised target and only the approved seven
  Dataset Row v2 diagnostic features as predictor inputs;
- exclude ground truth, rule outputs, evaluations, identifiers,
  paths, hashes, and explanation text from the feature matrix;
- precommit missing-value handling, deterministic seeds, candidate
  model families, and bounded selection criteria;
- fit only on train and select only on validation;
- keep G02 test unopened for selection and use it once only after the
  complete ML pipeline is frozen;
- reuse Method Evaluation Result v1 for the ML result; and
- stop before designing or evaluating the hybrid method.

## 6. Impact on central documents

- MASTER_CONTEXT records the accepted report, metrics, SHA-256, and
  interpretation boundary.
- DECISIONS updates D-068 to runtime-verified and adds D-069.
- STATUS closes P3-R0, moves the active phase to Phase 4, and names
  P4-R0 as the next milestone.
- ROADMAP marks Phase 3 completed and Phase 4 in progress.
- METHOD_EVALUATION_PROTOCOL records the accepted real baseline and
  its cryptographic binding.
