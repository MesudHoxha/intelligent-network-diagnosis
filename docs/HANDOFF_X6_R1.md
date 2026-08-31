# X6-R1 packet-loss handoff

X6-R1 implements only the frozen F1 controlled packet-loss vertical slice from
published source boundary `f737c05fde265610e2cddf0b536b4a30fe37bb5b`. It
uses the X6-R0.5 corrected topology and its symmetric endpoint `/32` routes;
the X6-R0.4 topology remains historical and unchanged.
Its source gate must pass before the single authorized Containerlab pilot. The
pilot is authoritative only if all six observations are available, the 10%
NetEm mutation independently yields 6--25 losses over exactly 150 probes,
pfifo `20:` has zero overflow drops, the exact conditional signature diagnoses
`R_X6_PERFORMANCE_001`, and restoration, fresh-process replay, three
baseline-after windows, raw hashes, and cleanup pass.

Raw baseline measurements remain unmodified in their durable window records.
Before the manifest is frozen, X6-R1 converts only the manifest's ten numeric
baseline inputs to the accepted six-decimal, half-even canonical form. This
keeps the serialized baseline list and independently recomputed manifest
fields semantically identical; it is not a threshold or parameter adjustment.
The pre-mutation tree from the failed semantic-validation attempt is preserved
as diagnostic/non-authoritative and contains no fault evidence or diagnosis.

Any valid but non-separating post-mutation run is durable diagnostic evidence,
not authority, and cannot be rerun opportunistically. F2--F4, datasets,
ML/Hybrid, metrics, API/dashboard, generalized claims, and P9-R2 remain out of
scope. No next milestone is authorized until this one controlled pilot is
classified and X6-R1 is locally committed.
