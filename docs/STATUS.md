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
- Evidence collection for route presence and next-hop state
- Rule R_ROUTING_001 for missing_static_route
- Rule R_ROUTING_002 for wrong_next_hop
- Automatic rule-based evaluation
- End-to-end experiment orchestration
- Ground-truth isolation from Collector and Rule Engine
- Full automated test suite with 18 passing tests

## Latest verified experiments

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

- Define the detailed experiment-manifest schema
- Define the dataset-row and feature schema
- Design parameterized normal, C1, and C2 experiment variants
- Prepare reproducible batch dataset generation

## Open issues

- Final FRRouting container image for later routing extensions
- Final set of pilot fault classes beyond C1 and C2
- Normal no-fault dataset generation
- Missing-evidence experiments
- Unseen scenario or topology variants
- Controlled multiple-fault subset
- Scenario- or topology-grouped dataset splitting
- Machine Learning method implementation
- Hybrid method implementation
- OSPF implementation; its current status remains proposed

## Next milestone

Create and validate the first reproducible dataset batch containing
normal operation and parameterized C1/C2 experiments, without
beginning ML training before the dataset contract is verified.

## Important limitation

PoC-B verifies the technical pipeline for two controlled routing
faults. It does not establish general diagnostic accuracy and does
not yet compare rule-based, Machine Learning, and hybrid methods.
