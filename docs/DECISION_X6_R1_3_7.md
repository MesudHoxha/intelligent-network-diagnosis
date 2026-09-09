# X6-R1.3.7 Decision — detached predecessor-snapshot validation

## Decision

The direct published invocation of the R1.3.6 gate at `bdf2fecb6c9042f36c8931175aa90bf91493433d` is preserved as a failed Phase-1 diagnostic: its R1.3.5 helper requires a repository whose `HEAD` is `03af67568c9ee55398d2bf7f8d4f76091d7f73b5`, but the published R1.3.6 checkout is necessarily a successor.

R1.3.7 does not edit that gate or reinterpret its result.  It validates R1.3.5 in an exact detached `03af675…` snapshot, validates the immutable R1.3.6 tree and committed inventory in a separate exact detached `bdf2fec…` snapshot, and checks current-successor ancestry separately.  No current-worktree file is used as historical proof.

## Safety boundary

This is source-only and preserves the historical authorization vector at `0/10_FALSE`.  It creates no prospective R1.4 authorization and authorizes no Containerlab lifecycle, traffic, measurement, mutation, recovery, evidence, diagnosis, dataset, model, metric, API, thesis result, or scientific claim.

## Frozen diagnostic acceptance convention

Six immutable R1.3.6 current-worktree nodes are separately retained as `R1_3_6_FROZEN_CURRENT_WORKTREE_TEST_RETAINED_AS_EXPECTED_DIAGNOSTIC`; each preserves its actual documented early-helper failure and hash-bound receipt.  They are not passing acceptance tests.  The successor-applicable set is every other collected node, with a disjoint exact-union proof.  R1.3.7 additionally proves blob-integrity rejection in a valid detached historical snapshot, so the sixth node's intended assertion remains positively covered.
