# HANDOFF — P2-R2 Evaluation Group Protocol

Date: 2026-07-30
Status: COMPLETED

## 1. What was completed

- Audited the P2-R1 split contract for shared laboratory-context
  leakage across no-fault and fault classes.
- Defined Evaluation Group Protocol v1.
- Reused split_group_id as the evaluation-context boundary without
  changing Dataset Row v2 or adding evaluation_context_id.
- Replaced class-specific split allocation with deterministic
  complete-context allocation.
- Added complete required-class coverage validation for every group.
- Added optional explicit expected_fault_types validation, including
  rejection of globally missing or unexpected classes.
- Preserved whole-group train/validation/test assignment and
  pre-output feasibility validation.
- Changed the split algorithm identifier to
  complete_context_group_hash_v2 and the split manifest schema version
  to 2.
- Added required_fault_types and source_group_class_coverage to the
  split manifest.
- Verified deterministic 3/1/1 allocation for five complete contexts
  under the default 0.6/0.2/0.2 ratios.
- Verified that fewer than three contexts, incomplete contexts,
  class-specific historical groups, mixed Dataset Row versions, and
  invalid expected-class declarations are rejected.
- Verified that infeasible sources create no split output directory.
- Executed 14 targeted splitter tests and the complete suite of 128
  tests successfully.
- Executed compileall and git diff checks successfully.
- Audited the real historical P1 JSONL and confirmed its required
  rejection under the complete-context protocol.

## 2. What was decided

- D-058 supersedes the single-class grouping and per-class allocation
  clauses of D-055 because those clauses allowed N0, C1, and C2 from
  one laboratory context to cross partitions.
- split_group_id identifies the smallest complete experiment set that
  must remain inside one partition because it shares one causal
  diagnostic context.
- One context is defined by the topology graph and forwarding
  configuration, directed path, route-observer/transit role binding,
  logical fault-injection location, and evidence producers.
- Every current context must contain no_fault,
  missing_static_route, and wrong_next_hop.
- Repetitions, alternate addressing on the same logical path, node
  renaming, identifiers, timestamps, and cosmetic parameter changes
  do not create independent groups.
- Dataset Row v2 remains the canonical row contract and is unchanged.
- Three complete contexts are the technical minimum for a three-way
  split.
- Five complete contexts are the readiness target before the first ML
  experiment, producing a default 3/1/1 group allocation.
- With three classes and two repetitions, the minimum planned campaign
  contains 30 rows.
- The planned coverage matrix reserves G01 for TOP-01, G02-G04 for
  three materially distinct TOP-02 contexts, and G05 for a TOP-03
  asymmetric context.
- TOP-02 and TOP-03 are planned, not implemented.
- Historical P1 and P2-R1 artifacts must not be relabelled or migrated
  to manufacture evaluation contexts.
- ML training remains blocked until the five reviewed contexts,
  complete class coverage, expanded campaign, and split audit are
  verified.

## 3. Files created or changed

Implementation:

- src/dataset/splitter.py

Tests:

- tests/unit/test_dataset_splitter.py

Protocol and central documentation:

- docs/EVALUATION_GROUP_PROTOCOL.md
- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/HANDOFF_P2_R2.md

No Dataset Row schema, scenario, topology, laboratory, or historical
dataset artifact was changed.

## 4. Open issues

- Freeze a shared multi-class split_group_id binding for future G01
  TOP-01 campaign rows.
- Convert the planned G02, G03, and G04 labels into concrete and
  demonstrably distinct TOP-02 designs.
- Implement and verify the first real TOP-02 laboratory, validator,
  scenarios, Evidence v2 artifacts, and Dataset Row v2 artifacts.
- Design and implement the G05 TOP-03 asymmetric context.
- Execute the complete minimum 30-row campaign.
- Produce and audit the first valid D-058 train/validation/test split.
- Implement and evaluate the Machine Learning method.
- Implement and evaluate the hybrid method.

## 5. Next step

Start P2-R3 with a TOP-02 context-design review before changing
laboratory files.

For G02, G03, and G04, record and compare:

- topology graph and forwarding configuration;
- directed source-to-destination path;
- route-observer and transit role binding;
- logical C1/C2 fault-injection location;
- evidence-producing components;
- topology/configuration fingerprint; and
- proposed shared split_group_id.

Implement the first TOP-02 context only after this review confirms
that it is materially distinct from G01 and from the other planned
TOP-02 contexts.

## 6. Impact on central documents

- MASTER_CONTEXT replaces the obsolete class-specific splitter model
  with the complete evaluation-context contract and records the
  five-context readiness target.
- DECISIONS records D-058 and explicitly identifies the incompatible
  D-055 clauses it supersedes.
- STATUS records 128 passing tests, the real P1 rejection audit, the
  planned TOP-01/TOP-02/TOP-03 matrix, the current ML block, and the
  concrete P2-R3 design milestone.
- EVALUATION_GROUP_PROTOCOL is the normative grouping and ML-readiness
  document for subsequent campaign design.
