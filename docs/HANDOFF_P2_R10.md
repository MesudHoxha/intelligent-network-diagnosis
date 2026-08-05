# HANDOFF — P2-R10 Campaign Coordinator, Execution, Merge, and Split

Date: 2026-08-04
Status: COMPLETED

## 1. What was completed

- Implemented the cross-topology coordinator for the frozen
  P2_ROUTING_5CTX_V1 plan.
- Added the five-context artifact-fingerprint manifest.
- Added Campaign Result v1 and its JSON Schema.
- Implemented fail-stop deploy, initial baseline, six-experiment
  batch, final baseline, destroy, cleanup, and artifact-audit stages.
- Implemented same-run provenance checks and atomic merge of only the
  five accepted context datasets.
- Implemented the class-conditional D-066 unavailable-feature gate
  without changing Evidence v2, Dataset Row v2, features, or labels.
- Implemented the separate rule-based reference audit.
- Integrated the existing complete_context_group_hash_v2 splitter and
  verified the frozen allocation.
- Preserved the first failed run as incomplete diagnostic evidence
  and excluded all of its rows from the accepted dataset.
- Completed a fresh real campaign with 5/5 contexts, 30/30
  experiments, 30/30 artifact revalidations, and 5/5 cleanups.
- Produced and audited the 30-row merged Dataset Row v2 JSONL.
- Produced and audited the 18/6/6-row, 3/1/1-group split without
  cross-partition leakage.
- Passed 11/11 targeted P2-R10 tests and 175/175 full regression
  tests.

Accepted campaign run:

p2_routing_5ctx_v1-20260804T073429388394Z-
617194fea9954ed98ec120bdefea23d9

Accepted cryptographic bindings:

- campaign plan:
  b0d054001136358b51eb08620de2d5e500c32b755183ee812a4ad3cd8d09a0e4
- fingerprint manifest:
  f1e69b0d048785a45967593a12071b536027c65e2daddebafbaec296746c88b3
- merged dataset:
  be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80
- train partition:
  cc196711cd2170bbd3393b3097b8b86d8bb12f8f8324f39f15b4a302c74859e8
- validation partition:
  52c2215ebf97b7e9fb66720b3631431dddd2ede7462cf10163df3362a99bf5c4
- test partition:
  03383705cdab2368446cbf4a967e3c7bb71ae63379ab63dcad8a8ab678cc8a08

## 2. What was decided

- D-066 accepts structural unavailability only for the one dependent
  next-hop-reachability feature in missing_static_route rows.
- D-067 accepts the complete fresh run as the canonical first P2
  dataset campaign and its grouped split as baseline-stage input.
- The failed earlier attempt remains excluded and is not repaired,
  merged, or selectively reused.
- The frozen G01-G05 bindings, class order, repetitions, group IDs,
  split seed, ratios, and partition allocation remain unchanged.
- Runtime evidence, Dataset Row v2, rule outputs, and evaluation
  outputs remain separate contracts.
- Generated datasets and reports remain local ignored artifacts; the
  run identifiers and SHA-256 bindings provide the accepted identity.
- The test group is frozen and must not be used for later feature or
  model selection.
- P2-R10 establishes dataset readiness, not general diagnostic
  performance or method superiority.

## 3. Files created or changed

Created implementation files:

- plans/campaigns/P2_ROUTING_5CTX_V1.fingerprints.json
- schemas/campaign_result_v1.schema.json
- src/campaign/runner.py
- tests/unit/test_p2_r10_campaign_runner.py

Created closeout document:

- docs/HANDOFF_P2_R10.md

Changed documentation:

- docs/DATASET_CAMPAIGN_DESIGN.md
- docs/DECISIONS.md
- docs/EVALUATION_GROUP_PROTOCOL.md
- docs/HANDOFF_P2_R9.md
- docs/MASTER_CONTEXT.md
- docs/ROADMAP.md
- docs/STATUS.md

Runtime artifacts created locally and intentionally excluded from the
implementation commit by the existing ignore policy include the two
campaign-result records, per-context batch metadata and JSONL files,
experiment evidence, the accepted merged JSONL, rule-audit report,
split manifest, and three split JSONL files.

## 4. Open issues

- Define one comparable evaluation-result contract for the
  rule-based, ML, and hybrid methods.
- Produce partition-aware rule-based baseline metrics without using
  the test group for design or tuning.
- Implement the first small, interpretable ML baseline using only the
  approved Dataset Row v2 features.
- Tune only against train and validation; reserve G02 test for the
  frozen final comparison.
- Implement the hybrid decision policy only after the independent
  rule and ML baselines exist.
- Add broader contexts, repetitions, fault classes, and missing-
  evidence experiments before making generalization claims.
- Define a reproducible backup/publication policy for generated
  runtime datasets before final thesis archiving.

## 5. Next step

Start P3-R0 — Formal Rule-Based Baseline Evaluation Protocol.

P3-R0 must:

- preserve the accepted campaign, dataset hash, and split unchanged;
- define metrics and a machine-readable result contract reusable by
  the rule-based, ML, and hybrid methods;
- map the separate P2-R10 rule audit to the frozen partitions;
- report per-class and macro metrics with explicit small-sample
  limitations;
- prohibit test-group use for feature, threshold, or model selection;
- keep diagnosis explanations and supporting evidence auditable; and
- stop before implementing or tuning the ML model.

## 6. Impact on central documents

- MASTER_CONTEXT records the accepted campaign, dataset hash, split,
  quality results, rule audit, tests, and limitation.
- DECISIONS adds D-067 and preserves D-066 as the explicit correction
  to the earlier quality-gate conflict.
- STATUS closes P2-R10, removes its completed items from open issues,
  and identifies P3-R0 as next.
- ROADMAP marks Phase 2 completed and Phase 3 in progress.
- EVALUATION_GROUP_PROTOCOL records the satisfied D-058 readiness
  gate and frozen accepted allocation.
- DATASET_CAMPAIGN_DESIGN records the implemented coordinator and
  accepted runtime closeout.
- HANDOFF_P2_R9 now points readers to D-066 for the one superseded
  quality-gate detail.
