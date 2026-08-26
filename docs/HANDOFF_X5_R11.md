# X5-R11 clean-checkout test correction

X5-R11 is source-only. It corrects a unit-test fixture dependency, not any
runtime behavior: the X5-R4 unavailable-evidence test now uses a temporary
synthetic Evidence v4 input and the canonical X5-R2 Feature Vector v2 builder.
That fixture is explicitly source-test-only and never accepted runtime evidence.

Receipt and archive validation remain materialized-only checks. A focused X5
source-test regression rejects direct ignored X5 raw-tree reads unless the test
is explicitly `accepted_runtime` gated. Corrected X5-R4 C4 and second X5-R9 C5
remain the authoritative boundary, unchanged.

Next: `X6_R1_PACKET_LOSS` remains paused. P9-R2 remains paused.
