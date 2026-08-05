# HANDOFF — P5-R1 Hybrid Engine and Validation Selection

Date: 2026-08-05

Status: COMPLETED

## 1. What was completed

P5-R1 implemented both candidates frozen by D-074, evaluated them
only on train and validation, selected one policy by the precommitted
validation order, and independently verified the selected-policy
artifact before any G02 hybrid access.

The milestone:

- preserved Hybrid Policy v1 byte-for-byte;
- preserved all five accepted rule/ML baseline artifact hashes;
- implemented Hybrid Prediction v1 and Hybrid Selection v1;
- kept prediction separate from ground-truth evaluation;
- generated both candidates for all 24 development samples before
  evaluation;
- implemented full-denominator abstention accounting;
- extended Method Evaluation Result v1 backwards-compatibly for the
  future hybrid report;
- selected from six G01 validation rows only; and
- independently recomputed and verified the winner and all runtime
  references before G02 access.

Accepted verification evidence:

- candidate predictions: 48/48 PASS;
- candidate evaluations: 48/48 PASS;
- candidate manifests: 2/2 PASS;
- runtime JSON files: 99/99 PASS;
- prediction partitions: train and validation only;
- selection partition: validation only;
- held-out partition: test;
- targeted tests: 14/14 PASS;
- complete regression suite: 229/229 PASS;
- policy plus baseline hashes: 6/6 SHA-256 PASS;
- test predictions and metrics: absent; and
- raw G02 hybrid outputs and P5-R2 report: absent.

Both candidates obtained 1.0 full-denominator macro-F1, 1.0 exact
diagnosis, and 1.0 coverage on train and validation, with zero
validation abstentions.

The selected candidate is consensus_abstain_v1 with complexity rank
0. The selected-policy SHA-256 is:

59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507

The 36 joblib/NumPy deprecation warnings were inherited from the
accepted P4-R1 tests and did not affect selection or artifact
integrity.

## 2. What was decided

D-075 is accepted and runtime-verified.

Because the two candidates tied on every reported train/validation
selection metric, the precommitted complexity rule selected
consensus_abstain_v1. This is a deterministic tie-break outcome; it
does not demonstrate empirical superiority over
rule_guarded_fallback_v1.

The selected policy is now frozen. P5-R2 may not refit the ML model,
rerun candidate selection, tune thresholds, change D-074, or replace
the winner after observing G02. It may evaluate only the frozen
consensus_abstain_v1 policy on the held-out test group.

P5-R1 closes only implementation and validation selection. It does
not establish hybrid test performance, complete the cross-method
comparison, or close Phase 5.

## 3. Files created or changed

P5-R1 committed files:

- docs/DECISIONS.md;
- docs/HANDOFF_P5_R1.md;
- docs/HYBRID_DIAGNOSIS_POLICY.md;
- docs/HYBRID_ENGINE_IMPLEMENTATION.md;
- docs/MASTER_CONTEXT.md;
- docs/METHOD_EVALUATION_PROTOCOL.md;
- docs/ROADMAP.md;
- docs/STATUS.md;
- schemas/hybrid_prediction_v1.schema.json;
- schemas/hybrid_selection_v1.schema.json;
- schemas/method_evaluation_result_v1.schema.json;
- src/evaluation/reporting.py;
- src/hybrid/engine.py;
- tests/unit/test_p3_r0_evaluation_reporting.py; and
- tests/unit/test_p5_r1_hybrid_engine.py.

The ignored runtime directory
models/p5_r1_hybrid_policy_v1 contains the selected-policy artifact,
two candidate manifests, 48 predictions, and 48 evaluations. Those
runtime files are verified experiment evidence but are not committed
source files.

No D-074 policy byte, rule baseline, feature matrix, ML selection,
ML estimator, or ML report was changed.

## 4. Open issues

- Reverify the committed P5-R1 implementation and the selected-policy
  hash before opening G02.
- Generate only the selected candidate's six held-out test
  predictions.
- Produce and validate the first complete hybrid Method Evaluation
  Result v1 with seven hashed sample references.
- Compare rule-based, ML, and hybrid results under the same frozen
  protocol without turning descriptive values into a statistical
  superiority claim.
- Keep G02 report_only and prohibit policy tuning, refit, or
  reselection.
- Broaden contexts, repetitions, missing-evidence cases, and fault
  classes before any real-world generalization claim.
- Define a reproducible archive or publication policy for ignored
  runtime artifacts before thesis release.

## 5. Next step

Start P5-R2 — Frozen-Policy Report-Only G02 Evaluation.

P5-R2 must:

- bind to the committed P5-R1 source state;
- verify the unchanged Hybrid Policy v1 SHA-256;
- verify all five accepted baseline hashes;
- verify selection SHA-256
  59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507;
- confirm consensus_abstain_v1 as the frozen winner;
- refuse refit, reselection, tuning, or policy mutation;
- generate only the six G02 test predictions for the selected policy;
- produce the hybrid Method Evaluation Result v1 and provenance
  audit; and
- close Phase 5 only if the report and cross-method comparison pass.

## 6. Impact on central documents

- DECISIONS marks D-075 accepted and runtime-verified.
- MASTER_CONTEXT records the selected candidate, tie-break, selection
  SHA-256, and unchanged G02 boundary.
- HYBRID_DIAGNOSIS_POLICY records the accepted selection without
  changing the frozen policy artifact.
- HYBRID_ENGINE_IMPLEMENTATION records the real runtime evidence and
  independent verification.
- METHOD_EVALUATION_PROTOCOL records the completed validation-only
  evaluator use and keeps G02 report-only.
- ROADMAP closes P5-R1 while keeping Phase 5 in progress.
- STATUS records P5-R1 as completed and names P5-R2 as the next
  milestone.
