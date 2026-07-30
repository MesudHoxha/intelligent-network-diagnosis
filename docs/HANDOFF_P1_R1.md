# HANDOFF — P1-R1 Routing Variant Diagnosis Fix

Date: 2026-07-30
Status: COMPLETED

## 1. What was completed

- Added destination_address and destination_prefix to collected
  observation evidence.
- Updated the Rule Engine to derive affected_prefix from observation
  evidence instead of a fixed canonical subnet.
- Verified 80/80 automated tests.
- Verified real alternate-subnet C1 and C2 experiments with
  affected_prefix=10.10.22.0/24 and exact_match=true.
- Regenerated P1_ROUTING_VARIANTS and obtained 12/12 exact matches.
- Verified the final TOP-01 baseline with 13/13 passing checks.

## 2. What was decided

- Batch status COMPLETED remains a technical execution and aggregation
  status.
- Diagnostic exact_match remains a separate evaluation result.
- The corrected 12-row P1 batch is the accepted pilot artifact.
- The earlier 8/12 batch remains unchanged as regression evidence.
- No Batch Runner code change is required for P1-R1.

## 3. Files created or changed

Code checkpoint:

- Commit f487c52 — fix: derive affected prefix from observation
  evidence
- src/collection/evidence_collector.py
- src/rules/rule_engine.py
- tests/unit/test_evidence_collector.py
- tests/unit/test_normal_experiment.py
- tests/unit/test_rule_engine.py

Accepted artifacts:

- data/processed/p1_routing_variants-
  20260730T082450785454Z-f283bfdd9ccc4b04afbc6462f6073a63.jsonl
- data/metadata/p1_routing_variants-
  20260730T082450785454Z-f283bfdd9ccc4b04afbc6462f6073a63.json
- Twelve corresponding experiment directories under data/raw/

Central documentation:

- docs/MASTER_CONTEXT.md
- docs/DECISIONS.md
- docs/STATUS.md
- docs/HANDOFF_P1_R1.md

## 4. Open issues

- Verify split_group_id assignments across P1.
- Implement and test group-aware dataset splitting.
- Define a larger and more varied controlled dataset campaign.
- Consider a separate reusable batch-level evaluation report.
- ML and hybrid methods remain unimplemented.

## 5. Next step

Audit split_group_id values in the accepted 12-row dataset, define the
group-aware split contract, implement it, and verify that related
variants cannot cross dataset partitions.

## 6. Impact on central documents

- MASTER_CONTEXT records the accepted P1 result and the distinction
  between completion and diagnostic correctness.
- DECISIONS adds the completion-semantics decision and acceptance of
  the first parameterized routing pilot.
- STATUS moves parameterized P1 generation to implemented and makes
  group-aware splitting the next milestone.
