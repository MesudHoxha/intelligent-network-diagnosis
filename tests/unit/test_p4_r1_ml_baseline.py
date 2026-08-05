from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import joblib
from jsonschema import Draft202012Validator

import src.ml.baseline as baseline
from src.dataset.contract import FEATURE_NAMES
from src.dataset.splitter import jsonl_payload, write_group_aware_split
from src.ml.baseline import (
    MLBaselineError,
    MODEL_FILE_NAME,
    REPORT_FILE_NAME,
    SELECTION_FILE_NAME,
    build_ml_baseline_report,
    build_prediction_document,
    candidate_sort_key,
    sha256_file,
    train_select_and_freeze,
    validate_frozen_pipeline,
    validate_ml_baseline_report,
    validate_selection_schema,
)
from src.ml.feature_matrix import CLASS_ORDER, build_ml_feature_matrix


ROOT = Path(__file__).resolve().parents[2]
MATRIX_SCHEMA = ROOT / "schemas/ml_feature_matrix_v1.schema.json"
SELECTION_SCHEMA = ROOT / "schemas/ml_pipeline_selection_v1.schema.json"
METHOD_SCHEMA = ROOT / "schemas/method_evaluation_result_v1.schema.json"
CAMPAIGN_RUN_ID = baseline.EXPECTED_CAMPAIGN_RUN_ID
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
    sample_id = f"sample-{group_slot.lower()}-{fault_type}-{repetition}"
    features = {name: "true" for name in FEATURE_NAMES}
    if fault_type == "missing_static_route":
        features.update({
            "destination_reachable": "false",
            "route_to_destination_exists_on_observer": "false",
            "route_next_hop_present_on_observer": "false",
            "route_next_hop_reachable_from_observer": "unavailable",
        })
    elif fault_type == "wrong_next_hop":
        features.update({
            "destination_reachable": "false",
            "route_next_hop_reachable_from_observer": "false",
        })
    normal = fault_type == "no_fault"
    return {
        "schema_version": 2,
        "sample_id": sample_id,
        "metadata": {
            "experiment_id": sample_id,
            "scenario_id": f"{fault_type}_{group_slot}",
            "variant_id": "canonical",
            "split_group_id": GROUPS[group_slot],
            "topology_id": f"TOP_{group_slot}",
            "direction": "hosta_to_hostb",
            "route_observer_node": "r1",
            "transit_node": "r2",
            "collected_at_utc": "2026-08-04T08:00:00+00:00",
        },
        "features": features,
        "labels": {
            "fault_category": None if normal else "routing",
            "fault_type": fault_type,
            "fault_location": None if normal else "r1",
            "affected_prefix": None if normal else "10.0.0.0/24",
        },
        "quality": {
            "experiment_completed": True,
            "collector_completed": True,
            "baseline_before_valid": True,
            "baseline_after_valid": True,
            "unavailable_feature_count": sum(
                value == "unavailable" for value in features.values()
            ),
        },
    }


def create_artifacts(tmp_path: Path) -> dict[str, Any]:
    rows = [
        make_row(group_slot, fault_type, repetition)
        for group_slot in GROUPS
        for fault_type in CLASS_ORDER
        for repetition in (1, 2)
    ]
    merged_path = tmp_path / "data/processed/accepted.jsonl"
    merged_path.parent.mkdir(parents=True)
    merged_path.write_text(jsonl_payload(rows), encoding="utf-8")
    split_directory = tmp_path / "data/processed/accepted-split"
    write_group_aware_split(
        merged_path,
        split_directory,
        seed=20260730,
        expected_fault_types=CLASS_ORDER,
    )
    campaign_path = tmp_path / "data/metadata/campaign.json"
    write_json(campaign_path, {
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
        "split": {
            "manifest_path": str(split_directory / "split_manifest.json"),
        },
    })
    matrix_path = tmp_path / "reports/matrix.json"
    build_ml_feature_matrix(
        campaign_result_path=campaign_path,
        output_path=matrix_path,
        schema_path=MATRIX_SCHEMA,
        expected_campaign_run_id=CAMPAIGN_RUN_ID,
        expected_dataset_sha256=sha256_file(merged_path),
    )
    experiments_root = tmp_path / "reports/experiments"
    for row in rows:
        sample_id = row["sample_id"]
        experiment = experiments_root / sample_id
        write_json(experiment / "manifest.json", {
            "schema_version": 2,
            "experiment_id": sample_id,
        })
        write_json(experiment / "ground_truth.json", {
            "fault_category": row["labels"]["fault_category"],
            "fault_type": row["labels"]["fault_type"],
            "fault_location": row["labels"]["fault_location"],
            "affected_prefix": row["labels"]["affected_prefix"],
        })
        write_json(experiment / "parsed/evidence.json", {
            "schema_version": 2,
            "experiment_id": sample_id,
            "features": row["features"],
        })
    return {
        "rows": rows,
        "merged": merged_path,
        "matrix": matrix_path,
        "matrix_sha256": sha256_file(matrix_path),
        "experiments_root": experiments_root,
    }


def freeze_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    artifacts = create_artifacts(tmp_path)
    monkeypatch.setattr(
        baseline,
        "EXPECTED_DATASET_SHA256",
        sha256_file(artifacts["merged"]),
    )
    pipeline_directory = tmp_path / "models/p4_r1_ml_pipeline_v1"
    selection = train_select_and_freeze(
        matrix_path=artifacts["matrix"],
        pipeline_directory=pipeline_directory,
        selection_schema_path=SELECTION_SCHEMA,
        expected_matrix_sha256=artifacts["matrix_sha256"],
    )
    artifacts.update({
        "pipeline_directory": pipeline_directory,
        "selection": selection,
        "selection_path": pipeline_directory / SELECTION_FILE_NAME,
        "model_path": pipeline_directory / MODEL_FILE_NAME,
    })
    artifacts["selection_sha256"] = sha256_file(artifacts["selection_path"])
    artifacts["model_sha256"] = sha256_file(artifacts["model_path"])
    return artifacts


def test_train_select_freezes_six_candidates_without_test(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = freeze_pipeline(tmp_path, monkeypatch)
    selection = artifacts["selection"]

    assert selection["status"] == "PIPELINE_FROZEN"
    assert len(selection["candidate_results"]) == 6
    assert selection["fit_summary"]["train"]["row_count"] == 18
    assert selection["fit_summary"]["validation"]["row_count"] == 6
    assert selection["model_artifact"]["refit_performed"] is False
    assert selection["leakage_audit"]["test_predictions_generated"] is False
    assert selection["leakage_audit"]["test_metrics_generated"] is False
    validate_selection_schema(selection, SELECTION_SCHEMA)


def test_selection_order_uses_all_frozen_tie_breakers() -> None:
    base = {
        "validation_metrics": {"macro_f1": 0.8, "accuracy": 0.8},
        "candidate": {
            "complexity_rank": 2,
            "candidate_id": "b",
        },
    }
    better_f1 = copy.deepcopy(base)
    better_f1["validation_metrics"]["macro_f1"] = 0.9
    better_accuracy = copy.deepcopy(base)
    better_accuracy["validation_metrics"]["accuracy"] = 0.9
    simpler = copy.deepcopy(base)
    simpler["candidate"]["complexity_rank"] = 1
    lexical = copy.deepcopy(base)
    lexical["candidate"]["candidate_id"] = "a"

    assert candidate_sort_key(better_f1) < candidate_sort_key(base)
    assert candidate_sort_key(better_accuracy) < candidate_sort_key(base)
    assert candidate_sort_key(simpler) < candidate_sort_key(base)
    assert candidate_sort_key(lexical) < candidate_sort_key(base)


def test_independent_ml_prediction_does_not_invent_localization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = freeze_pipeline(tmp_path, monkeypatch)
    bundle = joblib.load(artifacts["model_path"])
    matrix = json.loads(artifacts["matrix"].read_text())
    record = next(
        value
        for value in matrix["partitions"]["train"]["records"]
        if value["target_class"] == "missing_static_route"
    )
    prediction = build_prediction_document(
        sample_id=record["sample_id"],
        vector=record["feature_vector"],
        predicted_class="missing_static_route",
        estimator=bundle["estimator"],
        candidate_id=bundle["selected_candidate"]["candidate_id"],
        model_sha256=artifacts["model_sha256"],
    )

    assert prediction["diagnosis"]["fault_type"] == "missing_static_route"
    assert prediction["diagnosis"]["location"] is None
    assert prediction["diagnosis"]["affected_prefix"] is None
    assert len(prediction["supporting_evidence"]["observations"]) == 7


def test_selection_validator_rejects_test_access_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = freeze_pipeline(tmp_path, monkeypatch)
    selection = json.loads(artifacts["selection_path"].read_text())
    selection["leakage_audit"]["test_metrics_generated"] = True
    write_json(artifacts["selection_path"], selection)

    with pytest.raises(MLBaselineError, match="schema validation|leakage"):
        validate_frozen_pipeline(
            matrix_path=artifacts["matrix"],
            selection_path=artifacts["selection_path"],
            model_path=artifacts["model_path"],
            selection_schema_path=SELECTION_SCHEMA,
            expected_matrix_sha256=artifacts["matrix_sha256"],
        )


def test_selection_validator_rejects_model_hash_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = freeze_pipeline(tmp_path, monkeypatch)
    with artifacts["model_path"].open("ab") as file:
        file.write(b"drift")

    with pytest.raises(MLBaselineError, match="model hash"):
        validate_frozen_pipeline(
            matrix_path=artifacts["matrix"],
            selection_path=artifacts["selection_path"],
            model_path=artifacts["model_path"],
            selection_schema_path=SELECTION_SCHEMA,
            expected_matrix_sha256=artifacts["matrix_sha256"],
        )


def test_matrix_hash_drift_stops_before_pipeline_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = create_artifacts(tmp_path)
    monkeypatch.setattr(
        baseline,
        "EXPECTED_DATASET_SHA256",
        sha256_file(artifacts["merged"]),
    )
    pipeline_directory = tmp_path / "models/pipeline"

    with pytest.raises(MLBaselineError, match="SHA-256"):
        train_select_and_freeze(
            matrix_path=artifacts["matrix"],
            pipeline_directory=pipeline_directory,
            selection_schema_path=SELECTION_SCHEMA,
            expected_matrix_sha256="0" * 64,
        )
    assert not pipeline_directory.exists()


def test_report_is_opened_only_with_verified_freeze_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = freeze_pipeline(tmp_path, monkeypatch)
    report_directory = tmp_path / "reports/experiments/ml-report"

    with pytest.raises(MLBaselineError, match="Selection-result SHA-256"):
        build_ml_baseline_report(
            matrix_path=artifacts["matrix"],
            selection_path=artifacts["selection_path"],
            model_path=artifacts["model_path"],
            selection_schema_path=SELECTION_SCHEMA,
            method_schema_path=METHOD_SCHEMA,
            experiments_root=artifacts["experiments_root"],
            report_directory=report_directory,
            expected_matrix_sha256=artifacts["matrix_sha256"],
            expected_selection_sha256="0" * 64,
            expected_model_sha256=artifacts["model_sha256"],
        )
    assert not report_directory.exists()


def test_full_ml_report_has_comparable_metrics_and_explanations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = freeze_pipeline(tmp_path, monkeypatch)
    report_directory = tmp_path / "reports/experiments/p4_r1_ml_baseline_v1"
    result = build_ml_baseline_report(
        matrix_path=artifacts["matrix"],
        selection_path=artifacts["selection_path"],
        model_path=artifacts["model_path"],
        selection_schema_path=SELECTION_SCHEMA,
        method_schema_path=METHOD_SCHEMA,
        experiments_root=artifacts["experiments_root"],
        report_directory=report_directory,
        expected_matrix_sha256=artifacts["matrix_sha256"],
        expected_selection_sha256=artifacts["selection_sha256"],
        expected_model_sha256=artifacts["model_sha256"],
    )

    assert result["method"]["method_id"] == "machine_learning"
    assert result["partitions"]["test"]["use"] == "report_only"
    assert {
        name: result["partitions"][name]["row_count"]
        for name in ("train", "validation", "test")
    } == {"train": 18, "validation": 6, "test": 6}
    assert len(result["records"]) == 30
    assert result["provenance"]["artifact_reference_count"] == 150
    assert all(
        record["exact_match"] is False
        for record in result["records"]
        if record["expected_fault_type"] != "no_fault"
    )
    prediction_path = Path(result["records"][0]["artifacts"]["prediction"]["path"])
    prediction = json.loads(prediction_path.read_text())
    assert len(prediction["supporting_evidence"]["observations"]) == 7
    assert prediction["model_explanation"]["explanation_type"] in {
        "linear_feature_contributions",
        "decision_path",
    }

    verified = validate_ml_baseline_report(
        report_path=report_directory / REPORT_FILE_NAME,
        matrix_path=artifacts["matrix"],
        selection_path=artifacts["selection_path"],
        model_path=artifacts["model_path"],
        method_schema_path=METHOD_SCHEMA,
        expected_matrix_sha256=artifacts["matrix_sha256"],
        expected_selection_sha256=artifacts["selection_sha256"],
        expected_model_sha256=artifacts["model_sha256"],
    )
    assert verified["result_id"] == baseline.DEFAULT_RESULT_ID


def test_selection_schema_is_strict_draft_2020_12() -> None:
    schema = json.loads(SELECTION_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False


def test_existing_pipeline_and_report_outputs_are_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = freeze_pipeline(tmp_path, monkeypatch)
    with pytest.raises(MLBaselineError, match="already exists"):
        train_select_and_freeze(
            matrix_path=artifacts["matrix"],
            pipeline_directory=artifacts["pipeline_directory"],
            selection_schema_path=SELECTION_SCHEMA,
            expected_matrix_sha256=artifacts["matrix_sha256"],
        )

    report_directory = tmp_path / "reports/experiments/existing"
    report_directory.mkdir(parents=True)
    with pytest.raises(MLBaselineError, match="already exists"):
        build_ml_baseline_report(
            matrix_path=artifacts["matrix"],
            selection_path=artifacts["selection_path"],
            model_path=artifacts["model_path"],
            selection_schema_path=SELECTION_SCHEMA,
            method_schema_path=METHOD_SCHEMA,
            experiments_root=artifacts["experiments_root"],
            report_directory=report_directory,
            expected_matrix_sha256=artifacts["matrix_sha256"],
            expected_selection_sha256=artifacts["selection_sha256"],
            expected_model_sha256=artifacts["model_sha256"],
        )
