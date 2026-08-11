from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.campaign.phase6_plan import CLASS_ORDER, load_phase6_campaign_plan
from src.dataset.contract_v3 import validate_dataset_row_v3
from src.phase6 import coordinator
from src.phase6.contracts import sha256_file
from tests.unit.test_p6_r4_rule_engine_v3 import evidence_for


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        )
    )


def _labels(
    fault_type: str, *, source: str, observer: str, prefix: str
) -> dict[str, Any]:
    if fault_type == "no_fault":
        return {
            "fault_category": None,
            "fault_type": fault_type,
            "fault_location": None,
            "affected_prefix": None,
        }
    return {
        "fault_category": (
            "link"
            if fault_type == "interface_down"
            else "access_control"
            if fault_type == "acl_block"
            else "routing"
        ),
        "fault_type": fault_type,
        "fault_location": source if fault_type == "wrong_default_gateway" else observer,
        "affected_prefix": prefix,
    }


def _build_fixture_repository(tmp_path: Path) -> Path:
    source_root = Path.cwd()
    repository = tmp_path / "repo"
    repository.mkdir()
    for directory in ("src", "plans", "labs", "scenarios", "schemas"):
        shutil.copytree(source_root / directory, repository / directory)
    plan = load_phase6_campaign_plan(
        repository / coordinator.DEFAULT_PLAN_PATH, repository_root=repository
    )
    rows_by_partition: dict[str, list[dict[str, Any]]] = {
        "train": [],
        "validation": [],
        "test": [],
    }
    allocation = {
        group: partition
        for partition, groups in plan.split_allocation.items()
        for group in groups
    }
    raw_root = repository / coordinator.DEFAULT_RAW_ROOT
    all_rows: list[dict[str, Any]] = []
    for context in plan.contexts:
        partition = allocation[context.split_group_id]
        for fault_type in CLASS_ORDER:
            for repetition in range(2):
                sample_id = (
                    f"p6-{context.group_slot.lower()}-{fault_type}-{repetition + 1}"
                )
                evidence = deepcopy(evidence_for(fault_type))
                evidence.update(
                    {
                        "topology_id": context.topology_id,
                        "direction": context.direction,
                        "source_node": context.source_node,
                        "route_observer_node": context.route_observer_node,
                        "transit_node": context.transit_node,
                    }
                )
                evidence_path = (
                    raw_root
                    / context.group_slot
                    / sample_id
                    / "parsed"
                    / "evidence.json"
                )
                _write_json(evidence_path, evidence)
                features = {
                    name: (
                        "true"
                        if value is True
                        else "false"
                        if value is False
                        else "unavailable"
                    )
                    for name, value in evidence["features"].items()
                }
                availability = deepcopy(evidence["availability"])
                unavailable = sum(value == "unavailable" for value in features.values())
                structural = sum(
                    value == "structurally_unavailable"
                    for value in availability.values()
                )
                row = {
                    "schema_version": 3,
                    "sample_id": sample_id,
                    "metadata": {
                        "experiment_id": sample_id,
                        "scenario_id": f"scenario-{fault_type}",
                        "variant_id": f"repeat-{repetition + 1}",
                        "split_group_id": context.split_group_id,
                        "topology_id": context.topology_id,
                        "direction": context.direction,
                        "source_node": context.source_node,
                        "route_observer_node": context.route_observer_node,
                        "transit_node": context.transit_node,
                        "collected_at_utc": "2026-08-11T08:00:00+00:00",
                    },
                    "features": features,
                    "labels": _labels(
                        fault_type,
                        source=context.source_node,
                        observer=context.route_observer_node,
                        prefix=str(evidence["destination_prefix"]),
                    ),
                    "quality": {
                        "experiment_completed": True,
                        "collector_completed": True,
                        "baseline_before_valid": True,
                        "baseline_after_valid": True,
                        "unavailable_feature_count": unavailable,
                        "structural_unavailable_count": structural,
                        "collection_unavailable_count": 0,
                        "masked_missing_count": 0,
                    },
                    "provenance": {
                        "source_evidence_schema_version": 3,
                        "source_evidence_sha256": sha256_file(evidence_path),
                        "feature_availability": availability,
                        "mask_id": None,
                    },
                }
                validate_dataset_row_v3(row)
                rows_by_partition[partition].append(row)
                all_rows.append(row)
    for rows in rows_by_partition.values():
        rows.sort(key=lambda value: value["sample_id"])
    all_rows.sort(key=lambda value: value["sample_id"])
    split_root = repository / coordinator.DEFAULT_SPLIT_ROOT
    for partition, rows in rows_by_partition.items():
        _write_jsonl(split_root / f"{partition}.jsonl", rows)
    split_manifest = {
        "schema_version": 3,
        "algorithm": "explicit_complete_context_v1",
        "source": {"sha256": "pending"},
        "outputs": {
            f"{partition}.jsonl": {
                "sha256": sha256_file(split_root / f"{partition}.jsonl")
            }
            for partition in rows_by_partition
        },
    }
    _write_json(split_root / "split_manifest.json", split_manifest)
    merged_path = (
        repository
        / "data/processed"
        / f"{coordinator.ACCEPTED_CAMPAIGN_RUN_ID}.dataset-row-v3.jsonl"
    )
    _write_jsonl(merged_path, all_rows)
    campaign = {
        "campaign_run_id": coordinator.ACCEPTED_CAMPAIGN_RUN_ID,
        "status": "COMPLETED",
        "completed_context_count": 6,
        "completed_experiment_count": 72,
        "dataset_row_count": 72,
        "diagnosis_count": 0,
        "prediction_count": 0,
        "metric_count": 0,
        "masked_row_count": 0,
        "test_partition_status": "SEALED_FOR_P6_R6_REPORT_ONLY",
        "merged_dataset": {"sha256": sha256_file(merged_path)},
        "split": {"test_partition_status": "SEALED_FOR_P6_R6_REPORT_ONLY"},
    }
    _write_json(repository / coordinator.DEFAULT_CAMPAIGN_RESULT_PATH, campaign)
    return repository


def test_freeze_verification_precedes_one_report_only_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _build_fixture_repository(tmp_path)
    split_root = repository / coordinator.DEFAULT_SPLIT_ROOT
    campaign_path = repository / coordinator.DEFAULT_CAMPAIGN_RESULT_PATH
    merged_path = (
        repository
        / "data/processed"
        / f"{coordinator.ACCEPTED_CAMPAIGN_RUN_ID}.dataset-row-v3.jsonl"
    )
    monkeypatch.setattr(
        coordinator,
        "ACCEPTED_CAMPAIGN_RESULT_SHA256",
        sha256_file(campaign_path),
    )
    monkeypatch.setattr(
        coordinator,
        "ACCEPTED_MERGED_DATASET_SHA256",
        sha256_file(merged_path),
    )
    monkeypatch.setattr(
        coordinator,
        "ACCEPTED_SPLIT_MANIFEST_SHA256",
        sha256_file(split_root / "split_manifest.json"),
    )
    monkeypatch.setattr(
        coordinator,
        "ACCEPTED_PARTITION_SHA256",
        {
            partition: sha256_file(split_root / f"{partition}.jsonl")
            for partition in ("train", "validation", "test")
        },
    )

    freeze = coordinator.create_development_freeze(
        repository_root=repository,
        freeze_directory=coordinator.DEFAULT_FREEZE_DIRECTORY,
        report_directory=coordinator.DEFAULT_REPORT_DIRECTORY,
        gate_result_path=coordinator.DEFAULT_GATE_RESULT_PATH,
    )

    assert freeze["test_inputs_read"] == 0
    assert freeze["test_predictions_or_metrics"] == "ABSENT"
    assert not (repository / coordinator.DEFAULT_REPORT_DIRECTORY).exists()
    receipt = coordinator.verify_development_freeze(
        repository_root=repository,
        freeze_directory=coordinator.DEFAULT_FREEZE_DIRECTORY,
        report_directory=coordinator.DEFAULT_REPORT_DIRECTORY,
        gate_result_path=coordinator.DEFAULT_GATE_RESULT_PATH,
        write_receipt=True,
    )
    assert receipt["authorization"] == "ONE_REPORT_ONLY_TEST_EVALUATION"

    result = coordinator.run_report_only_evaluation(
        repository_root=repository,
        freeze_directory=coordinator.DEFAULT_FREEZE_DIRECTORY,
        report_directory=coordinator.DEFAULT_REPORT_DIRECTORY,
        gate_result_path=coordinator.DEFAULT_GATE_RESULT_PATH,
    )

    assert result["gate"]["status"] == "COMPLETED"
    assert result["gate"]["test_evaluation_attempt_count"] == 1
    report_root = repository / coordinator.DEFAULT_REPORT_DIRECTORY
    run_manifest = json.loads((report_root / "run_manifest.json").read_text())
    assert run_manifest["test_clean_inputs"] == 24
    assert run_manifest["test_masked_inputs"] == 96
    assert run_manifest["model_refit_after_freeze"] is False
    comparison = result["comparison"]
    assert comparison["comparison_type"] == "DESCRIPTIVE_ONLY"
    assert comparison["statistical_superiority_test"] == "NOT_PERFORMED"

    with pytest.raises(coordinator.Phase6CoordinatorError, match="already exists"):
        coordinator.run_report_only_evaluation(
            repository_root=repository,
            freeze_directory=coordinator.DEFAULT_FREEZE_DIRECTORY,
            report_directory=coordinator.DEFAULT_REPORT_DIRECTORY,
            gate_result_path=coordinator.DEFAULT_GATE_RESULT_PATH,
        )
