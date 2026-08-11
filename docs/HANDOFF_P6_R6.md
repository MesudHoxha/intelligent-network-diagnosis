# HANDOFF P6-R6

Date: 2026-08-11

Status: COMPLETED AND ACCEPTED

## 1. What was completed

P6-R6 implemented the four frozen non-destructive missing-evidence masks
and the new six-class Rule-based, Machine Learning, and Hybrid method
path. It transformed the accepted Dataset Row v3 split into a strict
ten-feature, 20-column leakage-safe representation without using labels,
partitions, mask identities, evaluation metadata, or provenance hashes as
predictors.

Six precommitted ML candidates were fit only on 36 clean E01/E03/E05
train rows. ML and five immutable Hybrid policies were selected only with
12 clean and 48 masked E04 validation inputs. The selected
`logreg_l2_c1` estimator and `rule_then_ml_fallback_v1` policy were frozen
and independently verified before any E02/E06 content was read.

One report-only evaluation then consumed the single authorization. It
created 24 clean and 96 masked E02/E06 inputs per method, completed with
one test attempt, and performed no refit, reselection, or test-guided
revision. All 185 targeted Phase 6 tests and the complete 428-test
regression suite passed.

## 2. What was decided

D-084 accepts the frozen P6-R6 model, policy, report-only artifacts, and
descriptive three-method comparison. All methods achieved 1.0 accuracy
and macro-F1 on 24 clean test inputs. On 96 masked inputs, Rule-based
returned `INSUFFICIENT_EVIDENCE` for every case, while ML and Hybrid both
achieved 0.791667 accuracy and 0.810486 macro-F1 with full coverage.

The Hybrid result is identical to the ML result and does not establish a
Hybrid advantage. No statistical-superiority test was performed. The
deterministic masked copies are robustness probes, not independent
network experiments. The E02/E06 one-use report-only authorization is
consumed, and the accepted test outputs may not influence later fitting,
selection, rules, features, thresholds, or policies.

## 3. Files created or changed

The implementation adds 15 P6-R6 files:

- the frozen method protocol;
- four strict method/freeze/report JSON Schemas;
- the Phase 6 method contracts, methods, and atomic coordinator;
- four unit-test modules plus their fixture; and
- `docs/P6_R6_SIX_CLASS_METHOD_GATE.md`.

Closeout also creates this HANDOFF and updates `docs/DECISIONS.md`,
`docs/MASTER_CONTEXT.md`, `docs/PHASE6_FAULT_TAXONOMY_PLAN.md`,
`docs/ROADMAP.md`, and `docs/STATUS.md`.

Runtime artifacts remain under `models/p6_r6_six_class_v1`,
`reports/experiments/p6_r6_six_class_v1`, and
`data/metadata/p6_r6_six_class_method_gate_v1.json`; they are verified
results rather than source files committed by this closeout.

## 4. Open issues

- decide whether a bounded multi-label multiple-fault experiment has
  sufficient academic value and feasible truth/evaluation semantics;
- if it is not justified, close Phase 6 without multiple-fault runtime;
- define a reproducible archive/publication policy for generated
  datasets, frozen models, and report artifacts before thesis archiving;
- keep OSPF proposed unless separately approved; and
- retain production execution and automatic remediation outside the
  current scope.

## 5. Next step

P6-R7 is the next milestone. It is a design and decision gate only. It
must assess multi-label truth, causal masking, non-identifiability,
dataset size, evaluation metrics, implementation cost, and bachelor-scope
value before deciding whether any bounded multiple-fault experiment is
authorized. P6-R7 must not inject combined faults by default.

## 6. Impact on central documents

- `DECISIONS.md`: adds D-084 and freezes the accepted P6-R6 result and
  its no-reuse/no-retuning boundary.
- `MASTER_CONTEXT.md`: records the selected candidates, one-use test
  execution, artifact hashes, metrics, and limitations.
- `STATUS.md`: marks P6-R6 completed and makes P6-R7 the next milestone.
- `ROADMAP.md`: records completion of the six-class method and
  missing-evidence evaluation gate.
- `PHASE6_FAULT_TAXONOMY_PLAN.md`: records the realized P6-R6 boundary
  without authorizing multiple faults or changing D-077/D-081.

## Accepted runtime identities

- selected ML candidate: `logreg_l2_c1`;
- selected Hybrid policy: `rule_then_ml_fallback_v1`;
- freeze-manifest SHA-256:
  `fa98a17e2ffae42f6dd009a13af65ad32174035eca8352bf26f321531a4fe0f5`;
- freeze-receipt SHA-256:
  `5c6c6537cb233efdeb52c6872f7a6ef7fb32eb3ac7b2474e2514b2908cd29bcc`;
- run-manifest SHA-256:
  `44c505b451c6211b4515564f4b889633b6d74ed0c618f19cc0ab3b9bdfe72b1d`;
- cross-method comparison SHA-256:
  `ca1c15d04828c0ae61cacaf80a5ee6f49f64a9cf3ac151a4b4ccd2386987e570`;
- targeted tests: 185/185 passed;
- full regression: 428/428 passed; and
- Containerlab use: not required and not started.
