# X6-R1.5.1 source-only acceptance-review addendum

Status: `ELIGIBLE_FOR_SOURCE_ONLY_ACCEPTANCE_PENDING_SEPARATE_EXPLICIT_ACCEPTANCE`

The one-off evidence decision is recorded in
`plans/expansion/X6_R1_5_1_SOURCE_ONLY_VERIFICATION_EVIDENCE_DECISION_V1.json`.
It is bound to candidate inventory SHA-256
`9d4c76de416d2b932856c0207efe7d37bad102af9ebafdfeb6dec34677039799`,
source-plan SHA-256
`74009c411d0d2dd60cdaa397f79468865e092f198bf9c04639e0db0b0a5f6628`,
final-reconciliation SHA-256
`1154a14fa0eef622d3a97ecce049800653384ce3b511c99b69700d9f5335afad`,
and primary verification-plan SHA-256
`af9f39a7e449e1c98df6a2756339b49f015cd8923a03e5f98bb4e6f9830ea39c`.

The preserved first primary shard-01 attempt has record SHA-256
`9972c4d7a5e9e48e7d1f460c0bc16a582047fcc8da7d9c5e503fb24c39f3ee22`.
It remains a failed verification attempt: 77 passed, one skipped, 13 errors,
and return code 1. The observed value was 5.526556567 seconds against the
five-second scheduling reference, yielding startup skew 0.526556567 seconds
against the unchanged 0.250-second limit. The underlying cause is unproven.
The attempt is not passed, an approved historical diagnostic, or an invalid
non-result.

The exact replacement record has SHA-256
`c119ec7f3c9ca838052b1eca7b36dfb087bfaf11f33d6f22cd0e71586cab12d6`.
It reports 90 passed, one skipped, and return code 0. Both attempts bind the
same frozen primary verification plan and the same 91-node list at SHA-256
`4da18be5e8b14a2fd64a8d9265f453e86770c07c7464b0eaa44f719a9ef70d71`.
The decision permits this replacement to satisfy final primary coverage only
for those exact bindings.

No node, threshold, criterion, diagnostic requirement, or verification
requirement is waived. The decision creates no general retry policy and does
not extend the earlier R1.5 lost-evidence exception. The immutable plans,
inventories, attempt records, receipts, reconciliation, and original 17-file
candidate remain byte-for-byte unchanged.

With the sole evidence-governance blocker resolved, the completed review now
recommends the R1.5.1 candidate as eligible for a separate explicit
source-only acceptance decision. This addendum does not accept R1.5.1,
authorize a commit or publication, establish a runtime result, or establish
scientific acceptance. The unchanged classifier methodology remains a
documented limitation. Historical authorization remains `0/10_FALSE`;
frozen thresholds, X5 authority, consumed-pilot evidence, the spent failed
runtime attempt, and all protected evidence remain unchanged.
