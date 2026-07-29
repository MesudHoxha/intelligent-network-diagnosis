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
- Full automated test suite with 46 passing tests

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

- Implement a reproducible runner that consumes Batch Plan v1
- Design parameterized normal, C1, and C2 experiment variants
- Validate every generated row against Dataset Row v1
- Prepare group-aware dataset splitting through split_group_id

## Open issues

- Final FRRouting container image for later routing extensions
- Final set of pilot fault classes beyond C1 and C2
- Repeated normal samples and parameterized normal variants
- Missing-evidence experiments
- Unseen scenario or topology variants
- Controlled multiple-fault subset
- Reproducible batch execution and dataset aggregation
- Scenario- or topology-grouped dataset splitting
- Machine Learning method implementation
- Hybrid method implementation
- OSPF implementation; its current status remains proposed

## Next milestone

Implement and test a reproducible batch runner that consumes
validated Batch Plan v1, preserves listed order, invokes the existing
experiment runner, and validates every completed Dataset Row v1.

After runner tests pass, execute B0_SMOKE_CANONICAL. Do not begin ML
training until batch execution, contract validation, and group-aware
splitting are verified.

## Important limitation

Experiment Manifest v2, Dataset Row v1, and the first real N0 row
validate the artifact contracts and normal execution path. Batch
Plan v1 validates plan structure and deterministic expansion only;
it has not yet executed repeated experiments.

The project still has only three individually verified experiments.
It does not yet have a training dataset, establish general
diagnostic accuracy, or compare rule-based, Machine Learning,
and hybrid methods.
