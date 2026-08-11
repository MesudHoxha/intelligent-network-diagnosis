# P6-R6 Six-Class Method Freeze and Report-Only Gate

Date: 2026-08-11

Status: IMPLEMENTED; REAL FREEZE AND REPORT-ONLY RUNTIME ACCEPTED

## Scope

P6-R6 implements the bounded six-class Rule-based, Machine Learning,
and Hybrid development/evaluation path authorized by D-083. It consumes
the accepted P6-R5 clean Dataset Row v3 split without modifying its
source artifacts.

The gate does not authorize multiple faults, automatic remediation,
production-network execution, paid services, test-guided revision, or a
statistical-superiority claim.

## Frozen method inputs

The leakage-safe Method Input v1 contract contains only the ten frozen
tri-state predictors plus role-neutral network context required to turn
a predicted class into a location and affected-prefix diagnosis. Labels,
ground truth, partition use, mask identity, hashes, metrics, correctness,
and explanation text are excluded from the encoded predictor vector.

Each tri-state predictor is encoded losslessly as an `available/true`
pair, producing 20 binary columns. Structural and masked unavailability
share the same predictor encoding; their different reasons remain audit
metadata and cannot reveal the mask to the classifier.

Development allocation is fixed:

- train: 36 clean E01/E03/E05 inputs and zero masked fit inputs;
- validation: 12 clean E04 inputs plus 48 deterministic masked copies;
- test: 24 clean E02/E06 inputs plus 96 deterministic masked copies,
  opened only after independent freeze verification.

The four mask families remain those frozen in D-077. A masked input
retains the clean Dataset Row v3 line hash and Evidence v3 artifact hash.
It changes only observed features belonging to the declared family and
does not impute a replacement value.

## Rule-based method

`rule_based_p6_v1` uses the six exact ten-feature signatures accepted in
P6-R4. A clean unique signature produces a diagnosis. Any artificial
masked-missing or collection-unavailable predictor produces
`INSUFFICIENT_EVIDENCE`; an unexpected complete vector produces
`NO_RULE_MATCH`. Neither outcome is removed from evaluation denominators.

## Machine Learning method

`machine_learning_p6_v1` fits six precommitted candidates only on the 36
clean train inputs: three L2 logistic-regression configurations and three
bounded shallow decision trees. The deterministic seed is `20260811`.

Selection uses only E04 in this order:

1. clean validation macro-F1, descending;
2. masked validation macro-F1, descending;
3. masked validation accuracy, descending;
4. declared complexity rank, ascending; and
5. candidate ID, ascending.

The selected estimator is not refitted on train plus validation.
Prediction uses estimator argmax. Test data cannot change the candidate,
features, encoding, seed, or selection order.

## Hybrid method

`hybrid_p6_v1` selects among five immutable policies using only the 60
E04 clean/masked validation inputs. The candidates are a Rule-first ML
fallback, three fixed confidence-guarded ML fallbacks, and a
consensus-abstain policy.

Selection uses overall validation macro-F1, clean macro-F1, coverage,
complexity rank, and candidate ID in that order. The selected policy is
not reselected after test access.

## Independent freeze boundary

The development stage writes train/validation inputs and targets,
validation predictions, the ML and Hybrid selection artifacts, the
selected estimator, and a development summary. The freeze manifest binds:

- the accepted P6-R5 campaign/split hashes;
- the protocol and method-affecting implementation hashes;
- all development artifact hashes;
- the selected model and Hybrid policy identities; and
- the software versions.

A separate verifier recomputes every binding, reloads the estimator,
confirms the six-class universe, confirms absence of report-only outputs,
and writes a one-use authorization receipt. No test JSONL content is read
by the development or freeze-verification stage.

## One report-only evaluation

Only a valid independent receipt authorizes the coordinator to open the
sealed test partition. Before reading it, the coordinator records that
the single report-only attempt has started. It then verifies the accepted
test SHA-256, creates 24 clean and 96 masked inputs, and produces Rule,
ML, and Hybrid predictions and reports without refitting or reselection.

Required report scopes are overall, clean, masked overall, each mask,
each context, and each class. Reports retain unresolved cases in the full
denominator and include accuracy, macro precision/recall/F1, exact
diagnosis, affected-prefix correctness, coverage, abstention rate, and
insufficient-evidence rate. The cross-method result is descriptive only.

## Implementation verification

The implementation has passed:

- 41/41 P6-R6 contract, method, schema, and atomic-coordinator tests;
- 185/185 targeted Phase 6 tests; and
- 428/428 full regression tests.

The coordinator test uses a synthetic 72-row six-context fixture to prove
the ordering `development freeze -> independent verification -> one
report-only evaluation`. These test results do not constitute empirical
P6-R6 performance results on E02/E06.

## Accepted real runtime

The real P6-R6 gate ran once on 2026-08-11. Development used 36 clean
train inputs and 60 E04 validation inputs: 12 clean plus 48 deterministic
masked copies. The validation-only selections were:

- ML candidate: `logreg_l2_c1`;
- Hybrid policy: `rule_then_ml_fallback_v1`.

The independent freeze verifier bound the protocol, implementation,
development artifacts, selected estimator, and selected policy before it
authorized one report-only test evaluation. Only then was the immutable
E02/E06 test source opened. The accepted report contains 24 clean inputs
and 96 deterministic masked copies, for 120 inputs per method. The gate
records one and only one test-evaluation attempt, no post-freeze model
refit, no policy reselection, and no test-guided revision.

The accepted descriptive summaries are:

| Method | Scope | n | Accuracy | Macro-F1 | Coverage | Insufficient evidence |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Rule-based | clean | 24 | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| Rule-based | masked | 96 | 0.000000 | 0.000000 | 0.000000 | 1.000000 |
| Rule-based | overall | 120 | 0.200000 | 0.333333 | 0.200000 | 0.800000 |
| Machine Learning | clean | 24 | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| Machine Learning | masked | 96 | 0.791667 | 0.810486 | 1.000000 | 0.000000 |
| Machine Learning | overall | 120 | 0.833333 | 0.846672 | 1.000000 | 0.000000 |
| Hybrid | clean | 24 | 1.000000 | 1.000000 | 1.000000 | 0.000000 |
| Hybrid | masked | 96 | 0.791667 | 0.810486 | 1.000000 | 0.000000 |
| Hybrid | overall | 120 | 0.833333 | 0.846672 | 1.000000 | 0.000000 |

Rule-based resolves every clean signature exactly and intentionally
returns `INSUFFICIENT_EVIDENCE` for every artificial mask. ML and Hybrid
have identical aggregate results in all three reported scopes. The
selected Rule-then-ML-fallback policy therefore does not establish an
empirical Hybrid advantage over the independent ML method in this gate.

Accepted runtime identities:

- freeze-manifest SHA-256:
  `fa98a17e2ffae42f6dd009a13af65ad32174035eca8352bf26f321531a4fe0f5`;
- independent freeze-receipt SHA-256:
  `5c6c6537cb233efdeb52c6872f7a6ef7fb32eb3ac7b2474e2514b2908cd29bcc`;
- report-only run-manifest SHA-256:
  `44c505b451c6211b4515564f4b889633b6d74ed0c618f19cc0ab3b9bdfe72b1d`;
- cross-method comparison SHA-256:
  `ca1c15d04828c0ae61cacaf80a5ee6f49f64a9cf3ac151a4b4ccd2386987e570`.

## Accepted boundary

P6-R6 is accepted as a controlled six-class and missing-evidence
evaluation. The comparison is `DESCRIPTIVE_ONLY`; no statistical
superiority test was performed. The masked copies are deterministic
transformations of the same 24 clean test rows, not 96 additional
independent network experiments. These results do not establish Hybrid
superiority, population-level generalization, production suitability, or
real-world missing-data performance.

The single authorized E02/E06 report-only use is consumed. The source
test bytes remain immutable, but P6-R6 may not be rerun and its results
may not trigger refitting, reselection, or revision. Multiple-fault
execution remains blocked until P6-R7 makes a separate multi-label
academic-value and feasibility decision.
