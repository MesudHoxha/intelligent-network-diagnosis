import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.dataset.contract import (
    DATASET_SCHEMA_VERSION,
    DatasetContractError,
    validate_dataset_row,
    validate_homogeneous_dataset_rows,
    write_dataset_row,
)
from src.dataset.contract_v3 import (
    FEATURE_NAMES_V3,
    DatasetRowV3ContractError,
    apply_missing_evidence_mask_v3,
    build_dataset_row_v3,
    validate_dataset_row_v3,
)
from tests.unit.test_p6_r1_evidence_v3 import valid_evidence_v3


COLLECTED_AT = "2026-08-06T08:00:00+00:00"


def valid_row_v3() -> dict[str, object]:
    features = {
        name: (
            "false" if name == "flow_blocked_by_policy" else "true"
        )
        for name in FEATURE_NAMES_V3
    }
    availability = {
        name: "observed" for name in FEATURE_NAMES_V3
    }
    return {
        "schema_version": 3,
        "sample_id": "experiment-p6-001",
        "metadata": {
            "experiment_id": "experiment-p6-001",
            "scenario_id": "N0_NORMAL_OPERATION_P6",
            "variant_id": "canonical",
            "split_group_id": (
                "CTX_P6_E01_TOP01_LINEAR_SOURCE_EDGE"
            ),
            "topology_id": "TOP_01",
            "direction": "hosta_to_hostb",
            "source_node": "hosta",
            "route_observer_node": "r1",
            "transit_node": "r2",
            "collected_at_utc": COLLECTED_AT,
        },
        "features": features,
        "labels": {
            "fault_category": None,
            "fault_type": "no_fault",
            "fault_location": None,
            "affected_prefix": None,
        },
        "quality": {
            "experiment_completed": True,
            "collector_completed": True,
            "baseline_before_valid": True,
            "baseline_after_valid": True,
            "unavailable_feature_count": 0,
            "structural_unavailable_count": 0,
            "collection_unavailable_count": 0,
            "masked_missing_count": 0,
        },
        "provenance": {
            "source_evidence_schema_version": 3,
            "source_evidence_sha256": "b" * 64,
            "feature_availability": availability,
            "mask_id": None,
        },
    }


def valid_row_v2() -> dict[str, object]:
    return {
        "schema_version": 2,
        "sample_id": "experiment-v2-001",
        "metadata": {
            "experiment_id": "experiment-v2-001",
            "scenario_id": "N0_NORMAL_OPERATION",
            "variant_id": "canonical",
            "split_group_id": "CTX_G01_TOP01_CANONICAL",
            "topology_id": "TOP_01",
            "direction": "hosta_to_hostb",
            "route_observer_node": "r1",
            "transit_node": "r2",
            "collected_at_utc": COLLECTED_AT,
        },
        "features": {
            "source_gateway_reachable": "true",
            "destination_reachable": "true",
            "route_to_destination_exists_on_observer": "true",
            "route_next_hop_present_on_observer": "true",
            "route_next_hop_reachable_from_observer": "true",
            "expected_next_hop_reachable_from_observer": "true",
            "destination_reachable_from_transit": "true",
        },
        "labels": {
            "fault_category": None,
            "fault_type": "no_fault",
            "fault_location": None,
            "affected_prefix": None,
        },
        "quality": {
            "experiment_completed": True,
            "collector_completed": True,
            "baseline_before_valid": True,
            "baseline_after_valid": True,
            "unavailable_feature_count": 0,
        },
    }


def nested(
    row: dict[str, object],
    field_name: str,
) -> dict[str, object]:
    value = row[field_name]
    assert isinstance(value, dict)
    return value


def write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def manifest_v2() -> dict[str, object]:
    return {
        "schema_version": 2,
        "experiment_id": "experiment-p6-001",
        "scenario_id": "N0_NORMAL_OPERATION_P6",
        "scenario_schema_version": 2,
        "scenario_kind": "normal",
        "topology_id": "TOP_01",
        "variant_id": "canonical",
        "split_group_id": "CTX_P6_E01_TOP01_LINEAR_SOURCE_EDGE",
        "diagnostic_method": "rule_based",
        "scenario_path": "scenarios/p6/N0_NORMAL_OPERATION_P6.yml",
        "experiment_directory": "data/raw/experiment-p6-001",
        "created_at_utc": COLLECTED_AT,
        "completed_at_utc": COLLECTED_AT,
        "current_state": "COMPLETED",
        "state_history": [
            {"state": "CREATED", "timestamp_utc": COLLECTED_AT},
            {"state": "COMPLETED", "timestamp_utc": COLLECTED_AT},
        ],
    }


def create_experiment(root: Path) -> Path:
    experiment = root / "experiment-p6-001"
    documents = {
        "manifest.json": manifest_v2(),
        "parsed/evidence.json": valid_evidence_v3(),
        "ground_truth.json": {
            "fault_category": None,
            "fault_type": "no_fault",
            "fault_location": None,
            "affected_prefix": None,
        },
        "collector_status.json": {
            "status": "COLLECTION_COMPLETED",
        },
        "validation/baseline_before.json": {"return_code": 0},
        "validation/baseline_after.json": {"return_code": 0},
    }
    for relative_path, document in documents.items():
        write_json(experiment / relative_path, document)
    return experiment


def test_runtime_default_remains_dataset_row_v2() -> None:
    assert DATASET_SCHEMA_VERSION == 2


def test_accepts_dataset_row_v3() -> None:
    validate_dataset_row_v3(valid_row_v3())
    validate_dataset_row(valid_row_v3())


def test_json_schema_accepts_dataset_row_v3() -> None:
    schema = json.loads(
        Path("schemas/dataset_row_v3.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(valid_row_v3())


def test_builds_clean_dataset_row_v3(tmp_path: Path) -> None:
    experiment = create_experiment(tmp_path)

    row = build_dataset_row_v3(experiment)

    assert row["schema_version"] == 3
    assert row["quality"]["unavailable_feature_count"] == 0
    assert row["provenance"]["mask_id"] is None
    assert len(row["provenance"]["source_evidence_sha256"]) == 64
    validate_dataset_row_v3(row)


def test_explicit_writer_emits_dataset_row_v3(tmp_path: Path) -> None:
    experiment = create_experiment(tmp_path)
    output = tmp_path / "row-v3.json"

    row = write_dataset_row(
        experiment,
        output,
        schema_version=3,
    )

    assert row["schema_version"] == 3
    assert json.loads(output.read_text(encoding="utf-8")) == row


def test_mask_preserves_source_binding_and_labels() -> None:
    row = valid_row_v3()
    source_hash = row["provenance"]["source_evidence_sha256"]
    labels = deepcopy(row["labels"])

    masked = apply_missing_evidence_mask_v3(
        row,
        "mask_route_family",
    )

    assert masked["provenance"]["source_evidence_sha256"] == source_hash
    assert masked["labels"] == labels
    assert masked["quality"]["masked_missing_count"] == 3
    assert masked["quality"]["unavailable_feature_count"] == 3
    assert row["quality"]["unavailable_feature_count"] == 0


def test_mask_preserves_structural_reason() -> None:
    row = valid_row_v3()
    features = nested(row, "features")
    provenance = nested(row, "provenance")
    availability = provenance["feature_availability"]
    assert isinstance(availability, dict)
    features["route_next_hop_matches_expected"] = "unavailable"
    availability["route_next_hop_matches_expected"] = (
        "structurally_unavailable"
    )
    quality = nested(row, "quality")
    quality["unavailable_feature_count"] = 1
    quality["structural_unavailable_count"] = 1
    validate_dataset_row_v3(row)

    masked = apply_missing_evidence_mask_v3(
        row,
        "mask_route_family",
    )

    masked_availability = masked["provenance"]["feature_availability"]
    assert (
        masked_availability["route_next_hop_matches_expected"]
        == "structurally_unavailable"
    )
    assert masked["quality"]["structural_unavailable_count"] == 1
    assert masked["quality"]["masked_missing_count"] == 2


def test_rejects_masked_missing_without_mask_id() -> None:
    row = valid_row_v3()
    nested(row, "features")["flow_blocked_by_policy"] = "unavailable"
    provenance = nested(row, "provenance")
    availability = provenance["feature_availability"]
    assert isinstance(availability, dict)
    availability["flow_blocked_by_policy"] = "masked_missing"
    quality = nested(row, "quality")
    quality["unavailable_feature_count"] = 1
    quality["masked_missing_count"] = 1

    with pytest.raises(
        DatasetRowV3ContractError,
        match="requires a non-null mask_id",
    ):
        validate_dataset_row_v3(row)


def test_rejects_partial_mask_family() -> None:
    row = valid_row_v3()
    nested(row, "features")[
        "route_to_destination_exists_on_observer"
    ] = "unavailable"
    provenance = nested(row, "provenance")
    provenance["mask_id"] = "mask_route_family"
    availability = provenance["feature_availability"]
    assert isinstance(availability, dict)
    availability["route_to_destination_exists_on_observer"] = (
        "masked_missing"
    )
    quality = nested(row, "quality")
    quality["unavailable_feature_count"] = 1
    quality["masked_missing_count"] = 1

    with pytest.raises(
        DatasetRowV3ContractError,
        match="must cover every observed feature",
    ):
        validate_dataset_row_v3(row)


def test_rejects_availability_count_drift() -> None:
    row = apply_missing_evidence_mask_v3(
        valid_row_v3(),
        "mask_policy_state",
    )
    nested(row, "quality")["masked_missing_count"] = 0

    with pytest.raises(
        DatasetRowV3ContractError,
        match="does not match provenance",
    ):
        validate_dataset_row_v3(row)


@pytest.mark.parametrize(
    "forbidden_name",
    [
        "fault_type",
        "scenario_id",
        "partition",
        "mask_id",
        "prediction",
        "metric",
        "explanation",
    ],
)
def test_rejects_predictor_leakage(forbidden_name: str) -> None:
    row = valid_row_v3()
    nested(row, "features")[forbidden_name] = "true"

    with pytest.raises(
        DatasetRowV3ContractError,
        match="version-3 whitelist",
    ):
        validate_dataset_row_v3(row)


def test_homogeneous_dispatch_accepts_v3_rows() -> None:
    version = validate_homogeneous_dataset_rows([
        valid_row_v3(),
        valid_row_v3(),
    ])

    assert version == 3


def test_homogeneous_dispatch_rejects_version_mixing() -> None:
    with pytest.raises(
        DatasetContractError,
        match="cannot mix row schema versions",
    ):
        validate_homogeneous_dataset_rows([
            valid_row_v2(),
            valid_row_v3(),
        ])


def test_generic_dispatch_rejects_unknown_version() -> None:
    row = deepcopy(valid_row_v3())
    row["schema_version"] = 4

    with pytest.raises(
        DatasetContractError,
        match="Unsupported dataset schema version",
    ):
        validate_dataset_row(row)
