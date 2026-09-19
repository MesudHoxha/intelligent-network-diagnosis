# X6-R1.4.1 handoff

The corrected prospective entrypoint is
`python -m src.orchestration.x6_r1_4_1_production_path`. Standalone
classification, ownership-scoped cleanup, and read-only replay use
`python -m src.orchestration.x6_r1_4_1_recovery`.

Neither command is authorized by this source-only correction. Any future
authorization must use the R1.4.1 schema, bind the eventual committed R1.4.1
source, and receive a fresh exact user review. The preserved R1.4 review wrapper
is historical, unissued, and incompatible with this successor.

Before any future issuance, repeat all accepted readiness and image checks.
Before any attempt, separately confirm that the concrete authorization remains
within its live boot and validity interval. Atomic create-if-absent publication
of the complete reservation spends it;
only the durable post-reservation positive decision permits lifecycle entry.
If interruption leaves `ADMITTED` or an incomplete `CONSUMED` persistence
sequence, standalone recovery may only validate and classify the spent state.
It must not complete consumption, create missing run evidence, resume traffic,
or clean resources because no lifecycle-owned deployment can precede complete
consumption persistence.
