from copy import deepcopy

import pytest

from src.contracts.experiment_manifest import (
    ExperimentManifestContractError,
    validate_experiment_manifest,
)


def completed_manifest() -> dict[str, object]:
    return {
        "schema_version": 2,
        "experiment_id": "experiment-001",
        "scenario_id": "C1_MISSING_STATIC_ROUTE",
        "scenario_schema_version": 1,
        "scenario_kind": "fault",
        "topology_id": "TOP_01",
        "variant_id": "canonical",
        "split_group_id": (
            "TOP_01:C1_MISSING_STATIC_ROUTE:canonical"
        ),
        "diagnostic_method": "rule_based",
        "scenario_path": "scenario.yml",
        "experiment_directory": "data/raw/experiment-001",
        "created_at_utc": (
            "2026-07-28T12:00:00+00:00"
        ),
        "current_state": "COMPLETED",
        "state_history": [
            {
                "state": "CREATED",
                "timestamp_utc": (
                    "2026-07-28T12:00:00+00:00"
                ),
            },
            {
                "state": "COMPLETED",
                "timestamp_utc": (
                    "2026-07-28T12:01:00+00:00"
                ),
            },
        ],
        "completed_at_utc": (
            "2026-07-28T12:01:00+00:00"
        ),
    }


def test_accepts_completed_manifest_v2() -> None:
    validate_experiment_manifest(
        completed_manifest()
    )


def test_rejects_state_history_mismatch() -> None:
    manifest = deepcopy(completed_manifest())
    manifest["current_state"] = "EVALUATED"

    with pytest.raises(
        ExperimentManifestContractError
    ):
        validate_experiment_manifest(manifest)


def test_completed_manifest_requires_timestamp() -> None:
    manifest = deepcopy(completed_manifest())
    del manifest["completed_at_utc"]

    with pytest.raises(
        ExperimentManifestContractError
    ):
        validate_experiment_manifest(manifest)
