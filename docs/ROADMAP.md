# ROADMAP

## Phase 0 — Project foundation
Status: In progress

- Central documents
- Repository
- Local environment
- Initial architecture

## Phase 1 — End-to-end proof of concept
Status: Completed

- Deploy TOP-01
- Validate normal routing
- Inject missing-route fault
- Collect evidence
- Produce rule-based diagnosis
- Evaluate against ground truth

## Phase 2 — Pilot multiclass dataset
Status: Completed

- Dataset artifact contracts: completed and tested
- Normal: canonical, alternate-subnet, G02, G03, G04, and G05 smoke
  executions completed
- Missing route: canonical, alternate-subnet, G02, G03, G04, and G05
  smoke executions completed
- Wrong next-hop: canonical, alternate-subnet, G02, G03, G04, and G05
  smoke executions completed
- Batch Plan v1 contract and canonical smoke plan: completed
  and tested
- Reproducible batch runner and dataset aggregation: implemented,
  tested, and verified through the first real canonical smoke batch
- Canonical B0 smoke batch: completed and semantically verified;
  three-row smoke dataset generated
- Complete evaluation-context-aware splitting: implemented, tested,
  and verified through the first valid five-context split
- G02 TOP_02_CHAIN: implemented and smoke-verified
- G03 TOP_02_BRANCH: implemented and smoke-verified
- G04 TOP_02_DUAL_TRANSIT: implemented and smoke-verified
- G05 TOP_03_ASYMMETRIC_RETURN: implemented and smoke-verified
- Five-context two-repetition campaign: G01 bindings, five context
  batches, Dataset Campaign Plan v1, and deterministic split
  precommitment completed and tested
- Cross-topology campaign coordinator: implemented and tested
- Real P2_ROUTING_5CTX_V1 campaign: 30/30 experiments completed and
  independently audited
- Atomic merged Dataset Row v2 dataset: 30 rows accepted
- Rule-based campaign reference audit: 30/30 exact matches and
  affected-prefix checks
- First valid five-context split: completed with 18/6/6 rows,
  3/1/1 groups, and no cross-partition group
- Wrong gateway: deferred to Phase 6
- Interface down: deferred to Phase 6
- ACL block: deferred to Phase 6

## Phase 3 — Rule-based baseline
Status: Completed

- Existing deterministic rule engine retained as the traditional
  baseline
- Campaign reference audit completed separately from model features
- Formal Method Evaluation Protocol v1: frozen
- Method Evaluation Result v1 runtime contract and JSON Schema:
  implemented and tested
- Shared partition roles and comparable per-class/macro metrics:
  implemented and tested
- P2-R10 rule-audit adapter with hashed evidence and explanation
  provenance: implemented and tested
- Real 30-record partition-aware rule-based result: completed and
  independently verified
- Train/validation/test accuracy and macro F1: 1.0/1.0/1.0 under the
  frozen controlled campaign
- Report SHA-256 and 150/150 source-artifact bindings: recorded
- P3-R0 closeout and HANDOFF: completed

## Phase 4 — Machine Learning baseline
Status: Completed

- Leakage-safe ML experiment protocol and feature-matrix contract:
  implemented and verified against the real D-067 artifacts
- Lossless seven-tri-state to 14-binary-column transformation:
  implemented and tested
- Predictor leakage gates and immutable partition roles: implemented
  and tested
- Bounded logistic-regression and shallow-tree candidate set:
  precommitted before fitting
- Real 30-record ML Feature Matrix v1: completed and independently
  verified
- Matrix SHA-256, 30/30 source-row bindings, and ten structural
  unavailable values: recorded
- P4-R0 closeout and HANDOFF: completed
- Train-only candidate fitting and validation-only selection
  implementation: completed and covered by 10 targeted tests and
  the 205-test regression suite
- Atomic ML Pipeline Selection v1 and selected-estimator freeze:
  executed and independently hash-verified
- Independent model/selection hash gate before test access:
  executed successfully before G02 access
- Evidence-bearing ML predictions with model-specific explanation:
  completed for 30/30 rows
- Selected candidate: logreg_l2_c0_1
- Single report-only G02 evaluation: completed without refit
- Fault-type accuracy and macro-F1: 1.0/1.0/1.0 on
  train/validation/test for the frozen controlled campaign
- Exact-diagnosis rate: 1/3 per partition; affected-prefix rate: 0.0,
  exposing the independent classifier's localization boundary
- Method Evaluation Result v1 ML report, selection SHA-256, model
  SHA-256, and 150/150 source-artifact bindings: recorded
- P4-R1 closeout and HANDOFF: completed

## Phase 5 — Hybrid diagnosis
Status: In progress

- P5-R0 Hybrid Diagnosis Policy v1 design: frozen and locally
  runtime-verified
- Accepted D-069 and D-073 artifact/hash bindings: encoded without
  changing either baseline
- Prediction-time label, ground-truth, partition, evaluation, and
  test leakage boundary: encoded
- Candidate set: consensus_abstain_v1 and
  rule_guarded_fallback_v1
- Agreement, disagreement, non-final-input, localization, prefix,
  explanation, and integrity-failure behavior: precommitted
- Validation-only candidate selection and deterministic tie-break
  order: precommitted for P5-R1
- Abstention-aware future evaluation and seven-reference hybrid
  provenance contract: precommitted
- Hybrid Policy v1 JSON Schema and semantic validator: implemented
  and verified with 11/11 targeted and 216/216 regression tests
- Policy SHA-256 and five accepted baseline artifact bindings:
  independently verified without baseline mutation
- Hybrid predictions, candidate selection, hybrid metrics, and G02
  access: absent in P5-R0
- P5-R0 closeout and HANDOFF: completed
- P5-R1 candidate implementation, Hybrid Prediction/Selection
  schemas, abstention-aware evaluator, and independent verifier:
  implemented and runtime-verified
- P5-R1 validation-only run: 48 predictions, 48 evaluations, two
  manifests, and 99 runtime JSON files; no test output
- P5-R1 selected candidate: consensus_abstain_v1 by the frozen
  complexity tie-break after equal train/validation metrics
- P5-R1 selected-policy SHA-256 and independent freeze verification:
  completed
- P5-R1 tests: 14/14 targeted and 229/229 full regression passed
- P5-R1 HANDOFF and closeout: completed
- P5-R2 frozen-policy report-only evaluation: pending

## Phase 6 — Extended fault taxonomy
Status: Not started

## Phase 7 — Dashboard and API
Status: Not started

## Phase 8 — Experiments and evaluation
Status: Not started

## Phase 9 — Thesis writing and defense
Status: Not started
