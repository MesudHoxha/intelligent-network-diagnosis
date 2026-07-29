# HANDOFF — First real B0 canonical smoke batch

## 1. What was completed

- Deployed and validated TOP-01 with a 9/9 baseline.
- Executed B0_SMOKE_CANONICAL through Batch Runner v1.
- Preserved the listed execution order N0, C1, and C2.
- Completed all three planned experiments.
- Generated three validated Dataset Row v1 records.
- Persisted one COMPLETED batch metadata artifact.
- Atomically generated one aggregated JSONL dataset.
- Verified unique experiment and sample identifiers.
- Verified semantic agreement between batch metadata, experiment
  artifacts, features, labels, and quality fields.
- Confirmed that rule-engine and evaluation outputs did not leak
  into model features.
- Confirmed successful C1 and C2 restoration.
- Confirmed the final TOP-01 9/9 baseline.
- Kept the repository worktree clean during real execution.

## 2. What was decided

- The B0 execution is accepted as the first real end-to-end smoke
  validation of Batch Runner v1.
- The execution contract remains listed order with
  failure_policy=stop.
- The aggregated output is classified as a smoke dataset, not a
  training dataset.
- Three exact-match results do not establish general diagnostic
  accuracy.
- ML training remains blocked until parameterized dataset
  generation and group-aware splitting are verified.

## 3. Files created or changed

Runtime artifacts generated locally:

- data/metadata/
  b0_smoke_canonical-20260729T110541686889Z-3866a05ce64f4363afec8ae7ace6ef97.json
- data/processed/
  b0_smoke_canonical-20260729T110541686889Z-3866a05ce64f4363afec8ae7ace6ef97.jsonl
- data/raw/
  n0_normal_operation-20260729T110541689385Z-a5ea12650fbf41d6ab75e457cc4dcd4b/
- data/raw/
  c1_missing_static_route-20260729T110558625085Z-ea6ab2af89aa4b6bb20ffb62be0fc0f6/
- data/raw/
  c2_wrong_next_hop-20260729T110622965087Z-7f79703b0d3748d181cdeff24004cc20/

Updated central documents:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/ROADMAP.md

Created:

- docs/HANDOFF_B0_SMOKE_CANONICAL.md

No functional source code was changed during this documentation
stage.

## 4. Open issues

- Parameterized N0, C1, and C2 variants
- Repeated pilot dataset generation
- Group-aware splitting through split_group_id
- Missing-evidence experiments
- Unseen scenario or topology variants
- Controlled multiple-fault subset
- Additional pilot fault classes
- Machine Learning baseline
- Hybrid diagnostic method
- Comparative experimental evaluation

## 5. Next step

Define the first parameterized pilot campaign for N0, C1, and C2.
Specify which variables change, how variant_id and split_group_id
are assigned, how repetitions are represented, and which checks
prevent data leakage.

After approving the design, implement the smallest reusable
parameterization path and execute a pilot batch. Do not begin ML
training yet.

## 6. Impact on central documents

- MASTER_CONTEXT records the first real batch and distinguishes
  the smoke dataset from a training dataset.
- DECISIONS adds D-052 without replacing D-050 or D-051.
- STATUS moves B0 execution into completed work and establishes
  parameterized pilot generation as the next milestone.
- ROADMAP marks real batch execution and aggregation as verified
  while retaining group-aware splitting and ML as pending work.
