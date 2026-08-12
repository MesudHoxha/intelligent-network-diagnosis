# P7-UX1 Dashboard Information Architecture Amendment

Date: 2026-08-12

Status: IMPLEMENTED AND AUTOMATED-TEST-VERIFIED; LOCAL VISUAL ACCEPTANCE PENDING

## 1. Purpose

P7-UX1 improves the user-friendliness, terminology, micro-explanations,
and information hierarchy of the accepted local Dashboard. It is a
presentation-only maintenance amendment performed after P9-R0 and before
P9-R1. It does not reopen Phase 6 evaluation or create a new Phase 9
drafting milestone.

The intended reading order is now:

1. result;
2. explanation;
3. evidence;
4. methodology; and
5. technical metadata.

The prior Dashboard exposed internal case/context identifiers and
methodological language before the user-facing diagnosis. Those values
remain available, but no longer lead the main view.

## 2. Controlled amendment to the accepted Phase 7 boundary

D-089 and D-090 accepted the original static Dashboard and closed Phase
7. P7-UX1 therefore records an explicit controlled amendment rather than
silently replacing that decision.

The following accepted boundaries remain unchanged:

- exactly six versioned same-origin `GET` data routes;
- exactly four Dashboard views and three static Dashboard assets;
- startup verification of the same 15 accepted projection sources;
- loopback-only `127.0.0.1:8000` operation;
- frozen Rule-based, Machine Learning, and Hybrid outputs;
- accepted ground truth, metrics, evidence, hashes, and provenance;
- no model deserialization, inference, retraining, remediation, network
  mutation, runtime artifact write, or new empirical claim; and
- fail-closed behavior when accepted sources are missing or drifted.

No OpenAPI, projection-layer, API-server, dataset, model, policy,
experiment, evaluator, or accepted runtime artifact is modified.

## 3. Main-view information architecture

### Overview

The main title is now `Network Diagnosis Evaluation`. It immediately
explains that the Dashboard compares expert rules, Machine Learning, and
a Hybrid method. The four primary cards are:

- Total evaluated cases;
- Original test cases;
- Missing-evidence tests; and
- Network conditions.

The descriptive-only research posture remains available as a methodology
note rather than occupying a primary result card.

### Method comparison

The comparison scopes are presented as `Original cases`, `Missing
evidence`, and `Overall`. Accuracy, Macro F1, Coverage, and Insufficient
evidence include short plain-language definitions. The remaining accepted
metrics and exact API-value metadata remain available under `View all
accepted metrics`.

### Case explorer

The table now leads with the network problem, human-readable network
scenario, evidence condition, and the three diagnostic outputs. Technical
input and context identifiers are removed from the primary columns. The
exact context filter remains available as an advanced filter, and each
case retains its technical identifier for detail retrieval.

`RESOLVED` is displayed as `Diagnosis available`. This avoids implying
that the network fault was remediated. Other statuses are also presented
in user-facing language without changing their API values.

### Case detail

The dialog title is the network condition rather than the input ID. It
shows, in order:

1. known ground truth with an explicit evaluation-only explanation;
2. traffic path, routing observer, affected/destination network, and
   evidence condition;
3. Rule-based, Machine Learning, and Hybrid diagnoses, confidence,
   status, location, and correctness;
4. a plain-language rephrasing of each accepted prediction reason;
5. all ten diagnostic evidence features with human labels, values,
   availability states, and micro-explanations; and
6. collapsed technical identifiers, artifact path, SHA-256 values, and
   exact accepted prediction reasons.

The per-case `Correct`, `Incorrect`, or `No diagnosis` display is a direct
presentation comparison between the already returned prediction and the
already returned evaluation target. It is not aggregated, persisted, or
introduced as a new metric.

### Research methodology and limitations

The former provenance view now leads with the research interpretation
and limitations. Selected model/policy IDs, artifact paths, and SHA-256
roots remain available in a collapsed technical-provenance section.

## 4. Explanation safety

P7-UX1 does not infer a new causal narrative from the feature vector. The
plain-language explanations use a closed mapping over accepted prediction
reason strings, including:

- exact deterministic rule-signature match;
- frozen six-class estimator selection;
- Hybrid acceptance of the rule output;
- Hybrid Machine-Learning fallback; and
- insufficient-evidence, no-rule-match, disagreement, and threshold
  outcomes.

The original reason string remains visible in Technical details. Feature
descriptions explain what each observation checks, not what new conclusion
should be computed from it. This preserves the distinction between
presentation and diagnosis execution.

## 5. Accessibility and responsive behavior

The existing skip link, semantic landmarks, native dialog, keyboard
focus, retry states, reduced-motion handling, and mobile table behavior
remain. New disclosure controls use native `details`/`summary` elements.
The new labels, evidence counts, result states, and helper text are
available as text and do not rely on color alone.

## 6. Verification

Verification checks:

- JavaScript syntax and HTML parsing;
- exact three-asset Dashboard boundary;
- exact six-route same-origin `GET` API boundary;
- main-view terminology and column ordering;
- evaluation-only ground-truth explanation;
- all ten evidence feature labels and descriptions;
- metric micro-explanations;
- retention of technical IDs, reasons, provenance, and SHA-256 values;
- loading, empty, fail-closed error, and retry states;
- responsive desktop/390-pixel DOM and stylesheet contract;
- 94/94 Phase 7 tests;
- 175/175 combined Phase 7 through Phase 9 tests;
- 185/185 targeted Phase 6 regression tests; and
- 603/603 full regression tests.

The 15 accepted projection-source hashes and the 1,488-artifact private
runtime chain remain outside the changed file set and are verified by the
local commit package before commit. Final visual acceptance remains
pending until the committed Dashboard is opened in the user's local
browser and the Overview, Case Explorer, and Case Detail views are
reviewed. The code environment's browser and the Work Mode cloud browser
cannot access the same loopback server, so no screenshot claim is made by
this document.
