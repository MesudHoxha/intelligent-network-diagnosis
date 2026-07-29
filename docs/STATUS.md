# STATUS

## Current phase

05 — Parameterized pilot dataset generation

## Implemented and tested

- Ubuntu 24.04 under WSL2
- Native Docker Engine inside WSL2
- Containerlab installation and execution
- Physical repository and central project documents
- TOP-01 topology: HostA -- R1 -- R2 -- HostB
- TOP-01 baseline validation with 9/9 checks
- C1_MISSING_STATIC_ROUTE fault injection and restoration
- C2_WRONG_NEXT_HOP fault injection and restoration
- N0_NORMAL_OPERATION no-fault execution path
- Evidence collection with seven tri-state diagnostic features
- Rule R_ROUTING_001 for missing_static_route
- Rule R_ROUTING_002 for wrong_next_hop
- NO_FAULT_DETECTED result for healthy evidence
- Automatic rule-based evaluation
- End-to-end experiment orchestration
- Ground-truth isolation from Collector and Rule Engine
- Experiment Manifest v2 runtime contract and JSON Schema
- Dataset Row v1 builder and JSON Schema
- Historical Dataset Row v1 exports for C1 and C2
- Real Dataset Row v1 export for N0
- Batch Plan v1 runtime validator and JSON Schema
- Canonical B0 smoke plan with the listed order N0, C1, and C2
- Batch Runner v1 orchestration over the existing experiment runner
- Fail-stop batch metadata persistence and atomic JSONL aggregation
- Per-row Dataset Row v1 revalidation and duplicate-output protection
- Collision-resistant experiment and batch-run identifiers
- Full automated test suite with 53 passing tests
- First real B0_SMOKE_CANONICAL batch completed with three validated
  Dataset Row v1 records and a final TOP-01 9/9 baseline

## Latest verified experiments

N0:

- Experiment: n0_normal_operation-20260729T110541689385Z-a5ea12650fbf41d6ab75e457cc4dcd4b
- Status: COMPLETED
- Diagnosis status: NO_FAULT_DETECTED
- Exact match: true
- Baseline restored: false
- Baseline valid after: true
- Diagnostic features true: 7/7
- Unavailable features: 0

C1:

- Experiment: c1_missing_static_route-20260729T110558625085Z-ea6ab2af89aa4b6bb20ffb62be0fc0f6
- Status: COMPLETED
- Matched rule: R_ROUTING_001
- Exact match: true
- Baseline restored: true

C2:

- Experiment: c2_wrong_next_hop-20260729T110622965087Z-7f79703b0d3748d181cdeff24004cc20
- Status: COMPLETED
- Observed next-hop: 10.10.12.254
- Next-hop reachable: false
- Matched rule: R_ROUTING_002
- Exact match: true
- Baseline restored: true

Final post-experiment baseline:

- Passed checks: 9
- Failed checks: 0
- Status: VALID

## Latest verified batch

- Batch ID: B0_SMOKE_CANONICAL
- Batch run ID:
  b0_smoke_canonical-20260729T110541686889Z-3866a05ce64f4363afec8ae7ace6ef97
- Status: COMPLETED
- Failure policy: stop
- Execution order: N0, C1, C2
- Planned/completed experiments: 3/3
- Validated Dataset Row v1 records: 3
- Semantic verification: PASS
- Final TOP-01 baseline: 9/9 VALID
- Interpretation: smoke dataset, not a training dataset

## Active

- Design parameterized normal, C1, and C2 experiment variants
- Define the first repeated pilot dataset campaign
- Prepare group-aware dataset splitting through split_group_id

## Open issues

- Final FRRouting container image for later routing extensions
- Final set of pilot fault classes beyond C1 and C2
- Repeated normal samples and parameterized normal variants
- Missing-evidence experiments
- Unseen scenario or topology variants
- Controlled multiple-fault subset
- Larger reproducible dataset generation beyond the canonical
  three-row smoke batch
- Scenario- or topology-grouped dataset splitting
- Machine Learning method implementation
- Hybrid method implementation
- OSPF implementation; its current status remains proposed

## Next milestone

Define and implement the first reproducible parameterized variants
for N0, C1, and C2. Then create a pilot batch plan with repetitions
and verify class counts, Dataset Row v1 validity, split_group_id
assignments, and baseline restoration across the campaign.

Do not begin ML training until parameterized dataset generation and
group-aware splitting are implemented and verified.

## Important limitation

Batch Runner v1 and the canonical B0 plan have been verified through
one real multi-experiment laboratory batch. The resulting JSONL file
contains only three canonical smoke samples.

The project does not yet have a sufficiently varied training
dataset, establish general diagnostic accuracy, or compare the
rule-based, Machine Learning, and hybrid methods. Repeated and
parameterized variants plus group-aware splitting remain required.
