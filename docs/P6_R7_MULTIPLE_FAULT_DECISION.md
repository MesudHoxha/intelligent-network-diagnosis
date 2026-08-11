# P6-R7 Multiple-Fault Academic-Value and Feasibility Decision

Date: 2026-08-11

Status: DECIDED — NOT AUTHORIZED IN THE CURRENT BACHELOR SCOPE

## 1. Decision question and boundary

P6-R7 asks whether a bounded simultaneous-fault experiment can add
defensible academic value to the accepted Phase 6 comparison without
creating ambiguous truth, invalid evaluation, or disproportionate new
scope.

This is a design and decision gate only. It does not inject a combined
fault, collect a new Evidence v3 artifact, create a multi-label row,
fit or select a model, change a rule or Hybrid policy, reopen E02/E06,
or calculate a new experimental metric. The accepted P6-R6 model,
policy, test results, and one-use report-only boundary remain immutable.

## 2. Required truth semantics

A valid simultaneous-fault experiment would have to distinguish at
least three sets for every sample:

- the **injected set**: mutations intentionally applied by the lab;
- the **effective set**: faults that still alter the observed flow
  after interactions with other injected faults; and
- the **diagnosable set**: root causes identifiable from the evidence
  available to the compared methods.

These sets are not guaranteed to be equal. Treating the injected set as
the prediction target would penalize a method for not reporting a fault
that another fault has made ineffective or unidentifiable. Treating only
the visible symptom as truth would discard the claimed multiple-root-
cause objective. The existing single-label `fault_type` and diagnosis
contracts cannot express this distinction.

## 3. Causal-masking and composition audit

The five non-healthy Phase 6 labels yield ten unordered two-fault label
pairs before any context or repetition is considered. The current
injectors do not form a generally composable pair system:

| Interaction | Design consequence |
| --- | --- |
| `missing_static_route` + `wrong_next_hop` on the same destination route | Mutually exclusive installed-route states; the route cannot be both absent and installed with the wrong next hop. |
| `interface_down` + a route fault bound to that interface | Linux removes the bound route; the route mutation can become impossible or observationally dominated. |
| An upstream forwarding failure + a downstream policy block | End-to-end failure alone cannot establish both causes; only independent policy evidence can expose the second state. |
| Two injectors with independent restoration snapshots | Injection order can change preconditions, recorded baselines, and safe restoration order. |

The direct Evidence v3 probes reduce ambiguity for some compatible
pairs, but they do not make all ten pairs valid or identifiable. A
scientifically defensible subset would therefore need pair-specific
causal definitions, legal injection orders, expected joint signatures,
and proofs that each label contributes observable information beyond
the other label.

## 4. Dataset and evaluation requirements

A balanced pair-only extension across the accepted six contexts and two
repetitions would nominally require 120 clean rows: ten pairs times six
contexts times two repetitions. Under the accepted 3/1/2 whole-context
allocation, each pair would still have only six train, two validation,
and four report-only test rows before incompatible pairs are removed.
Applying the four deterministic evidence masks only to the nominal 20
validation and 40 test rows would add 240 transformed inputs, but they
would not be independent network experiments.

Reusing the 72 single-label rows as if they were multi-label interaction
observations would be invalid. Reusing the consumed E02/E06 results for
design, fitting, selection, or threshold changes is also prohibited by
D-084. A valid extension would require a separately frozen campaign and
split, with sufficient support for every retained label combination.

The evaluation contract would need, at minimum:

- exact label-set match;
- per-label and micro/macro precision, recall, and F1;
- Hamming loss or error rate and Jaccard similarity;
- coverage, abstention, and insufficient-evidence rates; and
- explicit scoring rules for effective but non-identifiable labels.

None of those values is calculated in P6-R7.

## 5. Required implementation expansion

Authorizing runtime would require a separate versioned design for:

- compositional fault injection, preconditions, rollback order, and
  complete-baseline recovery;
- multi-set ground truth and Dataset Row contracts;
- multi-label Rule-based, Machine Learning, and Hybrid prediction
  contracts;
- leakage-safe multi-label fitting, selection, freeze, and one-use test
  authorization;
- multi-label evaluation and comparison reports; and
- pair-by-context acceptance tests and runtime smoke gates.

This is a new experimental track, not a small extension of the accepted
P6-R6 path. Its implementation cost would compete directly with the
remaining Dashboard/API, final evaluation, artifact archiving, thesis,
and defense work.

## 6. Gate assessment

| Criterion | Result | Basis |
| --- | --- | --- |
| Multi-label construct validity | FAIL | Injected, effective, and diagnosable sets are not yet equivalent or contractually separated. |
| Pair identifiability | FAIL | Some pairs are mutually exclusive, dominated, or order-dependent. |
| Dataset sufficiency | FAIL | A balanced nominal design is large while per-pair validation/test support remains small. |
| Comparable three-method evaluation | FAIL | All three accepted prediction/evaluation paths are single-label and require versioned redesign. |
| Safe reproducible execution | PARTIAL | Individual fail-stop injectors are proven, but atomic composition and rollback are not. |
| Incremental academic value | PARTIAL | Multiple faults are relevant future work, but the current thesis already realizes the required Rule/ML/Hybrid comparison over six classes and missing evidence. |
| Bachelor-scope proportionality | FAIL | The required new contracts, data, models, policies, and runtime gates are disproportionate to the defensible incremental claim. |

The gate does not meet the minimum conditions for runtime authorization.

## 7. Final decision

P6-R7 does **not** authorize a multiple-fault or multi-label runtime in
the current bachelor project. Phase 6 closes with the accepted
single-fault six-class campaign and the P6-R6 clean/missing-evidence
three-method comparison.

Multiple-fault diagnosis remains explicit future work. It may be
reconsidered only as a separately precommitted study with new truth,
composition, dataset, split, prediction, freeze, and evaluation
contracts. It may not reuse the consumed P6-R6 report-only test results
to guide that design.

The next milestone is P7-R0: freeze the scope and read-only contract for
the Dashboard and API. P7-R0 must expose only accepted artifacts and
must not add automatic remediation, production-network execution, or
new empirical claims.
