# Hybrid Diagnosis Policy v1

Date: 2026-08-05

Status: FROZEN AND RUNTIME-VERIFIED

## 1. Purpose

This document precommits the first bounded hybrid-diagnosis policy
before any hybrid implementation, prediction, metric, or test access.
It combines two already accepted independent baselines without
changing either one:

- D-069 deterministic Rule Engine; and
- D-073 frozen Machine Learning classifier.

The policy is machine-readable in
policies/hybrid/P5_HYBRID_POLICY_V1.json and constrained by
schemas/hybrid_policy_v1.schema.json. P5-R0 validates only that frozen
contract. It does not implement the Hybrid Engine.

## 2. Why fusion is needed

The accepted ML baseline correctly classifies fault_type on the small
controlled campaign but deliberately emits no location or affected
prefix. The accepted Rule Engine provides deterministic class,
location, prefix, and evidence for its implemented semantics.

The hybrid method therefore has a narrow technical purpose:

1. use independent ML classification as corroborating evidence;
2. retain rule-derived localization and operational explanation;
3. surface disagreement instead of hiding it; and
4. preserve enough provenance to reconstruct every decision.

The hybrid method is not a second copy of the Rule Engine, a way to
fill ML outputs from ground truth, or a claim that a probability is
calibrated confidence.

## 3. Immutable bindings

Hybrid Policy v1 is bound to the existing campaign and baselines:

- campaign P2_ROUTING_5CTX_V1 and its accepted run identifier;
- merged Dataset Row v2 SHA-256 from D-067;
- D-058 complete-context 18/6/6 split with G02 as test;
- D-069 rule-based result and report SHA-256;
- D-071 ML feature matrix and SHA-256;
- D-073 selection, estimator, and ML report SHA-256 values; and
- frozen class order no_fault, missing_static_route,
  wrong_next_hop.

Any binding mismatch is an integrity failure. The future Hybrid
Engine must fail before producing a prediction; it must not silently
substitute a file, retrain a model, or repair an input.

## 4. Prediction-time boundary

The future Hybrid Engine may read only:

- sample identity;
- a reference to the shared Evidence v2 artifact;
- the original rule prediction;
- the original ML prediction;
- the frozen hybrid policy; and
- the frozen ML model binding carried by the ML prediction.

The following inputs are forbidden at prediction time:

- ground truth or Dataset Row labels;
- partition identity;
- rule or ML correctness flags;
- per-experiment evaluation;
- Method Evaluation Result metrics; and
- test results.

Only the Evaluator may open ground truth. The rule and ML outputs are
immutable source artifacts. The Hybrid Engine creates a third output
and never rewrites the first two.

## 5. Normalization

The Rule Engine is normalized as follows:

- NO_FAULT_DETECTED with no diagnosis becomes no_fault;
- DIAGNOSIS_PRODUCED uses diagnosis.fault_type;
- INSUFFICIENT_EVIDENCE is non-final; and
- UNDETERMINED is non-final.

The ML output is normalized as follows:

- NO_FAULT_DETECTED becomes no_fault; and
- DIAGNOSIS_PRODUCED uses diagnosis.fault_type.

Unsupported statuses, classes, malformed documents, sample-identity
mismatches, or hash mismatches are integrity failures. A valid but
non-final diagnostic input leads to abstention rather than a guessed
class.

## 6. Frozen candidate policies

Exactly two candidates are precommitted in this order.

### 6.1 consensus_abstain_v1

This is the lower-complexity candidate.

- If normalized rule and ML classes agree, accept that class.
- If the agreed class is a fault, copy location and affected_prefix
  only from the rule diagnosis.
- If the agreed class is no_fault, keep location and prefix null.
- If the classes disagree, abstain.
- If either input is valid but non-final, abstain.

### 6.2 rule_guarded_fallback_v1

This candidate has the same agreement and non-final behavior. On a
class disagreement it may accept the rule class only when all five
guards pass:

1. the rule status is final;
2. exactly one known rule matches the normalized class;
3. rule_support_score equals 1.0;
4. contradicting_evidence is empty; and
5. a fault contains non-empty rule-derived location and prefix.

The score is deterministic rule support, not a calibrated
probability. Failure of any guard causes abstention.

No ML-priority candidate is included. The current classifier has no
localization output and its probabilities are not calibrated. Using
one of those probabilities as an unconditional override would add an
unsupported threshold and weaken the explanation contract.

## 7. Decision output

A future hybrid prediction has method hybrid and exactly one of:

- NO_FAULT_DETECTED;
- DIAGNOSIS_PRODUCED; or
- ABSTAINED.

ABSTAINED has a null diagnosis and a machine-readable reason. A
produced fault diagnosis requires a rule-derived location and affected
prefix. Copying either value from ML or ground truth is forbidden.

Every output explanation must retain:

- the hybrid decision reason;
- references and hashes for the original rule and ML predictions;
- rule supporting evidence;
- the ML model explanation;
- the frozen policy binding; and
- the frozen model binding.

Explanation means traceable decision provenance. It does not mean a
post-hoc claim that either source method was correct.

## 8. Validation-only selection

P5-R1 will implement both candidates and run selection only on the
six validation rows in G01. Candidate selection is lexicographic:

1. maximize macro-F1 over the full validation denominator;
2. maximize exact-diagnosis rate over the full denominator;
3. maximize decision coverage;
4. minimize complexity_rank; and
5. use ascending candidate_id as the final deterministic tie-break.

An abstention counts as incorrect for supervised selection metrics
and is also reported separately. This prevents a candidate from
obtaining an artificially strong score by refusing difficult rows.

If the candidates tie on the observed validation data, the lower
complexity rank selects consensus_abstain_v1. This is a precommitted
tie-break, not a conclusion about test performance.

G02 remains closed until candidate implementation, validation-only
selection, policy-selection artifact persistence, and an independent
freeze verification all succeed. No test prediction or metric may
exist in the P5-R0 artifact.

## 9. Abstention-aware evaluation

The future hybrid report keeps the shared three-class targets and
full partition denominators. An abstention:

- is a false negative for the actual class;
- is not a false positive for any predicted class;
- is incorrect for accuracy and exact diagnosis;
- is incorrect for affected-prefix correctness on a fault row; and
- is counted in coverage, abstention count, abstention rate, and
  per-class abstention count.

The existing three-by-three class confusion matrix remains for
resolved class predictions. Per-class abstention counts account for
the remaining rows, so matrix cells plus abstentions reconcile with
each actual-class support.

Before a real hybrid report, Method Evaluation Result v1 must receive
a backwards-compatible hybrid provenance and abstention extension.
No existing D-069 or D-073 report may be rewritten.

## 10. Provenance contract

A future hybrid report must bind:

- Hybrid Policy v1 and the later selected-policy artifact;
- D-069 rule baseline;
- D-071 feature matrix;
- D-073 selection, estimator, and ML report;
- campaign result; and
- split manifest.

Each sample must carry seven path-and-SHA-256 references:

1. Experiment Manifest;
2. ground truth;
3. Evidence v2;
4. original rule prediction;
5. original ML prediction;
6. hybrid prediction; and
7. per-experiment evaluation.

Ground-truth and evaluation references are report provenance only.
They are not Hybrid Engine inputs.

## 11. Planned Phase 5 sequence

- P5-R0: freeze this policy, schema, bindings, candidates, selection
  order, abstention semantics, and provenance requirements.
- P5-R1: implement both candidates, use only G01 validation for
  selection, and persist the selected policy before any test access.
- P5-R2: independently verify the selected policy and source hashes,
  run one report-only G02 evaluation, and produce the first hybrid
  Method Evaluation Result.
- A cross-method interpretation is permitted only after P5-R2 passes
  the shared evaluation and provenance gates.

## 12. P5-R0 exclusions

P5-R0 does not:

- generate hybrid predictions or metrics;
- open G02;
- choose a candidate;
- change D-069 or D-073;
- recalibrate ML probabilities;
- add a threshold;
- infer ML-only localization;
- add fault classes; or
- address multiple simultaneous faults.

These exclusions keep the policy auditable and prevent the observed
test result from influencing its design.

## 13. Accepted P5-R0 verification

The frozen contract was applied and verified on 2026-08-05 against
the accepted P4-R1 closeout at commit 753e075.

- Policy SHA-256:
  a25467e9cfd8bb52cc67b0c3886eb439466ee51a27b22d292ee468d060bdecc7.
- Accepted baseline hash bindings: 5/5 PASS.
- Frozen candidate definitions: 2/2 PASS.
- Selection partition: validation only.
- Selected candidate: absent.
- Hybrid prediction API: absent.
- Hybrid predictions and metrics: absent.
- Targeted contract tests: 11/11 PASS.
- Complete regression suite: 216/216 PASS.
- Accepted baseline artifacts after verification: 5/5 SHA-256
  unchanged.

This evidence closes P5-R0 as a policy-freeze milestone. It does not
implement either candidate or establish hybrid performance. P5-R1
must preserve this policy byte-for-byte while implementing both
candidates and selecting only on validation.

## 14. P5-R1 implementation boundary

The P5-R1 implementation preserves the policy bytes and canonical
SHA-256. Hybrid prediction is separated from ground-truth evaluation:

1. verify the policy and five accepted baseline hashes;
2. bind only the 18 train and six validation source predictions;
3. generate both candidates for all 24 samples;
4. only then allow the Evaluator to read development ground truth;
5. compute the frozen abstention-aware metrics;
6. select only from G01 validation summaries; and
7. atomically persist and independently verify selection.json.

The runtime directory is models/p5_r1_hybrid_policy_v1. It contains
two candidate manifests, 48 immutable candidate predictions, 48
per-sample evaluations, and one selected-policy artifact. It must not
contain a test partition or any G02 hybrid output.

Hybrid Prediction v1 retains the three source references, the rule
and ML explanation forms, the policy/candidate binding, the ML model
binding, the decision reason, and all five guard outcomes when the
guarded fallback is evaluated. Integrity drift fails before output;
it never becomes abstention.

The canonical P5-R1 execution and independent verification succeeded
without changing this policy. Both candidates produced 1.0
full-denominator macro-F1, 1.0 exact diagnosis, and 1.0 coverage on
train and validation, with zero validation abstentions. The frozen
tie-break selected consensus_abstain_v1 by complexity rank 0.

The selected-policy SHA-256 is
59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507.
All 48 predictions, 48 evaluations, two manifests, and 99 runtime JSON
files are limited to train and validation. G02 remains closed until
P5-R2 independently rebinds the committed implementation, this
policy, the selected-policy artifact, and the five accepted
baselines.

## 15. Accepted P5-R2 execution

The P5-R2 coordinator executed without modifying this frozen policy.
It independently verified policy SHA-256, the five baseline hashes,
selected-policy SHA-256, consensus_abstain_v1, and all P5-R1
development runtime artifacts before any G02 source collection.

It generated only six selected-candidate G02 predictions, finished
that batch before ground-truth evaluation, and atomically produced
the complete hybrid report plus Cross-Method Comparison v1. The
report reused 24 P5-R1 development outputs and carried 210
sample-level artifact references across 30 records.

The real G02 hybrid result has 1.0 macro-F1, exact diagnosis,
affected-prefix correctness, and coverage, with zero abstentions. The
report and comparison hashes are recorded in HANDOFF_P5_R2. All
14/14 targeted and 243/243 regression tests passed, and independent
verification confirmed that G02 remained report_only and introduced
no test-derived policy or selection change.
