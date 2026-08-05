from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from src.dataset.contract import FEATURE_NAMES
from src.dataset.splitter import (
    PARTITION_NAMES,
    jsonl_payload,
    write_group_aware_split,
)
from src.evaluation.reporting import (
    DEFAULT_CLASS_ORDER,
    EvaluationReportingError,
    build_method_evaluation_result,
    build_rule_based_baseline_report,
    compute_classification_metrics,
    sha256_file,
    validate_method_evaluation_result,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "schemas/method_evaluation_result_v1.schema.json"
)
CAMPAIGN_RUN_ID = (
    "p2_routing_5ctx_v1-"
    "20260804T073429388394Z-"
    "617194fea9954ed98ec120bdefea23d9"
)
GROUPS = {
    "G01": "CTX_G01_TOP01_LINEAR_2R",
    "G02": "CTX_G02_TOP02_CHAIN_3R",
    "G03": "CTX_G03_TOP02_BRANCH_MID",
    "G04": "CTX_G04_TOP02_DUAL_TRANSIT",
    "G05": "CTX_G05_TOP03_ASYMMETRIC_RETURN",
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def make_row(
    group_slot: str,
    fault_type: str,
    repetition: int,
) -> dict[str, Any]:
    sample_id = (
        f"sample-{group_slot.lower()}-"
        f"{fault_type}-{repetition}"
    )
    features = {
        name: "true"
        for name in FEATURE_NAMES
    }

    if fault_type == "missing_static_route":
        features.update({
            "destination_reachable": "false",
            "route_to_destination_exists_on_observer": (
                "false"
            ),
            "route_next_hop_present_on_observer": (
                "false"
            ),
            "route_next_hop_reachable_from_observer": (
                "unavailable"
            ),
        })
    elif fault_type == "wrong_next_hop":
        features.update({
            "destination_reachable": "false",
            "route_next_hop_reachable_from_observer": (
                "false"
            ),
        })

    is_normal = fault_type == "no_fault"
    return {
        "schema_version": 2,
        "sample_id": sample_id,
        "metadata": {
            "experiment_id": sample_id,
            "scenario_id": (
                f"{fault_type}_{group_slot}"
            ),
            "variant_id": "canonical",
            "split_group_id": GROUPS[group_slot],
            "topology_id": f"TOP_{group_slot}",
            "direction": "hosta_to_hostb",
            "route_observer_node": "r1",
            "transit_node": "r2",
            "collected_at_utc": (
                "2026-08-04T08:00:00+00:00"
            ),
        },
        "features": features,
        "labels": {
            "fault_category": (
                None if is_normal else "routing"
            ),
            "fault_type": fault_type,
            "fault_location": (
                None if is_normal else "r1"
            ),
            "affected_prefix": (
                None if is_normal else "10.0.0.0/24"
            ),
        },
        "quality": {
            "experiment_completed": True,
            "collector_completed": True,
            "baseline_before_valid": True,
            "baseline_after_valid": True,
            "unavailable_feature_count": sum(
                value == "unavailable"
                for value in features.values()
            ),
        },
    }


def create_accepted_artifacts(
    root: Path,
) -> dict[str, Path]:
    rows = [
        make_row(group_slot, fault_type, repetition)
        for group_slot in GROUPS
        for fault_type in DEFAULT_CLASS_ORDER
        for repetition in (1, 2)
    ]
    merged_path = root / "data/processed/accepted.jsonl"
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path.write_text(
        jsonl_payload(rows),
        encoding="utf-8",
    )
    split_directory = root / "data/processed/accepted-split"
    split_manifest = write_group_aware_split(
        merged_path,
        split_directory,
        seed=20260730,
        expected_fault_types=DEFAULT_CLASS_ORDER,
    )
    assert split_manifest["partitions"]["train"][
        "group_ids"
    ] == sorted([
        GROUPS["G03"],
        GROUPS["G04"],
        GROUPS["G05"],
    ])
    assert split_manifest["partitions"]["validation"][
        "group_ids"
    ] == [GROUPS["G01"]]
    assert split_manifest["partitions"]["test"][
        "group_ids"
    ] == [GROUPS["G02"]]

    rule_records: list[dict[str, Any]] = []

    for sequence_number, row in enumerate(rows, start=1):
        sample_id = row["sample_id"]
        fault_type = row["labels"]["fault_type"]
        experiment = root / "data/raw" / sample_id
        evaluation_path = (
            experiment / "evaluation/rule_based.json"
        )
        is_normal = fault_type == "no_fault"

        write_json(
            experiment / "manifest.json",
            {
                "schema_version": 2,
                "experiment_id": sample_id,
                "current_state": "COMPLETED",
            },
        )
        write_json(
            experiment / "ground_truth.json",
            row["labels"],
        )
        write_json(
            experiment / "parsed/evidence.json",
            {
                "schema_version": 2,
                "observations": row["features"],
            },
        )
        write_json(
            experiment / "diagnosis/rule_based.json",
            {
                "method": "rule_based",
                "status": (
                    "NO_FAULT_DETECTED"
                    if is_normal
                    else "DIAGNOSIS_PRODUCED"
                ),
            },
        )
        write_json(
            evaluation_path,
            {
                "schema_version": 1,
                "method": "rule_based",
                "expected": {
                    "fault_type": fault_type,
                },
                "predicted": {
                    "status": (
                        "NO_FAULT_DETECTED"
                        if is_normal
                        else "DIAGNOSIS_PRODUCED"
                    ),
                    "fault_type": (
                        None if is_normal else fault_type
                    ),
                },
                "metrics": {
                    "exact_match": True,
                    "affected_prefix_correct": True,
                },
            },
        )
        rule_records.append({
            "campaign_sequence_number": sequence_number,
            "sample_id": sample_id,
            "split_group_id": row[
                "metadata"
            ]["split_group_id"],
            "fault_type": fault_type,
            "evaluation_path": str(evaluation_path),
            "exact_match": True,
            "affected_prefix_correct": True,
        })

    rule_audit_path = root / "reports/rule-audit.json"
    write_json(
        rule_audit_path,
        {
            "schema_version": 1,
            "campaign_run_id": CAMPAIGN_RUN_ID,
            "campaign_id": "P2_ROUTING_5CTX_V1",
            "method": "rule_based",
            "record_count": len(rule_records),
            "exact_match_count": len(rule_records),
            "affected_prefix_correct_count": (
                len(rule_records)
            ),
            "records": rule_records,
        },
    )
    campaign_path = root / "data/metadata/campaign.json"
    write_json(
        campaign_path,
        {
            "schema_version": 1,
            "status": "COMPLETED",
            "campaign_run_id": CAMPAIGN_RUN_ID,
            "campaign_id": "P2_ROUTING_5CTX_V1",
            "dataset_row_schema_version": 2,
            "merged_dataset": {
                "path": str(merged_path),
                "sha256": sha256_file(merged_path),
                "row_count": 30,
            },
            "rule_audit": {
                "path": str(rule_audit_path),
                "record_count": 30,
                "exact_match_count": 30,
                "affected_prefix_correct_count": 30,
            },
            "split": {
                "manifest_path": str(
                    split_directory / "split_manifest.json"
                ),
            },
        },
    )
    return {
        "campaign": campaign_path,
        "merged": merged_path,
        "rule_audit": rule_audit_path,
        "split_manifest": (
            split_directory / "split_manifest.json"
        ),
    }


def build_realistic_report(
    tmp_path: Path,
) -> tuple[dict[str, Any], dict[str, Path], Path]:
    artifacts = create_accepted_artifacts(tmp_path)
    output_path = (
        tmp_path / "reports/experiments/p3-r0.json"
    )
    result = build_rule_based_baseline_report(
        campaign_result_path=artifacts["campaign"],
        output_path=output_path,
        schema_path=SCHEMA_PATH,
        expected_campaign_run_id=CAMPAIGN_RUN_ID,
        expected_dataset_sha256=sha256_file(
            artifacts["merged"]
        ),
    )
    return result, artifacts, output_path


def test_classification_metrics_use_frozen_class_order() -> None:
    records = [
        {
            "expected_fault_type": "no_fault",
            "predicted_fault_type": "no_fault",
        },
        {
            "expected_fault_type": "missing_static_route",
            "predicted_fault_type": "wrong_next_hop",
        },
        {
            "expected_fault_type": "wrong_next_hop",
            "predicted_fault_type": "wrong_next_hop",
        },
    ]

    metrics = compute_classification_metrics(
        records,
        DEFAULT_CLASS_ORDER,
    )

    assert metrics["accuracy"] == pytest.approx(2 / 3)
    assert metrics["confusion_matrix"]["values"] == [
        [1, 0, 0],
        [0, 0, 1],
        [0, 0, 1],
    ]
    assert metrics["per_class"][
        "missing_static_route"
    ]["precision"] == 0.0
    assert metrics["per_class"][
        "missing_static_route"
    ]["recall"] == 0.0
    assert metrics["per_class"][
        "wrong_next_hop"
    ]["f1"] == pytest.approx(2 / 3)
    assert metrics["zero_division_policy"] == 0.0


def test_builds_partition_aware_rule_baseline(
    tmp_path: Path,
) -> None:
    result, _, output_path = build_realistic_report(tmp_path)

    assert output_path.is_file()
    assert result["method"] == {
        "method_id": "rule_based",
        "family": "traditional",
        "implementation_id": (
            "deterministic_rule_engine_v1"
        ),
        "trained": False,
        "selection_statement": (
            "The rule engine predates the frozen P2 split; "
            "P3-R0 performs reporting only and changes no "
            "rule, threshold, feature, or prediction."
        ),
    }
    assert {
        name: (
            result["partitions"][name]["row_count"],
            result["partitions"][name]["group_count"],
        )
        for name in PARTITION_NAMES
    } == {
        "train": (18, 3),
        "validation": (6, 1),
        "test": (6, 1),
    }
    assert all(
        result["partitions"][name]["metrics"][
            "classification"
        ]["macro"]["f1"] == 1.0
        for name in PARTITION_NAMES
    )
    assert result["partitions"]["test"]["use"] == (
        "report_only"
    )
    assert result["overall"]["row_count"] == 30
    assert len(result["records"]) == 30
    assert result["provenance"][
        "artifact_reference_count"
    ] == 150
    assert all(
        len(record["artifacts"]) == 5
        for record in result["records"]
    )


def test_result_matches_formal_json_schema(
    tmp_path: Path,
) -> None:
    result, _, _ = build_realistic_report(tmp_path)
    schema = json.loads(
        SCHEMA_PATH.read_text(encoding="utf-8")
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(result)


def test_generic_contract_accepts_future_method_ids(
    tmp_path: Path,
) -> None:
    baseline, _, _ = build_realistic_report(tmp_path)

    for method_id, family, trained in (
        ("rule_based", "traditional", False),
        ("machine_learning", "machine_learning", True),
        ("hybrid", "hybrid", True),
    ):
        result = build_method_evaluation_result(
            result_id=f"result_{method_id}",
            method={
                "method_id": method_id,
                "family": family,
                "implementation_id": f"{method_id}_v1",
                "trained": trained,
                "selection_statement": "Synthetic contract test.",
            },
            dataset_binding=baseline["dataset_binding"],
            provenance=baseline["provenance"],
            records=baseline["records"],
            partition_group_ids={
                name: baseline["partitions"][name][
                    "group_ids"
                ]
                for name in PARTITION_NAMES
            },
            generated_at_utc=(
                "2026-08-05T08:00:00+00:00"
            ),
        )
        assert result["method"]["method_id"] == method_id
        assert result["evaluation_policy"][
            "primary_metric"
        ] == "macro_f1"


def test_rejects_test_partition_as_selection_input(
    tmp_path: Path,
) -> None:
    result, _, _ = build_realistic_report(tmp_path)
    changed = deepcopy(result)
    changed["evaluation_policy"][
        "selection_partitions"
    ].append("test")

    with pytest.raises(
        EvaluationReportingError,
        match="Only train and validation",
    ):
        validate_method_evaluation_result(changed)


def test_rejects_rule_audit_label_mismatch(
    tmp_path: Path,
) -> None:
    artifacts = create_accepted_artifacts(tmp_path)
    rule_audit = json.loads(
        artifacts["rule_audit"].read_text(
            encoding="utf-8"
        )
    )
    rule_audit["records"][0]["fault_type"] = (
        "wrong_next_hop"
    )
    write_json(artifacts["rule_audit"], rule_audit)

    with pytest.raises(
        EvaluationReportingError,
        match="Rule-audit label mismatch",
    ):
        build_rule_based_baseline_report(
            campaign_result_path=artifacts["campaign"],
            output_path=tmp_path / "report.json",
            schema_path=SCHEMA_PATH,
        )


def test_rejects_prediction_outside_frozen_class_set(
    tmp_path: Path,
) -> None:
    artifacts = create_accepted_artifacts(tmp_path)
    rule_audit = json.loads(
        artifacts["rule_audit"].read_text(
            encoding="utf-8"
        )
    )
    fault_record = next(
        record
        for record in rule_audit["records"]
        if record["fault_type"] != "no_fault"
    )
    evaluation_path = Path(fault_record["evaluation_path"])
    evaluation = json.loads(
        evaluation_path.read_text(encoding="utf-8")
    )
    evaluation["predicted"]["fault_type"] = (
        "interface_down"
    )
    write_json(evaluation_path, evaluation)

    with pytest.raises(
        EvaluationReportingError,
        match="Unsupported predicted class",
    ):
        build_rule_based_baseline_report(
            campaign_result_path=artifacts["campaign"],
            output_path=tmp_path / "report.json",
            schema_path=SCHEMA_PATH,
        )


def test_rejects_wrong_accepted_dataset_binding(
    tmp_path: Path,
) -> None:
    artifacts = create_accepted_artifacts(tmp_path)

    with pytest.raises(
        EvaluationReportingError,
        match="accepted binding",
    ):
        build_rule_based_baseline_report(
            campaign_result_path=artifacts["campaign"],
            output_path=tmp_path / "report.json",
            schema_path=SCHEMA_PATH,
            expected_dataset_sha256="0" * 64,
        )


def test_refuses_to_overwrite_existing_report(
    tmp_path: Path,
) -> None:
    _, artifacts, output_path = build_realistic_report(tmp_path)

    with pytest.raises(
        EvaluationReportingError,
        match="Output already exists",
    ):
        build_rule_based_baseline_report(
            campaign_result_path=artifacts["campaign"],
            output_path=output_path,
            schema_path=SCHEMA_PATH,
        )


def test_fault_only_prefix_metric_excludes_no_fault(
    tmp_path: Path,
) -> None:
    result, _, _ = build_realistic_report(tmp_path)

    for name, expected_support in (
        ("train", 12),
        ("validation", 4),
        ("test", 4),
    ):
        check = result["partitions"][name]["metrics"][
            "diagnostic_checks"
        ]["affected_prefix_fault_only"]
        assert check == {
            "applicable_count": expected_support,
            "correct_count": expected_support,
            "rate": 1.0,
        }
