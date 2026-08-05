from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from src.dataset.contract import FEATURE_NAMES
from src.dataset.splitter import (
    jsonl_payload,
    write_group_aware_split,
)
from src.ml.feature_matrix import (
    CLASS_ORDER,
    ENCODED_FEATURE_NAMES,
    RAW_FEATURE_NAMES,
    MLFeatureMatrixError,
    build_ml_feature_matrix,
    encode_tristate_features,
    frozen_protocol,
    sha256_file,
    sha256_text,
    validate_against_schema,
    validate_ml_feature_matrix,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas/ml_feature_matrix_v1.schema.json"
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
                value == "unavailable"
                for value in features.values()
            ),
        },
    }


def create_accepted_artifacts(root: Path) -> dict[str, Path]:
    rows = [
        make_row(group_slot, fault_type, repetition)
        for group_slot in GROUPS
        for fault_type in CLASS_ORDER
        for repetition in (1, 2)
    ]
    merged_path = root / "data/processed/accepted.jsonl"
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path.write_text(jsonl_payload(rows), encoding="utf-8")
    split_directory = root / "data/processed/accepted-split"
    split_manifest = write_group_aware_split(
        merged_path,
        split_directory,
        seed=20260730,
        expected_fault_types=CLASS_ORDER,
    )
    assert split_manifest["partitions"]["train"]["group_ids"] == sorted([
        GROUPS["G03"],
        GROUPS["G04"],
        GROUPS["G05"],
    ])
    assert split_manifest["partitions"]["validation"]["group_ids"] == [
        GROUPS["G01"]
    ]
    assert split_manifest["partitions"]["test"]["group_ids"] == [
        GROUPS["G02"]
    ]
    campaign_path = root / "data/metadata/campaign.json"
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
            "manifest_path": str(
                split_directory / "split_manifest.json"
            ),
        },
    })
    return {
        "campaign": campaign_path,
        "merged": merged_path,
        "split_manifest": split_directory / "split_manifest.json",
        "split_directory": split_directory,
    }


def build_realistic_matrix(
    tmp_path: Path,
    output_name: str = "matrix.json",
) -> tuple[dict[str, Any], dict[str, Path], Path]:
    artifacts = create_accepted_artifacts(tmp_path)
    output_path = tmp_path / "reports" / output_name
    result = build_ml_feature_matrix(
        campaign_result_path=artifacts["campaign"],
        output_path=output_path,
        schema_path=SCHEMA_PATH,
        expected_campaign_run_id=CAMPAIGN_RUN_ID,
        expected_dataset_sha256=sha256_file(artifacts["merged"]),
    )
    return result, artifacts, output_path


def test_tristate_pair_encoding_is_lossless_and_fixed() -> None:
    features = {name: "false" for name in RAW_FEATURE_NAMES}
    features[RAW_FEATURE_NAMES[0]] = "true"
    features[RAW_FEATURE_NAMES[1]] = "unavailable"

    vector = encode_tristate_features(features)

    assert vector[:6] == [1, 1, 0, 0, 1, 0]
    assert len(vector) == 14
    assert len(ENCODED_FEATURE_NAMES) == 14


def test_frozen_protocol_precommits_selection_without_test() -> None:
    protocol = frozen_protocol()

    assert protocol["partition_policy"] == {
        "fit_partition": "train",
        "selection_partition": "validation",
        "held_out_partition": "test",
        "test_use": "report_only_once_after_pipeline_freeze",
        "refit_on_train_plus_validation": False,
    }
    assert protocol["selection_policy"]["primary_metric"] == (
        "validation_macro_f1"
    )
    assert protocol["selection_policy"]["test_metrics_allowed"] is False
    assert len(protocol["candidate_models"]) == 6
    assert {
        candidate["family"]
        for candidate in protocol["candidate_models"]
    } == {"multinomial_logistic_regression", "decision_tree"}


def test_builds_complete_leakage_safe_matrix(tmp_path: Path) -> None:
    result, artifacts, output_path = build_realistic_matrix(tmp_path)

    assert result["row_count"] == 30
    assert result["raw_feature_count"] == 7
    assert result["encoded_feature_count"] == 14
    assert {
        name: result["partitions"][name]["row_count"]
        for name in ("train", "validation", "test")
    } == {"train": 18, "validation": 6, "test": 6}
    assert {
        name: result["partitions"][name]["group_count"]
        for name in ("train", "validation", "test")
    } == {"train": 3, "validation": 1, "test": 1}
    assert result["partitions"]["test"]["use"] == "report_only"
    assert result["leakage_audit"] == {
        "predictor_source": "features_only",
        "transformation_fit_required": False,
        "no_cross_partition_group": True,
        "test_used_for_fit": False,
        "test_used_for_selection": False,
        "unexpected_predictor_fields": [],
        "unavailable_value_count": 10,
    }
    assert result["dataset_binding"]["merged_dataset"]["sha256"] == (
        sha256_file(artifacts["merged"])
    )
    assert output_path.is_file()
    validate_ml_feature_matrix(result)
    validate_against_schema(result, SCHEMA_PATH)


def test_output_is_byte_deterministic(tmp_path: Path) -> None:
    artifacts = create_accepted_artifacts(tmp_path)
    outputs = [tmp_path / "one.json", tmp_path / "two.json"]

    for output in outputs:
        build_ml_feature_matrix(
            campaign_result_path=artifacts["campaign"],
            output_path=output,
            schema_path=SCHEMA_PATH,
            expected_campaign_run_id=CAMPAIGN_RUN_ID,
            expected_dataset_sha256=sha256_file(artifacts["merged"]),
        )

    assert outputs[0].read_bytes() == outputs[1].read_bytes()


def test_rejects_existing_output(tmp_path: Path) -> None:
    _, artifacts, output_path = build_realistic_matrix(tmp_path)

    with pytest.raises(MLFeatureMatrixError, match="already exists"):
        build_ml_feature_matrix(
            campaign_result_path=artifacts["campaign"],
            output_path=output_path,
            schema_path=SCHEMA_PATH,
            expected_campaign_run_id=CAMPAIGN_RUN_ID,
            expected_dataset_sha256=sha256_file(artifacts["merged"]),
        )


def test_rejects_merged_dataset_hash_drift(tmp_path: Path) -> None:
    artifacts = create_accepted_artifacts(tmp_path)
    expected_hash = sha256_file(artifacts["merged"])
    with artifacts["merged"].open("a", encoding="utf-8") as file:
        file.write("\n")

    with pytest.raises(MLFeatureMatrixError, match="hash does not match"):
        build_ml_feature_matrix(
            campaign_result_path=artifacts["campaign"],
            output_path=tmp_path / "matrix.json",
            schema_path=SCHEMA_PATH,
            expected_campaign_run_id=CAMPAIGN_RUN_ID,
            expected_dataset_sha256=expected_hash,
        )


def test_rejects_non_v2_partition_row(tmp_path: Path) -> None:
    artifacts = create_accepted_artifacts(tmp_path)
    train_path = artifacts["split_directory"] / "train.jsonl"
    lines = train_path.read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["schema_version"] = 1
    lines[0] = json.dumps(row, sort_keys=True, separators=(",", ":"))
    train_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = json.loads(
        artifacts["split_manifest"].read_text(encoding="utf-8")
    )
    manifest["outputs"]["train.jsonl"]["sha256"] = sha256_file(train_path)
    write_json(artifacts["split_manifest"], manifest)

    with pytest.raises(MLFeatureMatrixError, match="Dataset Row v2"):
        build_ml_feature_matrix(
            campaign_result_path=artifacts["campaign"],
            output_path=tmp_path / "matrix.json",
            schema_path=SCHEMA_PATH,
            expected_campaign_run_id=CAMPAIGN_RUN_ID,
            expected_dataset_sha256=sha256_file(artifacts["merged"]),
        )


def test_runtime_validator_rejects_test_selection_or_leakage(
    tmp_path: Path,
) -> None:
    result, _, _ = build_realistic_matrix(tmp_path)
    invalid_policy = copy.deepcopy(result)
    invalid_policy["protocol"]["partition_policy"][
        "selection_partition"
    ] = "test"
    with pytest.raises(MLFeatureMatrixError, match="frozen ML protocol"):
        validate_ml_feature_matrix(invalid_policy)

    invalid_record = copy.deepcopy(result)
    invalid_record["partitions"]["train"]["records"][0][
        "prediction"
    ] = "no_fault"
    with pytest.raises(MLFeatureMatrixError):
        validate_against_schema(invalid_record, SCHEMA_PATH)


def test_runtime_validator_rejects_invalid_encoding_pair(
    tmp_path: Path,
) -> None:
    result, _, _ = build_realistic_matrix(tmp_path)
    invalid = copy.deepcopy(result)
    invalid["partitions"]["train"]["records"][0][
        "feature_vector"
    ][:2] = [0, 1]

    with pytest.raises(MLFeatureMatrixError, match="invalid pair"):
        validate_ml_feature_matrix(invalid)


def test_schema_is_draft_2020_12_and_rejects_extra_fields() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False
    assert sha256_text("stable") == sha256_text("stable")
