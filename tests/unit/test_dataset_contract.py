import json
from pathlib import Path

import pytest

from src.dataset.contract import (
    DatasetContractError,
    build_dataset_row,
    build_dataset_row_v1,
    build_dataset_row_v2,
    migrate_dataset_row_v1_to_v2,
    to_tristate,
    validate_dataset_row,
    validate_dataset_row_v1,
    validate_dataset_row_v2,
    write_dataset_row,
)


COLLECTED_AT_UTC = (
    "2026-07-30T12:00:00+00:00"
)


def write_json(
    path: Path,
    document: object,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(document),
        encoding="utf-8",
    )


def legacy_evidence(
    **overrides: object,
) -> dict[str, object]:
    evidence: dict[str, object] = {
        "schema_version": 1,
        "topology_id": "TOP_01",
        "collected_at_utc": COLLECTED_AT_UTC,
        "source_gateway_reachable": True,
        "destination_reachable": False,
        "route_to_destination_exists_on_r1": False,
        "route_next_hop_on_r1": None,
        "route_next_hop_reachable_from_r1": None,
        "transit_next_hop_reachable": True,
        "destination_reachable_from_r2": True,
    }
    evidence.update(overrides)
    return evidence


def role_neutral_evidence(
    **overrides: object,
) -> dict[str, object]:
    evidence: dict[str, object] = {
        "schema_version": 2,
        "topology_id": "TOP_01",
        "collected_at_utc": COLLECTED_AT_UTC,
        "direction": "hosta_to_hostb",
        "route_observer_node": "r1",
        "transit_node": "r2",
        "destination_address": "10.10.2.10",
        "destination_prefix": "10.10.2.0/24",
        "source_gateway_reachable": True,
        "destination_reachable": False,
        (
            "route_to_destination_exists_on_observer"
        ): False,
        "route_next_hop_on_observer": None,
        (
            "route_next_hop_reachable_from_observer"
        ): None,
        (
            "expected_next_hop_reachable_from_observer"
        ): True,
        "destination_reachable_from_transit": True,
    }
    evidence.update(overrides)
    return evidence


def manifest_v2(
    *,
    topology_id: str = "TOP_01",
    scenario_id: str = (
        "C1_MISSING_STATIC_ROUTE"
    ),
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "experiment_id": "experiment-001",
        "scenario_id": scenario_id,
        "scenario_schema_version": 1,
        "scenario_kind": "fault",
        "topology_id": topology_id,
        "variant_id": "canonical",
        "split_group_id": (
            f"{topology_id}:"
            "C1_MISSING_STATIC_ROUTE:"
            "canonical"
        ),
        "diagnostic_method": "rule_based",
        "scenario_path": (
            "scenarios/routing/"
            "C1_MISSING_STATIC_ROUTE.yml"
        ),
        "experiment_directory": (
            "data/raw/experiment-001"
        ),
        "created_at_utc": COLLECTED_AT_UTC,
        "completed_at_utc": COLLECTED_AT_UTC,
        "current_state": "COMPLETED",
        "state_history": [
            {
                "state": "CREATED",
                "timestamp_utc": (
                    COLLECTED_AT_UTC
                ),
            },
            {
                "state": "COMPLETED",
                "timestamp_utc": (
                    COLLECTED_AT_UTC
                ),
            },
        ],
    }


def create_experiment(
    root: Path,
    *,
    evidence: dict[str, object] | None = None,
    manifest: dict[str, object] | None = None,
) -> Path:
    experiment = root / "experiment-001"

    documents = {
        "manifest.json": (
            manifest
            if manifest is not None
            else {
                "schema_version": 1,
                "experiment_id": "experiment-001",
                "scenario_id": (
                    "C1_MISSING_STATIC_ROUTE"
                ),
                "current_state": "COMPLETED",
            }
        ),
        "parsed/evidence.json": (
            evidence
            if evidence is not None
            else legacy_evidence()
        ),
        "ground_truth.json": {
            "fault_category": "routing",
            "fault_type": "missing_static_route",
            "fault_location": "r1",
            "affected_prefix": "10.10.2.0/24",
        },
        "collector_status.json": {
            "status": "COLLECTION_COMPLETED",
        },
        "validation/baseline_before.json": {
            "return_code": 0,
        },
        "validation/baseline_after.json": {
            "return_code": 0,
        },
    }

    for relative_path, document in documents.items():
        write_json(
            experiment / relative_path,
            document,
        )

    return experiment


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, "true"),
        (False, "false"),
        (None, "unavailable"),
    ],
)
def test_to_tristate(
    value: bool | None,
    expected: str,
) -> None:
    assert to_tristate(value) == expected


def test_rejects_non_boolean_tristate() -> None:
    with pytest.raises(DatasetContractError):
        to_tristate(1)


def test_builds_leakage_safe_v1_row(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(tmp_path)

    write_json(
        experiment
        / "diagnosis"
        / "rule_based.json",
        {"fault_type": "poisoned_prediction"},
    )
    write_json(
        experiment
        / "evaluation"
        / "rule_based.json",
        {"exact_match": False},
    )
    write_json(
        experiment / "injection_record.json",
        {"wrong_next_hop": "poisoned_value"},
    )

    row = build_dataset_row_v1(experiment)

    assert row["features"] == {
        "source_gateway_reachable": "true",
        "destination_reachable": "false",
        "route_to_destination_exists_on_r1": "false",
        "route_next_hop_present_on_r1": "false",
        "route_next_hop_reachable_from_r1": (
            "unavailable"
        ),
        "transit_next_hop_reachable": "true",
        "destination_reachable_from_r2": "true",
    }
    assert row["schema_version"] == 1
    assert (
        row["labels"]["fault_type"]
        == "missing_static_route"
    )
    assert (
        row["quality"][
            "unavailable_feature_count"
        ]
        == 1
    )

    serialized = json.dumps(row)

    assert "poisoned" not in serialized
    assert "matched_rules" not in serialized
    assert "exact_match" not in serialized
    assert (
        "route_next_hop_on_r1"
        not in row["features"]
    )


def test_v1_builds_c2_next_hop_features(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        evidence=legacy_evidence(
            route_to_destination_exists_on_r1=True,
            route_next_hop_on_r1=(
                "10.10.12.254"
            ),
            route_next_hop_reachable_from_r1=(
                False
            ),
        ),
    )

    row = build_dataset_row_v1(experiment)

    assert (
        row["features"][
            "route_next_hop_present_on_r1"
        ]
        == "true"
    )
    assert (
        row["features"][
            "route_next_hop_reachable_from_r1"
        ]
        == "false"
    )
    assert (
        "10.10.12.254"
        not in json.dumps(row["features"])
    )


def test_v1_missing_probe_is_unavailable(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        evidence=legacy_evidence(
            destination_reachable_from_r2=None,
        ),
    )

    row = build_dataset_row_v1(experiment)

    assert (
        row["features"][
            "destination_reachable_from_r2"
        ]
        == "unavailable"
    )
    assert (
        row["quality"][
            "unavailable_feature_count"
        ]
        == 2
    )


def test_v1_rejects_invalid_evidence(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        evidence=legacy_evidence(
            destination_reachable="false",
        ),
    )

    with pytest.raises(DatasetContractError):
        build_dataset_row_v1(experiment)


def test_v1_adapts_role_neutral_top01_evidence(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        evidence=role_neutral_evidence(),
    )

    row = build_dataset_row_v1(experiment)

    assert row["schema_version"] == 1
    assert row["metadata"]["topology_id"] == "TOP_01"
    assert row["features"] == {
        "source_gateway_reachable": "true",
        "destination_reachable": "false",
        "route_to_destination_exists_on_r1": "false",
        "route_next_hop_present_on_r1": "false",
        "route_next_hop_reachable_from_r1": (
            "unavailable"
        ),
        "transit_next_hop_reachable": "true",
        "destination_reachable_from_r2": "true",
    }


@pytest.mark.parametrize(
    "overrides",
    [
        {
            "topology_id": "TOP_02",
            "route_observer_node": "edge1",
            "transit_node": "core1",
            "destination_address": "10.20.2.10",
            "destination_prefix": "10.20.2.0/24",
        },
        {
            "direction": "hostb_to_hosta",
            "route_observer_node": "r2",
            "transit_node": "r1",
        },
    ],
)
def test_v1_rejects_nonlegacy_role_binding(
    tmp_path: Path,
    overrides: dict[str, object],
) -> None:
    experiment = create_experiment(
        tmp_path,
        evidence=role_neutral_evidence(
            **overrides
        ),
    )

    with pytest.raises(
        DatasetContractError,
        match="Use Dataset Row v2",
    ):
        build_dataset_row_v1(experiment)


def test_v2_builds_role_neutral_top02_row(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        manifest=manifest_v2(
            topology_id="TOP_02"
        ),
        evidence=role_neutral_evidence(
            topology_id="TOP_02",
            direction="client_to_server",
            route_observer_node="edge1",
            transit_node="core1",
            destination_address="10.20.2.10",
            destination_prefix="10.20.2.0/24",
        ),
    )

    row = build_dataset_row_v2(experiment)

    assert row["schema_version"] == 2
    assert row["metadata"][
        "route_observer_node"
    ] == "edge1"
    assert row["metadata"]["transit_node"] == "core1"
    assert row["features"] == {
        "source_gateway_reachable": "true",
        "destination_reachable": "false",
        (
            "route_to_destination_exists_on_observer"
        ): "false",
        (
            "route_next_hop_present_on_observer"
        ): "false",
        (
            "route_next_hop_reachable_from_observer"
        ): "unavailable",
        (
            "expected_next_hop_reachable_from_observer"
        ): "true",
        (
            "destination_reachable_from_transit"
        ): "true",
    }

    serialized_features = json.dumps(
        row["features"]
    )

    assert "edge1" not in serialized_features
    assert "core1" not in serialized_features
    assert "10.20.2.10" not in serialized_features
    assert "_r1" not in serialized_features
    assert "_r2" not in serialized_features


def test_canonical_builder_defaults_to_v2(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        manifest=manifest_v2(),
        evidence=role_neutral_evidence(),
    )

    row = build_dataset_row(experiment)

    assert row["schema_version"] == 2
    validate_dataset_row(row)


def test_v2_rejects_evidence_v1(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        manifest=manifest_v2(),
        evidence=legacy_evidence(),
    )

    with pytest.raises(
        DatasetContractError,
        match="Invalid Evidence v2",
    ):
        build_dataset_row_v2(experiment)


def test_v2_rejects_manifest_evidence_topology_mismatch(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        manifest=manifest_v2(
            topology_id="TOP_01"
        ),
        evidence=role_neutral_evidence(
            topology_id="TOP_02",
        ),
    )

    with pytest.raises(
        DatasetContractError,
        match="topology_id must match",
    ):
        build_dataset_row_v2(experiment)


def test_explicit_v1_to_v2_migration(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(tmp_path)
    legacy_row = build_dataset_row_v1(
        experiment
    )

    migrated = migrate_dataset_row_v1_to_v2(
        legacy_row,
        direction="hosta_to_hostb",
        route_observer_node="r1",
        transit_node="r2",
    )

    assert migrated["schema_version"] == 2
    assert (
        migrated["sample_id"]
        == legacy_row["sample_id"]
    )
    assert (
        migrated["metadata"]["split_group_id"]
        == legacy_row["metadata"][
            "split_group_id"
        ]
    )
    assert migrated["labels"] == legacy_row["labels"]
    assert migrated["quality"] == legacy_row["quality"]
    assert (
        migrated["features"][
            "route_to_destination_exists_on_observer"
        ]
        == legacy_row["features"][
            "route_to_destination_exists_on_r1"
        ]
    )

    validate_dataset_row_v2(migrated)


def test_v1_migration_rejects_unproven_context(
    tmp_path: Path,
) -> None:
    legacy_row = build_dataset_row_v1(
        create_experiment(tmp_path)
    )

    with pytest.raises(
        DatasetContractError,
        match="historical TOP_01",
    ):
        migrate_dataset_row_v1_to_v2(
            legacy_row,
            direction="client_to_server",
            route_observer_node="edge1",
            transit_node="core1",
        )


def test_versioned_validators_reject_wrong_contract(
    tmp_path: Path,
) -> None:
    legacy_row = build_dataset_row_v1(
        create_experiment(tmp_path)
    )

    validate_dataset_row_v1(legacy_row)
    validate_dataset_row(legacy_row)

    with pytest.raises(DatasetContractError):
        validate_dataset_row_v2(legacy_row)


def test_v2_validator_checks_unavailable_count(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        manifest=manifest_v2(),
        evidence=role_neutral_evidence(),
    )
    row = build_dataset_row_v2(experiment)
    row["quality"][
        "unavailable_feature_count"
    ] = 0

    with pytest.raises(
        DatasetContractError,
        match="does not match features",
    ):
        validate_dataset_row_v2(row)


def test_write_dataset_row_supports_explicit_v1(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        evidence=role_neutral_evidence(),
    )
    output_path = tmp_path / "row.json"

    row = write_dataset_row(
        experiment,
        output_path,
        schema_version=1,
    )

    assert row["schema_version"] == 1
    assert json.loads(
        output_path.read_text(encoding="utf-8")
    ) == row
