# X6-R1.3.4 handoff

This append-only source-only milestone adds a separate future baseline-only
execution CLI, a complete C01--C10/C11--C20/H01--H10 lifecycle, canonical
threshold finalization before C11, exact bounded raw command records,
idempotent owned-resource cleanup, standalone replay, and an independent
materialized verifier. It does not create a real authorization, invoke the
runner, collect runtime evidence, or change any of the ten authorization
fields: they remain `0/10_FALSE`.

The only test authorization is temporary and explicitly `source_test_only`.
The next milestone remains paused at
`X6_R1_4_BASELINE_ONLY_RUNTIME_AUTHORIZATION_REVIEW`.
