# Hybrid Engine Implementation — P5-R1

## 1. Purpose

P5-R1 implements the two candidates frozen by D-074 and selects one
only from the G01 validation group. It does not evaluate the selected
policy on G02 and does not produce the final hybrid Method Evaluation
Result.

The implementation is deterministic, local, open-source, and bounded
to the accepted three-class routing campaign.

## 2. Components

- src/hybrid/engine.py implements prediction, evaluation
  orchestration, validation-only selection, persistence, and
  independent verification.
- schemas/hybrid_prediction_v1.schema.json defines each candidate
  decision and its evidence/explanation bindings.
- schemas/hybrid_selection_v1.schema.json defines the atomic
  selected-policy artifact.
- src/evaluation/reporting.py implements full-denominator abstention
  metrics and the future hybrid report contract.

Hybrid Policy v1 remains unchanged at:

policies/hybrid/P5_HYBRID_POLICY_V1.json

Its canonical SHA-256 remains:

a25467e9cfd8bb52cc67b0c3886eb439466ee51a27b22d292ee468d060bdecc7

## 3. Prediction-time boundary

build_hybrid_prediction accepts only:

- sample_id;
- Evidence v2 artifact reference;
- rule prediction artifact reference;
- ML prediction artifact reference;
- the frozen policy and its path;
- candidate_id; and
- schema/hash verification configuration.

It has no parameter for ground truth, labels, partition identity,
correctness, evaluation documents, method metrics, or test results.

Integrity failures include malformed documents, unexpected statuses
or classes, source hash drift, sample/path identity drift, policy
drift, and ML model-binding drift. Integrity failure stops without a
prediction. A valid non-final rule result instead produces ABSTAINED.

## 4. Candidate behavior

consensus_abstain_v1 accepts only class agreement. On disagreement it
abstains.

rule_guarded_fallback_v1 shares agreement and non-final behavior. On
disagreement it evaluates the five D-074 guards in frozen order and
accepts the rule class only when every guard passes.

An accepted fault always copies location and affected_prefix from the
rule diagnosis. The ML diagnosis and ground truth are never a
localization source.

## 5. Ground-truth isolation

The coordinator first generates 48 predictions:

- two candidates;
- 18 train samples; and
- six validation samples.

Ground-truth references are path-bound during source indexing but
their content/hash is not read until all 48 candidate predictions
exist. The Evaluator then reads only the 24 development ground-truth
artifacts and writes candidate-specific evaluations.

No referenced G02 prediction, ground truth, or evaluation artifact is
opened in P5-R1. The accepted source report files are hash-verified,
but their G02 artifact references are not traversed.

## 6. Abstention-aware metrics

For each train/validation candidate summary:

- the denominator contains every row;
- abstention is a false negative for the actual class;
- abstention adds no false positive;
- accuracy and exact diagnosis count abstention as incorrect;
- fault-only affected-prefix correctness counts fault abstention as
  incorrect;
- coverage, abstention count/rate, and per-class counts are explicit;
  and
- the three-by-three confusion matrix contains resolved predictions
  only.

## 7. Selection and atomic output

Candidate ranking uses only validation metrics in this order:

1. maximize macro_f1_full_denominator;
2. maximize exact_diagnosis_rate_full_denominator;
3. maximize coverage;
4. minimize complexity_rank; and
5. use ascending candidate_id.

All runtime files are written into a temporary directory and renamed
atomically to:

models/p5_r1_hybrid_policy_v1

The final directory contains:

- selection.json;
- one candidate_manifest.json per candidate;
- one prediction.json per candidate/sample; and
- one evaluation.json per candidate/sample.

The implementation refuses to overwrite an existing P5-R1 output.

## 8. Independent verification

verify-selection rechecks:

- the policy and all five baseline hashes;
- Hybrid Selection v1 schema and semantics;
- both candidate manifests and every referenced runtime file;
- all Hybrid Prediction v1 documents;
- recomputed train/validation abstention metrics;
- the frozen selection order and winner;
- identical 24-sample candidate sets;
- absence of test records/directories; and
- the selected-policy SHA-256 supplied by the caller.

P5-R2 may open G02 only after this independent verification succeeds
and the selected-policy bytes are frozen in the next milestone.

## 9. Accepted P5-R1 status

The real hash-bound P5-R1 execution completed on 2026-08-05. It
generated 48 candidate predictions, 48 evaluations, two candidate
manifests, and 99 runtime JSON files for train and validation only.
Both candidates obtained 1.0 full-denominator macro-F1, 1.0 exact
diagnosis, 1.0 coverage, and zero validation abstentions.

The precommitted tie-break selected consensus_abstain_v1 by its lower
complexity rank of 0. The selected-policy SHA-256 is
59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507.
Independent verification recomputed the development metrics and
winner before G02 access. The policy and five baseline artifacts
remained unchanged, 14/14 targeted tests and the complete 229/229
regression suite passed, and no test prediction or metric exists.

P5-R1 is closed. P5-R2 must reverify the committed implementation and
frozen selection before it may create the single report-only G02
hybrid evaluation.
