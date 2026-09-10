# X6-R1.3.8 handoff

R1.3.8 corrects the production integration defects found by the R1.4 Phase-1
review without changing accepted historical files or creating authorization.
The normal successor CLI is
`python -m src.orchestration.x6_r1_3_8_production_path`; it requires a separate
canonical R1.4 authorization and explicit `--execute`.  Standalone recovery is
`python -m src.orchestration.x6_r1_3_8_recovery`.

The correction binds the actual canonical output location, globally reserves
one attempt before any stateful action, uses the R0.5 topology and frozen image,
enforces deployment/observation/cleanup order, reconstructs composite timing
and measurements from raw command records, terminalizes failures, and supports
new-process recovery from durable intermediate state.  Test execution resolves
every external executable to the repository simulation stub and remains
`source_test_only`.

Historical-context preflight completed successfully.  The exact six R1.3.6
successor-context failures remain separately classified diagnostics.  The
seventh shared-document rewrite test passed through its intended rejection
path.  R1.3.7 valid-detached-snapshot, changed-blob source-integrity rejection,
and exact-partition replacement tests passed.

Full primary and archive-free source-only verification remains pending.  After
R1.3.8 acceptance, the next action is a renewed
`X6_R1_4_BASELINE_ONLY_RUNTIME_AUTHORIZATION_REVIEW`; baseline qualification
remains unexecuted.
