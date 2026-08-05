# STATUS

## Current phase

Phase 4 — Machine Learning baseline

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
- Dataset Row v2 runtime contract and JSON Schema
- Seven role-neutral Dataset Row v2 diagnostic feature names
- Dataset Row v2 observation-context metadata
- Canonical Dataset Row v2 builder for new experiments
- Explicit historical Dataset Row v1 to v2 migration
- Version-aware validation for Dataset Row v1 and v2
- Historical Dataset Row v1 exports for C1 and C2
- Real Dataset Row v1 export for N0
- Batch Plan v1 runtime validator and JSON Schema
- Canonical B0 smoke plan with the listed order N0, C1, and C2
- Batch Runner v1 orchestration over the existing experiment runner
- Fail-stop batch metadata persistence and atomic JSONL aggregation
- Per-row version-aware revalidation and duplicate-output protection
- Dataset Row v2 as the default Batch Runner output
- Mixed-version dataset rejection at the batch boundary
- Collision-resistant experiment and batch-run identifiers
- Full automated test suite with 155 passing tests
- First real B0_SMOKE_CANONICAL batch completed with three validated
  Dataset Row v1 records and a final TOP-01 9/9 baseline
- Canonical and alternate HostB-subnet variants for N0, C1, and C2
- Observation-derived affected-prefix diagnosis for routing variants
- P1_ROUTING_VARIANTS completed with 12 validated Dataset Row v1
  records, 12/12 exact matches, and a final TOP-01 13/13 baseline
- Deterministic, class-stratified, group-aware dataset splitter
- Split manifest with source/output hashes and partition statistics
- Homogeneous Dataset Row v1/v2 support in the splitter
- Mixed-version source rejection and source-version manifest metadata
- Verified rejection of P1 before output creation because every
  historical class-specific group lacks the complete required class
  set
- Real B0 regression completed for N0, C1, and C2 using Evidence v2
- Three regression diagnoses with exact_match true
- TOP-01 remained valid with 13/13 checks before and after the
  Evidence v2 regression
- Real B0 regression produced three validated Dataset Row v2 records
- Dataset Row v2 role-neutral feature and metadata audit passed
- Evaluation Group Protocol v1
- split_group_id defined as the complete evaluation-context boundary
- Complete multi-class group enforcement for N0, C1, and C2
- Explicit expected_fault_types coverage validation
- Deterministic complete_context_group_hash_v2 allocation
- Minimum three-context feasibility check before output creation
- Five-context 3/1/1 ML-readiness target
- Planned context matrix covering TOP-01, TOP-02, and TOP-03
- Verified real P1 rejection under the complete-context protocol
- G02 TOP_02_CHAIN five-node Containerlab topology
- G02 baseline validator with 28 route, forwarding, and reachability
  checks
- G02 N0, C1, and C2 scenario bindings sharing
  CTX_G02_TOP02_CHAIN_3R
- Real P2_G02_SMOKE batch with three completed experiments
- Three validated G02 Evidence v2 artifacts
- Three validated G02 Dataset Row v2 records
- G02 rule-based exact matches: 3/3
- G02 fault restoration and final 28/28 baseline verification
- Real G02 artifact-bundle SHA-256 fingerprint
- G03 TOP_02_BRANCH seven-node Containerlab topology
- G03 baseline validator with 40 checks covering both live branches
- G03 N0, C1, and C2 scenario bindings sharing
  CTX_G03_TOP02_BRANCH_MID
- Real C1/C2 branch-isolation audits proving that the HostB arm
  remains reachable while the selected HostC arm fails
- Real P2_G03_SMOKE batch with three completed experiments
- Three validated G03 Evidence v2 artifacts
- Three validated G03 Dataset Row v2 records
- Verified G03 hosta_to_hostc, observer r2, transit r4 binding
- G03 feature semantics and rule-based exact matches: 3/3
- G03 fault restoration and final 40/40 baseline verification
- Real G03 artifact-bundle SHA-256 fingerprint
- G04 TOP_02_DUAL_TRANSIT six-node Containerlab topology
- G04 baseline validator with 33 checks covering both live transit
  arms
- G04 N0, C1, and C2 scenario bindings sharing
  CTX_G04_TOP02_DUAL_TRANSIT
- Real C1 isolation and C2 cross-segment next-hop audits proving that
  the r2-HostB alternate arm remains reachable while the selected
  HostC path fails
- Real P2_G04_SMOKE batch with three completed experiments
- Three validated G04 Evidence v2 artifacts
- Three validated G04 Dataset Row v2 records
- Verified G04 hosta_to_hostc, observer r1, transit r3 binding
- G04 feature semantics and rule-based exact matches: 3/3
- G04 fault restoration and final 33/33 baseline verification
- Real G04 artifact-bundle SHA-256 fingerprint
- G05 TOP_03_ASYMMETRIC_RETURN six-node Containerlab topology
- G05 baseline validator with 52 checks covering both directed paths,
  reverse-path filtering, route lookups, and adjacency health
- G05 N0, C1, and C2 scenario bindings sharing
  CTX_G05_TOP03_ASYMMETRIC_RETURN
- Real baseline and runtime forward/return distinction audits
- Real C1 asymmetric-isolation and C2 same-segment next-hop audits
- Real P2_G05_SMOKE batch with three completed experiments
- Three validated G05 Evidence v2 artifacts
- Three validated G05 Dataset Row v2 records
- Verified G05 hosta_to_hostb, observer r2, transit r3 binding
- G05 feature semantics and rule-based exact matches: 3/3
- G05 fault restoration and final 52/52 baseline verification
- Real G05 artifact-bundle SHA-256 fingerprint
- Formal Method Evaluation Protocol v1
- Method Evaluation Result v1 runtime validator and JSON Schema
- Shared rule-based, Machine Learning, and hybrid method identifiers
- Frozen fault_type class order and macro-F1 comparison metric
- Partition-aware accuracy, per-class precision/recall/F1 and support
- Fixed-order confusion matrix and explicit zero-division policy
- Separate full-diagnosis and fault-only affected-prefix checks
- Immutable train-development, validation-selection, and
  test-report-only roles
- P2-R10 rule-audit adapter with sample, label, group, and hash
  verification
- Per-sample audit bindings for Manifest, ground truth, Evidence,
  prediction, and evaluation artifacts
- Atomic report writing and existing-output protection
- Real 30-record P3-R0 rule-based baseline report
- P3-R0 partition rows 18/6/6 and groups 3/1/1 verified
- Train, validation, and report-only test macro F1: 1.0/1.0/1.0
- P3-R0 exact diagnosis match: 30/30
- P3-R0 fault-only affected-prefix correctness: 20/20
- P3-R0 artifact references: 150/150 SHA-256 verified
- P3-R0 targeted tests: 10/10 passed
- Full automated regression suite: 185/185 passed

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

## Latest P2-R1 regression

- Batch ID: B0_SMOKE_CANONICAL
- Batch run ID:
  b0_smoke_canonical-20260730T115517979203Z-
  24c80549d03d4e84ad7e066f19409ecb
- Status: COMPLETED
- Planned/completed experiments: 3/3
- Validated Dataset Row v2 records: 3
- Dataset row schema version: 2
- Labels: no_fault, missing_static_route, wrong_next_hop
- Features per row: 7 role-neutral tri-state features
- Observation binding: TOP-01, hosta_to_hostb, r1/r2
- Rule-based exact matches: 3/3
- Role-neutral dataset audit: PASS
- Semantic verification: PASS
- Baseline before and after: TOP-01 13/13 VALID
- Interpretation: real Dataset Row v2 pipeline regression, not a
  training dataset or multi-topology evaluation

## Latest P2-R2 verification

- Evaluation Group Protocol version: 1
- Split algorithm: complete_context_group_hash_v2
- Grouping boundary: complete multi-class evaluation context
- Current required classes: no_fault, missing_static_route,
  wrong_next_hop
- Target context count before ML: 5
- Default group allocation target: 3/1/1
- Minimum planned campaign: 30 rows with two repetitions
- Targeted splitter tests: 14/14 passed
- Full automated suite: 128/128 passed
- Compile and diff checks: PASS
- Real historical P1 rejection audit: PASS
- Protocol audit: PASS
- Docker/laboratory execution: not required for this contract stage
- Interpretation: grouping semantics and readiness gate are verified;
  the five planned contexts are not yet implemented

## Latest P2-R3 design review

- Decision: D-059
- Design document: docs/TOP02_CONTEXT_DESIGN.md
- Future G01 group: CTX_G01_TOP01_LINEAR_2R
- G02: TOP_02_CHAIN / CTX_G02_TOP02_CHAIN_3R
- G03: TOP_02_BRANCH / CTX_G03_TOP02_BRANCH_MID
- G04: TOP_02_DUAL_TRANSIT /
  CTX_G04_TOP02_DUAL_TRANSIT
- Static routing and current N0/C1/C2 semantics retained
- Observation Profile v1, Evidence v2, and Dataset Row v2 unchanged
- Cross-context distinction audit: PASS at design level
- Real TOP-02 topology files: not implemented
- Real TOP-02 laboratory execution: not executed
- New dataset rows or split: none
- Next implementation target: G02 TOP_02_CHAIN
- Interpretation: G02-G04 are concrete design commitments, not
  verified experimental contexts

## Latest P2-R4 verification

- Decision: D-060
- Batch ID: P2_G02_SMOKE
- Batch run ID:
  p2_g02_smoke-20260730T133227173375Z-
  c74243e48485444fa795cb0f852f58d7
- Status: COMPLETED
- Planned/completed experiments: 3/3
- Classes: no_fault, missing_static_route, wrong_next_hop
- Shared evaluation context: CTX_G02_TOP02_CHAIN_3R
- Observation binding: TOP_02_CHAIN, hosta_to_hostb, r1/r2
- Evidence contract: Evidence v2
- Dataset row schema version: 2
- Validated Dataset Row v2 records: 3
- Rule-based exact matches: 3/3
- Restoration audit: PASS
- Semantic artifact audit: PASS
- Initial and final G02 baseline: 28/28 VALID
- Targeted G02 tests: 6/6 passed
- Full automated suite: 134/134 passed
- Artifact-bundle SHA-256:
  fa411079e19fa7047a467ae46ff1ba7edd54657daee254f74f6c57cd58e4adc3
- Interpretation: first real non-TOP-01 complete-class smoke context,
  not the final campaign or a train/validation/test split

## Latest P2-R5 verification

- Decision: D-061
- Batch ID: P2_G03_SMOKE
- Batch run ID:
  p2_g03_smoke-20260731T065808868462Z-
  a2b3766efaa449aeaf9007d4d1b664ea
- Status: COMPLETED
- Planned/completed experiments: 3/3
- Classes: no_fault, missing_static_route, wrong_next_hop
- Shared evaluation context: CTX_G03_TOP02_BRANCH_MID
- Observation binding: TOP_02_BRANCH, hosta_to_hostc, r2/r4
- Evidence contract: Evidence v2
- Dataset row schema version: 2
- Validated Dataset Row v2 records: 3
- Role-binding audit: PASS
- Feature-semantics audit: PASS
- Rule-based exact matches: 3/3
- C1 branch-isolation audit: PASS
- C2 branch-isolation audit: PASS
- Restoration audit: PASS
- Semantic artifact audit: PASS
- Initial and final G03 baseline: 40/40 VALID
- Targeted G03 tests: 7/7 passed
- Full automated suite: 141/141 passed
- Artifact-bundle SHA-256:
  2092d0702a8e107a7757ff1754872f518f0be25c89883edb2c5638371a18f0fc
- Laboratory cleanup: PASS
- Interpretation: first real interior r2/r4 role-binding and branched
  complete-class smoke context, not the final campaign or a split

## Latest P2-R6 verification

- Decision: D-062
- Batch ID: P2_G04_SMOKE
- Batch run ID:
  p2_g04_smoke-20260731T074745682481Z-
  5c865fccfdf244858aa04003187730a4
- Status: COMPLETED
- Planned/completed experiments: 3/3
- Classes: no_fault, missing_static_route, wrong_next_hop
- Shared evaluation context: CTX_G04_TOP02_DUAL_TRANSIT
- Observation binding: TOP_02_DUAL_TRANSIT, hosta_to_hostc, r1/r3
- Evidence contract: Evidence v2
- Dataset row schema version: 2
- Validated Dataset Row v2 records: 3
- Role-binding audit: PASS
- Feature-semantics audit: PASS
- Rule-based exact matches: 3/3
- C1 dual-transit isolation audit: PASS
- C2 cross-segment next-hop audit: PASS
- Runtime dual-transit distinction audit: PASS
- Restoration audit: PASS
- Semantic artifact audit: PASS
- Initial and final G04 baseline: 33/33 VALID
- Targeted G04 tests: 7/7 passed
- Full automated suite: 148/148 passed
- Artifact-bundle SHA-256:
  1e9aa7d2ea8ea1f1691821f8639c60820bbdcd9c0d0bd182e4b72b810b948d54
- Laboratory cleanup: PASS
- Interpretation: first real r1/r3 dual-transit and cross-segment
  wrong-next-hop complete-class smoke context, not the final campaign
  or a split

## Latest P2-R7 design review

- Decision: D-063
- Design document: docs/TOP03_CONTEXT_DESIGN.md
- G05 topology_id: TOP_03_ASYMMETRIC_RETURN
- G05 split_group_id: CTX_G05_TOP03_ASYMMETRIC_RETURN
- Physical router graph: r1-r2-r3-r4-r1 cycle
- Forward path: hosta-r1-r2-r3-hostb
- Return path: hostb-r3-r4-r1-hosta
- Observation binding: hosta_to_hostb, observer r2, transit r3
- Fault target: r2 route toward 10.50.3.0/24
- C2 binding: correct 10.50.23.2, wrong 10.50.23.6
- Reverse-path-filter requirement: frozen and mandatory
- Observation Profile v1, Evidence v2, and Dataset Row v2: unchanged
- Cross-context distinction audit: PASS at design level
- Full automated regression suite: 148/148 passed
- Real G05 topology, scenario, evidence, dataset row, and artifact
  SHA-256: not implemented
- Interpretation: G05 is a concrete design commitment, not a verified
  fifth experimental context

## Latest P2-R8 verification

- Decision: D-064
- Batch ID: P2_G05_SMOKE
- Batch run ID:
  p2_g05_smoke-20260731T083408705159Z-
  4badf5fdf6da4141af74af11d4b5f1a2
- Status: COMPLETED
- Planned/completed experiments: 3/3
- Classes: no_fault, missing_static_route, wrong_next_hop
- Shared evaluation context: CTX_G05_TOP03_ASYMMETRIC_RETURN
- Observation binding:
  TOP_03_ASYMMETRIC_RETURN, hosta_to_hostb, r2/r3
- Evidence contract: Evidence v2
- Dataset row schema version: 2
- Validated Dataset Row v2 records: 3
- Role-binding audit: PASS
- Feature-semantics audit: PASS
- Rule-based exact matches: 3/3
- Baseline forward/return distinction audit: PASS
- C1 asymmetric-isolation audit: PASS
- C2 same-segment next-hop audit: PASS
- Runtime asymmetric-distinction audit: PASS
- Reverse-path-filter checks: PASS
- Restoration audit: PASS
- Semantic artifact audit: PASS
- Initial and final G05 baseline: 52/52 VALID
- Targeted G05 tests: 7/7 passed
- Full automated suite: 155/155 passed
- Artifact-bundle SHA-256:
  6bd4de9818ba0c3b589e5a17cf47553f523fc743d6feb12334bd525ea79ca870
- Laboratory cleanup: PASS
- Interpretation: first real r2/r3 asymmetric-return complete-class
  smoke context, not the expanded campaign or a split

## Latest P2-R9 verification

- Decision: D-065
- Campaign plan: P2_ROUTING_5CTX_V1
- Campaign plan schema: Dataset Campaign Plan v1
- Dataset row schema version: 2
- Context jobs: 5
- Per-context Batch Plan v1 jobs: 5
- Classes per context: 3
- Repetitions per class and context: 2
- Planned experiments/rows: 30
- Explicit G01 complete-context scenario bindings: 3
- G01 split group: CTX_G01_TOP01_LINEAR_2R
- Historical scenario and dataset relabelling: none
- Execution order: G01, G02, G03, G04, G05
- Failure policy: stop
- Split algorithm: complete_context_group_hash_v2
- Split seed: 20260730
- Split ratios and group counts: 0.6/0.2/0.2 and 3/1/1
- Expected train groups: G03, G04, G05
- Expected validation group: G01
- Expected test group: G02
- Expected train/validation/test rows: 18/6/6
- Targeted P2-R9 tests: 9/9 passed
- Full automated suite: 164/164 passed
- Real campaign execution: not executed
- Merged 30-row dataset: not created
- Real split manifest or partitions: not created
- Interpretation: campaign inputs and leakage-safe split
  precommitment are implemented and verified; ML readiness has not
  yet been established

## Latest P2-R10 verification

- Decisions: D-066 and D-067
- Campaign ID: P2_ROUTING_5CTX_V1
- Accepted campaign run ID:
  p2_routing_5ctx_v1-20260804T073429388394Z-
  617194fea9954ed98ec120bdefea23d9
- Status: COMPLETED
- Context batches: 5/5 COMPLETED
- Planned/completed experiments: 30/30
- Evidence v2 and Dataset Row v2 revalidation: 30/30 PASS
- Rows per context: 6
- Rows per class: 10
- Quality policy: N0:0/C1:1 exact/C2:0
- Expected structural unavailable features: 10
- Unexpected unavailable features: 0
- Rule-based exact matches: 30/30
- Affected-prefix checks: 30/30
- Merged Dataset Row v2 records: 30
- Merged dataset SHA-256:
  be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc95e8afb5e830c80
- Split rows: 18/6/6
- Split groups: 3/1/1
- Train groups: G03, G04, G05
- Validation group: G01
- Test group: G02
- No cross-partition group: PASS
- Initial/final baselines: 5/5 PASS
- Laboratory cleanup: 5/5 PASS
- Campaign Result v1 schema: PASS
- Targeted P2-R10 tests: 11/11 passed
- Full automated suite: 175/175 passed
- Interpretation: the first leakage-controlled five-context dataset
  and split are accepted for reviewed baseline work; general
  diagnostic performance is not established

The earlier run
p2_routing_5ctx_v1-20260804T070959526851Z-
9f1062d3dbdd44258657c144ec3755fc remains a failed campaign artifact.
It supplied the runtime evidence for D-066 but contributed no row to
the accepted merge or split.

## Latest P3-R0 verification

- Decisions: D-068 and D-069
- Protocol: docs/METHOD_EVALUATION_PROTOCOL.md
- Result contract: Method Evaluation Result v1
- Result schema:
  schemas/method_evaluation_result_v1.schema.json
- Runtime implementation: src/evaluation/reporting.py
- Primary target: fault_type
- Primary metric: macro F1
- Reported partitions: train, validation, and test
- Selection partitions: train and validation only
- Test use: report_only
- Overall use: descriptive_only
- Result ID: p3_r0_rule_based_baseline_v1
- Result status: COMPLETED
- Report path:
  reports/experiments/p3_r0_rule_based_baseline_v1.json
- Report SHA-256:
  7158f1de31a892779bbce2eaad8f5c5e5bb7c2fc08e0766b49a55047ddc56424
- Rows: 30
- Partition rows: 18/6/6
- Partition groups: 3/1/1
- Train accuracy / macro F1: 1.0 / 1.0
- Validation accuracy / macro F1: 1.0 / 1.0
- Test accuracy / macro F1: 1.0 / 1.0
- Exact diagnosis match: 30/30
- Fault-only affected-prefix correctness: 20/20
- Artifact references: 150/150 SHA-256 PASS
- Rule Engine changes: none
- Dataset or split changes: none
- Targeted tests: 10/10 passed
- Full automated suite: 185/185 passed
- Interpretation: P3-R0 is closed for the frozen controlled campaign;
  the perfect values do not establish generalization or method
  superiority

## Active

- Preserve the accepted campaign run, dataset hash, split seed,
  group identifiers, ratios, and partition allocation.
- Freeze a leakage-safe ML baseline protocol before model fitting.
- Define the seven-feature input matrix without admitting labels,
  ground truth, evaluation outputs, or provenance as predictors.
- Restrict fitting to train, selection to validation, and G02 test to
  one report-only evaluation after the pipeline is frozen.
- Reuse Method Evaluation Result v1 for the future ML report.

## Open issues

- Future cross-method comparison report after ML and hybrid exist
- Final FRRouting container image for later routing extensions
- Final set of pilot fault classes beyond C1 and C2
- Missing-evidence experiments
- Unseen scenario or topology variants
- Controlled multiple-fault subset
- Larger and more varied dataset beyond the accepted 30-row P2
  campaign
- Reproducible backup or publication policy for generated runtime
  datasets before final thesis archiving
- Machine Learning method implementation
- Hybrid method implementation
- OSPF implementation; its current status remains proposed

## Next milestone

P4-R0 — Leakage-Safe ML Baseline Protocol and Feature Matrix.

Freeze the supervised target, seven-feature transformation, missing-
value handling, candidate model families, deterministic seeds,
train-only fitting, validation-only selection, and the one-time
report-only test policy before evaluating a fitted model. Preserve
the D-067 campaign and split and the D-068 result contract. Exclude
ground truth, rule predictions, evaluation results, identifiers,
paths, hashes, and explanation text from model features. Stop before
hybrid-policy design.

## Important limitation

The accepted P1 JSONL file contains 12 rows from three classes,
two HostB-subnet variants, and two repetitions per combination.
It validates parameterized execution, evidence-based diagnosis,
aggregation, and restoration. Its three split groups are historical
class-specific identifiers, not three complete evaluation contexts.

The evaluation-context-aware splitter is implemented and verified.
It correctly refuses P1 because every historical group is missing the
other required fault types. This refusal is a dataset-feasibility
result, not a failure of the accepted P1 pipeline artifact.

P2-R0 made the observation, evidence, and rule layers role-neutral.
P2-R1 made Dataset Row v2 the role-neutral canonical dataset
contract. P2-R4 proved the first non-TOP-01 laboratory through G02.
P2-R5 then verified the real interior r2 observer and r4 transit
binding in G03, and P2-R6 verified the r1/r3 dual-transit binding and
cross-segment wrong-next-hop context in G04, without changing
Evidence v2 or Dataset Row v2.

The explicit Dataset Row v1 to v2 migration is limited to the
historical TOP_01, hosta_to_hostb, r1/r2 context. Migrating historical
rows does not create new experimental evidence or independent split
groups. The three-row P2-R1 regression validates pipeline integration
only and is not a training dataset.

P2-R2 defines five complete evaluation contexts as the target for the
first ML experiment and plans coverage across TOP-01, TOP-02, and
TOP-03. P2-R3 froze concrete G02-G04 designs. P2-R4 and P2-R5
implemented G02 and G03, and P2-R6 implemented G04, each with one
execution per current class. P2-R7 froze G05 as
TOP_03_ASYMMETRIC_RETURN, and P2-R8 implemented and verified it with
one execution per current class.

P2-R9 added explicit G01 campaign bindings without modifying
historical files, created five two-repetition context plans, and
implemented Dataset Campaign Plan v1. P2-R10 then executed that exact
plan in a fresh accepted run. The atomic merge contains 30 Dataset Row
v2 records, and the D-058 split contains 18/6/6 rows in 3/1/1 whole
context groups with no cross-partition leakage.

P3-R0 produced the first accepted traditional baseline through the
formal comparable evaluation protocol. Its perfect values are
descriptive results for the frozen known campaign, not general
diagnostic accuracy. The project has not yet implemented or evaluated
the Machine Learning and hybrid methods, so no cross-method comparison
or superiority claim is possible. Additional controlled variation,
ML implementation, and hybrid evaluation remain required.
