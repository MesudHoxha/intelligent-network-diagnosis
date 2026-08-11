# STATUS

## Current phase

Phase 7 — Read-only Dashboard/API implementation

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
- Observation Profile v2 runtime contract and JSON Schema
- Evidence v3 runtime contract and JSON Schema
- Dataset Row v3 runtime contract, explicit builder, and JSON Schema
- Exact ten-feature Phase 6 predictor whitelist
- SHA-256-bound raw-probe provenance for Evidence v3
- Explicit structural, collection, and masked missingness reasons
- Backwards-compatible version dispatch through Dataset Row v3
- Homogeneous v1-v3 dataset aggregation gate
- Dataset Row v2 retained as the runtime default pending collector v3
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
- Leakage-Safe Machine Learning Baseline Protocol v1
- ML Feature Matrix v1 runtime validator and JSON Schema
- Exact seven-feature predictor whitelist and separate fault_type
  target
- Lossless tri-state available/true pair encoding with 14 binary
  output columns
- Explicit exclusion of labels, metadata, quality, ground truth,
  rule output, evaluation output, identifiers, paths, hashes, and
  explanation text from predictors
- Frozen train-fit, validation-selection, and test-report-only roles
- Six bounded logistic-regression and shallow-tree candidates
- Deterministic model seed and validation-only tie-break policy
- Atomic byte-deterministic feature-matrix writing and existing-output
  protection
- Negative leakage, split-drift, schema-version, hash, and encoding
  gates
- Real 30-record P4-R0 ML Feature Matrix v1
- P4-R0 partition rows 18/6/6 and groups 3/1/1 verified
- Seven raw tri-state features encoded as 14 binary columns
- Ten expected structural unavailable values preserved
- P4-R0 source-row references: 30/30 SHA-256 verified
- P4-R0 predictor-leakage audit passed with G02 test report_only
- P4-R0 targeted tests: 10/10 passed
- Full automated regression suite: 195/195 passed
- ML Pipeline Selection v1 runtime validator and JSON Schema
- Exact six-candidate scikit-learn estimator factory
- Train-only fitting and validation-only deterministic selection
- Atomic selected-model and selection-result pipeline freeze
- Fitted train-sample, feature-order, candidate-order, software, and
  artifact-hash bindings
- Independent freeze verification before any test prediction
- ML prediction artifacts with seven decoded evidence states
- Logistic feature-contribution and tree decision-path explanations
- Explicit class-only boundary with no invented location or prefix
- Backwards-compatible Method Evaluation Result v1 ML provenance
- Atomic 30-record ML report builder with 150 artifact references
- Negative gates for test access, matrix/model/selection drift,
  existing outputs, and non-frozen report execution
- P4-R1 targeted synthetic tests: 10/10 passed
- Full automated regression suite: 205/205 passed
- Hybrid Diagnosis Policy v1 machine-readable artifact and JSON
  Schema
- Frozen consensus-abstain and guarded-rule-fallback candidates
- Prediction-time ground-truth, label, partition, evaluation, and
  test leakage gates
- Validation-only hybrid candidate selection contract
- Abstention-aware future evaluation and seven-reference provenance
  contract
- P5-R0 accepted baseline hash bindings: 5/5 SHA-256 PASS
- P5-R0 targeted contract tests: 11/11 passed
- Full automated regression suite: 216/216 passed
- P5-R0 hybrid predictions, metrics, selection, and test access:
  absent

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

## Latest P4-R0 verification

- Decisions: D-070 and D-071
- Protocol: docs/ML_BASELINE_PROTOCOL.md
- Matrix contract: ML Feature Matrix v1
- Matrix schema: schemas/ml_feature_matrix_v1.schema.json
- Runtime implementation: src/ml/feature_matrix.py
- Matrix ID: p4_r0_ml_feature_matrix_v1
- Matrix status: COMPLETED
- Artifact path:
  reports/experiments/p4_r0_ml_feature_matrix_v1.json
- Artifact SHA-256:
  9193b4b8c676bf94ef9af05562d9d0047faef61bc94c9d81b0485b88bf599730
- Accepted campaign binding: PASS
- Rows: 30
- Partition rows: 18/6/6
- Partition groups: 3/1/1
- Raw predictor features: 7
- Encoded binary columns: 14
- Structural unavailable values: 10 EXPECTED
- Source-row references: 30/30 SHA-256 PASS
- Predictor-leakage audit: PASS
- Test use: report_only
- ML fitted estimators: none
- Predictions or metrics: none
- Targeted tests: 10/10 passed
- Full automated suite: 195/195 passed
- Interpretation: P4-R0 is closed as an input-integrity milestone;
  at that closeout point no ML performance result existed

## Active

- Preserve the accepted campaign run, dataset hash, split seed,
  group identifiers, ratios, and partition allocation.
- Preserve D-069 as the accepted independent rule-based baseline and
  D-073 as the accepted independent ML baseline.
- Preserve the accepted frozen Hybrid Diagnosis Policy v1 contract
  while implementing both candidates in P5-R1.
- Keep G02 test report_only and prohibit test-guided hybrid policy,
  threshold, fallback, or explanation design.
- Preserve the two precommitted candidates and validation-only
  selection order without selecting either candidate in P5-R0.

## Latest P4-R1 verification

- Decisions: D-072 and D-073
- Runtime implementation: src/ml/baseline.py
- Selection contract: ML Pipeline Selection v1
- Selection schema: schemas/ml_pipeline_selection_v1.schema.json
- Open-source dependencies: scikit-learn >=1.5,<1.8 and
  joblib >=1.4,<2
- Frozen candidate implementations: 6/6
- Fit partition: train only
- Selection partition: validation only
- Pipeline refit on train plus validation: forbidden
- Test predictions and metrics in selection artifact: forbidden
- Report gate: accepted matrix plus selection/model hash verification
- Prediction explanation: evidence states plus linear contributions
  or tree path
- Predicted fault localization/prefix: intentionally absent
- Method Evaluation Result v1 provenance extension: backwards
  compatible with D-069
- Selected candidate: logreg_l2_c0_1
- Selected family: multinomial_logistic_regression
- Candidate fit partition: 18 train rows in 3 groups
- Selection partition: 6 validation rows in 1 group
- Selection validation accuracy / macro-F1: 1.0 / 1.0
- Selection SHA-256:
  a02536d6f2478d9fdc40510275dd3b48a2824ee7b1f0fa08c1aed472611fb6fb
- Model SHA-256:
  90db38e625f4bcf6a234b6a0516371b76f98e01b4437f684ffea119cbc09cdb2
- Pipeline freeze before test: PASS
- Report ID: p4_r1_ml_baseline_v1
- Report path:
  reports/experiments/p4_r1_ml_baseline_v1/
  method_evaluation_result.json
- Report SHA-256:
  8fc6e77e5008cd7cc74e5ce130b901ed750afab9a35eb62652ff55f9205b0e92
- Report rows: 30
- Partition rows: 18/6/6
- Partition groups: 3/1/1
- Train/validation/test accuracy: 1.0/1.0/1.0
- Train/validation/test macro-F1: 1.0/1.0/1.0
- Exact-diagnosis rate: 1/3 in each partition
- Fault-only affected-prefix rate: 0.0 in each partition
- Evidence/model explanations: 30/30 PASS
- Source-artifact references: 150/150 SHA-256 PASS
- Test use: report_only PASS
- Model refit during report/recovery: ABSENT
- Targeted tests: 10/10 passed
- Full automated regression suite: 205/205 passed
- Interpretation: P4-R1 and Phase 4 are closed for the frozen
  controlled campaign; perfect class metrics do not establish
  real-world generalization or superiority

## Latest P5-R0 verification

- Decision: D-074, approved and runtime-verified
- Protocol: docs/HYBRID_DIAGNOSIS_POLICY.md
- Contract: Hybrid Policy v1
- Policy artifact:
  policies/hybrid/P5_HYBRID_POLICY_V1.json
- JSON Schema: schemas/hybrid_policy_v1.schema.json
- Semantic validator: src/hybrid/policy.py
- Candidate count: 2 FROZEN
- Candidates: consensus_abstain_v1 and
  rule_guarded_fallback_v1
- Agreement action: accept agreed fault_type
- Fault localization/prefix source: rule prediction only
- Disagreement: abstain or five-guard rule fallback, depending on
  candidate
- Non-final input action: abstain
- Ground truth reader: evaluator only
- Raw rule and ML outputs: immutable
- Selection stage: P5-R1, validation only
- Held-out G02 test: report_only after selected-policy freeze
- Selected candidate: none
- Hybrid predictions or metrics: absent
- Hybrid Engine implementation: absent
- Runtime artifact changes: none
- Policy SHA-256:
  a25467e9cfd8bb52cc67b0c3886eb439466ee51a27b22d292ee468d060bdecc7
- Accepted baseline hashes: 5/5 SHA-256 PASS
- Frozen candidates: 2/2 PASS
- Targeted tests: 11/11 passed
- Full automated regression suite: 216/216 passed
- P5-R0 closeout: completed

## Latest P5-R1 verification

- Decision: D-075, accepted and runtime-verified
- Hybrid Engine: src/hybrid/engine.py
- Hybrid Prediction schema:
  schemas/hybrid_prediction_v1.schema.json
- Hybrid Selection schema:
  schemas/hybrid_selection_v1.schema.json
- Runtime output: models/p5_r1_hybrid_policy_v1
- Candidate predictions: 48/48 PASS
- Candidate evaluations: 48/48 PASS
- Candidate manifests: 2/2 PASS
- Runtime JSON files: 99/99 PASS
- Prediction partitions: train and validation only
- Selection rows: six G01 validation rows only
- Train/validation macro-F1: 1.0/1.0 for both candidates
- Train/validation exact diagnosis: 1.0/1.0 for both candidates
- Train/validation coverage: 1.0/1.0 for both candidates
- Validation abstentions: 0 for both candidates
- Selected candidate: consensus_abstain_v1
- Selected complexity rank: 0
- Selection SHA-256:
  59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507
- Independent selected-policy verification: PASS
- Policy and accepted baseline integrity: 6/6 SHA-256 PASS
- Targeted tests: 14/14 passed
- Full automated regression suite: 229/229 passed
- Test/G02 hybrid predictions and metrics: absent
- P5-R1 closeout: completed

The identical development results do not establish that the selected
candidate is empirically superior to rule_guarded_fallback_v1. The
selection follows the frozen complexity tie-break. Hybrid test
performance and the three-method comparison remain unknown until
P5-R2.

## Latest P5-R2 verification

- Decision: D-076, accepted and runtime-verified
- Coordinator: src/hybrid/reporting.py
- Comparison schema:
  schemas/cross_method_comparison_v1.schema.json
- Implementation document: docs/P5_R2_REPORT_IMPLEMENTATION.md
- Freeze gate order: P5-R1 independent verification before G02
  source collection
- Required selection SHA-256:
  59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507
- Frozen selected candidate: consensus_abstain_v1
- New G02 predictions: 6 selected candidate only, PASS
- Prediction batch before test ground-truth reads: enforced
- Complete hybrid report: 30 rows and 210/210 sample references PASS
- Atomic runtime output: 14/14 JSON files PASS
- Comparison: Rule-based vs Machine Learning vs Hybrid under
  the same 18/6/6 split
- Comparison interpretation: descriptive_only
- Statistical superiority test: forbidden/absent
- G02 hybrid macro-F1: 1.0
- G02 hybrid exact-diagnosis rate: 1.0
- G02 hybrid affected-prefix correctness: 1.0
- G02 hybrid coverage: 1.0
- G02 hybrid abstentions: 0
- Hybrid report SHA-256:
  e990a29882f1b7cec4fe003ee5ee65b3fa3dfd25250092a0f9f2a908074a9c75
- Cross-method comparison SHA-256:
  eebf97dfe340a05feba70874f54727e1a8ccf7ce4224301f162544537d8ecf80
- Test use: report_only PASS
- Test influenced policy or selection: false
- Targeted tests: 14/14 passed
- Full regression suite: 243/243 passed
- P5-R2 closeout: completed
- Phase 5: Completed

The accepted values describe the frozen controlled campaign. They do
not establish statistical superiority or real-world generalization.

## Latest P6-R0 verification

- Decision: D-077, approved and design-contract verified
- Design document: docs/PHASE6_FAULT_TAXONOMY_PLAN.md
- Machine-readable plan:
  plans/taxonomies/P6_EXTENDED_FAULT_TAXONOMY_V1.json
- Strict schema: schemas/fault_taxonomy_plan_v1.schema.json
- Semantic validator: src/planning/fault_taxonomy.py
- Canonical class count: 6
- Canonical class order: no_fault, missing_static_route,
  wrong_next_hop, wrong_default_gateway, interface_down, acl_block
- Planned Evidence v3/Dataset Row v3 feature count: 10
- Complete context groups: 6 design-only groups
- Repetitions: 2 per class/context pair
- Expected clean campaign rows: 72
- Frozen split rows: 36 train, 12 validation, 24 test
- Frozen split groups: 3 train, 1 validation, 2 test
- Test role: report_only after independent freeze verification
- Missing-evidence masks: 4 deterministic non-destructive families
- Multiple faults: excluded pending a later multi-label design gate
- Accepted P2-P5 rows and artifacts: immutable; no Phase 6 training
  reuse
- Canonical plan SHA-256:
  f2cf0feced412af5fa76f1ffa861b3500389c430209d8e5b09a4d9e985f1b4f9
- Targeted tests: 16/16 passed
- Full regression suite: 259/259 passed
- New Phase 6 scenarios executed: 0
- Phase 6 dataset rows collected: 0
- Phase 6 models/predictions/metrics: absent
- Containerlab required for P6-R0: no
- P6-R0 closeout: completed

The expected signatures are frozen design targets, not observed
results. Real smoke execution and restoration verification remain
blocked until the collector, injector, and topology milestones are
separately accepted.

## Latest P6-R1 verification

- Decision: D-078, implemented and contract-tested
- Contract document: docs/P6_R1_CONTRACTS.md
- Observation Profile v2 schema:
  schemas/observation_profile_v2.schema.json
- Evidence v3 schema: schemas/evidence_v3.schema.json
- Dataset Row v3 schema: schemas/dataset_row_v3.schema.json
- Frozen predictor features: 10/10 exact-order match with D-077
- Observation dispatch: v1/v2 PASS
- Evidence dispatch: v2/v3 PASS
- Dataset Row dispatch: v1/v2/v3 PASS
- Cross-version aggregation: rejected
- Predictor-leakage negative gates: PASS
- Raw artifact path and SHA-256 provenance gates: PASS
- Structural unavailable, collection unavailable, and masked missing
  reasons: distinct and count-verified
- Four frozen non-destructive mask families: contract-tested
- Source Evidence v3 hash preservation after masking: PASS
- Dataset Row v2 runtime default: retained
- Targeted tests: 57/57 passed
- Full regression suite: 316/316 passed in isolated verification
- New Containerlab execution: absent
- Real Evidence v3 and Dataset Row v3 artifacts: absent
- Phase 6 model, prediction, and metric: absent
- P6-R1 closeout: completed

The P6-R1 tests use synthetic contract fixtures. They verify contract
semantics and backwards compatibility, not laboratory feasibility or
the expected six-class signatures.

## Latest P6-R2 verification

- Decision: D-079, implemented and synthetic-test verified
- Implementation document: docs/P6_R2_EVIDENCE_COLLECTOR.md
- Collector: src/collection/evidence_collector_v3.py
- Required input: validated Observation Profile v2 only
- Ground truth, label, fault type, expected signature, partition,
  prediction, and metric inputs: absent
- Frozen feature order: 10/10 preserved
- Bounded command families: ping, ip -j route, ip -j link, and
  iptables/filter/FORWARD
- Atomic raw artifact directory: raw/v3
- Exact raw-byte SHA-256 provenance: verified
- Installed and expected next-hop reachability probes: separate
- Observed absent route versus failed route probe: distinct
- Exact tagged policy selector and duplicate-match failure: tested
- Existing-output overwrite protection: tested
- Evidence v2 collector source and historical runtime path: unchanged
- Dataset Row v2 runtime default: retained
- New collector v3 tests: 22/22 passed
- Targeted v2/v3 collector boundary: 26/26 passed
- Full regression suite: 338/338 passed in isolated verification
- New Containerlab execution: absent
- Real Evidence v3 and Dataset Row v3 artifacts: absent
- New fault injection, model, prediction, and metric: absent
- P6-R2 closeout: completed

P6-R2 verifies implementation behavior with synthetic command outputs.
It does not establish laboratory tool availability, healthy runtime
features, fault signatures, restoration, or experimental performance.

## Latest P6-R3 verification

- Decision: D-080, implemented and real-runtime verified
- Runtime-gate document: docs/P6_R3_HEALTHY_EVIDENCE_GATE.md
- Reviewed scenario: N0_NORMAL_OPERATION_P6_TOP01
- Topology and direction: TOP_01, hosta_to_hostb
- Observation roles: source hosta, route observer r1, transit r2,
  destination hostb
- Historical TOP-01 topology and frozen G01 fingerprint: unchanged
- Image base: Ubuntu 24.04
- Required commands: ip, ping, and iptables present
- iptables version/backend: 1.8.10, nf_tables
- Previous image recovery tag: ind-linux:p6-r2-preflight
- New ind-linux:0.1 image ID:
  sha256:66392daabae6054416fba5043f312bfc464bcc18246956867870e4953847ff5c
- Real experiment: p6_r3_healthy_top01-20260806T090542Z
- Collector runtime return code: 0
- Healthy Evidence v3 features: 10/10 observed and signature-verified
- Raw probe artifacts: 9/9 present and SHA-256 verified
- Evidence SHA-256:
  654cb717aa823091b6832d586b22503eb26f37aad81dc3e2f40f7d1f64c75ac2
- Collector-status SHA-256:
  d68b14f65b80f72ab7f0b8c7f3709b37b2f0a18165167ec3dd3593c914aed88d
- TOP-01 baseline before binding: 13/13 valid
- TOP-01 baseline before collection: 13/13 valid
- TOP-01 baseline after collection: 13/13 valid
- New P6-R3 verification tests: 5/5 passed
- Targeted v2/v3/gate boundary: 31/31 passed
- Full regression suite: 343/343 passed in the real local environment
- Containerlab containers after cleanup: 0
- Fault injection and restoration: absent
- Dataset Row v2 runtime default: retained
- Dataset Row v3, campaign row, model, prediction, and metric: absent
- P6-R3 closeout: completed

P6-R3 establishes only one controlled healthy runtime signature and its
provenance. It does not establish the three new fault signatures,
restoration, six-class separability, cross-topology behavior, campaign
results, ML performance, or real-world generalization.

## Latest P6-R4 verification

- Decisions: D-081 runtime amendment and D-082 smoke-gate acceptance
- P6-R4 status: completed
- First stopped interface runtime:
  `p6_r4_new_class_smoke-20260810T114903Z`
- First observed kernel behavior: `eth2=DOWN`, exact bound routes absent
- Second stopped interface runtime:
  `p6_r4_interface_recovery_smoke-20260810T122212Z`
- Route recreation through down device: 2/2 rejected with return code 2
- Exact stderr: `Error: Nexthop device is not up.`
- Safe interface, route, 13/13 baseline, and healthy Evidence v3
  restoration after the second gate: confirmed
- Superseded D-077 interface signature: T,T,F,T,T,F,F,F,T,F
- Amended D-081 interface signature: T,T,F,F,U,U,F,F,T,F
- Amended raw/availability boundary: 8 raw probes, 8 observed features,
  2 structurally unavailable route-dependent features
- Amended plan SHA-256:
  571cc26518d81a1768261970fb2d3847587fc4bbc1a9c62678c8f97f3e524746
- Accepted D-081 runtime:
  `p6_r4_d081_amended_smoke-20260810T130119Z`
- Accepted new-class smokes: 3/3
- Accepted rules: R_P6_ROUTING_003, R_P6_LINK_001, R_P6_POLICY_001
- Rule exact matches: 3/3
- Injection confirmations: 3/3
- Exact restorations: 3/3
- Restored healthy Evidence v3 signatures: 3/3
- Fault raw artifacts: 26/26 SHA-256 bound
- Fault-feature availability: 28 observed, 2 structurally unavailable
- Gate-summary SHA-256:
  d7d8dd30e0ad537c1a2897209c2a58285ba7fbe241653fa561649869e8c46a4b
- Targeted P6-R4 tests: 46/46 passed
- Full regression suite: 373/373 passed
- Final TOP-01 baseline: 13/13 valid
- TOP-01 containers after cleanup: 0
- Previous stopped runtime digests: 2/2 unchanged
- Dataset Row v3 aggregation, E01-E06, campaign, fitting, prediction,
  and metrics: absent
- P6-R4 closeout: completed

The two stopped interface runtimes are diagnostic evidence, not
accepted class samples. The three accepted smokes establish only
single-context fault feasibility, restoration, Evidence v3 signatures,
and exact Rule Engine v3 matches. P6-R5 must implement and review all
E01-E06 bindings before executing the frozen 72-row campaign.

## Latest P6-R5 verification

- Decision: D-083, clean six-context campaign accepted
- P6-R5 status: completed
- Frozen campaign plan SHA-256:
  `ef295fc436d383dc94925c3dc8fd11d9f3a7f6d8e87549d6c1c82db590277988`
- Recovered fingerprint manifest SHA-256:
  `e5e721e4b9fc1ad71fa6a9acf0fd37f8df5af1faa2e5846bf9e221e843c2cbe9`
- First failed campaign:
  `p6_r5_clean_campaign-20260811T063119Z`
- Failed campaign completed rows: 8, diagnostic-only
- Failed C4 attempt: 1, no Dataset Row v3 produced
- Failure cause: obsolete `preserved_routes` scenario key versus the
  accepted D-081 `baseline_routes` injector contract
- Failed runtime tree SHA-256:
  `531c872cd392ac7308ae4684ab422b06736e7d1c894f04c7ac5780745fd69d79`
- C4 recovery smoke:
  `p6_r5_c4_recovery_smoke-20260811T070536Z`
- C4 recovery injection/restoration: 6/6 confirmed
- C4 diagnostic Dataset Row export: 0
- Accepted clean campaign:
  `p6_r5_clean_campaign_recovery-20260811T070536Z`
- Contexts completed and cleanup-verified: 6/6
- Experiments completed: 72/72
- Dataset Row v3 records: 72/72 clean and unmasked
- Class balance: 12 rows for each of six classes
- Context balance: 12 rows for each of six contexts
- Collection-unavailable rows: 0
- Explicit split: 36 train, 12 validation, 24 test
- Split groups: 3 train, 1 validation, 2 test
- Cross-partition group leakage: absent
- Report-only test groups: E02 and E06
- Test status: `SEALED_FOR_P6_R6_REPORT_ONLY`
- Campaign-result SHA-256:
  `c4c45e19e8b98d00a3fa2ed3b4d4a8ad2ba6debd04baae05c2d7d7377f9df4d2`
- Merged Dataset Row v3 SHA-256:
  `50dd030e51e4873eac7665980e033a0236e4ddf26e446b66bd3d11613c4a0a9d`
- Split-manifest SHA-256:
  `adf70942a740be43e085aca67f9acb4085dd118827ceba8482913dbc6adb5f9f`
- Train partition SHA-256:
  `128e3b6316a2f9065db0d8478b9571cd0474c39f3cec1c0e766e8f489884fec7`
- Validation partition SHA-256:
  `8ae10a384f318e4e01a18da386585300547456ed32004eacd39054899176e60b`
- Test partition SHA-256:
  `4757ba82cbe939fadb2491b1907f0f13cc70be9d3f0117758896931484bcfee7`
- Diagnosis/model/selection/prediction/evaluation/metric outputs: absent
- Targeted Phase 6 tests: 144/144 passed
- Full regression suite: 387/387 passed
- Containerlab containers after final cleanup: 0
- Failed campaign retained: diagnostic-only
- P6-R5 closeout: completed

P6-R5 proves controlled six-class data collection, exact restoration,
complete-context balance, and a leakage-safe sealed split in six local
laboratory contexts. It does not prove ML or Hybrid accuracy,
missing-evidence robustness, statistical superiority, production
suitability, or real-world generalization.

## Latest P6-R6 verification

- Decision: D-084, six-class method freeze and report-only result
  accepted
- P6-R6 status: completed
- Method input: ten frozen tri-state features encoded as 20 binary
  predictor columns
- Forbidden predictors: labels, ground truth, partition, mask identity,
  identifiers, hashes, correctness, metrics, and explanations
- Missing-evidence masks: 4/4 deterministic and non-destructive
- Fit inputs: 36 clean E01/E03/E05 rows; masked fit inputs: 0
- Validation inputs: 12 clean and 48 masked E04 inputs
- Selected ML candidate: `logreg_l2_c1`
- Selected Hybrid policy: `rule_then_ml_fallback_v1`
- Independent freeze verification: passed before test access
- Test evaluation attempts: 1/1
- Report-only inputs per method: 24 clean, 96 masked, 120 total
- Model refit after freeze: false
- Policy reselection after freeze: false
- Test-guided revision: false
- Statistical-superiority test: not performed
- Rule-based clean accuracy/macro-F1/coverage: 1.0/1.0/1.0
- Rule-based masked accuracy/macro-F1/coverage: 0.0/0.0/0.0
- Rule-based masked insufficient-evidence rate: 1.0
- Rule-based overall accuracy/macro-F1/coverage:
  0.200000/0.333333/0.200000
- ML clean accuracy/macro-F1/coverage: 1.0/1.0/1.0
- ML masked accuracy/macro-F1/coverage: 0.791667/0.810486/1.0
- ML overall accuracy/macro-F1/coverage: 0.833333/0.846672/1.0
- Hybrid clean accuracy/macro-F1/coverage: 1.0/1.0/1.0
- Hybrid masked accuracy/macro-F1/coverage: 0.791667/0.810486/1.0
- Hybrid overall accuracy/macro-F1/coverage: 0.833333/0.846672/1.0
- ML versus Hybrid aggregate difference: absent in every reported scope
- Freeze-manifest SHA-256:
  `fa98a17e2ffae42f6dd009a13af65ad32174035eca8352bf26f321531a4fe0f5`
- Freeze-receipt SHA-256:
  `5c6c6537cb233efdeb52c6872f7a6ef7fb32eb3ac7b2474e2514b2908cd29bcc`
- Run-manifest SHA-256:
  `44c505b451c6211b4515564f4b889633b6d74ed0c618f19cc0ab3b9bdfe72b1d`
- Cross-method comparison SHA-256:
  `ca1c15d04828c0ae61cacaf80a5ee6f49f64a9cf3ac151a4b4ccd2386987e570`
- Targeted Phase 6 tests: 185/185 passed
- Full regression suite: 428/428 passed
- Containerlab: not required and not started
- P6-R6 closeout: completed

P6-R6 establishes a controlled descriptive comparison under four
deterministic missing-evidence transformations. The masks are not
independent network experiments or observed production missingness. The
accepted run establishes neither Hybrid superiority over ML nor
population-level or real-world generalization.

## Open issues

- Final FRRouting container image for later routing extensions
- Reproducible backup or publication policy for generated runtime
  datasets, models, and reports before final thesis archiving
- OSPF implementation; its current status remains proposed

## Latest P6-R7 decision

- Decision: D-085, no multiple-fault runtime in the current bachelor
  scope
- P6-R7 status: completed as a design-only gate
- Injected/effective/diagnosable truth separation: required but absent
  from the accepted single-label contracts
- Nominal unordered two-fault pairs: 10
- Nominal balanced pair-only campaign: 120 clean rows across six
  contexts and two repetitions
- Pair support under the existing 3/1/2 context allocation: 6 train,
  2 validation, and 4 test rows before invalid pairs are removed
- Mutually exclusive, causally dominated, or order-dependent pairs:
  identified at the design level
- New multi-label contracts, campaign, methods, freeze, and evaluation:
  not authorized
- Containerlab commands and combined injections: 0
- New Evidence, Dataset Row, model, prediction, or metric artifacts: 0
- P6-R6 artifacts and one-use test boundary: unchanged
- Phase 6 status: complete

## Latest P7-R0 decision

- Decision: D-086, local read-only projection of accepted P6-R6
  artifacts
- P7-R0 status: completed as a contract-only gate
- API stack: FastAPI with Uvicorn, bound by default to `127.0.0.1`
- Dashboard stack: static same-origin HTML/CSS/JavaScript
- Required database, React/Node, cloud, external asset, or paid service:
  none
- Accepted root bindings: 4 exact SHA-256 values
- Projection allowlist: 15 JSON/JSONL artifacts
- API surface: 6 versioned `GET` routes
- Dashboard views: overview, method comparison, case explorer, and
  provenance/limitations
- Model deserialization, inference, training, selection, new metrics,
  network commands, subprocesses, filesystem writes, and automatic
  remediation: prohibited
- API server or Dashboard implementation in P7-R0: absent
- Runtime artifact access or change in P7-R0: none

## Latest P7-R1 implementation

- Decision: D-087, bind all 15 allowed projection sources before use
- P7-R1 status: artifact catalog and immutable projection layer
  implemented and test-verified
- Accepted P7-R0 root identities: unchanged, 4/4 required
- Git-tracked projection catalog: 15/15 canonical path, SHA-256, and
  byte-size bindings
- Transitive gate, freeze, receipt, run, report, input, target, and
  prediction references: verified
- Immutable in-memory index: 120 inputs, 120 targets, and 120
  predictions for each of three methods
- Deep immutability: mappings frozen and arrays converted to tuples
- Deterministic projections: health, overview, comparison, case list,
  case detail, and provenance
- Estimator file in synthetic loader test: absent, proving no model read
  or deserialization
- Missing, drifted, rebound, malformed, and join-inconsistent sources:
  fail closed
- FastAPI/Uvicorn server and Dashboard: not implemented or started
- Inference, refit, selection, new metric, network command, subprocess,
  and runtime artifact write: absent
- P7-R1 tests: 23/23 passed
- Combined Phase 7 tests: 33/33 passed
- Targeted Phase 6 regression: 185/185 passed
- Full regression suite: 461/461 passed

## Latest P7-R2 implementation

- Decision: D-088, serve only verified immutable projections over local
  HTTP
- P7-R2 status: read-only FastAPI transport implemented and test-
  verified
- Runtime route set: exactly 6 versioned `GET` routes
- Automatic FastAPI docs, Redoc, and generated OpenAPI routes: disabled
- Catalog behavior: verified once during startup and retained as one
  immutable in-memory projection
- Per-request artifact reads or writes: none
- Success responses: P7-R0 schema version, data, and source metadata
  envelopes
- Normalized errors: `400 INVALID_QUERY`, `404 CASE_NOT_FOUND`,
  `405 METHOD_NOT_ALLOWED`, both frozen artifact `503` codes, and
  path-free `500 INTERNAL_ERROR`
- Local server entry point: Uvicorn on `127.0.0.1:8000`, reload disabled
- Response validation: all success families and the error envelope
  checked against the frozen OpenAPI 3.1 schemas
- Estimator in full API fixture: absent and never required
- Accepted source hashes after full API exercise: 15/15 unchanged
- Dashboard HTML/CSS/JavaScript: not implemented
- Diagnosis execution, inference, refit, selection, new metrics,
  Containerlab, subprocesses, and runtime artifact writes: absent
- P7-R2 tests: 32/32 passed
- Combined Phase 7 tests: 65/65 passed
- Targeted Phase 6 regression: 185/185 passed
- Full regression suite: 493/493 passed

## Next milestone

P7-R3 — Static Dashboard Implementation and Visual Verification.

P7-R3 may implement only the four frozen same-origin views—overview,
method comparison, case explorer, and provenance/limitations—using
static HTML/CSS/JavaScript over the accepted six-route API. It must not
add data routes, change API semantics, introduce a Node/React build,
deserialize the estimator, execute diagnosis, create metrics, or write
runtime artifacts. Visual verification and responsive/accessibility
checks are required before P7-R3 closes.

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
diagnostic accuracy.

P4-R0 produced the accepted deterministic feature matrix without
fitting or evaluating a model. Its successful leakage and provenance
audits establish only that the frozen D-067 inputs were transformed
according to D-070. They do not establish ML accuracy, validation or
test performance, generalization, or a comparison with D-069.

P4-R1 produced the first accepted independent Machine Learning
baseline. Its 1.0 fault_type accuracy and macro-F1 in every partition
describe the same small controlled campaign: train has three contexts,
while validation and test each have one. The classifier deliberately
does not localize faults or affected prefixes, which yields 1/3 exact
diagnosis and 0.0 affected-prefix correctness per partition. The
hybrid policy is precommitted and P5-R0 runtime-verified. P5-R1
implemented both candidates and selected consensus_abstain_v1 only
from G01 validation after an exact metric tie, using the frozen lower-
complexity rule. P5-R2 then evaluated that frozen policy once on G02,
produced the complete three-method descriptive comparison, and closed
Phase 5. The hybrid result is exact for the accepted six-row G02 test
group, but the small one-context test still cannot establish
statistical superiority or real-world generalization. Additional
controlled variation remains required in Phase 6.

P6-R0 addresses that limitation only at the design level. It freezes
a new six-class, six-context, 72-row clean campaign; ten planned
tri-state features; a 3/1/2 whole-context split; and four missing-
evidence masks. It produces no new empirical evidence. The planned
signatures and row counts cannot be described as implemented or
observed until their later milestones complete.

P6-R1 implements the contract boundary for those planned artifacts.
Its 57 targeted tests and 316-test regression establish strict
structure, version dispatch, leakage rejection, provenance binding,
and unavailable-reason semantics on synthetic fixtures. They do not
show that the raw probes, fault injectors, topology changes, or class
signatures work in Containerlab. Those empirical claims remain
absent.

P6-R2 implements the raw probe and Evidence v3 construction path. Its
22 new collector tests, 26-test targeted v2/v3 collector boundary, and
338-test regression establish fail-safe parsing, atomic persistence,
raw-byte hash binding, output protection, and no v2 regression on
synthetic command outputs. They still do not prove command availability
or any expected signature in Containerlab. P6-R3 is the first milestone
authorized to test only the healthy Evidence v3 runtime path.

P6-R3 proves that ip, ping, and open-source iptables are present in the
rebuilt local image and that one reviewed fault-free TOP-01 flow produces
the frozen ten-feature healthy Evidence v3 signature with nine exact raw
hash bindings. Three 13/13 baseline validations and zero remaining lab
containers establish preservation for this execution. This single
healthy context does not prove any new fault signature, injector
restoration, campaign feasibility, six-class generalization, or method
performance. Those claims remain prohibited until their later gates.
