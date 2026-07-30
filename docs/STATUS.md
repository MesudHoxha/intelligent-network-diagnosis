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
- Role-neutral Observation Profile v1 topology and node-role binding
- Evidence v2 runtime contract and JSON Schema
- Collector-side and Rule-Engine-side Evidence v2 validation
- Legacy Evidence v1 compatibility in the Rule Engine
- Role-derived diagnosis locations, explanations, and recommendations
- Dataset Row v1 adapter for Evidence v2 under TOP-01 r1/r2
- Explicit Dataset Row v1 rejection of other topology/role bindings
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
- Full automated test suite with 114 passing tests
- First real B0_SMOKE_CANONICAL batch completed with three validated
  Dataset Row v1 records and a final TOP-01 9/9 baseline
- Canonical and alternate HostB-subnet variants for N0, C1, and C2
- Observation-derived affected-prefix diagnosis for routing variants
- P1_ROUTING_VARIANTS completed with 12 validated Dataset Row v1
  records, 12/12 exact matches, and a final TOP-01 13/13 baseline
- Deterministic, class-stratified, group-aware dataset splitter
- Split manifest with source/output hashes and partition statistics
- Eleven targeted splitter tests, including leakage and feasibility
  checks
- Verified rejection of P1 before output creation because every class
  has only one independent split group
- Real B0 regression completed for N0, C1, and C2 using Evidence v2
- Three regression diagnoses with exact_match true
- TOP-01 remained valid with 13/13 checks before and after the
  Evidence v2 regression

## Representative verified experiments

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

- Batch ID: P1_ROUTING_VARIANTS
- Batch run ID:
  p1_routing_variants-20260730T082450785454Z-
  f283bfdd9ccc4b04afbc6462f6073a63
- Status: COMPLETED
- Failure policy: stop
- Planned/completed experiments: 12/12
- Validated Dataset Row v1 records: 12
- Scenario/variant combinations: 6
- Repetitions per combination: 2
- Rule-based exact matches: 12/12
- Affected-prefix correctness: 12/12
- Semantic verification: PASS
- Final TOP-01 baseline: 13/13 VALID
- Interpretation: parameterized pilot dataset, not a final
  training dataset

## Latest P2-R0 regression

- Batch ID: B0_SMOKE_CANONICAL
- Batch run ID:
  b0_smoke_canonical-20260730T112109248368Z-
  e589527badc546feb1426f41b78fdb1a
- Status: COMPLETED
- Planned/completed experiments: 3/3
- Validated Dataset Row v1 records: 3
- Evidence contract: Evidence v2
- Observation binding: TOP-01, hosta_to_hostb, r1/r2
- Rule-based exact matches: 3/3
- Semantic verification: PASS
- Baseline before and after: TOP-01 13/13 VALID
- Interpretation: real backward-compatibility regression for P2-R0,
  not a new training dataset

## Active

- Define a role-neutral Dataset Row v2 while preserving historical
  Dataset Row v1 compatibility
- Design TOP-02 only after the Dataset Row v2 contract is tested
- Define the controlled dataset expansion beyond the 12-row routing
  pilot using genuinely independent topology and observation groups
- Provide at least three independent split_group_id values for every
  fault_type before producing the first three-way split
- Preserve controlled variation and group independence while
  increasing dataset diversity
- Keep rule-based evaluation reporting separate from Dataset Row v1
  features and Batch Runner completion semantics

## Open issues

- Reusable batch-level evaluation summary or validation report
- Role-neutral Dataset Row v2 contract and schema
- Real TOP-02 topology, scenarios, validator, and laboratory execution
- Final FRRouting container image for later routing extensions
- Final set of pilot fault classes beyond C1 and C2
- Missing-evidence experiments
- Unseen scenario or topology variants
- Controlled multiple-fault subset
- Larger and more varied dataset beyond the 12-row P1 pilot
- Sufficient independent split groups for every fault class
- Machine Learning method implementation
- Hybrid method implementation
- OSPF implementation; its current status remains proposed

## Next milestone

Implement and test Dataset Row v2 with role-neutral feature names,
explicit migration behavior from Dataset Row v1, and unchanged
ground-truth isolation. Then design and validate TOP-02 before using
it in the next controlled dataset campaign.

Do not begin ML training until Dataset Row v2, TOP-02, the expanded
dataset, group independence, class coverage, and the generated split
manifest are verified.

## Important limitation

The accepted P1 JSONL file contains 12 rows from three classes,
two HostB-subnet variants, and two repetitions per combination.
It validates parameterized execution, evidence-based diagnosis,
aggregation, and restoration, but it contains only three independent
split groups: one for each class.

The group-aware splitter is implemented and verified, but it
correctly refuses P1 because no class has the three independent
groups required for train/validation/test coverage. This refusal is
a dataset-feasibility result, not a failure of the accepted P1
pipeline artifact.

P2-R0 makes the observation, evidence, and rule layers role-neutral.
Its real laboratory regression still used TOP-01. Synthetic tests
with TOP-02 identifiers validate contract behavior but do not prove
that a real TOP-02 laboratory or dataset pipeline exists. Dataset Row
v1 intentionally blocks non-legacy role bindings until Dataset Row
v2 is defined.

The project has not yet established general diagnostic accuracy or
compared the rule-based, Machine Learning, and hybrid methods.
Additional controlled variation, the first successful grouped split,
ML implementation, and hybrid evaluation remain required.
