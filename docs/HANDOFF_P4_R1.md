# HANDOFF — P4-R1 Machine Learning Baseline

Date: 2026-08-05

Status: COMPLETED

## 1. What was completed

P4-R1 implemented and executed the first independent Machine Learning
baseline over the accepted D-071 feature matrix.

The implementation:

- instantiated exactly the six D-070 candidate configurations;
- fitted every candidate only on the 18 train rows;
- calculated selection metrics only on the six validation rows;
- applied the frozen macro-F1, accuracy, complexity-rank, and
  candidate-ID tie-break order;
- selected logreg_l2_c0_1, a multinomial logistic-regression model
  with L2 regularization and C=0.1;
- serialized the selected train-only estimator without refitting on
  validation or test;
- persisted and hash-bound ML Pipeline Selection v1 before test
  access;
- independently reverified the freeze before opening G02 once as
  report_only;
- produced evidence-bearing model explanations for 30/30 rows; and
- emitted and validated the ML Method Evaluation Result v1.

The real accepted results are:

- rows: 30;
- partition rows: 18/6/6;
- partition groups: 3/1/1;
- train accuracy / macro-F1: 1.0 / 1.0;
- validation accuracy / macro-F1: 1.0 / 1.0;
- test accuracy / macro-F1: 1.0 / 1.0;
- exact-diagnosis rate: 0.3333333333333333 in every partition;
- affected-prefix rate: 0.0 in every partition;
- source-artifact references: 150/150 SHA-256 PASS;
- test use: report_only PASS; and
- model refit during reporting or recovery: ABSENT.

The first report command stopped because its delivery script supplied
reports/experiments as the source-experiment root. The canonical
source artifacts are under data/raw. Recovery verified the existing
selection and model hashes, verified 90/90 canonical source artifacts,
changed only that runtime argument, and resumed reporting without
training or refitting.

Ten targeted tests and the complete 205-test regression suite passed.
The observed joblib/NumPy deprecation warnings were non-fatal and did
not change any artifact or result.

## 2. What was decided

D-072 remains the approved two-stage pipeline-freeze and report gate.

D-073 accepts the first independent ML baseline with these immutable
artifact identities:

- feature matrix SHA-256:
  9193b4b8c676bf94ef9af05562d9d0047faef61bc94c9d81b0485b88bf599730;
- selection SHA-256:
  a02536d6f2478d9fdc40510275dd3b48a2824ee7b1f0fa08c1aed472611fb6fb;
- selected estimator SHA-256:
  90db38e625f4bcf6a234b6a0516371b76f98e01b4437f684ffea119cbc09cdb2;
  and
- ML report SHA-256:
  8fc6e77e5008cd7cc74e5ce130b901ed750afab9a35eb62652ff55f9205b0e92.

The ML baseline predicts only fault_type. It does not copy or infer
fault_location or affected_prefix. Its lower exact-diagnosis and
affected-prefix metrics are therefore accepted limitations, not
missing values to be repaired from labels, metadata, or rule output.

The result closes P4-R1 and Phase 4. It does not establish real-world
generalization, statistical superiority over the rule-based baseline,
or hybrid performance. Phase 5 must freeze its hybrid policy before
implementation or evaluation.

## 3. Files created or changed

Committed P4-R1 files:

- docs/DECISIONS.md;
- docs/HANDOFF_P4_R1.md;
- docs/MASTER_CONTEXT.md;
- docs/METHOD_EVALUATION_PROTOCOL.md;
- docs/ML_BASELINE_PROTOCOL.md;
- docs/ROADMAP.md;
- docs/STATUS.md;
- pyproject.toml;
- schemas/method_evaluation_result_v1.schema.json;
- schemas/ml_pipeline_selection_v1.schema.json;
- src/evaluation/reporting.py;
- src/ml/baseline.py; and
- tests/unit/test_p4_r1_ml_baseline.py.

Generated local runtime artifacts, intentionally ignored by Git:

- models/p4_r1_ml_pipeline_v1/estimator.joblib;
- models/p4_r1_ml_pipeline_v1/selection.json; and
- reports/experiments/p4_r1_ml_baseline_v1/
  method_evaluation_result.json.

The accepted P4-R0 feature matrix and all D-067 data/raw artifacts were
read and hash-verified but were not modified.

## 4. Open issues

- The hybrid decision and provenance contract is not yet frozen.
- The hybrid method is not implemented or evaluated.
- The ML baseline does not localize faults or affected prefixes.
- The campaign contains only 30 controlled rows from five contexts;
  validation and test contain one context each.
- Unseen-context, missing-evidence, multiple-fault, and extended-class
  experiments remain future work.
- Generated data, model, and report artifacts still require a final
  reproducible archive or publication policy before thesis release.
- The current NumPy 2.5/joblib combination emits a non-blocking
  serialization deprecation warning in tests; dependency upgrades
  must preserve the accepted artifact contract and reproducibility.

## 5. Next step

Start P5-R0 — Freeze the Hybrid Diagnosis Policy.

P5-R0 must:

- consume the accepted D-069 rule result and D-073 ML pipeline/report
  identities without modifying either baseline;
- define the exact hybrid inputs available at prediction time;
- define deterministic agreement, disagreement, abstention,
  localization, affected-prefix, and explanation behavior;
- define method-specific provenance for a future hybrid Method
  Evaluation Result v1;
- precommit any bounded policy alternatives and validation-only
  selection order before implementation;
- preserve the D-067 campaign and D-058 group-aware split; and
- keep G02 closed and emit no hybrid prediction or metric during
  P5-R0.

## 6. Impact on central documents

- DECISIONS adds D-073 and accepts the real independent ML baseline.
- MASTER_CONTEXT records the frozen pipeline identities, the real
  report, and the classifier's localization boundary.
- METHOD_EVALUATION_PROTOCOL records the accepted P4-R1 result under
  the shared comparison contract.
- ML_BASELINE_PROTOCOL changes from implementation-ready to real
  runtime-accepted status.
- ROADMAP closes Phase 4 and leaves Phase 5 as the next phase.
- STATUS moves the current phase to Phase 5, records the full P4-R1
  audit, and names P5-R0 as the next milestone.
