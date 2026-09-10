# X6-R1.3.8 decisions

## D-X6-R1.3.8 — Correct the integrated production lifecycle before authorization

R1.3.8 is an append-only, source-only correction over published R1.3.7
(`4f62b04112f8af23ab31ab98b92e0cc54e42b5cb`).  It leaves every historical
file unchanged and supplies the normal successor production and recovery
entrypoints needed to correct the R1.4 Phase-1 blockers.

The corrected lifecycle uses the R0.5 topology and frozen `ind-linux:0.1`
image, validates actual canonical output identity, reserves one attempt in a
sibling durable ledger before creating the run tree, records command intent
before invocation, deploys before container-dependent observations, captures
in-container controls before destruction, and derives post-destruction cleanup
from host-side observations.  A host-wide topology lease prevents concurrent
successor controllers from sharing the fixed `x6r1` resource identity.

Composite traffic uses the accepted monotonic schedule.  Duration and startup
skew are reconstructed from bound command timestamps.  Numeric observations
are represented at the accepted six-place, half-even boundary before threshold
construction.  The threshold formula, cohort partition, timing constants,
topology, traffic, and scientific meaning are unchanged.

Handled failures and interruptions are terminalized durably.  A distinct
process may recover an abruptly terminated attempt from the durable global
reservation, action intents, ownership observations, and failed or incomplete
command records.  Authorization remains spent.  Independent verification
reconstructs measurements, timing, ordering, thresholds, controls, cleanup,
and replay from raw records and rejects contradictory summaries.

This correction creates no R1.4 authorization and executes no runtime work.
The historical authorization vector remains exactly `0/10_FALSE`.  Synthetic
external observations are test evidence only and can never qualify or become
networking evidence.

