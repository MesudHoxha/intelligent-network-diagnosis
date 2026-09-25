# X6-R1.5.1 decisions

## D-X6-R1.5.1 — Failed-path reconstruction and diagnostic abstention

X6-R1.5.1 is an append-only source-only successor to published R1.5 commit
`287809ecc74bc3962de67fb903058fc6db09e899`. Published R1.5 source, its failed
runtime attempt, the spent authorization, postmortem, frozen threshold
manifest, and every historical record remain unchanged.

The successor independently reconstructs each completed fault window from
bound raw command observations on successful, failed, and interrupted paths.
When F01-F03 are complete it recomputes fault effectiveness, Evidence v4,
Feature Vector v2, the six preserved predicates, and diagnosis. Persisted
artifacts are comparison targets. A commit-last assessment record binds the
ledger, authorization, source, run, original boot, frozen manifest, raw record
range, and derived artifact hashes. Complete, partial, legitimately absent,
missing-required, and contradictory states are distinct; partial persistence
never becomes accepted evidence.

A well-formed diagnostic abstention is an unsuccessful diagnostic outcome. It
may proceed through owned restoration, cooldown, R01-R03, cleanup, durable
terminalization, and replay while operational evidence remains valid. Command,
integrity, ownership, timing, unsafe-state, or interruption failures stop new
measurements and use the accepted recovery path. Restoration success cannot
convert abstention into overall acceptance.

Numeric observations use finite `Decimal` values. Each window feature is
normalized to six places with `ROUND_HALF_EVEN`; the established
feature-specific aggregation is then applied; and the aggregate is normalized
once to six places before comparison with unchanged Decimal boundaries and
operators. Pooled RTT p95 is selected from individual retained replies rather
than window percentiles. Integer counters and Boolean controls retain their
native types. Non-finite numeric inputs fail closed.

The immutable manifest, all six predicates, and all thresholds are unchanged.
The R1.5 methodological limitation remains unresolved and cannot be used to
reclassify the spent attempt, revise the classifier, or authorize another
experiment. Source-only verification establishes no runtime or scientific
outcome. Historical authorization remains `0/10_FALSE`.
