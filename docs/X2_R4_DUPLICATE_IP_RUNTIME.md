# X2-R4 — Duplicate IP Runtime

Date: 2026-08-17

Status: IMPLEMENTED — TRANSACTIONAL ACCEPTANCE PENDING

## Scope

HostA keeps `10.20.1.10/24` and its default route. A crash-safe injector creates
a second L2 claimant with a reviewed distinct MAC and a temporary isolated
observer on the existing topology. No permanent topology file is changed.

## Evidence rule

`R_X2_ADDRESSING_004` requires address, prefix and default route to remain
correct, plus both active duplicate response and temporal responder-MAC churn.
The observer uses the already-installed `tcpdump`, repeated ARP-triggering
`ping` probes and neighbor-cache flushes; no runtime package installation is
allowed.
One signal alone is not diagnostic. Missing collection produces insufficient
evidence; other complete combinations abstain.

## Safety and boundary

Recovery intent precedes mutation. Restoration deletes the observer namespace
and claimant interface idempotently, then verifies the original source state.
The release creates Evidence v4 and a Rule-Based v2 result only. Dataset, model,
metric, ML/Hybrid, multiple faults, API v2 and P9-R1 remain outside scope.
