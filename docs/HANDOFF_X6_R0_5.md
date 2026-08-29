# X6-R0.5 topology bootstrap correction

X6-R0.5 preserves X6-R0.4 and changes only the experimental topology artifact
and bootstrap route semantics. Endpoint management defaults on `eth0` remain
untouched. The corrected topology installs explicit `/32` experiment routes on
`eth1`; static router routes are idempotent replacements. Its smoke test is
non-scientific: it cannot install qdiscs, run traffic measurements, create
Evidence v4, freeze thresholds, or invoke a rule.

The three earlier X6-R1 trees are retained as pre-mutation, non-authoritative
bootstrap diagnostics. They do not consume the one official F1 pilot. The
corrected bootstrap smoke passed locally with preserved management defaults,
exact structured route resolution, forwarding/reachability, and `r2:eth2`
`noqueue 0:`/no-filter pre-state. Its ignored provenance is non-scientific and
not F1 Evidence v4. X6-R1 may resume only after this correction is reviewed
and published.
