# HANDOFF — P2-R9 Dataset Campaign Binding and Plan

Date: 2026-07-31
Status: COMPLETED

## 1. What was completed

- Added three explicit G01 TOP-01 campaign scenarios for N0, C1, and
  C2 using CTX_G01_TOP01_LINEAR_2R.
- Preserved all historical TOP-01 scenarios, experiment artifacts,
  rows, and split-group metadata.
- Added one two-repetition Batch Plan v1 for each context G01-G05.
- Added the canonical P2_ROUTING_5CTX_V1 campaign plan.
- Implemented Dataset Campaign Plan v1 runtime validation.
- Added the Dataset Campaign Plan v1 JSON Schema.
- Bound every context to its topology, executable validator, Batch
  Plan v1, direction, observer, transit, and frozen split group.
- Validated the exact class order N0/C1/C2 and two repetitions per
  class and context.
- Verified six planned experiments per context and exactly 30 across
  the campaign.
- Precommitted the D-058 deterministic 3/1/1 group allocation using
  seed 20260730 and ratios 0.6/0.2/0.2.
- Added nine targeted P2-R9 tests.
- Passed 9/9 targeted tests and the complete 164/164 regression
  suite.
- Documented the future coordinator, merge, quality, rule-audit, and
  split acceptance gates.

## 2. What was decided

- D-065 accepts Dataset Campaign Plan v1 and
  P2_ROUTING_5CTX_V1 as the canonical first ML-readiness campaign
  input.
- The campaign is one logical fail-stop unit composed of five ordered
  per-laboratory Batch Plan v1 jobs.
- Batch Runner v1 remains a single-laboratory executor and is not
  changed to switch topologies or validators inside one batch.
- G01 uses three new scenario bindings rather than relabelling
  historical scenarios or rows.
- G02-G05 reuse their verified scenario bindings unchanged.
- The exact planned dataset is:
  5 contexts x 3 classes x 2 repetitions = 30 Dataset Row v2 records.
- The frozen expected split is:
  - train: G03, G04, G05;
  - validation: G01; and
  - test: G02.
- The split is a pre-run hash consequence, not a result-dependent
  context selection.
- The first campaign requires zero unavailable features as a
  campaign-specific quality gate while preserving tri-state Dataset
  Row v2 and the later missing-evidence scope.
- Rule-based exact match is audited separately and never becomes a
  model feature or a synonym for Batch Runner completion.
- ML and hybrid diagnosis remain blocked.

## 3. Files created or changed

Created campaign contract files:

- src/campaign/__init__.py
- src/campaign/plan.py
- schemas/dataset_campaign_plan_v1.schema.json
- plans/campaigns/P2_ROUTING_5CTX_V1.yml

Created G01 campaign scenarios:

- scenarios/routing/N0_NORMAL_OPERATION_G01_TOP01_LINEAR_2R.yml
- scenarios/routing/C1_MISSING_STATIC_ROUTE_G01_TOP01_LINEAR_2R.yml
- scenarios/routing/C2_WRONG_NEXT_HOP_G01_TOP01_LINEAR_2R.yml

Created context batch plans:

- plans/batches/P2_G01_CAMPAIGN.yml
- plans/batches/P2_G02_CAMPAIGN.yml
- plans/batches/P2_G03_CAMPAIGN.yml
- plans/batches/P2_G04_CAMPAIGN.yml
- plans/batches/P2_G05_CAMPAIGN.yml

Created tests and documentation:

- tests/unit/test_p2_r9_dataset_campaign_plan.py
- docs/DATASET_CAMPAIGN_DESIGN.md
- docs/HANDOFF_P2_R9.md

Changed central documents:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/ROADMAP.md
- docs/EVALUATION_GROUP_PROTOCOL.md
- docs/TOP02_CONTEXT_DESIGN.md

No runtime experiment, evidence, batch result, merged dataset, split,
ML model, or hybrid artifact was created.

## 4. Open issues

- Implement a cross-topology campaign coordinator that consumes only
  the frozen Dataset Campaign Plan v1 contract.
- Define and implement the campaign result and atomic merge output.
- Verify the five accepted context artifact fingerprints before
  execution.
- Execute all 30 experiments under one campaign run.
- Apply the exact per-row, per-group, role-binding, quality, and
  source-provenance gates.
- Produce the separate 30-row rule-based reference audit.
- Create and verify the first real D-058 split manifest and
  train/validation/test files.
- Implement the ML baseline only after the campaign closeout passes.
- Implement hybrid diagnosis only after the ML baseline.

## 5. Next step

Start P2-R10 — Campaign Coordinator, Real Execution, Merge, and Split.

P2-R10 must:

- preserve P2_ROUTING_5CTX_V1 unchanged;
- implement fail-stop G01-G05 laboratory coordination;
- deploy only one topology at a time;
- verify initial and final baselines and cleanup for every context;
- execute exactly five six-experiment Batch Plan v1 jobs;
- accept only 30/30 complete Dataset Row v2 records from one campaign
  run;
- merge the five datasets atomically;
- verify all gates in docs/DATASET_CAMPAIGN_DESIGN.md;
- keep the rule-based reference audit separate;
- invoke the existing splitter with the frozen seed and ratios;
- verify exact 18/6/6 row and 3/1/1 group counts;
- prove no group crosses partitions; and
- stop before ML training or hybrid implementation.

## 6. Impact on central documents

- MASTER_CONTEXT records the implemented campaign contract and
  explicitly distinguishes it from real campaign execution.
- DECISIONS adds D-065 without changing D-058 or weakening the
  readiness gate.
- STATUS records the 30-experiment plan, expected split, tests, and
  P2-R10 boundary.
- ROADMAP marks campaign binding and plan validation complete and
  identifies coordinator implementation and real execution as next.
- EVALUATION_GROUP_PROTOCOL records G01 future bindings and the
  precommitted whole-context split.
- TOP02_CONTEXT_DESIGN removes superseded G01/G05 implementation-state
  text while preserving its G02-G04 normative scope.
- DATASET_CAMPAIGN_DESIGN is the normative P2-R10 execution and
  acceptance specification.
