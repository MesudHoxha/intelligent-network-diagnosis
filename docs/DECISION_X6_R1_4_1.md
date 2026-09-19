# X6-R1.4.1 decisions

## D-X6-R1.4.1 — Commit authorization after durable reservation

R1.4.1 is an append-only source-only correction to published R1.4
(`9e2dee01d3f486cd0a523944523a1885bf8b9fac`). Published R1.4 source and
evidence remain historical and unchanged.

The one-attempt reservation is staged as a complete fsynced O_EXCL file and
atomically published under the final name with create-if-absent semantics. Its
publication is the spend point and never exposes partial JSON. It initially
grants no lifecycle authority. After the reservation file and parent directory
have been fsynced, the controller captures a post-reservation observation containing the
monotonic time and boot ID. That observation is the sole authorization decision
point. The lifecycle is reachable only when the observation is within the
authorization interval, matches its boot, and the positive decision has itself
been durably recorded. A late or interrupted decision is durably rejected and
remains spent. Expiry after a valid committed decision does not revoke cleanup,
terminalization, recovery, or evidence verification.

`RESERVED_UNDECIDED` and `REJECTED` precede authorization commitment.
`ADMITTED` is the durable positive commitment even when interruption prevents
the later `CONSUMED` persistence sequence from completing. Such an attempt is
permanently spent and is classified
`AUTHORIZATION_COMMITTED_CONSUMPTION_INCOMPLETE`; it cannot enter or resume the
lifecycle. A durable `CONSUMED` ledger without its identical run-local copy is
classified `AUTHORIZATION_CONSUMED_RECORD_INCOMPLETE` and is likewise never
resumed. Recovery and materialized verification use the same validator and
classification. They do not create a missing run root or fill missing
run-local records, and contradictory roots, identities, decisions, or state
combinations fail closed.

New-attempt validation uses the live boot and live monotonic clock. Historical
validation instead verifies the immutable authorization and its recorded
post-reservation decision in their original boot epoch. It never compares
monotonic timestamps from different boots. Each recovery session records its
own boot, process, command interval, and terminal result.

Recovery never resumes deployment, traffic, windows, or qualification. It may
reconstruct evidence and may run the existing ownership-scoped cleanup only
when deployment identity independently proves lifecycle ownership. Ambiguous
ownership produces `CLEANUP_FAILED`, preserves the observations, and performs
no destructive action.

The trust model remains `LOCAL_OPERATOR_ACCOUNT_V1`; the coordination lock may
still precede consumption solely for mutual exclusion. Historical authorization
remains `0/10_FALSE`. This correction issues and consumes no real authorization
and performs no runtime work.
