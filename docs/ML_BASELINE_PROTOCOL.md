# Leakage-Safe Machine Learning Baseline Protocol v1

Date: 2026-08-05
Status: COMPLETED; REAL P4-R0 FEATURE MATRIX ACCEPTED

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
