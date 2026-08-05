# P5-R2 Frozen-Policy Report Implementation

Date: 2026-08-05

Status: COMPLETED AND INDEPENDENTLY VERIFIED

## 1. Purpose

P5-R2 is the one authorized report-only evaluation of the frozen
hybrid policy on the held-out G02 group. It must produce the first
complete hybrid Method Evaluation Result v1 and a descriptive
Rule-based versus Machine Learning versus Hybrid comparison.

This implementation does not change Hybrid Policy v1, candidate
selection, the ML estimator, the Rule Engine, or either accepted
baseline report.

## 2. Freeze gate

Before any G02 source is traversed, src/hybrid/reporting.py reruns the
independent P5-R1 verifier and requires:

- Hybrid Policy SHA-256
  a25467e9cfd8bb52cc67b0c3886eb439466ee51a27b22d292ee468d060bdecc7;
- all five accepted D-069/D-071/D-073 baseline hashes;
- selected-policy SHA-256
  59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507;
- selected candidate consensus_abstain_v1;
- all 48 development predictions, 48 evaluations, two manifests, and
  99 P5-R1 runtime JSON files; and
- absence of test output inside the P5-R1 selection directory.

Any mismatch is fail-stop and occurs before test-source collection.

## 3. One-way held-out execution

After the freeze gate passes, the coordinator indexes only the six
G02 source identities and the three inputs permitted by D-074:

- Evidence v2 reference;
- immutable rule prediction reference; and
- immutable ML prediction reference.

The Hybrid Engine receives no ground truth, target, partition,
correctness flag, evaluation, or method metric. It generates all six
consensus_abstain_v1 predictions before the Evaluator may read any
G02 ground-truth document.

The output directory is created atomically and refuses overwrite:

reports/experiments/p5_r2_hybrid_baseline_v1

It will contain exactly:

- six G02 hybrid prediction documents;
- six G02 per-sample evaluation documents;
- one complete method_evaluation_result.json; and
- one cross_method_comparison.json.

That is 14 JSON files. No second candidate and no new train or
validation prediction is generated.

## 4. Complete hybrid report

The hybrid report reuses the selected candidate's 24 immutable P5-R1
development predictions and evaluations, then adds the six P5-R2
G02 prediction/evaluation pairs.

Each of the 30 records contains seven path-and-SHA-256 references:

1. Experiment Manifest;
2. ground truth;
3. Evidence v2;
4. original rule prediction;
5. original ML prediction;
6. hybrid prediction; and
7. per-sample evaluation.

The complete report therefore verifies 210 sample-level references.
It uses the existing abstention-aware, full-denominator metrics and
keeps G02 test use equal to report_only.

## 5. Cross-method comparison

Cross-Method Comparison v1 is constrained by
schemas/cross_method_comparison_v1.schema.json. It binds the accepted
rule and ML reports plus the new hybrid report and compares the same
30 rows, class order, partition roles, and group-aware split.

For train, validation, test, and overall, it records:

- accuracy;
- macro precision, recall, and F1;
- exact-diagnosis rate;
- fault-only affected-prefix correctness;
- coverage; and
- abstention count and rate.

For methods without abstention, coverage is 1.0 and abstention values
are zero. The comparison is descriptive_only. It performs no
statistical superiority test and explicitly records that G02 did not
influence policy design or selection.

## 6. Independent verification

The verify-report command repeats the freeze gate and verifies:

- the hybrid report and comparison SHA-256 values;
- Method Evaluation Result v1 and Cross-Method Comparison v1 schemas;
- the exact 30-row and 18/6/6 partition bindings;
- all 210 sample artifact references;
- prediction policy, model, source, candidate, and sample identities;
- P5-R1 path ownership for development outputs;
- P5-R2 path ownership and report_only evaluator role for G02;
- exactly six held-out prediction/evaluation pairs; and
- the exact 14-file runtime JSON set.

## 7. Accepted verification evidence

The canonical execution and independent verification completed with:

- frozen-policy and selection gate before G02: passed;
- G02 predictions before ground-truth reads: 6/6 passed;
- runtime JSON file set: 14/14 passed;
- hybrid sample references: 210/210 passed;
- targeted P5-R2 tests: 14/14 passed; and
- complete regression suite: 243/243 passed.

The hybrid report SHA-256 is:

e990a29882f1b7cec4fe003ee5ee65b3fa3dfd25250092a0f9f2a908074a9c75

The cross-method comparison SHA-256 is:

eebf97dfe340a05feba70874f54727e1a8ccf7ce4224301f162544537d8ecf80

## 8. Result and limitation

The frozen hybrid policy obtained 1.0 macro-F1, 1.0 exact-diagnosis
rate, 1.0 affected-prefix correctness, 1.0 coverage, and zero
abstentions on the six-row G02 test group. Test use remained
report_only and did not influence the policy or selection.

These values are descriptive evidence from one small controlled test
context. They do not establish statistical superiority, robustness
across unseen fault families, or real-world generalization. P5-R2 and
Phase 5 are complete only for the frozen P2_ROUTING_5CTX_V1 campaign.
