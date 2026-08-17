# X2-R3 — Missing Default Route Runtime

Date: 2026-08-17

Status: IMPLEMENTED — TRANSACTIONAL ACCEPTANCE PENDING

## Scope

X2-R3 reuses the verified X2 addressing topology. HostA retains exactly
`10.20.1.10/24`; the injector removes only the default route via `10.20.1.1`
on `eth1`. Wrong IP, wrong subnet mask, duplicate IP, wrong gateway and
multiple-fault execution are outside this release.

## Safety lifecycle

The runtime validates the healthy baseline, writes durable recovery intent
before mutation, removes the exact route, confirms the fault signature,
collects native Evidence v4, creates Feature Vector v2, applies the reviewed
rule and restores the exact route. Restoration is idempotent and the final
baseline must pass. Failure after a mutation attempt triggers best-effort
restoration from the durable journal.

## Diagnostic signature

`R_X2_ADDRESSING_003` requires all four observed values:

- source address matches expected: `true`;
- source prefix matches expected: `true`;
- source default route present: `false`;
- duplicate address detected: `false`.

Rules `R_X2_ADDRESSING_001` and `R_X2_ADDRESSING_002` remain unchanged.
Unavailable evidence produces `insufficient_evidence`; any unreviewed
combination produces abstention.

## Scientific boundary

This release creates no dataset row, model fit, model selection, ML/Hybrid
prediction, metric or Phase 8 result. Evidence v3, accepted results, API v1
and the X2-R1/X2-R2 gates remain unchanged.

