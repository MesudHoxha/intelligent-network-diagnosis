# HANDOFF — P5-R2 Frozen-Policy Report and Three-Method Comparison

Date: 2026-08-05

Status: COMPLETED

## 1. What was completed

P5-R2 performed the single authorized report-only evaluation of the
frozen consensus_abstain_v1 hybrid policy on the held-out G02 group
and completed the first Rule-based versus Machine Learning versus
Hybrid comparison under one frozen protocol.

Accepted verification evidence:

- policy, five baselines, and selected-policy freeze gate: PASS;
- selected candidate: consensus_abstain_v1;
- selection SHA-256:
  59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507;
- G02 selected-candidate predictions: 6/6 PASS;
- G02 evaluations: 6/6 PASS;
- all predictions completed before test ground-truth evaluation;
- hybrid report rows: 30 with 18/6/6 partition binding;
- hybrid artifact references: 210/210 SHA-256 PASS;
- atomic runtime JSON set: 14/14 PASS;
- independent report verification: PASS;
- targeted tests: 14/14 PASS;
- complete regression suite: 243/243 PASS;
- test use: report_only;
- test influenced policy or selection: false; and
- statistical-superiority claim: absent.

The hybrid result on G02 has 1.0 macro-F1, 1.0 exact-diagnosis rate,
1.0 affected-prefix correctness, 1.0 coverage, and zero abstentions.

The accepted hybrid report SHA-256 is:

e990a29882f1b7cec4fe003ee5ee65b3fa3dfd25250092a0f9f2a908074a9c75

The accepted cross-method comparison SHA-256 is:

eebf97dfe340a05feba70874f54727e1a8ccf7ce4224301f162544537d8ecf80

The 36 joblib/NumPy deprecation warnings were inherited from the
accepted P4-R1 regression tests and did not affect report generation,
metrics, or artifact integrity.

## 2. What was decided

D-076 is accepted and runtime-verified. P5-R2 and Phase 5 are closed
for the frozen P2_ROUTING_5CTX_V1 campaign.

The cross-method result is descriptive. Rule-based and Hybrid both
retain complete diagnosis and affected-prefix localization in the
accepted campaign. Machine Learning classifies fault_type correctly
but, by its frozen class-only contract, does not invent location or
affected-prefix values. The hybrid therefore restores complete
diagnosis by using only rule-provided localization when the frozen
fusion policy accepts a class.

The six-row G02 result cannot establish statistical superiority,
robustness across new fault families, or real-world generalization.
No policy, threshold, model, selection, or baseline may be changed in
response to the test result.

## 3. Files created or changed

P5-R2 committed files:

- docs/DECISIONS.md;
- docs/HANDOFF_P5_R2.md;
- docs/HYBRID_DIAGNOSIS_POLICY.md;
- docs/HYBRID_ENGINE_IMPLEMENTATION.md;
- docs/MASTER_CONTEXT.md;
- docs/METHOD_EVALUATION_PROTOCOL.md;
- docs/P5_R2_REPORT_IMPLEMENTATION.md;
- docs/ROADMAP.md;
- docs/STATUS.md;
- schemas/cross_method_comparison_v1.schema.json;
- src/hybrid/reporting.py; and
- tests/unit/test_p5_r2_hybrid_reporting.py.

The ignored runtime directory
reports/experiments/p5_r2_hybrid_baseline_v1 contains six G02 hybrid
predictions, six evaluations, method_evaluation_result.json, and
cross_method_comparison.json. These files are verified experimental
evidence but are not committed source files.

No Hybrid Policy v1 byte, P5-R1 selection byte, rule/ML baseline,
feature matrix, ML estimator, or development hybrid output changed.

## 4. Open issues

- Freeze the bounded Phase 6 fault taxonomy before implementation.
- Define evidence and controlled injection for wrong_gateway,
  interface_down, and acl_block candidate classes.
- Add missing-evidence and unseen-context experiments without mixing
  related contexts across dataset partitions.
- Expand the number and diversity of complete evaluation contexts
  before any statistical or real-world claim.
- Define a reproducible archive or publication policy for ignored
  runtime datasets and reports before thesis release.
- Keep OSPF proposed until its academic value, scope, and test plan
  are approved.

## 5. Next step

Start P6-R0 — Extended Fault Taxonomy and Evaluation Plan.

P6-R0 should remain design-first. It must bound the new classes,
their evidence signatures, topology needs, injection/restoration
contracts, class balance, split-group policy, missing-evidence cases,
and acceptance tests before new Containerlab execution or dataset
collection. Existing P2-P5 artifacts remain immutable references.

## 6. Impact on central documents

- DECISIONS marks D-076 accepted and runtime-verified.
- MASTER_CONTEXT records the real G02 result, both report hashes, and
  the descriptive-only interpretation.
- HYBRID_DIAGNOSIS_POLICY records execution without changing the
  frozen policy artifact.
- HYBRID_ENGINE_IMPLEMENTATION records the accepted coordinator and
  independent verification evidence.
- METHOD_EVALUATION_PROTOCOL records the complete hybrid report and
  unchanged report_only test role.
- P5_R2_REPORT_IMPLEMENTATION records the real accepted outputs.
- ROADMAP marks Phase 5 completed and identifies Phase 6 planning.
- STATUS records P5-R2 closeout and P6-R0 as the next milestone.
