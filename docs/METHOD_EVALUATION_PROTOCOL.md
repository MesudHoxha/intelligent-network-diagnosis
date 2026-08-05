# Formal Method Evaluation Protocol v1

Date: 2026-08-05
Status: COMPLETED; REAL RULE-BASED AND ML BASELINES ACCEPTED

## 1. Purpose

This protocol defines one partition-aware and machine-readable
evaluation boundary for the three required diagnostic approaches:

1. rule_based;
2. machine_learning; and
3. hybrid.

It prevents metric or partition semantics from changing between
methods. P3-R0 applies the protocol only to the existing deterministic
Rule Engine. It does not implement or tune a Machine Learning model.

## 2. Frozen input

The first protocol application is bound to the accepted campaign from
D-067:

- campaign ID: P2_ROUTING_5CTX_V1;
- campaign run ID:
  p2_routing_5ctx_v1-20260804T073429388394Z-
  617194fea9954ed98ec120bdefea23d9;
- Dataset Row contract: v2;
- merged dataset SHA-256:
  be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80;
- split algorithm: complete_context_group_hash_v2;
- seed: 20260730;
- ratios: 0.6/0.2/0.2; and
- rows/groups: 18/6/6 and 3/1/1.

The partition allocation remains:

- train: G03, G04, and G05;
- validation: G01; and
- test: G02.

P3-R0 must verify these artifacts and hashes. It must not regenerate,
reshuffle, relabel, filter, or repair the dataset.

## 3. Evaluation unit and target

One evaluation record corresponds to one accepted sample_id. The
primary supervised target is labels.fault_type with the frozen class
order:

1. no_fault;
2. missing_static_route; and
3. wrong_next_hop.

For a rule-based NO_FAULT_DETECTED prediction with no fault_type
field, the comparable predicted class is normalized to no_fault.
Every other prediction must provide one class from the frozen set.

The normalizing rule changes only the evaluation representation. It
does not change the original diagnosis artifact.

## 4. Partition roles

The partition roles are normative:

- train — development;
- validation — selection; and
- test — report_only.

Only train and validation may influence later feature processing,
model choice, hyperparameters, decision thresholds, or hybrid policy.
The G02 test group must not be used for those decisions.

P3-R0 reports the already existing Rule Engine on all partitions only
after this protocol is frozen. It changes no rule, threshold, feature,
or prediction in response to train, validation, or test results.

An overall 30-row summary is descriptive_only. It is not a substitute
for the three partition summaries and cannot be used for method
selection.

## 5. Classification metrics

For every partition and for the descriptive overall view, Method
Evaluation Result v1 records:

- sample count;
- correct prediction count;
- accuracy;
- per-class precision, recall, F1, and support;
- unweighted macro precision, macro recall, and macro F1; and
- a confusion matrix with actual classes as rows and predicted
  classes as columns.

For class c:

- precision(c) = TP(c) / (TP(c) + FP(c));
- recall(c) = TP(c) / (TP(c) + FN(c)); and
- F1(c) = 2 * precision(c) * recall(c) /
  (precision(c) + recall(c)).

Macro metrics are the arithmetic mean of the three corresponding
per-class values. The primary comparison metric is macro F1 because
every approved fault class must contribute equally to the method
comparison.

When a metric denominator is zero, its value is defined as 0.0. This
zero-division policy is stored in every report and cannot vary by
method.

## 6. Separate diagnostic checks

Fault-type classification does not replace the more demanding
diagnostic evaluation already performed per experiment. The result
therefore reports two secondary checks separately:

- exact_diagnosis_match over every sample; and
- affected_prefix_fault_only over fault samples only.

The second denominator excludes no_fault rows because they have no
affected prefix. This avoids treating a non-applicable normal prefix
as additional fault-localization evidence.

Classification accuracy and exact diagnosis match must not be
presented as interchangeable metrics. A future method may predict the
correct fault_type while failing another diagnostic field.

## 7. Method identity

The shared contract accepts exactly these method identifiers:

- rule_based;
- machine_learning; and
- hybrid.

Every report also records:

- method family;
- implementation identifier;
- whether training occurred; and
- a selection statement describing how train and validation were
  used and confirming that test remained report-only.

The P3-R0 rule baseline uses:

- method_id: rule_based;
- family: traditional;
- implementation_id: deterministic_rule_engine_v1; and
- trained: false.

## 8. Provenance and auditability

The report is derived from the separate P2-R10 rule audit and frozen
split. It must verify that:

1. the campaign result is COMPLETED;
2. the accepted campaign run and merged-dataset SHA-256 match D-067;
3. the split manifest source hash matches the merged dataset;
4. every partition file matches its stored SHA-256;
5. every sample occurs exactly once in the split and rule audit;
6. labels and split_group_id values agree across Dataset Row v2, the
   rule audit, and the evaluation artifact;
7. the evaluation method is rule_based;
8. audit booleans agree with the source evaluation metrics; and
9. all required source artifacts exist.

Each sample record stores path and SHA-256 references for:

- Experiment Manifest v2;
- ground truth;
- Evidence v2;
- the method prediction;
- the per-experiment evaluation.

These references make explanations and supporting evidence auditable
without copying ground truth, evidence, or rule output into Dataset
Row v2 model features.

## 9. Machine-readable contract

The formal artifact is Method Evaluation Result v1, defined by:

- schemas/method_evaluation_result_v1.schema.json; and
- src/evaluation/reporting.py.

The runtime implementation recalculates every metric from the record
list and rejects a report whose summaries do not match its records.
It also enforces the train/validation selection boundary and
report-only test role.

The output is written atomically and an existing report is never
overwritten.

## 10. Acceptance gates for the real P3-R0 report

The first real report is accepted only if:

- the exact D-067 run and merged-dataset hash are verified;
- all 30 split samples map one-to-one to 30 rule-audit records;
- the split remains 18/6/6 rows and 3/1/1 whole groups;
- all 150 per-sample artifact references are present and hashed;
- runtime validation and the JSON Schema pass;
- the output report hash is recorded; and
- targeted tests and the complete regression suite pass.

The numerical metrics must be reported from the generated artifact.
They must not be inserted into central documents before the real
report succeeds.

## 11. Interpretation limits

The accepted input has 30 controlled rows, three classes, and five
laboratory contexts. Validation and test each contain only one
context and two repetitions per class. Repeated rows within a context
are execution repetitions, not independent topology samples.

Consequently:

- percentages are descriptive controlled-laboratory results;
- no confidence interval, significance test, or real-world
  generalization claim is justified at this scale;
- a perfect result, if observed, mainly confirms that the existing
  deterministic rules cover the same frozen fault semantics; and
- no claim of superiority over Machine Learning or hybrid diagnosis
  is possible before those independent methods are implemented and
  evaluated through this same contract.

## 12. Out of scope for P3-R0

- changing the seven Dataset Row v2 features;
- adding or removing classes;
- modifying rule logic;
- training or tuning an ML model;
- designing a hybrid decision policy;
- changing the accepted campaign or split;
- using G02 test results for selection; and
- claiming general diagnostic performance.

## 13. Accepted P3-R0 result

The frozen adapter was executed once against the accepted D-067
runtime artifacts on 2026-08-05. The accepted result is:

- result_id: p3_r0_rule_based_baseline_v1;
- method: rule_based / deterministic_rule_engine_v1;
- report path:
  reports/experiments/p3_r0_rule_based_baseline_v1.json;
- report SHA-256:
  7158f1de31a892779bbce2eaad8f5c5e5bb7c2fc08e0766b49a55047ddc56424;
- accepted campaign run:
  p2_routing_5ctx_v1-20260804T073429388394Z-
  617194fea9954ed98ec120bdefea23d9;
- merged dataset SHA-256:
  be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80;
- partition rows: 18/6/6;
- partition groups: 3/1/1; and
- verified artifact references: 150/150.

Train, validation, and test each reported accuracy 1.0 and macro F1
1.0. All 30 records matched the complete expected diagnosis, and all
20 fault records matched the expected affected prefix. Test remained
report_only and the overall 30-row view remained descriptive_only.
No rule, feature, threshold, prediction, dataset row, group, or split
was changed after observing any partition metric.

This result closes P3-R0. Its perfect values describe the frozen
controlled campaign and confirm coverage of its known fault
semantics. They are not evidence of real-world generalization,
statistical superiority, or Machine Learning or hybrid performance.

## 14. Backwards-compatible method provenance extension

P4-R1 exposed one rule-specific constraint in the original shared
JSON Schema: provenance.rule_audit was mandatory even when method_id
was machine_learning or hybrid. The runtime and schema now preserve
the existing rule-based branch and add an ML-specific branch.

For rule_based, provenance.rule_audit remains mandatory. For
machine_learning, provenance.feature_matrix,
provenance.selection_result, and provenance.model_artifact are
mandatory. Both branches continue to require the campaign result,
split manifest, input-record count, and exactly five hashed artifact
references per sample.

No metric definition, class order, partition role, record field,
test policy, overall interpretation, or accepted D-069 report is
changed by this extension.

## 15. Accepted P4-R1 Machine Learning result

The P4-R1 freeze and report gates succeeded against D-071 on
2026-08-05. The accepted result is:

- result_id: p4_r1_ml_baseline_v1;
- method: machine_learning / multinomial_logistic_regression;
- selected candidate: logreg_l2_c0_1;
- report path:
  reports/experiments/p4_r1_ml_baseline_v1/
  method_evaluation_result.json;
- report SHA-256:
  8fc6e77e5008cd7cc74e5ce130b901ed750afab9a35eb62652ff55f9205b0e92;
- selection SHA-256:
  a02536d6f2478d9fdc40510275dd3b48a2824ee7b1f0fa08c1aed472611fb6fb;
- model SHA-256:
  90db38e625f4bcf6a234b6a0516371b76f98e01b4437f684ffea119cbc09cdb2;
- partition rows: 18/6/6;
- partition groups: 3/1/1; and
- verified artifact references: 150/150.

Train, validation, and report-only test each reported fault_type
accuracy 1.0 and macro-F1 1.0. Every one of the 30 predictions
contains a decoded evidence view and a model-specific explanation.
The independent classifier emits neither predicted fault_location nor
predicted affected_prefix, so each partition reports exact-diagnosis
match 1/3 and affected-prefix correctness 0.0.

The report-stage recovery changed only the source root to the
canonical data/raw location after verifying the existing selection
and model hashes. It did not refit the estimator. This result closes
P4-R1 and provides the independent ML baseline for later comparison;
its controlled values do not establish real-world generalization,
statistical superiority, or hybrid performance.

## 16. Precommitted future hybrid extension

D-074 freezes the Hybrid Diagnosis Policy v1 boundary before any
hybrid prediction or metric. The future hybrid branch must bind the
hybrid policy, selected-policy artifact, D-069 rule result, D-071
feature matrix, D-073 selection, estimator and ML report, campaign
result, and split manifest.

Each hybrid sample record will retain seven path-and-SHA-256 artifact
references:

- Experiment Manifest;
- ground truth;
- Evidence v2;
- original rule prediction;
- original ML prediction;
- hybrid prediction; and
- per-experiment evaluation.

Ground truth and evaluation remain report provenance only. They are
forbidden Hybrid Engine inputs.

The hybrid output may also be ABSTAINED. An abstention is counted as a
false negative for the actual class, is not a false positive for any
predicted class, and is incorrect for accuracy and exact diagnosis. On
a fault row it is also incorrect for affected-prefix correctness.
Coverage, abstention count, abstention rate, and per-class abstention
counts are reported separately. The existing three-by-three class
confusion matrix retains resolved predictions; class-specific
abstention counts reconcile the remaining support.

This section freezes the required semantics only. P5-R0 does not
change the current Method Evaluation Result v1 schema or runtime,
generate a hybrid report, or access G02. A backwards-compatible
schema/runtime extension must be implemented and tested before the
first hybrid report. Existing D-069 and D-073 reports remain immutable.

## 17. P5-R1 implemented hybrid evaluation boundary

P5-R1 implements the previously frozen abstention semantics without
producing the final three-partition hybrid report. The new
compute_abstention_aware_metrics function keeps the complete
supervised denominator, the existing three-class order, and a
three-by-three matrix for resolved decisions. It additionally reports
resolved_count, coverage, abstention count, abstention rate, and
per-class abstention counts.

Method Evaluation Result v1 now supports a method-specific hybrid
branch. A future hybrid result must include:

- hybrid_policy and hybrid_selection provenance;
- the D-069 rule baseline;
- the D-071 feature matrix;
- the D-073 ML selection, estimator, and ML baseline;
- seven hashed sample references; and
- an explicit abstained boolean with a nullable predicted class.

The rule-based and Machine Learning branches retain their original
fields and five references. No accepted report is rewritten.

P5-R1 used this evaluator only for train and validation candidate
selection. The canonical run produced complete 24-row development
evaluations for each candidate. Both candidates obtained 1.0
full-denominator macro-F1, 1.0 exact diagnosis, 1.0 coverage, and zero
validation abstentions; the precommitted complexity tie-break selected
consensus_abstain_v1.

The selection artifact was independently verified with SHA-256
59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507.
No test prediction or metric was produced. G02 report-only evaluation
remains reserved for P5-R2 and must use the frozen selected policy
without reselection or tuning.

## 18. P5-R2 report-only implementation gate

P5-R2 adds a separate reporting coordinator without changing the
Hybrid Engine prediction API. Before any G02 source collection, the
coordinator reruns the P5-R1 independent verifier against the policy,
five accepted baselines, 99 development runtime JSON files, selected
candidate, and selection SHA-256.

Only after this gate may it bind the six test sample identities and
the Evidence v2, rule-prediction, and ML-prediction inputs allowed by
D-074. It generates all six selected-candidate predictions before the
Evaluator reads ground truth. Test evaluation remains report_only.

The complete hybrid Method Evaluation Result combines 24 immutable
P5-R1 development records with six P5-R2 test records. It uses the
existing full-denominator abstention metrics and requires 30 times
seven, or 210, sample artifact references.

Cross-Method Comparison v1 binds the three immutable method reports
and presents the same classification, diagnostic, coverage, and
abstention fields for train, validation, test, and overall. The
comparison is descriptive_only and cannot convert these controlled
values into a statistical superiority or real-world generalization
claim.

The canonical P5-R2 execution passed the freeze gate, generated all
six G02 predictions before test ground-truth evaluation, and produced
the complete 30-row hybrid report plus Cross-Method Comparison v1.
The G02 hybrid result has 1.0 macro-F1, exact diagnosis,
affected-prefix correctness, and coverage, with zero abstentions.

Independent verification passed all 210 sample references, the exact
14-file runtime set, 14/14 targeted tests, and 243/243 regression
tests. Test use remained report_only and did not influence policy or
selection. The comparison remains descriptive_only; these values do
not authorize a statistical-superiority or real-world-generalization
claim.
