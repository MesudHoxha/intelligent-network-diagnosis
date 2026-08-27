# X6-R0.2 F1 measurement-semantics correction

X6-R0.2 is source-only and append-only after published X5-R11. It preserves
X6-R0 and X6-R0.1 history, accepted X5 authority, and every scientific result.

For the future X6-R1 F1 pilot, use the locale-frozen non-quiet iputils ping
contract in `src/collection/x6_r0_2_measurement_semantics.py`. It derives loss
and exact successful-reply p95 from the same 50-packet window; it never uses
quiet-summary RTT reconstruction. Threshold manifests use canonical
baseline-only median/MAD calculation and SHA-256 binding. NetEm `10:` records
impairment effect; child pfifo `20:` is the only X1 queue-drop owner.

The X6-R1 pilot must still verify the actual Linux qdisc counters, source raw
output, threshold manifest before mutation, conditional predicates, recovery,
and cleanup. F3 finite bottleneck work remains blocked until X6-R3; F4 neutral
cap semantics remain blocked until X6-R4. P9-R2 remains paused.
