# X6-R1.5.1 postmortem-correction review handoff

Status: `REVIEW_ONLY_NOT_ACCEPTED`

The append-only proposal is
`plans/expansion/X6_R1_5_1_POSTMORTEM_CORRECTION_REVIEW_PROPOSAL_V1.json`.
Its SHA-256 is
`c908748d102511f201f9d06e79e50022ffddd33ec4582624e2a3f5f353810f92`.
It is bound to published commit
`287809ecc74bc3962de67fb903058fc6db09e899`, the accepted frozen manifest,
the immutable failed attempt, and the external postmortem inventory. Nothing in
this review changes `F1_ATTEMPT_FAILED`, the spent authorization,
`qualified:false`, `scientific_acceptance:false`, or historical `0/10_FALSE`.

Two source corrections are proposed. First, failed-path replay must reconstruct
every completed F01-F03 raw observation and compare any persisted fault
effectiveness, Evidence v4, Feature Vector v2, predicate, diagnosis, and
commit-record artifacts. It must distinguish a legitimate incomplete prefix
from a missing required artifact or contradiction, and it must not require
nonexistent R01-R03 windows to verify completed fault evidence. Second, a
well-formed diagnostic abstention must be persisted as an unsuccessful outcome
without preventing owned restoration, cooldown, R01-R03, cleanup,
terminalization, and replay when a separate operational safety gate still
passes. Command, integrity, ownership, timing, unsafe-state, and interruption
failures still stop further measurements and enter the accepted recovery path.

The proposal also makes the existing six-place `ROUND_HALF_EVEN` promise exact:
derive and normalize each window, aggregate normalized decimal values, normalize
each aggregate once, and compare Decimal values to unchanged frozen Decimal
boundaries with unchanged operators. This needs explicit acceptance because the
published implementation uses binary floats for the fault aggregate and
predicate comparisons. The discrepancy did not change this attempt's outcome.

The methodological question remains separate. TCP standards make major
throughput degradation during packet loss plausible because loss invokes TCP
recovery and congestion response, and the retained run shows loss,
retransmission-related observations, increased RTT, and reduced receiver
throughput together. The evidence does not isolate causation or establish that
baseline-level latency and throughput are the best F1 discriminators. The
smallest compliance successor therefore preserves the frozen manifest and all
six predicate operators. Any alternative rule requires a later prospective
review and independent future evidence across relevant fault classes; this
spent attempt cannot tune it.

No central record changes are proposed now. If these exact decisions are
accepted, the next step is the smallest append-only source successor with
focused failpoint, abstention/restoration, failure-path replay, and numeric
boundary coverage, followed by finalized-source verification. That acceptance
would authorize source implementation and source-only verification only. It
would not authorize a new F1 attempt, threshold changes, historical
reclassification, or scientific acceptance.
