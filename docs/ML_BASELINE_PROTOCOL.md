# Leakage-Safe Machine Learning Baseline Protocol v1

Date: 2026-08-05
Status: COMPLETED; REAL P4-R1 ML BASELINE ACCEPTED

## 1. Purpose

This protocol freezes the Machine Learning input and selection
boundary before fitting any model. It prevents ground truth,
identifiers, rule outputs, evaluation results, or held-out test
results from influencing predictor construction or model selection.

P4-R0 implements the protocol and ML Feature Matrix v1. It does not
fit, select, or evaluate a Machine Learning model and does not design
the hybrid method.

## 2. Frozen source

The only accepted source is the D-067 campaign:

- campaign ID: P2_ROUTING_5CTX_V1;
- campaign run ID:
  p2_routing_5ctx_v1-20260804T073429388394Z-
  617194fea9954ed98ec120bdefea23d9;
- Dataset Row contract: v2;
- merged dataset SHA-256:
  be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80;
- split algorithm: complete_context_group_hash_v2;
- split seed: 20260730;
- split ratios: 0.6/0.2/0.2;
- rows: 18/6/6; and
- complete context groups: 3/1/1.

The fixed allocation is train G03/G04/G05, validation G01, and test
G02. P4-R0 verifies the campaign, merged dataset, split manifest, and
every partition file by SHA-256. It does not regenerate, reshuffle,
filter, relabel, or repair them.

## 3. Supervised target

The target is only labels.fault_type, with the D-068 class order:

1. no_fault;
2. missing_static_route; and
3. wrong_next_hop.

The target is stored separately from the numeric predictor vector. It
is never included in encoded_feature_names.

## 4. Predictor whitelist

The raw predictor whitelist is exactly the seven Dataset Row v2
diagnostic features, in this order:

1. source_gateway_reachable;
2. destination_reachable;
3. route_to_destination_exists_on_observer;
4. route_next_hop_present_on_observer;
5. route_next_hop_reachable_from_observer;
6. expected_next_hop_reachable_from_observer; and
7. destination_reachable_from_transit.

No other Dataset Row section or runtime artifact supplies a
predictor. The following remain excluded:

- every labels field;
- metadata and quality fields;
- ground truth;
- rule predictions and explanations;
- evaluation results;
- identifiers and topology or scenario names;
- paths and hashes; and
- explanation or recommendation text.

sample_id, split_group_id, target_class, and source-row SHA-256 are
audit fields outside feature_vector. They may not be passed to a
model as predictors.

## 5. Tri-state transformation

Each raw feature is expanded to two ordered binary columns:

- `<feature>__available`; and
- `<feature>__true`.

The fixed mapping is:

| Dataset Row v2 value | available | true |
|---|---:|---:|
| true | 1 | 1 |
| false | 1 | 0 |
| unavailable | 0 | 0 |

The pair `[0, 1]` is invalid. Seven raw features therefore produce
14 binary columns in a fixed order.

This representation is lossless for the three states, keeps missing
evidence explicit, and avoids imposing the artificial numeric order
`unavailable < false < true`. It requires no learned imputer,
category discovery, scaling, or statistic from train, validation, or
test. Structural C1 unavailability remains evidence under D-066; it
is not silently replaced with true, false, a mean, or a mode.

## 6. Partition roles and access

The D-068 roles remain normative:

- train — the only fitting partition;
- validation — the only selection partition; and
- test — one report-only evaluation after the complete pipeline is
  frozen.

The selected estimator is not refitted on train plus validation.
Validation labels may select one predeclared candidate, but they may
not update fitted parameters. Test features, labels, predictions, and
metrics may not influence preprocessing, candidates, hyperparameters,
thresholds, or tie-breakers.

P4-R0 materializes the deterministic representation of every frozen
partition only after this transformation is committed. It produces no
prediction or metric. Later ML code must enforce the partition uses
stored in ML Feature Matrix v1.

## 7. Candidate model set

The first baseline comparison is deliberately small because train has
only 18 rows and three complete context groups. Six candidates are
predeclared across two interpretable families:

- multinomial logistic regression with L2 regularization and
  C in `{0.1, 1.0, 10.0}`; and
- decision tree with the fixed shallow configurations
  `(max_depth=1, min_samples_leaf=1)`,
  `(max_depth=2, min_samples_leaf=1)`, and
  `(max_depth=3, min_samples_leaf=2)`.

Logistic regression uses lbfgs, no class weights, and max_iter 1000.
Trees use Gini impurity and the best splitter. All stochastic-capable
estimators use model seed 20260730. The candidate list, parameters,
and complexity ranks are machine-readable in ML Feature Matrix v1.

No neural network, ensemble search, unbounded hyperparameter search,
feature selection, resampling, synthetic data generation, or test-
guided candidate may be added inside this baseline run.

## 8. Selection rule

Every candidate is fitted once on train and scored on validation.
The winner is selected by this frozen order:

1. highest validation macro F1;
2. highest validation accuracy;
3. lowest declared complexity_rank; and
4. lexicographically smallest candidate_id.

Predicted class is the estimator argmax. There is no threshold tuning.
Train performance is descriptive and cannot outrank validation.
Test metrics are forbidden during selection.

After the winning pipeline identity and fitted train-only model are
persisted and verified, G02 test may be evaluated once and only for
the Method Evaluation Result v1 ML report. A software failure before
an accepted test result must be documented; it must not become an
opportunity to change the frozen pipeline using partial test output.

## 9. ML Feature Matrix v1

The machine-readable contract is implemented by:

- schemas/ml_feature_matrix_v1.schema.json; and
- src/ml/feature_matrix.py.

The artifact records:

- the frozen protocol and candidate set;
- all dataset and split bindings;
- 14-column feature vectors and separate target classes;
- sample and group audit identities outside the predictor vector;
- per-partition row, group, class, and unavailable-value counts;
- source-row hashes and source-artifact hashes; and
- an explicit leakage audit.

The builder validates both the runtime contract and JSON Schema,
writes atomically, refuses an existing output, and produces identical
bytes for identical accepted inputs.

## 10. P4-R0 acceptance gates

The real matrix is accepted only if:

- the exact D-067 campaign run and merged-dataset hash match;
- every partition file matches the split manifest hash;
- 30 unique Dataset Row v2 samples map exactly once;
- rows remain 18/6/6 and groups remain 3/1/1 without overlap;
- every partition retains balanced frozen class coverage;
- only the seven whitelisted raw features produce the 14 columns;
- all encoded values are binary and no `[0, 1]` pair occurs;
- the expected ten structural C1 unavailable values are preserved;
- test remains report_only and produces no metric;
- runtime and JSON Schema validation pass; and
- targeted tests and the full regression suite pass.

The real artifact path and SHA-256 must be recorded only after that
execution succeeds.

## 11. Interpretation limits

The feature matrix is an input-integrity result, not an ML performance
result. It does not prove that either candidate family generalizes,
that the structural unavailable indicator is robust outside the
current scenarios, or that ML can outperform deterministic rules.

The accepted campaign contains only 30 controlled rows, three fault
classes, and five contexts. Each validation/test partition contains
one context, and repetitions within one context are not independent
topology samples. These limits remain mandatory when later metrics
are interpreted.

## 12. Out of scope for P4-R0

- fitting or selecting a model;
- reading test metrics;
- emitting Method Evaluation Result v1 for ML;
- changing Dataset Row v2 or the D-067 split;
- adding features or classes;
- tuning from rule-based or test results;
- comparing ML performance with D-069; and
- designing or evaluating the hybrid method.

## 13. Accepted P4-R0 feature matrix

The frozen builder was executed once against the accepted D-067
runtime artifacts on 2026-08-05. The accepted result is:

- matrix_id: p4_r0_ml_feature_matrix_v1;
- path:
  reports/experiments/p4_r0_ml_feature_matrix_v1.json;
- SHA-256:
  9193b4b8c676bf94ef9af05562d9d0047faef61bc94c9d81b0485b88bf599730;
- accepted campaign run:
  p2_routing_5ctx_v1-20260804T073429388394Z-
  617194fea9954ed98ec120bdefea23d9;
- merged dataset SHA-256:
  be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80;
- rows: 30;
- raw features: 7;
- encoded binary columns: 14;
- partition rows: 18/6/6;
- partition groups: 3/1/1;
- structurally unavailable values: 10; and
- source-row references: 30/30 verified by SHA-256.

Runtime and JSON Schema validation passed, the predictor-leakage
audit passed, and every partition retained its frozen use. G02 test
remained report_only. The artifact contains no fitted estimator,
prediction, or metric. Ten targeted tests and the complete 195-test
regression suite passed.

This result closes P4-R0 and accepts the deterministic input boundary
for the first ML baseline. It is not an ML performance result and
does not establish model quality, generalization, hybrid behavior, or
superiority over the D-069 rule-based baseline.

## 14. P4-R1 pipeline-freeze contract

P4-R1 is split into two ordered runtime stages:

1. train, select, and freeze; and
2. verify the freeze, then produce the report-only evaluation.

The first stage may materialize only train and validation predictor
arrays. It fits each of the six frozen candidates on train, produces
train and validation predictions, applies the selection order from
Section 8, and serializes only the selected train-only estimator. It
does not request test records for prediction or metrics.

The atomic pipeline directory contains:

- estimator.joblib; and
- selection.json under ML Pipeline Selection v1.

The selection artifact binds the accepted matrix path and SHA-256,
all six candidate identities and train/validation summaries, selected
candidate, train and validation group/sample hashes, 14 feature names,
class order, software versions, model SHA-256, and the no-test/no-
refit audit. Existing output is never overwritten.

## 15. Test-opening gate

The report stage must independently verify all of the following before
requesting one test prediction:

- accepted D-071 matrix identity and SHA-256;
- ML Pipeline Selection v1 runtime and JSON Schema;
- exact six-candidate order and parameters;
- deterministic winning-candidate tie-break result;
- reproduced selected-model train and validation predictions;
- exact 18-row train sample-set binding;
- 14-column feature and three-class order;
- selection-result SHA-256;
- estimator SHA-256; and
- no validation fit, train-plus-validation refit, test prediction, or
  test metric in the freeze artifact.

Only after this gate passes may the selected already-fitted estimator
predict G02 once for Method Evaluation Result v1. The report command
does not call fit and cannot change a candidate, threshold, feature,
or partition role.

## 16. ML prediction and explanation boundary

The independent ML baseline predicts fault_type only. It emits the
seven decoded tri-state evidence values plus a model-specific local
explanation:

- predicted-class feature contributions for logistic regression; or
- the traversed decision path for a decision tree.

It does not use labels, metadata, ground truth, rule outputs, or
evaluation results to create the prediction. Ground truth is opened
only after the prediction document exists in memory, for evaluation.

The baseline does not infer fault_location or affected_prefix. For a
predicted fault, both values remain null. This means a correct class
prediction can still fail full-diagnosis exact match and fault-only
affected-prefix correctness. That separation is intentional: P4-R1
must expose the independent classifier's scope rather than copy
ground truth or rule localization. Hybrid policy design remains out
of scope.

## 17. Backwards-compatible evaluation provenance

The original Method Evaluation Result v1 JSON Schema required
rule_audit provenance even though the same contract already declared
machine_learning and hybrid method identifiers. P4-R1 generalizes
only this provenance branch:

- the accepted D-069 rule report remains valid with rule_audit; and
- an ML report must instead bind feature_matrix, selection_result,
  and model_artifact.

Campaign, split, partition, metric, record, five-artifact-per-sample,
report-only test, and descriptive-only overall semantics are
unchanged.

## 18. Local open-source dependency boundary

P4-R1 uses scikit-learn and joblib locally. The project dependency
range is scikit-learn >=1.5,<1.8 and joblib >=1.4,<2. No paid API,
cloud service, external dataset, or remote inference is required.
Every accepted runtime selection records the exact Python,
scikit-learn, NumPy, and joblib versions.

## 19. P4-R1 implementation status

The two-stage implementation, ML Pipeline Selection v1 JSON Schema,
strict output and hash gates, ML explanation output, and comparable
report adapter are implemented. Ten targeted synthetic tests pass.
The complete regression suite passes 205/205.

The implementation was executed against the real accepted D-071
matrix on 2026-08-05. All six candidates fitted only on train, and
selection used only validation. The precommitted ordering selected
logreg_l2_c0_1. The serialized train-only estimator and selection
artifact were frozen before any test prediction or metric existed.

The accepted freeze identities are:

- selection SHA-256:
  a02536d6f2478d9fdc40510275dd3b48a2824ee7b1f0fa08c1aed472611fb6fb;
  and
- model SHA-256:
  90db38e625f4bcf6a234b6a0516371b76f98e01b4437f684ffea119cbc09cdb2.

The first report attempt stopped before producing a report because it
looked for source experiments under reports/experiments. Recovery
reverified the existing frozen artifacts and all 90 canonical source
artifacts, corrected only the source root to data/raw, and resumed the
report stage without calling fit.

The accepted p4_r1_ml_baseline_v1 report contains 30 rows, preserves
the 18/6/6-row and 3/1/1-group allocation, verifies 150/150 source-
artifact references, and retains G02 as report_only. Train,
validation, and test each report fault_type accuracy 1.0 and macro-F1
1.0. All 30 predictions contain evidence-bearing model explanations.

The independent classifier intentionally emits no predicted
fault_location or affected_prefix. Therefore every partition reports
exact-match rate 0.3333333333333333 and affected-prefix rate 0.0. The
report SHA-256 is
8fc6e77e5008cd7cc74e5ce130b901ed750afab9a35eb62652ff55f9205b0e92.
D-073 accepts this result and closes P4-R1 and Phase 4.

These are descriptive results for the frozen 30-row controlled
campaign. They do not establish real-world generalization,
statistical superiority, unseen-context robustness, or hybrid
performance.
