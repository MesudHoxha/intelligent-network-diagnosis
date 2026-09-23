# X6-R1.5 source-only acceptance-review addendum

Status: `ELIGIBLE_FOR_SOURCE_ONLY_ACCEPTANCE_PENDING_SEPARATE_EXPLICIT_ACCEPTANCE`

The narrow verification-evidence decision is recorded in
`plans/expansion/X6_R1_5_SOURCE_ONLY_VERIFICATION_EVIDENCE_EXCEPTION_V1.json`.
Its SHA-256 is
`a94b64c6f646aa607b7cfa0edd304d368d4a8a04753a06b8fdda0eaff8c1b882`.
It applies only to the first archive-free shard-14 attempt under source plan
SHA-256 `58a5caf1e66b609ff5de66e352a85898ac86022ee7f10a2d998fd07170a173ab`,
execution inventory SHA-256
`db7c19dcf3b9b9d5bbd8ae42eda4e1caf3a3dfad4a8b8f81facb1d908f14c487`,
and reconciliation SHA-256
`67df32c0e7c5c5621e059269fa077e08945018193c10d2534d9da624d2fbcd23`.

The first attempt remains a reported failed attempt with incomplete durable
evidence: 80 passed, one skipped, seven errors, and return code 1. Its error
causes and exact execution bindings are unrecoverable. The errors are not
attributed to the WSL reboot. The attempt is not harmless, passed, or an
approved historical diagnostic.

The independently bound replacement record at SHA-256
`3fa5e54eeb1b2f58d6bec777ce8446d6f46f9f99338c85ce9f65a1cac1d88f37`
may satisfy this candidate's final source-verification coverage. This does not
establish equivalence with the lost attempt, erase the reported failure, waive
any node or criterion, or create a general retry policy. All original plans,
inventories, receipts, attempt records, and reconciliation bytes remain
unchanged.

The two primary shard-01 startup-skew failures also remain visible. Attempt 1
reported 75 passed and 13 errors after C19 reached 0.315212119-second skew;
attempt 2 reported 75 passed and 13 errors after C06 reached
0.408197222-second skew. Both exceeded the unchanged 0.250000-second limit,
returned 1, and remain excluded from final passing totals without being
erased.

With the residual uncertainty explicitly accepted for this source-only review,
the previous evidence-governance blocker is resolved. The corrected R1.5
candidate is eligible for a separate explicit source-only acceptance decision.
This addendum does not itself accept R1.5, authorize a commit or publication,
or establish any runtime or scientific result. Historical authorization
remains `0/10_FALSE`; frozen thresholds, X5 authority, consumed-pilot evidence,
and protected evidence remain unchanged.
