# STATUS

## Current phase

05 — Dataset preparation after PoC-B

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

## Latest verified experiments

N0:

- Experiment: n0_normal_operation-20260728T133851Z
- Status: COMPLETED
- Diagnosis status: NO_FAULT_DETECTED
- Exact match: true
- Baseline restored: false
- Baseline valid after: true
- Diagnostic features true: 7/7
- Unavailable features: 0

C1:

- Experiment: c1_missing_static_route-20260728T120013Z
- Status: COMPLETED
- Matched rule: R_ROUTING_001
- Exact match: true
- Baseline restored: true

C2:

- Experiment: c2_wrong_next_hop-20260728T120038Z
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

## Active

- Execute B0_SMOKE_CANONICAL through Batch Runner v1
- Verify the real batch metadata and aggregated Dataset Row v1 records
- Design parameterized normal, C1, and C2 experiment variants
- Prepare group-aware dataset splitting through split_group_id

## Open issues

- Final FRRouting container image for later routing extensions
- Final set of pilot fault classes beyond C1 and C2
- Repeated normal samples and parameterized normal variants
- Missing-evidence experiments
- Unseen scenario or topology variants
- Controlled multiple-fault subset
- First real B0_SMOKE_CANONICAL execution and artifact verification
- Scenario- or topology-grouped dataset splitting
- Machine Learning method implementation
- Hybrid method implementation
- OSPF implementation; its current status remains proposed

## Next milestone

Execute B0_SMOKE_CANONICAL through Batch Runner v1 as the first real
batch. Verify the N0, C1, and C2 execution order, the COMPLETED batch
result, all three validated Dataset Row v1 records, and the final
TOP-01 baseline.

Do not begin ML training until real batch execution, artifact
validation, parameterized dataset generation, and group-aware
splitting are verified.

## Important limitation

Batch Runner v1 has been validated through isolated automated tests,
not through a real multi-experiment laboratory batch. The canonical
B0 plan has not yet produced real batch metadata or an aggregated
dataset.

The project still has only three individually verified experiments.
It does not yet have a training dataset, establish general
diagnostic accuracy, or compare rule-based, Machine Learning,
and hybrid methods.
