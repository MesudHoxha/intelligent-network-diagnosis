# X6-R1.5 decisions

## D-X6-R1.5 — Future F1 consumes the qualified baseline freeze

X6-R1.5 is an append-only source-only successor to published boundary
`ff327c10e69e0f08a5c3586e169392667fe2d893`. It preserves all published
baseline and historical F1 sources and records.

The successor consumes the exact accepted baseline manifest. Its ten pre-fault
windows validate compatibility only. They cannot build, retune, replace, or
select thresholds. Pre-fault and restoration observations use six-place
`ROUND_HALF_EVEN` normalization and both frozen inclusive bounds. Fault
diagnosis retains the directional six-predicate `R_X6_PERFORMANCE_001` rule.

All phases derive interface utilization from the first pre-control command's
raw monotonic start through the last post-control command's raw monotonic
completion. Baseline and restoration require exact `noqueue 0:` and empty
filters. The fault phase requires the owned NetEm `10:` root and pfifo `20:`
child at `10:1`, with empty filters. These phase contexts are intentionally
different; their traffic-context identifiers are not aliases.

Fault effectiveness, diagnosis, restoration, owned cleanup, and independent
verification are separate outcomes. A complete runtime and replay are
necessary but do not by themselves establish scientific acceptance. Source
tests use only controlled external substitutes and establish no runtime result.

The R1.4.1 one-attempt commitment remains intact: atomic reservation spends an
attempt, durable admission precedes lifecycle entry, and recovery cannot resume
traffic. Recovery may restore and clean only independently established owned
state. Threshold rebuilding, automatic retry, fault-derived calibration,
F2-F4 work, datasets, models, API work, and generalized claims remain
prohibited.

Historical authorization remains `0/10_FALSE`; this source successor creates
and consumes no runtime authorization.

The independent verifier rebuilds the complete F01-F03 aggregate from raw
command observations, including pooled RTT, loss count, NetEm and pfifo deltas,
Evidence v4, Feature Vector v2, provenance hashes, effectiveness, predicates,
and diagnosis. Persisted derived artifacts are comparison targets and never
reconstruction inputs.

For a committed interrupted attempt, any completed-cleanup claim requires
independent reconstruction of cleanup-before ownership, action ordering,
cleanup-after absence, the cleanup journal, restoration controls when mutation
occurred, and recovery-session consistency. Pre-deployment ineligibility may
claim that cleanup was not required. `CLEANUP_FAILED` may preserve incomplete
or failed observations but cannot claim cleanup success.
