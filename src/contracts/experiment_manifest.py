from __future__ import annotations

from datetime import datetime
from typing import Any


EXPERIMENT_MANIFEST_SCHEMA_VERSION = 2

VALID_SCENARIO_KINDS = {
    "fault",
    "normal",
}

VALID_STATES = {
    "CREATED",
    "BASELINE_VALIDATED",
    "FAULT_CONFIRMED",
    "NORMAL_CONFIRMED",
    "EVIDENCE_COLLECTED",
    "DIAGNOSIS_PRODUCED",
    "EVALUATED",
    "FAULT_RESTORED",
    "BASELINE_RESTORED",
    "POST_RUN_VALIDATED",
    "FAILED",
    "COMPLETED",
}

REQUIRED_FIELDS = {
    "schema_version",
    "experiment_id",
    "scenario_id",
    "scenario_schema_version",
    "scenario_kind",
    "topology_id",
    "variant_id",
    "split_group_id",
    "diagnostic_method",
    "scenario_path",
    "experiment_directory",
    "created_at_utc",
    "current_state",
    "state_history",
}

OPTIONAL_FIELDS = {
    "completed_at_utc",
    "error",
}


class ExperimentManifestContractError(ValueError):
    """Raised when a manifest violates the v2 contract."""


def validate_timestamp(
    value: object,
    field_name: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise ExperimentManifestContractError(
            f"{field_name} must be a non-empty timestamp string."
        )

    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise ExperimentManifestContractError(
            f"{field_name} must be an ISO-8601 timestamp."
        ) from error

    if timestamp.tzinfo is None:
        raise ExperimentManifestContractError(
            f"{field_name} must contain timezone information."
        )


def validate_experiment_manifest(
    manifest: dict[str, Any],
) -> None:
    if not isinstance(manifest, dict):
        raise ExperimentManifestContractError(
            "Experiment manifest must be an object."
        )

    missing = REQUIRED_FIELDS - set(manifest)
    unexpected = (
        set(manifest)
        - REQUIRED_FIELDS
        - OPTIONAL_FIELDS
    )

    if missing:
        raise ExperimentManifestContractError(
            "Missing manifest fields: "
            + ", ".join(sorted(missing))
        )

    if unexpected:
        raise ExperimentManifestContractError(
            "Unexpected manifest fields: "
            + ", ".join(sorted(unexpected))
        )

    if (
        manifest["schema_version"]
        != EXPERIMENT_MANIFEST_SCHEMA_VERSION
    ):
        raise ExperimentManifestContractError(
            "Unsupported experiment manifest schema version."
        )

    scenario_schema_version = manifest[
        "scenario_schema_version"
    ]

    if (
        isinstance(scenario_schema_version, bool)
        or not isinstance(scenario_schema_version, int)
        or scenario_schema_version < 1
    ):
        raise ExperimentManifestContractError(
            "scenario_schema_version must be "
            "a positive integer."
        )

    string_fields = (
        "experiment_id",
        "scenario_id",
        "topology_id",
        "variant_id",
        "split_group_id",
        "diagnostic_method",
        "scenario_path",
        "experiment_directory",
        "current_state",
    )

    for field_name in string_fields:
        value = manifest[field_name]

        if not isinstance(value, str) or not value:
            raise ExperimentManifestContractError(
                f"{field_name} must be a non-empty string."
            )

    if (
        manifest["scenario_kind"]
        not in VALID_SCENARIO_KINDS
    ):
        raise ExperimentManifestContractError(
            "scenario_kind must be 'fault' or 'normal'."
        )

    if manifest["current_state"] not in VALID_STATES:
        raise ExperimentManifestContractError(
            "Manifest current_state is not supported."
        )

    validate_timestamp(
        manifest["created_at_utc"],
        "created_at_utc",
    )

    history = manifest["state_history"]

    if not isinstance(history, list) or not history:
        raise ExperimentManifestContractError(
            "state_history must be a non-empty array."
        )

    for index, entry in enumerate(history):
        if (
            not isinstance(entry, dict)
            or set(entry) != {
                "state",
                "timestamp_utc",
            }
        ):
            raise ExperimentManifestContractError(
                "Every state_history entry must contain "
                "only state and timestamp_utc."
            )

        if entry["state"] not in VALID_STATES:
            raise ExperimentManifestContractError(
                f"Unsupported state at history index {index}."
            )

        validate_timestamp(
            entry["timestamp_utc"],
            f"state_history[{index}].timestamp_utc",
        )

    if (
        history[-1]["state"]
        != manifest["current_state"]
    ):
        raise ExperimentManifestContractError(
            "current_state must equal the final "
            "state_history entry."
        )

    if manifest["current_state"] == "COMPLETED":
        if "completed_at_utc" not in manifest:
            raise ExperimentManifestContractError(
                "Completed manifests require completed_at_utc."
            )

        validate_timestamp(
            manifest["completed_at_utc"],
            "completed_at_utc",
        )

    if manifest["current_state"] == "FAILED":
        error = manifest.get("error")

        if (
            not isinstance(error, dict)
            or set(error) != {"type", "message"}
            or not isinstance(error["type"], str)
            or not error["type"]
            or not isinstance(error["message"], str)
        ):
            raise ExperimentManifestContractError(
                "Failed manifests require an error object "
                "with type and message."
            )
