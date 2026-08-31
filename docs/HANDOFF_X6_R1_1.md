# X6-R1.1 handoff

Source boundary: `430333f4cc78ebad5aa3bdc1a1e7a24b1d991c11`.

The only X6-R1 pilot was consumed. Its mutation effectiveness, restoration,
and standalone replay records are hash-bound by
`plans/expansion/X6_R1_1_FAILED_PILOT_FAILURE_RECEIPT_V1.json`, but its
baseline-after record is `BASELINE_INVALID_AFTER`; the tree is therefore
diagnostic/non-authoritative. The receipt is a later closeout record, not a
runtime artifact. It must never be used to create missing Evidence v4, feature
vector, diagnosis, or acceptance claims.

The single-run failure receipt uses the repository accepted-runtime helper: an
ordinary archive-free checkout skips its materialized test explicitly, while an
explicit materialized request or an available incomplete/hash-drifted tree
fails. No synthetic runtime substitute is permitted.

The future runner writes atomic diagnostic terminal lifecycle records after
incomplete lifecycles without masking their original failure. The read-only
throughput audit is class C: current raw provenance cannot distinguish an
implementation error from host-local throughput variability. No runtime is
authorized. Keep F2–F4, X7, and P9-R2 paused.
