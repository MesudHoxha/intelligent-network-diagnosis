# HANDOFF — Batch Plan v1

## 1. What was completed

- Implemented the Batch Plan v1 runtime validator and planner.
- Added the Batch Plan v1 JSON Schema.
- Added B0_SMOKE_CANONICAL as the first canonical smoke plan.
- Verified deterministic expansion in the listed order:
  N0_NORMAL_OPERATION, C1_MISSING_STATIC_ROUTE, and
  C2_WRONG_NEXT_HOP.
- Verified a planned experiment count of three.
- Enforced a maximum of 1000 batch entries in both the runtime
  validator and JSON Schema.
- Registered jsonschema as a project dependency.
- Removed the package import behavior that caused RuntimeWarning
  during module execution.
- Completed the full automated test suite with 46 passing tests.

No laboratory experiment was executed during this stage.

## 2. What was decided

- Batch Plan v1 is the canonical input contract for reproducible
  dataset-batch planning.
- The first version preserves listed execution order.
- The first version supports failure_policy=stop.
- Plan validation and deterministic expansion remain separate
  from real batch execution.
- Validation of B0_SMOKE_CANONICAL does not constitute a generated
  dataset or an executed batch.
- ML training must not begin before reproducible batch execution,
  row validation, and group-aware splitting are verified.

## 3. Files created or changed

Changed project metadata:

- pyproject.toml

Created implementation and contracts:

- src/batch/__init__.py
- src/batch/plan.py
- schemas/batch_plan_v1.schema.json
- plans/batches/B0_SMOKE_CANONICAL.yml

Created tests:

- tests/unit/test_batch_plan.py
- tests/unit/test_batch_plan_schema.py

Updated central documents:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/ROADMAP.md

Created handoff:

- docs/HANDOFF_BATCH_PLAN.md

## 4. Open issues

- Reproducible batch runner
- Batch-level execution result and dataset aggregation
- Repeated normal experiments
- Parameterized N0, C1, and C2 variants
- Validation of every generated Dataset Row v1
- Group-aware dataset splitting
- Missing-evidence and unseen-variant experiments
- Machine Learning and hybrid diagnostic approaches

## 5. Next step

Implement and test the batch runner that consumes a validated
Batch Plan v1, preserves the planned order, invokes the existing
experiment runner, and validates every completed Dataset Row v1.

After automated runner tests pass, execute B0_SMOKE_CANONICAL as
the first real batch.

## 6. Impact on central documents

- MASTER_CONTEXT now distinguishes validated batch planning from
  real batch execution and dataset generation.
- DECISIONS records Batch Plan v1 as the canonical planning
  contract.
- STATUS records the planner and schema as implemented and tested,
  while keeping the runner and dataset generation pending.
- ROADMAP separates the completed planning contract from the
  unimplemented batch runner and dataset aggregation.
