from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.contracts.evidence import EvidenceContractError
from src.contracts.evidence_v3 import (
    EVIDENCE_V3_FEATURE_NAMES,
    validate_evidence_v3,
)
from src.contracts.experiment_manifest import (
    ExperimentManifestContractError,
    validate_experiment_manifest,
)
from src.contracts.observation_profile import (
    DIRECTION_PATTERN,
    IDENTIFIER_PATTERN,
)


DATASET_ROW_V3_SCHEMA_VERSION = 3
FEATURE_NAMES_V3 = EVIDENCE_V3_FEATURE_NAMES
TRISTATE_VALUES = {"true", "false", "unavailable"}
AVAILABILITY_STATES_V3 = {
    "observed",
    "structurally_unavailable",
    "collection_unavailable",
    "masked_missing",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

DATASET_V3_SECTIONS = {
    "schema_version",
    "sample_id",
    "metadata",
    "features",
    "labels",
    "quality",
    "provenance",
}

METADATA_FIELDS_V3 = {
    "experiment_id",
    "scenario_id",
    "variant_id",
    "split_group_id",
    "topology_id",
    "direction",
    "source_node",
    "route_observer_node",
    "transit_node",
    "collected_at_utc",
}

LABEL_FIELDS = {
    "fault_category",
    "fault_type",
    "fault_location",
    "affected_prefix",
}

QUALITY_FIELDS_V3 = {
    "experiment_completed",
    "collector_completed",
    "baseline_before_valid",
    "baseline_after_valid",
    "unavailable_feature_count",
    "structural_unavailable_count",
    "collection_unavailable_count",
    "masked_missing_count",
}

PROVENANCE_FIELDS_V3 = {
    "source_evidence_schema_version",
    "source_evidence_sha256",
    "feature_availability",
    "mask_id",
}

MISSING_EVIDENCE_MASKS_V1 = {
    "mask_source_gateway_family": (
        "source_expected_gateway_reachable",
        "source_default_gateway_matches_expected",
    ),
    "mask_route_family": (
        "route_to_destination_exists_on_observer",
        "route_next_hop_matches_expected",
        "route_next_hop_reachable_from_observer",
    ),
    "mask_interface_state": (
        "observer_egress_interface_oper_up",
    ),
    "mask_policy_state": (
        "flow_blocked_by_policy",
    ),
}

FORBIDDEN_PREDICTOR_NAMES = {
    "fault_type",
    "fault_category",
    "ground_truth",
    "scenario_id",
    "topology_id",
    "split_group_id",
    "partition",
    "mask_id",
    "prediction",
    "metric",
    "explanation",
}


class DatasetRowV3ContractError(ValueError):
    """Raised when Dataset Row v3 is structurally invalid."""


def _require_string(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise DatasetRowV3ContractError(
            f"{field_name} must be a non-empty string."
        )


def _validate_utc_timestamp(value: object) -> None:
    _require_string(value, "metadata.collected_at_utc")
    assert isinstance(value, str)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise DatasetRowV3ContractError(
            "metadata.collected_at_utc must be ISO-8601."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise DatasetRowV3ContractError(
            "metadata.collected_at_utc must include the UTC offset."
        )


def _validate_metadata(row: dict[str, Any]) -> None:
    metadata = row["metadata"]
    if not isinstance(metadata, dict) or set(metadata) != METADATA_FIELDS_V3:
        raise DatasetRowV3ContractError(
            "Metadata does not match Dataset Row v3."
        )
    for field_name in (
        "experiment_id",
        "scenario_id",
        "variant_id",
        "split_group_id",
        "topology_id",
        "direction",
        "source_node",
        "route_observer_node",
        "transit_node",
    ):
        _require_string(metadata[field_name], f"metadata.{field_name}")
    if row["sample_id"] != metadata["experiment_id"]:
        raise DatasetRowV3ContractError(
            "sample_id must equal metadata.experiment_id."
        )
    if not IDENTIFIER_PATTERN.fullmatch(metadata["topology_id"]):
        raise DatasetRowV3ContractError(
            "metadata.topology_id must be an identifier."
        )
    if not DIRECTION_PATTERN.fullmatch(metadata["direction"]):
        raise DatasetRowV3ContractError(
            "metadata.direction must use the "
            "'source_to_destination' format."
        )
    for field_name in (
        "source_node",
        "route_observer_node",
        "transit_node",
    ):
        if not IDENTIFIER_PATTERN.fullmatch(metadata[field_name]):
            raise DatasetRowV3ContractError(
                f"metadata.{field_name} must be an identifier."
            )
    if len({
        metadata["source_node"],
        metadata["route_observer_node"],
        metadata["transit_node"],
    }) != 3:
        raise DatasetRowV3ContractError(
            "Dataset Row v3 observation roles must be different."
        )
    _validate_utc_timestamp(metadata["collected_at_utc"])


def _validate_labels(labels: object) -> None:
    if not isinstance(labels, dict) or set(labels) != LABEL_FIELDS:
        raise DatasetRowV3ContractError(
            "Labels do not match Dataset Row v3."
        )
    _require_string(labels["fault_type"], "labels.fault_type")
    for field_name in (
        "fault_category",
        "fault_location",
        "affected_prefix",
    ):
        value = labels[field_name]
        if value is not None:
            _require_string(value, f"labels.{field_name}")


def _availability_counts(
    availability: dict[str, str],
) -> dict[str, int]:
    return {
        "structural_unavailable_count": sum(
            state == "structurally_unavailable"
            for state in availability.values()
        ),
        "collection_unavailable_count": sum(
            state == "collection_unavailable"
            for state in availability.values()
        ),
        "masked_missing_count": sum(
            state == "masked_missing"
            for state in availability.values()
        ),
    }


def _validate_provenance_and_quality(row: dict[str, Any]) -> None:
    provenance = row["provenance"]
    quality = row["quality"]
    features = row["features"]
    if (
        not isinstance(provenance, dict)
        or set(provenance) != PROVENANCE_FIELDS_V3
    ):
        raise DatasetRowV3ContractError(
            "Provenance does not match Dataset Row v3."
        )
    if provenance["source_evidence_schema_version"] != 3:
        raise DatasetRowV3ContractError(
            "Dataset Row v3 must bind to Evidence v3."
        )
    source_hash = provenance["source_evidence_sha256"]
    if (
        not isinstance(source_hash, str)
        or not SHA256_PATTERN.fullmatch(source_hash)
    ):
        raise DatasetRowV3ContractError(
            "provenance.source_evidence_sha256 must be a lowercase "
            "SHA-256 digest."
        )
    availability = provenance["feature_availability"]
    if (
        not isinstance(availability, dict)
        or set(availability) != set(FEATURE_NAMES_V3)
    ):
        raise DatasetRowV3ContractError(
            "feature_availability must match the frozen ten-feature "
            "whitelist."
        )

    for feature_name in FEATURE_NAMES_V3:
        state = availability[feature_name]
        value = features[feature_name]
        if state not in AVAILABILITY_STATES_V3:
            raise DatasetRowV3ContractError(
                f"feature_availability.{feature_name} is invalid."
            )
        if state == "observed":
            if value not in {"true", "false"}:
                raise DatasetRowV3ContractError(
                    f"features.{feature_name} must be true or false "
                    "when observed."
                )
        elif value != "unavailable":
            raise DatasetRowV3ContractError(
                f"features.{feature_name} must be unavailable when "
                f"its state is {state}."
            )

    mask_id = provenance["mask_id"]
    masked_features = {
        name
        for name, state in availability.items()
        if state == "masked_missing"
    }
    if mask_id is None:
        if masked_features:
            raise DatasetRowV3ContractError(
                "masked_missing requires a non-null mask_id."
            )
    else:
        if mask_id not in MISSING_EVIDENCE_MASKS_V1:
            raise DatasetRowV3ContractError(
                "provenance.mask_id is not a frozen P6 mask."
            )
        allowed = set(MISSING_EVIDENCE_MASKS_V1[mask_id])
        if not masked_features or not masked_features <= allowed:
            raise DatasetRowV3ContractError(
                "masked_missing features do not match provenance.mask_id."
            )
        still_observed = {
            name
            for name in allowed
            if availability[name] == "observed"
        }
        if still_observed:
            raise DatasetRowV3ContractError(
                "A frozen missing-evidence mask must cover every "
                "observed feature in its family."
            )

    if not isinstance(quality, dict) or set(quality) != QUALITY_FIELDS_V3:
        raise DatasetRowV3ContractError(
            "Quality does not match Dataset Row v3."
        )
    for field_name in (
        "experiment_completed",
        "collector_completed",
        "baseline_before_valid",
        "baseline_after_valid",
    ):
        if not isinstance(quality[field_name], bool):
            raise DatasetRowV3ContractError(
                f"quality.{field_name} must be boolean."
            )
    for field_name in (
        "unavailable_feature_count",
        "structural_unavailable_count",
        "collection_unavailable_count",
        "masked_missing_count",
    ):
        value = quality[field_name]
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= len(FEATURE_NAMES_V3)
        ):
            raise DatasetRowV3ContractError(
                f"quality.{field_name} is invalid."
            )

    counts = _availability_counts(availability)
    for field_name, expected in counts.items():
        if quality[field_name] != expected:
            raise DatasetRowV3ContractError(
                f"quality.{field_name} does not match provenance."
            )
    unavailable_count = sum(
        value == "unavailable" for value in features.values()
    )
    if quality["unavailable_feature_count"] != unavailable_count:
        raise DatasetRowV3ContractError(
            "quality.unavailable_feature_count does not match features."
        )
    if unavailable_count != sum(counts.values()):
        raise DatasetRowV3ContractError(
            "Every unavailable feature must have exactly one explicit "
            "availability reason."
        )


def validate_dataset_row_v3(row: dict[str, Any]) -> None:
    if not isinstance(row, dict):
        raise DatasetRowV3ContractError(
            "Dataset row must be an object."
        )
    if set(row) != DATASET_V3_SECTIONS:
        raise DatasetRowV3ContractError(
            "Dataset row does not match the version-3 contract."
        )
    if row["schema_version"] != DATASET_ROW_V3_SCHEMA_VERSION:
        raise DatasetRowV3ContractError(
            "Unsupported dataset schema version."
        )
    _require_string(row["sample_id"], "sample_id")
    features = row["features"]
    if (
        not isinstance(features, dict)
        or set(features) != set(FEATURE_NAMES_V3)
    ):
        raise DatasetRowV3ContractError(
            "Features do not match the version-3 whitelist."
        )
    if set(features).intersection(FORBIDDEN_PREDICTOR_NAMES):
        raise DatasetRowV3ContractError(
            "Dataset Row v3 predictors contain leakage fields."
        )
    invalid_values = {
        name: value
        for name, value in features.items()
        if value not in TRISTATE_VALUES
    }
    if invalid_values:
        raise DatasetRowV3ContractError(
            f"Invalid tri-state values: {invalid_values}"
        )
    _validate_metadata(row)
    _validate_labels(row["labels"])
    _validate_provenance_and_quality(row)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise DatasetRowV3ContractError(
            f"Required artifact does not exist: {path}"
        )
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DatasetRowV3ContractError(
            f"Expected a JSON object in: {path}"
        )
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_labels(ground_truth: dict[str, Any]) -> dict[str, Any]:
    fault_type = ground_truth.get("fault_type")
    _require_string(fault_type, "ground_truth.fault_type")
    return {
        "fault_category": ground_truth.get("fault_category"),
        "fault_type": fault_type,
        "fault_location": ground_truth.get("fault_location"),
        "affected_prefix": ground_truth.get("affected_prefix"),
    }


def _build_quality(
    manifest: dict[str, Any],
    collector_status: dict[str, Any],
    baseline_before: dict[str, Any],
    baseline_after: dict[str, Any],
    features: dict[str, str],
    availability: dict[str, str],
) -> dict[str, Any]:
    quality = {
        "experiment_completed": manifest.get("current_state") == "COMPLETED",
        "collector_completed": (
            collector_status.get("status") == "COLLECTION_COMPLETED"
        ),
        "baseline_before_valid": baseline_before.get("return_code") == 0,
        "baseline_after_valid": baseline_after.get("return_code") == 0,
        "unavailable_feature_count": sum(
            value == "unavailable" for value in features.values()
        ),
        **_availability_counts(availability),
    }
    failed = [
        name
        for name in (
            "experiment_completed",
            "collector_completed",
            "baseline_before_valid",
            "baseline_after_valid",
        )
        if quality[name] is not True
    ]
    if failed:
        raise DatasetRowV3ContractError(
            "Experiment is not Dataset Row v3 eligible: "
            + ", ".join(failed)
        )
    return quality


def build_dataset_row_v3(
    experiment_directory: Path,
) -> dict[str, Any]:
    manifest = _read_json(experiment_directory / "manifest.json")
    evidence_path = (
        experiment_directory / "parsed" / "evidence.json"
    )
    evidence = _read_json(evidence_path)
    ground_truth = _read_json(
        experiment_directory / "ground_truth.json"
    )
    collector_status = _read_json(
        experiment_directory / "collector_status.json"
    )
    baseline_before = _read_json(
        experiment_directory / "validation" / "baseline_before.json"
    )
    baseline_after = _read_json(
        experiment_directory / "validation" / "baseline_after.json"
    )

    try:
        validate_experiment_manifest(manifest)
    except ExperimentManifestContractError as error:
        raise DatasetRowV3ContractError(
            f"Invalid Experiment Manifest v2: {error}"
        ) from error
    try:
        validate_evidence_v3(evidence)
    except EvidenceContractError as error:
        raise DatasetRowV3ContractError(
            f"Invalid Evidence v3: {error}"
        ) from error
    if manifest["topology_id"] != evidence["topology_id"]:
        raise DatasetRowV3ContractError(
            "Manifest and Evidence v3 topology_id must match."
        )

    features = {
        name: (
            "true"
            if evidence["features"][name] is True
            else "false"
            if evidence["features"][name] is False
            else "unavailable"
        )
        for name in FEATURE_NAMES_V3
    }
    availability = copy.deepcopy(evidence["availability"])
    quality = _build_quality(
        manifest,
        collector_status,
        baseline_before,
        baseline_after,
        features,
        availability,
    )
    row = {
        "schema_version": 3,
        "sample_id": manifest["experiment_id"],
        "metadata": {
            "experiment_id": manifest["experiment_id"],
            "scenario_id": manifest["scenario_id"],
            "variant_id": manifest["variant_id"],
            "split_group_id": manifest["split_group_id"],
            "topology_id": evidence["topology_id"],
            "direction": evidence["direction"],
            "source_node": evidence["source_node"],
            "route_observer_node": evidence["route_observer_node"],
            "transit_node": evidence["transit_node"],
            "collected_at_utc": evidence["collected_at_utc"],
        },
        "features": features,
        "labels": _extract_labels(ground_truth),
        "quality": quality,
        "provenance": {
            "source_evidence_schema_version": 3,
            "source_evidence_sha256": _sha256_file(evidence_path),
            "feature_availability": availability,
            "mask_id": None,
        },
    }
    validate_dataset_row_v3(row)
    return row


def apply_missing_evidence_mask_v3(
    row: dict[str, Any],
    mask_id: str,
) -> dict[str, Any]:
    validate_dataset_row_v3(row)
    if row["provenance"]["mask_id"] is not None:
        raise DatasetRowV3ContractError(
            "Missing-evidence masks may be applied only to a clean "
            "Dataset Row v3."
        )
    if mask_id not in MISSING_EVIDENCE_MASKS_V1:
        raise DatasetRowV3ContractError(
            "Unknown P6 missing-evidence mask."
        )

    masked = copy.deepcopy(row)
    availability = masked["provenance"]["feature_availability"]
    changed = 0
    for feature_name in MISSING_EVIDENCE_MASKS_V1[mask_id]:
        if availability[feature_name] == "observed":
            masked["features"][feature_name] = "unavailable"
            availability[feature_name] = "masked_missing"
            changed += 1
    if changed == 0:
        raise DatasetRowV3ContractError(
            "The selected mask has no observed feature to mask."
        )
    masked["provenance"]["mask_id"] = mask_id
    counts = _availability_counts(availability)
    masked["quality"].update(counts)
    masked["quality"]["unavailable_feature_count"] = sum(
        value == "unavailable"
        for value in masked["features"].values()
    )
    validate_dataset_row_v3(masked)
    return masked
