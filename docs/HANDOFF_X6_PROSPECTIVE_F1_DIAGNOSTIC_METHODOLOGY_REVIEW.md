# HANDOFF — prospective F1 diagnostic methodology review

Status: `REVIEW_ONLY_NOT_ACCEPTED`

This revision supersedes only the unaccepted proposal and HANDOFF at SHA-256
`ef4db7d2c140525d6aa29caa451b9b4ac53df93843d50075fd7414c412a3265c`
and `ba1c2914f61bb83340f04007b21a5c25b286ed305d56e71936b1548dff6c74b3`.

The governing X6-R0.1 contract defines the F1–F4 predicate vectors as
conditional hypotheses. The spent R1.5 attempt truthfully rejected the exact
`R_X6_PERFORMANCE_001` conjunction: the owned 10% loss mutation was effective,
but pooled successful-reply RTT exceeded its frozen upper bound and TCP
throughput fell below its frozen lower bound. The rule abstained as designed.

The attempt establishes physical loss effectiveness, observed TCP
retransmissions and receiver-throughput degradation, exact raw-to-derived
artifact consistency, qdisc restoration, and diagnostic abstention. It does
not establish exclusive causation, population sensitivity or specificity,
cross-class separation, R01–R03 performance restoration, classifier validity,
or scientific acceptance. Correct execution of the exact six predicates and
the resulting abstention is not scientific validation of the rule.

TCP standards require congestion and loss recovery behavior after detected
loss. Primary measurement guidance also requires retransmission, delay,
windowing, host capacity, and network integrity context when interpreting TCP
throughput. Baseline-level TCP throughput is therefore not a generally
warranted invariant under effective packet loss. RFC 6349 guidance remains
context for TCP throughput testing, not a classifier threshold. RFC 6298
governs TCP-native RTT estimation and retransmission timers; it does not
explain or validate the measured ICMP ping p95. The project-defined latency
value pools only successful ICMP replies, while lost probes contribute to the
separate loss ratio. RFC 2681 is relevant to packet type, path, calibration,
and loss-handling disclosure, but its percentile treatment of undefined/lost
observations differs from this accepted successful-reply-only statistic.

The current six-predicate rule remains the historical strict conjunctive
comparator with unknown sensitivity and specificity. Prospectively describing
its narrow conjunction does not redefine the historical task, exclude the
spent attempt, change its expected outcome, or convert abstention into success.
The spent attempt remains an unsuccessful diagnostic outcome in evaluation.

The smallest justified next step is to preserve that historical comparator
and separately review a preregistered, versioned successor diagnostic design.
Before any new observation, that review must freeze inputs, aggregation,
operators, abstention, confounders, leakage controls, causal-context data
separation, sample-size justification, and numeric evaluation bounds.
Identifiers, paths, artifact names, collection timestamps, partition metadata,
injection state, labels, and effectiveness classifications may support
provenance, grouping, effectiveness, and audit but may never become rule or ML
predictors or hybrid selectors. Bound monotonic elapsed-time measurements remain
permitted only when they derive an accepted observable feature and carry no
wall-clock, identity, ordering, or partition information.

Every window, command observation, and derived artifact from an attempt must
remain in one partition. Correlated repetitions and parameter or topology
variants sharing a causal context must be grouped. The exact grouping key and
independence claim must be frozen before collection; window-level splitting is
prohibited. The spent attempt motivated this review and remains historical
evidence, but it is not untouched independent evaluation data for a successor
designed with knowledge of its results and cannot select a new rule.

For the thesis comparison, rule-based, ML, and hybrid methods must receive the
same leakage-reviewed observable boundary and independent evaluation examples.
Report per-class outcomes, abstention, evidence availability, and restoration
separately. A hybrid design requires its own selection/leakage review and may
not gain privileged ground-truth access.

Unresolved decisions remain the target diagnosis, predictor boundary, exact
no-fault and F2–F4 controls/confounders, independent evaluation unit and
grouping key, sample-size rationale and numeric bounds, outcome denominators,
and the common fairness contract for rule-based, ML, and hybrid comparison.
This proposal resolves none of those design choices implicitly.

Proposal:
`plans/expansion/X6_PROSPECTIVE_F1_DIAGNOSTIC_METHODOLOGY_REVIEW_PROPOSAL_V1.json`

This HANDOFF records no accepted methodological change, implementation,
runtime authority, dataset, model, metric, classifier validity, or scientific
result. Published R1.5.1, the frozen thresholds, six predicates, failed
attempt, spent authorization, X5 authority, consumed-pilot classification,
`0/10_FALSE`, and all protected evidence remain unchanged.
