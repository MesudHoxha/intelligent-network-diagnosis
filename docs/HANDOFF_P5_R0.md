# HANDOFF — P5-R0 Hybrid Diagnosis Policy Freeze

Date: 2026-08-05

Status: COMPLETED

## 1. What was completed

P5-R0 froze and runtime-verified Hybrid Diagnosis Policy v1 before
any Hybrid Engine implementation, candidate execution, metric, or
test access.

The milestone:

- bound the unchanged D-067 campaign, D-058 split, D-069 rule report,
  D-071 feature matrix, and D-073 ML selection, estimator, and report;
- defined the exact prediction-time allowed and forbidden inputs;
- froze consensus_abstain_v1 and rule_guarded_fallback_v1;
- defined agreement, disagreement, non-final-input, integrity-failure,
  localization, affected-prefix, and explanation behavior;
- reserved candidate selection for P5-R1 validation only;
- kept G02 closed until selected-policy persistence and independent
  freeze verification;
- precommitted full-denominator abstention accounting and future
  seven-reference sample provenance; and
- implemented the JSON Schema and semantic validator for the frozen
  machine-readable policy.

Accepted verification evidence:

- policy ID: p5_r0_hybrid_policy_v1;
- policy SHA-256:
  a25467e9cfd8bb52cc67b0c3886eb439466ee51a27b22d292ee468d060bdecc7;
- accepted baseline hashes: 5/5 SHA-256 PASS;
- candidate definitions: 2/2 FROZEN;
- targeted tests: 11/11 PASS;
- complete regression suite: 216/216 PASS;
- selected candidate: absent;
- Hybrid Engine prediction API: absent;
- hybrid predictions and metrics: absent; and
- baseline mutations: absent.

The 36 joblib/NumPy deprecation warnings were inherited from the
accepted P4-R1 tests and did not affect the policy or any baseline
artifact.

## 2. What was decided

D-074 is approved, implemented, and runtime-verified.

Exactly two candidate policies remain authorized:

1. consensus_abstain_v1 accepts only rule/ML class agreement and
   otherwise abstains; and
2. rule_guarded_fallback_v1 may accept the rule class on disagreement
   only when all five frozen rule-integrity guards pass.

Both candidates abstain on non-final input. Accepted fault location
and affected_prefix may come only from a complete rule diagnosis.
ML-only localization, ground-truth copying, raw-output mutation,
test-guided design, threshold tuning, and probability recalibration
remain forbidden.

P5-R1 must implement both candidates and select only on the G01
validation group. The frozen order is full-denominator macro-F1,
full-denominator exact diagnosis, coverage, lower complexity rank,
and ascending candidate ID. An abstention remains incorrect on the
full supervised denominator and is reported separately.

P5-R0 closes only the policy-freeze milestone. It does not establish
hybrid performance or complete Phase 5.

## 3. Files created or changed

P5-R0 committed files:

- docs/DECISIONS.md;
- docs/HANDOFF_P5_R0.md;
- docs/HYBRID_DIAGNOSIS_POLICY.md;
- docs/MASTER_CONTEXT.md;
- docs/METHOD_EVALUATION_PROTOCOL.md;
- docs/ROADMAP.md;
- docs/STATUS.md;
- policies/hybrid/P5_HYBRID_POLICY_V1.json;
- schemas/hybrid_policy_v1.schema.json;
- src/hybrid/__init__.py;
- src/hybrid/policy.py; and
- tests/unit/test_p5_r0_hybrid_policy.py.

No generated hybrid runtime artifact was created. The accepted rule,
feature-matrix, ML selection, model, and ML report artifacts were
read through their frozen bindings and remained unchanged.

## 4. Open issues

- Implement both frozen candidate policies without changing D-074.
- Add backwards-compatible Hybrid Prediction and selected-policy
  artifact contracts.
- Extend Method Evaluation Result v1 with abstention and hybrid
  provenance while preserving the accepted D-069 and D-073 reports.
- Generate candidate outputs only for train and validation before
  selection.
- Persist and independently verify the selected policy before G02.
- Run the single report-only G02 evaluation only in P5-R2.
- Defer cross-method interpretation until the P5-R2 report passes all
  shared evaluation and provenance gates.
- Broaden contexts, repetitions, missing-evidence cases, and fault
  classes before any real-world generalization claim.
- Define a reproducible archive or publication policy for ignored
  runtime artifacts before thesis release.

## 5. Next step

Start P5-R1 — Implement and Select the Hybrid Candidates.

P5-R1 must:

- preserve the canonical P5-R0 policy bytes and SHA-256;
- implement both frozen candidates without adding a third policy;
- consume immutable rule and ML predictions without ground truth,
  labels, partition identity, correctness flags, or method metrics;
- implement deterministic abstention and rule-only localization;
- extend evaluation for full-denominator abstention accounting;
- execute candidate selection only on validation;
- persist the selected-policy artifact with source and policy hashes;
- independently verify the freeze before any test access; and
- stop before G02 report-only evaluation, which belongs to P5-R2.

## 6. Impact on central documents

- DECISIONS marks D-074 approved and runtime-verified.
- MASTER_CONTEXT records the accepted policy hash, verification
  evidence, and P5-R0 exclusions.
- HYBRID_DIAGNOSIS_POLICY records the accepted runtime verification.
- METHOD_EVALUATION_PROTOCOL retains the precommitted future hybrid
  abstention and provenance semantics without producing a report.
- ROADMAP closes P5-R0 while keeping Phase 5 in progress.
- STATUS records the verified policy freeze and names P5-R1 as the
  next milestone.
