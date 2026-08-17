# HANDOFF X2-R4 — Duplicate IP

Date: 2026-08-17

Status: ACCEPTED — REAL CONTAINERLAB LIFECYCLE VERIFIED

## 1. Completed

- isolated duplicate claimant and observer namespace;
- durable recovery and idempotent restoration;
- Evidence v4 active plus temporal MAC proof;
- `R_X2_ADDRESSING_004` with fail-closed behavior;
- unit and opt-in Containerlab lifecycle coverage.

## 2. Decisions

Duplicate IP requires two positive observations: an active responder and at
least two distinct responder MACs in temporal samples. Neither alone suffices.

## 3. Files

Scenario, runtime contract, injector, collector, rule engine, orchestrator,
tests, gate, schema, plan and central documentation are added or updated.

## 4. Open issues

No X2-R4 runtime issue remains. Final acceptance used the existing `tcpdump`,
`ping` and neighbor-cache tools to prove the two-MAC temporal trace, followed
by confirmed restoration and zero-container cleanup.

## 5. Next step

X2-R5 closes the addressing slice group only after X2-R4 acceptance.

## 6. Central-document impact

`MASTER_CONTEXT`, `DECISIONS`, `STATUS` and `ROADMAP` record the isolated
runtime slice without modifying frozen Phase 6/7/8 or API v1.
