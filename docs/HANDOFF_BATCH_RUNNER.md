# HANDOFF — Batch Runner v1

## 1. What was completed

- Implemented Batch Runner v1.
- Connected Batch Plan v1 to the existing experiment runner.
- Preserved deterministic listed execution order.
- Implemented failure_policy=stop.
- Required every experiment result to have COMPLETED status.
- Built and revalidated every Dataset Row v1 at the batch boundary.
- Enforced equality between sample_id and experiment_id.
- Added duplicate sample-ID and experiment-directory detection.
- Persisted batch-level metadata during execution.
- Implemented atomic JSONL aggregation after complete success.
- Prevented overwriting existing batch-result and dataset outputs.
- Replaced second-precision experiment identifiers with identifiers
  containing UTC microseconds and UUID values.
- Added collision-resistant default batch-run identifiers.
- Completed seven isolated Batch Runner tests.
- Completed the full automated suite with 53 passing tests.
- Completed syntax, CLI-help, and whitespace checks successfully.

No Docker, Containerlab, or real laboratory batch was executed during
this stage.

## 2. What was decided

- Batch Runner v1 is the canonical orchestration layer for executing
  Batch Plan v1.
- The runner reuses the existing experiment runner rather than
  duplicating laboratory orchestration.
- The first version supports only listed order and
  failure_policy=stop.
- A failed batch retains its metadata result but does not publish a
  partial JSONL dataset.
- Dataset output is published only after all planned experiments and
  Dataset Row v1 validations succeed.
- Existing output files must never be overwritten silently.
- Real batch execution remains distinct from isolated runner testing.
- ML training must not begin after runner implementation alone.

## 3. Files created or changed

Changed implementation:

- src/orchestration/experiment_runner.py

Created implementation:

- src/batch/runner.py

Created tests:

- tests/unit/test_batch_runner.py

Updated central documents:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/ROADMAP.md

Created handoff:

- docs/HANDOFF_BATCH_RUNNER.md

## 4. Open issues

- Execute B0_SMOKE_CANONICAL as the first real batch.
- Verify real batch metadata and the aggregated JSONL dataset.
- Confirm the final TOP-01 9/9 baseline after the batch.
- Generate repeated and parameterized N0, C1, and C2 variants.
- Implement group-aware dataset splitting through split_group_id.
- Add missing-evidence and unseen-variant experiments.
- Implement and evaluate the Machine Learning baseline.
- Implement and evaluate the hybrid diagnostic method.

## 5. Next step

Commit Batch Runner v1 as an isolated checkpoint. After that clean
checkpoint, deploy TOP-01 and execute B0_SMOKE_CANONICAL through the
real Batch Runner v1 CLI.

The real run must verify:

- execution order N0, C1, and C2;
- three COMPLETED experiments;
- three valid Dataset Row v1 records;
- a COMPLETED batch result;
- successful restoration and the final 9/9 TOP-01 baseline.

## 6. Impact on central documents

- MASTER_CONTEXT now distinguishes implemented runner behavior from
  real batch execution.
- DECISIONS records the canonical batch execution, aggregation, and
  identifier contracts.
- STATUS moves runner implementation into completed work and makes
  real B0 execution the next milestone.
- ROADMAP marks the runner as implemented and tested in isolation
  while keeping the first real batch pending.
