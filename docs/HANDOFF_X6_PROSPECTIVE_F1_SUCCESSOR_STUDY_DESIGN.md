# HANDOFF — prospective F1 successor study design

Status: `REVIEW_ONLY_NOT_ACCEPTED`
Published boundary: `babde86fd863d105b30262d205ced09995251515`

The accepted methodology proposal, its HANDOFF, and the methodology acceptance
record remain unchanged. This revision changes only the unaccepted study design
proposal and this HANDOFF.

The proposed study remains an exploratory binary comparison in the exact X6
context: 50 fixed paired blocks, each containing one preassigned matched
no-fault slot and one preassigned 10% packet-loss slot at `r2:eth2`. Thirty
whole blocks are development and twenty later whole blocks are evaluation. The
embedded inventory uses a fixed SHA-256 rank algorithm and seed to balance
N0-first/F1-first order 15/15 in development and 10/10 in evaluation. No slot
may be replaced, topped up, re-paired, or reused.

Precommitted assignment is the primary label. Physical effectiveness is an
independently reconstructed post-assignment outcome, and method prediction is a
third quantity. Every one of the 40 evaluation slots remains in primary
full-denominator accounting, including ineffective or ambiguous mutations,
operational failures, interruptions, and `NOT_RUN` slots. Effectiveness-qualified
sensitivity and clean-control specificity are secondary conditional results.
A correct prediction cannot create end-to-end success unless effectiveness or
clean control, terminalization, cleanup, replay, and required restoration also
pass.

ML receives only four target-phase aggregates: packet loss, successful-reply
ICMP RTT p95, TCP throughput, and interface utilization. Queue zero and absence
of rate limiting are common pre-method eligibility controls. Their qdisc
identity, hierarchy, phase, derivation, value, and gate status never enter ML
or hybrid routing. The historical six-predicate comparator remains unchanged.

The proposed ML arm is now fully specified: canonical six-place Decimal input,
NumPy float64 conversion, development-only population scaling with deterministic
zero-variance handling, and scikit-learn 1.7.2 `liblinear` L2 logistic
regression with fixed parameters, seed, convergence rules, and canonical
float-hex JSON serialization. The hybrid remains rule-first with inclusive
0.20/0.80 ML fallback limits; those limits are explicitly exploratory and
unvalidated. Preprocessing, model, thresholds, implementations, dependencies,
and report code freeze before evaluation collection or access.

Combined uncertainty and method differences use the 20 paired evaluation
blocks, not 40 independent attempts. The fixed procedure is a 10,000-replicate
paired-block percentile bootstrap using NumPy 2.5.1 PCG64 with the recorded
seed. Each sampled block carries both members and every incomplete or failed
status. Supplemental class-specific exact-binomial intervals assume blocks are
conditionally independent and remain descriptive because one shared host and
topology can retain serial dependence.

Development requires at least 24 complete eligible slots per assigned class
and 48 total fit rows. Evaluation requires at least 18 complete paired blocks
and at least 18 common-gate-passing slots per assigned class for the planned
exploratory interpretation. Failure, unusable model, environment drift, or
insufficient evaluation produces an explicit inconclusive terminal outcome.
All unstarted slots remain recorded; no additional collection follows
automatically.

The fixed planning estimate remains 100 attempts, 320 active measurement
seconds per attempt, roughly 13.3--20 serialized runtime hours, and 200--300
MiB with a 500 MiB reserve. Existing evidence supports the estimate: the
incomplete 13-window F1 lifecycle through recovery cleanup spans about 461.857
seconds and occupies 1,246,777 bytes; the complete 30-window baseline tree
occupies 2,284,429 bytes plus 268,443 bytes of external assessment. These are
planning references, not runtime authorization.

Focused consistency rereview: the revised proposal resolves the six review
findings without adding a class, model search, replacement policy, or campaign.
It is internally consistent and suitable for a separate design-acceptance
decision. Acceptance would still authorize only later source-only campaign
contract preparation. No implementation, collection, dataset/model operation,
or runtime slot is authorized; historical authorization remains `0/10_FALSE`.
