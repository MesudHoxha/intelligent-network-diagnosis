# HANDOFF — Dataset Contract and Normal Control

## 1. What was completed

- Defined Experiment Manifest v2.
- Added runtime validation for the manifest contract.
- Added the formal Experiment Manifest v2 JSON Schema.
- Defined Dataset Row v1.
- Added the Dataset Row v1 builder and JSON Schema.
- Added scenario kind, variant_id, and split_group_id metadata.
- Added N0_NORMAL_OPERATION as a no-fault scenario.
- Extended the experiment runner with a dedicated normal path
  that performs no fault injection or restoration.
- Exported the historical C1 and C2 experiments as Dataset Row
  v1.
- Executed and audited the first real N0 normal experiment.
- Completed the automated suite with 32 passing tests.
- Completed git diff whitespace validation.

Verified runtime experiment:

- data/raw/n0_normal_operation-20260728T133851Z

Verified N0 results:

- Status: COMPLETED
- Diagnosis: NO_FAULT_DETECTED
- Exact match: true
- Baseline valid before and after: true
- Fault restoration invoked: false
- Dataset label: no_fault
- Diagnostic features true: 7/7
- Unavailable feature count: 0

## 2. What was decided

- Experiment Manifest v2 is the canonical contract for new
  experiment runs.
- Dataset Row v1 represents one completed experiment per row.
- The initial supervised target is fault_type.
- Features use true, false, or unavailable.
- scenario_id, concrete IP addresses, ground truth, rule outputs,
  and evaluation results are excluded from model features.
- split_group_id will control group-aware dataset splitting.
- Valid no-fault experiments are part of the dataset.
- ML training remains blocked until reproducible batch generation
  and group-aware splitting are validated.
- The existing HANDOFF_POC_B remains unchanged as the preserved
  PoC-B checkpoint.

## 3. Files created or changed

Changed:

- scenarios/routing/C1_MISSING_STATIC_ROUTE.yml
- scenarios/routing/C2_WRONG_NEXT_HOP.yml
- src/orchestration/experiment_runner.py
- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/ROADMAP.md

Created:

- scenarios/routing/N0_NORMAL_OPERATION.yml
- schemas/experiment_manifest_v2.schema.json
- schemas/dataset_row_v1.schema.json
- src/contracts/__init__.py
- src/contracts/experiment_manifest.py
- src/dataset/__init__.py
- src/dataset/contract.py
- tests/unit/test_contract_schemas.py
- tests/unit/test_dataset_contract.py
- tests/unit/test_experiment_manifest.py
- tests/unit/test_normal_experiment.py
- docs/HANDOFF_DATASET_CONTRACT.md

## 4. Open issues

- Parameterized variants for N0, C1, and C2
- Reproducible batch experiment runner
- Repeated normal samples
- Dataset-batch validation and summary
- Group-aware train, validation, and test splitting
- Missing-evidence experiments
- Unseen variants
- Additional pilot fault classes
- ML and hybrid methods

## 5. Next step

Implement a reproducible batch-generation layer for repeated N0
runs and parameterized C1/C2 variants. Validate every completed
experiment against the artifact contracts and preserve
split_group_id before starting ML training.

## 6. Impact on central documents

- MASTER_CONTEXT now records Manifest v2, Dataset Row v1, and the
  verified N0 normal execution.
- DECISIONS now records the manifest and dataset-row contracts,
  while D-040 records the tested normal class.
- STATUS now distinguishes the completed contract milestone from
  the still-pending reproducible dataset batch.
- ROADMAP now records the completed Phase 2 contract work and the
  pending variant, batch-generation, and splitting work.
- HANDOFF_POC_B remains unchanged.
