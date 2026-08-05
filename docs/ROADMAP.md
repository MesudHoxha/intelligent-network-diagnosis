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
Status: In progress

- Leakage-safe ML experiment protocol and feature-matrix contract:
  next target
- Interpretable supervised baseline trained only on the frozen train
  partition: not started
- Validation-only selection before a single report-only test
  evaluation: not started
- Method Evaluation Result v1 ML report: not started

## Phase 5 — Hybrid diagnosis
Status: Not started

## Phase 6 — Extended fault taxonomy
Status: Not started

## Phase 7 — Dashboard and API
Status: Not started

## Phase 8 — Experiments and evaluation
Status: Not started

## Phase 9 — Thesis writing and defense
Status: Not started
