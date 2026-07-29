import json
from pathlib import Path

import pytest

from src.dataset.contract import (
    DatasetContractError,
    build_dataset_row,
    to_tristate,
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


def create_experiment(
    root: Path,
    overrides: dict[str, object] | None = None,
) -> Path:
    experiment = root / "experiment-001"

    evidence = {
        "schema_version": 1,
        "topology_id": "TOP_01",
        "collected_at_utc": (
            "2026-07-28T12:00:00+00:00"
        ),
        "source_gateway_reachable": True,
        "destination_reachable": False,
        "route_to_destination_exists_on_r1": False,
        "route_next_hop_on_r1": None,
        "route_next_hop_reachable_from_r1": None,
        "transit_next_hop_reachable": True,
        "destination_reachable_from_r2": True,
    }

    evidence.update(overrides or {})

    documents = {
        "manifest.json": {
            "schema_version": 1,
            "experiment_id": "experiment-001",
            "scenario_id": (
                "C1_MISSING_STATIC_ROUTE"
            ),
            "current_state": "COMPLETED",
        },
        "parsed/evidence.json": evidence,
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


def test_builds_leakage_safe_c1_row(
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

    row = build_dataset_row(experiment)

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


def test_builds_c2_next_hop_features(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        {
            "route_to_destination_exists_on_r1": True,
            "route_next_hop_on_r1": (
                "10.10.12.254"
            ),
            "route_next_hop_reachable_from_r1": (
                False
            ),
        },
    )

    row = build_dataset_row(experiment)

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


def test_missing_probe_is_unavailable(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        {
            "destination_reachable_from_r2": None,
        },
    )

    row = build_dataset_row(experiment)

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


def test_rejects_invalid_evidence(
    tmp_path: Path,
) -> None:
    experiment = create_experiment(
        tmp_path,
        {"destination_reachable": "false"},
    )

    with pytest.raises(DatasetContractError):
        build_dataset_row(experiment)
