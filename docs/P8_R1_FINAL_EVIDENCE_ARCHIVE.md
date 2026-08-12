# P8-R1 Immutable Final Evidence Registry and Private Archive

Date: 2026-08-12

Status: IMPLEMENTED — FINAL RUNTIME CHAIN ARCHIVED WITHOUT RECOMPUTATION

## 1. Purpose

P8-R1 closes the reproducibility-archive gap identified by D-091. It
creates one Git-tracked registry for the accepted final experimental
chain and one separate private deterministic archive containing the
ignored runtime bytes bound by that registry.

This milestone is archival only. It does not start Containerlab, mutate
a network, execute a diagnosis, deserialize an estimator, refit a model,
reselect a policy, reopen the test partition for evaluation, recalculate
a metric, or create a new empirical result.

## 2. Archive scope

The private runtime scope is the final numerical chain used by the
thesis, from the accepted P6-R5 dataset campaign through the accepted
P6-R6 report-only comparison:

- the accepted P6-R5 campaign result;
- all regular files in its 72-experiment raw runtime tree;
- six per-context Dataset Row v3 JSONL files;
- the 72-row merged Dataset Row v3 file;
- the split manifest and train, validation, and test JSONL files;
- the P6-R6 method gate;
- exactly 13 frozen development/model files, including the selected
  estimator as opaque bytes; and
- exactly 10 report-only input, target, prediction, report, comparison,
  and run-manifest files.

The exact file count, byte count, paths, roles, sizes, and SHA-256
digests are generated from the accepted repository at closeout and
recorded in
`plans/phase8/P8_R1_FINAL_EVIDENCE_REGISTRY_V1.json`.

## 3. Public/private separation

The tracked Git checkpoint remains the public source archive. The
registry binds the relevant tracked plans, contracts, implementation
files, HANDOFFs, P7 catalog, and P8-R0 scope gate, but marks them as
non-members of the private runtime payload.

The private archive contains only `REGISTRY.json`, a short archival
README, and the accepted ignored runtime artifacts beneath their
repository-relative paths. Failed campaigns, diagnostic-only attempts,
P7 self-test fixtures, caches, virtual environments, and unrelated
runtime files are excluded.

P1-P5 runtime artifacts remain developmental history. Their accepted
identities and outcomes stay recorded in tracked HANDOFFs and decisions,
but they are not silently promoted into the final P6 numerical evidence
archive. This keeps the archive aligned with D-091, which designates
P6-R6 as the final evaluation.

## 4. Integrity and failure behavior

The registry builder fails closed when:

- the accepted P6-R5 campaign, merged dataset, split manifest, or any
  partition hash has drifted;
- the raw tree does not contain exactly 72 experiment manifests;
- the six context datasets, four split files, 13 model files, or 10
  report files differ from the frozen sets;
- a method-gate, freeze, receipt, run-manifest, P7-catalog, or P8-scope
  reference is missing or hash-inconsistent;
- any runtime file is a symbolic link or escapes the repository; or
- a relevant public binding is not present in the tracked source
  checkpoint.

Archive members use fixed file mode, owner, group, timestamp, ordering,
and gzip timestamp. Rebuilding from the same registry and accepted bytes
therefore produces identical archive bytes. Verification reads every
member as raw bytes and checks the full member set, size, and SHA-256.

## 5. Estimator and test boundary

The selected estimator is required for a complete final chain, unlike
the narrower Phase 7 presentation bundle. P8-R1 hashes and copies its
raw bytes but never imports a serialization loader or inspects model
state. The receipt records `estimator_deserialized=false`.

The frozen test JSONL is similarly hashed and copied for preservation.
This byte-level archival access is not evaluation access: no prediction,
metric, comparison, model choice, rule change, or policy choice is
executed or revised.

## 6. Registry and receipt

The tracked registry records:

- the exact source commit and branch;
- eight accepted root bindings;
- every private runtime member;
- every relevant tracked public-source binding;
- the P7 catalog and P8 scope identities;
- the deterministic archive layout;
- ten false runtime-authorization flags; and
- the explicit exclusions and next milestone.

The separate tracked receipt binds the completed private archive by
filename, SHA-256, byte size, member count, registry identity, and
source checkpoint. The receipt is not embedded in the archive, avoiding
a circular hash dependency.

## 7. Verification

P8-R1 tests cover complete inventory, opaque estimator handling,
public/private separation, P7/P8 bindings, both JSON Schemas,
deterministic rebuilds, archive verification, receipt generation,
missing/drifted/extra/symlink failures, archive tampering, overwrite
refusal, and explicit exclusions.

Closeout also runs the combined Phase 7 plus Phase 8 suite, targeted
Phase 6 regression, and the full project regression. Accepted runtime
bytes are snapshotted before tests and compared after all verification.

## 8. Reproduction and preservation

The one-run closeout writes the private archive outside the Git
repository, beside the project directory by default, then commits only
the registry, receipt, implementation, tests, schemas, and documentation.
The archive must be backed up together with its receipt. A Git clone
alone intentionally does not contain ignored experimental artifacts.

## 9. Next step and limitation

P8-R2 is next. It may format already accepted metrics into thesis-ready
tables, figures, and claim-to-evidence references. It may not rerun the
experiment, recompute metrics, introduce a new metric, or broaden the
eight D-091 claims.

P8-R1 establishes byte-preserving reproducibility for the accepted
controlled final chain. It does not establish independent external
replication, production readiness, statistical significance, or
real-world generalization.
