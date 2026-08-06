from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.contracts.evidence import (
    EvidenceContractError,
    validate_evidence_v2,
)
from src.contracts.experiment_manifest import (
    ExperimentManifestContractError,
    validate_experiment_manifest,
)
from src.contracts.observation_profile import (
    DIRECTION_PATTERN,
    IDENTIFIER_PATTERN,
)
from src.dataset.contract_v3 import (
    DATASET_ROW_V3_SCHEMA_VERSION,
    FEATURE_NAMES_V3,
    DatasetRowV3ContractError,
    build_dataset_row_v3,
    validate_dataset_row_v3,
)


DATASET_ROW_V1_SCHEMA_VERSION = 1
DATASET_ROW_V2_SCHEMA_VERSION = 2
# The runtime default intentionally remains v2 until a real Evidence
# v3 collector is implemented and accepted in a later Phase 6 gate.
DATASET_SCHEMA_VERSION = DATASET_ROW_V2_SCHEMA_VERSION

TRISTATE_VALUES = {
    "true",
    "false",
    "unavailable",
}

FEATURE_NAMES_V1 = (
    "source_gateway_reachable",
    "destination_reachable",
    "route_to_destination_exists_on_r1",
    "route_next_hop_present_on_r1",
    "route_next_hop_reachable_from_r1",
    "transit_next_hop_reachable",
    "destination_reachable_from_r2",
)

FEATURE_NAMES_V2 = (
    "source_gateway_reachable",
    "destination_reachable",
    "route_to_destination_exists_on_observer",
    "route_next_hop_present_on_observer",
    "route_next_hop_reachable_from_observer",
    "expected_next_hop_reachable_from_observer",
    "destination_reachable_from_transit",
)

# FEATURE_NAMES identifies the canonical feature contract for new
# dataset rows. Version-specific consumers should import the explicit
# FEATURE_NAMES_V1 or FEATURE_NAMES_V2 constant.
FEATURE_NAMES = FEATURE_NAMES_V2

METADATA_FIELDS_V1 = {
    "experiment_id",
    "scenario_id",
    "variant_id",
    "split_group_id",
    "topology_id",
    "collected_at_utc",
}

METADATA_FIELDS_V2 = {
    *METADATA_FIELDS_V1,
    "direction",
    "route_observer_node",
    "transit_node",
}

LABEL_FIELDS = {
    "fault_category",
    "fault_type",
    "fault_location",
    "affected_prefix",
}

QUALITY_FIELDS = {
    "experiment_completed",
    "collector_completed",
    "baseline_before_valid",
    "baseline_after_valid",
    "unavailable_feature_count",
}

DATASET_SECTIONS = {
    "schema_version",
    "sample_id",
    "metadata",
    "features",
    "labels",
    "quality",
}

ROLE_NEUTRAL_EVIDENCE_KEYS = {
    "route_to_destination_exists_on_r1": (
        "route_to_destination_exists_on_observer"
    ),
    "route_next_hop_on_r1": (
        "route_next_hop_on_observer"
    ),
    "route_next_hop_reachable_from_r1": (
        "route_next_hop_reachable_from_observer"
    ),
    "transit_next_hop_reachable": (
        "expected_next_hop_reachable_from_observer"
    ),
    "destination_reachable_from_r2": (
        "destination_reachable_from_transit"
    ),
}

V1_TO_V2_FEATURE_NAMES = {
    "source_gateway_reachable": (
        "source_gateway_reachable"
    ),
    "destination_reachable": (
        "destination_reachable"
    ),
    "route_to_destination_exists_on_r1": (
        "route_to_destination_exists_on_observer"
    ),
    "route_next_hop_present_on_r1": (
        "route_next_hop_present_on_observer"
    ),
    "route_next_hop_reachable_from_r1": (
        "route_next_hop_reachable_from_observer"
    ),
    "transit_next_hop_reachable": (
        "expected_next_hop_reachable_from_observer"
    ),
    "destination_reachable_from_r2": (
        "destination_reachable_from_transit"
    ),
}

LEGACY_V1_CONTEXT = {
    "topology_id": "TOP_01",
    "direction": "hosta_to_hostb",
    "route_observer_node": "r1",
    "transit_node": "r2",
}


class DatasetContractError(ValueError):
    """Raised when an experiment cannot produce a valid row."""


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise DatasetContractError(
            f"Required artifact does not exist: {path}"
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(data, dict):
        raise DatasetContractError(
            f"Expected a JSON object in: {path}"
        )

    return data


def to_tristate(value: object) -> str:
    if value is True:
        return "true"

    if value is False:
        return "false"

    if value is None:
        return "unavailable"

    raise DatasetContractError(
        "Tri-state evidence must be true, false, or null; "
        f"received {value!r}."
    )


def _next_hop_present(
    route_exists: object,
    next_hop: object,
    *,
    route_field_name: str,
    next_hop_field_name: str,
) -> str:
    if route_exists is None:
        return "unavailable"

    if route_exists is False:
        return "false"

    if route_exists is not True:
        raise DatasetContractError(
            f"{route_field_name} must be "
            "true, false, or null."
        )

    if (
        next_hop is not None
        and not isinstance(next_hop, str)
    ):
        raise DatasetContractError(
            f"{next_hop_field_name} must be "
            "a string or null."
        )

    return (
        "true"
        if isinstance(next_hop, str)
        and next_hop.strip()
        else "false"
    )


def extract_features_v1(
    evidence: dict[str, Any],
) -> dict[str, str]:
    evidence_schema_version = evidence.get(
        "schema_version",
        1,
    )

    if (
        isinstance(evidence_schema_version, bool)
        or evidence_schema_version not in {1, 2}
    ):
        raise DatasetContractError(
            "Unsupported evidence schema version."
        )

    def evidence_value(legacy_name: str) -> object:
        if evidence_schema_version == 1:
            source_name = legacy_name
        else:
            source_name = ROLE_NEUTRAL_EVIDENCE_KEYS.get(
                legacy_name,
                legacy_name,
            )

        return evidence.get(source_name)

    route_exists = evidence_value(
        "route_to_destination_exists_on_r1"
    )
    next_hop_present = _next_hop_present(
        route_exists,
        evidence_value("route_next_hop_on_r1"),
        route_field_name=(
            "route_to_destination_exists_on_r1"
        ),
        next_hop_field_name="route_next_hop_on_r1",
    )

    return {
        "source_gateway_reachable": to_tristate(
            evidence_value(
                "source_gateway_reachable"
            )
        ),
        "destination_reachable": to_tristate(
            evidence_value(
                "destination_reachable"
            )
        ),
        "route_to_destination_exists_on_r1": (
            to_tristate(route_exists)
        ),
        "route_next_hop_present_on_r1": (
            next_hop_present
        ),
        "route_next_hop_reachable_from_r1": (
            to_tristate(
                evidence_value(
                    "route_next_hop_reachable_from_r1"
                )
            )
        ),
        "transit_next_hop_reachable": to_tristate(
            evidence_value(
                "transit_next_hop_reachable"
            )
        ),
        "destination_reachable_from_r2": (
            to_tristate(
                evidence_value(
                    "destination_reachable_from_r2"
                )
            )
        ),
    }


def extract_features_v2(
    evidence: dict[str, Any],
) -> dict[str, str]:
    try:
        validate_evidence_v2(evidence)
    except EvidenceContractError as error:
        raise DatasetContractError(
            f"Invalid Evidence v2: {error}"
        ) from error

    route_exists = evidence[
        "route_to_destination_exists_on_observer"
    ]
    next_hop_present = _next_hop_present(
        route_exists,
        evidence["route_next_hop_on_observer"],
        route_field_name=(
            "route_to_destination_exists_on_observer"
        ),
        next_hop_field_name=(
            "route_next_hop_on_observer"
        ),
    )

    return {
        "source_gateway_reachable": to_tristate(
            evidence["source_gateway_reachable"]
        ),
        "destination_reachable": to_tristate(
            evidence["destination_reachable"]
        ),
        (
            "route_to_destination_exists_on_observer"
        ): to_tristate(route_exists),
        (
            "route_next_hop_present_on_observer"
        ): next_hop_present,
        (
            "route_next_hop_reachable_from_observer"
        ): to_tristate(
            evidence[
                "route_next_hop_reachable_from_observer"
            ]
        ),
        (
            "expected_next_hop_reachable_from_observer"
        ): to_tristate(
            evidence[
                "expected_next_hop_reachable_from_observer"
            ]
        ),
        (
            "destination_reachable_from_transit"
        ): to_tristate(
            evidence[
                "destination_reachable_from_transit"
            ]
        ),
    }


# Historical compatibility alias.
extract_features = extract_features_v1


def extract_labels(
    ground_truth: dict[str, Any],
) -> dict[str, Any]:
    fault_type = ground_truth.get("fault_type")

    if not isinstance(fault_type, str) or not fault_type:
        raise DatasetContractError(
            "ground_truth fault_type must be "
            "a non-empty string."
        )

    return {
        "fault_category": ground_truth.get(
            "fault_category"
        ),
        "fault_type": fault_type,
        "fault_location": ground_truth.get(
            "fault_location"
        ),
        "affected_prefix": ground_truth.get(
            "affected_prefix"
        ),
    }


def _validate_utc_timestamp(
    value: object,
    field_name: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise DatasetContractError(
            f"{field_name} must be a non-empty "
            "UTC timestamp string."
        )

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise DatasetContractError(
            f"{field_name} must be an ISO-8601 timestamp."
        ) from error

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timedelta(0)
    ):
        raise DatasetContractError(
            f"{field_name} must include the UTC offset."
        )


def _validate_string_field(
    value: object,
    field_name: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise DatasetContractError(
            f"{field_name} must be a non-empty string."
        )


def _validate_metadata(
    row: dict[str, Any],
    *,
    schema_version: int,
) -> None:
    metadata = row["metadata"]
    expected_fields = (
        METADATA_FIELDS_V1
        if schema_version
        == DATASET_ROW_V1_SCHEMA_VERSION
        else METADATA_FIELDS_V2
    )

    if (
        not isinstance(metadata, dict)
        or set(metadata) != expected_fields
    ):
        raise DatasetContractError(
            "Metadata does not match Dataset Row "
            f"v{schema_version}."
        )

    for field_name in (
        "experiment_id",
        "scenario_id",
        "variant_id",
        "split_group_id",
        "topology_id",
    ):
        _validate_string_field(
            metadata[field_name],
            f"metadata.{field_name}",
        )

    if (
        row["sample_id"]
        != metadata["experiment_id"]
    ):
        raise DatasetContractError(
            "sample_id must equal "
            "metadata.experiment_id."
        )

    collected_at_utc = metadata[
        "collected_at_utc"
    ]

    if (
        schema_version
        == DATASET_ROW_V1_SCHEMA_VERSION
    ):
        if (
            collected_at_utc is not None
            and (
                not isinstance(
                    collected_at_utc,
                    str,
                )
                or not collected_at_utc
            )
        ):
            raise DatasetContractError(
                "metadata.collected_at_utc must be "
                "a non-empty string or null."
            )
    else:
        _validate_utc_timestamp(
            collected_at_utc,
            "metadata.collected_at_utc",
        )

        for field_name in (
            "direction",
            "route_observer_node",
            "transit_node",
        ):
            _validate_string_field(
                metadata[field_name],
                f"metadata.{field_name}",
            )

        if not IDENTIFIER_PATTERN.fullmatch(
            metadata["topology_id"]
        ):
            raise DatasetContractError(
                "metadata.topology_id must be "
                "a valid identifier."
            )

        if not DIRECTION_PATTERN.fullmatch(
            metadata["direction"]
        ):
            raise DatasetContractError(
                "metadata.direction must use the "
                "'source_to_destination' format."
            )

        for field_name in (
            "route_observer_node",
            "transit_node",
        ):
            if not IDENTIFIER_PATTERN.fullmatch(
                metadata[field_name]
            ):
                raise DatasetContractError(
                    f"metadata.{field_name} must be "
                    "a valid identifier."
                )

        if (
            metadata["route_observer_node"]
            == metadata["transit_node"]
        ):
            raise DatasetContractError(
                "metadata.route_observer_node and "
                "metadata.transit_node must be different."
            )


def _validate_labels(row: dict[str, Any]) -> None:
    labels = row["labels"]

    if (
        not isinstance(labels, dict)
        or set(labels) != LABEL_FIELDS
    ):
        raise DatasetContractError(
            "Labels do not match the dataset contract."
        )

    _validate_string_field(
        labels["fault_type"],
        "labels.fault_type",
    )

    for field_name in (
        "fault_category",
        "fault_location",
        "affected_prefix",
    ):
        value = labels[field_name]

        if (
            value is not None
            and (
                not isinstance(value, str)
                or not value
            )
        ):
            raise DatasetContractError(
                f"labels.{field_name} must be "
                "a non-empty string or null."
            )


def _validate_quality(
    row: dict[str, Any],
) -> None:
    quality = row["quality"]

    if (
        not isinstance(quality, dict)
        or set(quality) != QUALITY_FIELDS
    ):
        raise DatasetContractError(
            "Quality does not match the dataset contract."
        )

    for field_name in (
        "experiment_completed",
        "collector_completed",
        "baseline_before_valid",
        "baseline_after_valid",
    ):
        if not isinstance(
            quality[field_name],
            bool,
        ):
            raise DatasetContractError(
                f"quality.{field_name} must be boolean."
            )

    unavailable_feature_count = quality[
        "unavailable_feature_count"
    ]

    if (
        isinstance(unavailable_feature_count, bool)
        or not isinstance(
            unavailable_feature_count,
            int,
        )
        or unavailable_feature_count < 0
        or unavailable_feature_count
        > len(row["features"])
    ):
        raise DatasetContractError(
            "quality.unavailable_feature_count "
            "is invalid."
        )

    actual_unavailable_count = sum(
        value == "unavailable"
        for value in row["features"].values()
    )

    if (
        unavailable_feature_count
        != actual_unavailable_count
    ):
        raise DatasetContractError(
            "quality.unavailable_feature_count "
            "does not match features."
        )


def _validate_dataset_row_version(
    row: dict[str, Any],
    *,
    schema_version: int,
    feature_names: tuple[str, ...],
) -> None:
    if not isinstance(row, dict):
        raise DatasetContractError(
            "Dataset row must be an object."
        )

    if set(row) != DATASET_SECTIONS:
        raise DatasetContractError(
            "Dataset row does not match "
            f"the version-{schema_version} contract."
        )

    if row["schema_version"] != schema_version:
        raise DatasetContractError(
            "Unsupported dataset schema version."
        )

    _validate_string_field(
        row["sample_id"],
        "sample_id",
    )

    features = row["features"]

    if (
        not isinstance(features, dict)
        or set(features) != set(feature_names)
    ):
        raise DatasetContractError(
            "Features do not match the "
            f"version-{schema_version} whitelist."
        )

    invalid_values = {
        name: value
        for name, value in features.items()
        if value not in TRISTATE_VALUES
    }

    if invalid_values:
        raise DatasetContractError(
            "Invalid tri-state values: "
            f"{invalid_values}"
        )

    _validate_metadata(
        row,
        schema_version=schema_version,
    )
    _validate_labels(row)
    _validate_quality(row)


def validate_dataset_row_v1(
    row: dict[str, Any],
) -> None:
    _validate_dataset_row_version(
        row,
        schema_version=(
            DATASET_ROW_V1_SCHEMA_VERSION
        ),
        feature_names=FEATURE_NAMES_V1,
    )


def validate_dataset_row_v2(
    row: dict[str, Any],
) -> None:
    _validate_dataset_row_version(
        row,
        schema_version=(
            DATASET_ROW_V2_SCHEMA_VERSION
        ),
        feature_names=FEATURE_NAMES_V2,
    )


def validate_dataset_row(
    row: dict[str, Any],
) -> None:
    if not isinstance(row, dict):
        raise DatasetContractError(
            "Dataset row must be an object."
        )

    schema_version = row.get("schema_version")

    if isinstance(schema_version, bool):
        raise DatasetContractError(
            "Unsupported dataset schema version."
        )

    if (
        schema_version
        == DATASET_ROW_V1_SCHEMA_VERSION
    ):
        validate_dataset_row_v1(row)
        return

    if (
        schema_version
        == DATASET_ROW_V2_SCHEMA_VERSION
    ):
        validate_dataset_row_v2(row)
        return

    if (
        schema_version
        == DATASET_ROW_V3_SCHEMA_VERSION
    ):
        try:
            validate_dataset_row_v3(row)
        except DatasetRowV3ContractError as error:
            raise DatasetContractError(
                f"Invalid Dataset Row v3: {error}"
            ) from error
        return

    raise DatasetContractError(
        "Unsupported dataset schema version."
    )


def validate_homogeneous_dataset_rows(
    rows: list[dict[str, Any]],
) -> int:
    """Validate rows and reject cross-version aggregation."""

    if not isinstance(rows, list) or not rows:
        raise DatasetContractError(
            "Dataset rows must be a non-empty list."
        )

    versions: set[int] = set()
    for row in rows:
        validate_dataset_row(row)
        schema_version = row.get("schema_version")
        assert isinstance(schema_version, int)
        versions.add(schema_version)

    if len(versions) != 1:
        raise DatasetContractError(
            "Dataset aggregation cannot mix row schema versions."
        )

    return next(iter(versions))


def _read_experiment_artifacts(
    experiment_directory: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    return (
        read_json(
            experiment_directory / "manifest.json"
        ),
        read_json(
            experiment_directory
            / "parsed"
            / "evidence.json"
        ),
        read_json(
            experiment_directory
            / "ground_truth.json"
        ),
        read_json(
            experiment_directory
            / "collector_status.json"
        ),
        read_json(
            experiment_directory
            / "validation"
            / "baseline_before.json"
        ),
        read_json(
            experiment_directory
            / "validation"
            / "baseline_after.json"
        ),
    )


def _build_quality(
    manifest: dict[str, Any],
    collector_status: dict[str, Any],
    baseline_before: dict[str, Any],
    baseline_after: dict[str, Any],
    features: dict[str, str],
) -> dict[str, Any]:
    quality = {
        "experiment_completed": (
            manifest.get("current_state")
            == "COMPLETED"
        ),
        "collector_completed": (
            collector_status.get("status")
            == "COLLECTION_COMPLETED"
        ),
        "baseline_before_valid": (
            baseline_before.get("return_code") == 0
        ),
        "baseline_after_valid": (
            baseline_after.get("return_code") == 0
        ),
        "unavailable_feature_count": sum(
            value == "unavailable"
            for value in features.values()
        ),
    }

    required_quality = (
        "experiment_completed",
        "collector_completed",
        "baseline_before_valid",
        "baseline_after_valid",
    )

    failed_quality = [
        name
        for name in required_quality
        if quality[name] is not True
    ]

    if failed_quality:
        raise DatasetContractError(
            "Experiment is not dataset-eligible: "
            + ", ".join(failed_quality)
        )

    return quality


def _require_non_empty_artifact_fields(
    fields: tuple[tuple[str, object], ...],
) -> None:
    for name, value in fields:
        _validate_string_field(value, name)


def build_dataset_row_v1(
    experiment_directory: Path,
) -> dict[str, Any]:
    (
        manifest,
        evidence,
        ground_truth,
        collector_status,
        baseline_before,
        baseline_after,
    ) = _read_experiment_artifacts(
        experiment_directory
    )

    experiment_id = manifest.get("experiment_id")
    scenario_id = manifest.get("scenario_id")
    topology_id = evidence.get("topology_id")

    _require_non_empty_artifact_fields((
        ("experiment_id", experiment_id),
        ("scenario_id", scenario_id),
        ("topology_id", topology_id),
    ))

    evidence_schema_version = evidence.get(
        "schema_version",
        1,
    )

    if evidence_schema_version == 2:
        route_observer_node = evidence.get(
            "route_observer_node"
        )
        transit_node = evidence.get("transit_node")

        if (
            topology_id
            != LEGACY_V1_CONTEXT["topology_id"]
            or evidence.get("direction")
            != LEGACY_V1_CONTEXT["direction"]
            or route_observer_node
            != LEGACY_V1_CONTEXT[
                "route_observer_node"
            ]
            or transit_node
            != LEGACY_V1_CONTEXT["transit_node"]
        ):
            raise DatasetContractError(
                "Dataset Row v1 supports role-neutral evidence "
                "only for the legacy TOP_01, "
                "hosta_to_hostb, r1/r2 binding. "
                "Use Dataset Row v2 for other topologies "
                "or observation contexts."
            )

    variant_id = manifest.get(
        "variant_id",
        "canonical",
    )

    _validate_string_field(
        variant_id,
        "variant_id",
    )

    split_group_id = manifest.get(
        "split_group_id",
        (
            f"{topology_id}:"
            f"{scenario_id}:"
            f"{variant_id}"
        ),
    )

    _validate_string_field(
        split_group_id,
        "split_group_id",
    )

    features = extract_features_v1(evidence)
    labels = extract_labels(ground_truth)
    quality = _build_quality(
        manifest,
        collector_status,
        baseline_before,
        baseline_after,
        features,
    )

    row = {
        "schema_version": (
            DATASET_ROW_V1_SCHEMA_VERSION
        ),
        "sample_id": experiment_id,
        "metadata": {
            "experiment_id": experiment_id,
            "scenario_id": scenario_id,
            "variant_id": variant_id,
            "split_group_id": split_group_id,
            "topology_id": topology_id,
            "collected_at_utc": evidence.get(
                "collected_at_utc"
            ),
        },
        "features": features,
        "labels": labels,
        "quality": quality,
    }

    validate_dataset_row_v1(row)
    return row


def build_dataset_row_v2(
    experiment_directory: Path,
) -> dict[str, Any]:
    (
        manifest,
        evidence,
        ground_truth,
        collector_status,
        baseline_before,
        baseline_after,
    ) = _read_experiment_artifacts(
        experiment_directory
    )

    try:
        validate_experiment_manifest(manifest)
    except ExperimentManifestContractError as error:
        raise DatasetContractError(
            f"Invalid Experiment Manifest v2: {error}"
        ) from error

    try:
        validate_evidence_v2(evidence)
    except EvidenceContractError as error:
        raise DatasetContractError(
            f"Invalid Evidence v2: {error}"
        ) from error

    if (
        manifest["topology_id"]
        != evidence["topology_id"]
    ):
        raise DatasetContractError(
            "Manifest and evidence topology_id "
            "must match."
        )

    features = extract_features_v2(evidence)
    labels = extract_labels(ground_truth)
    quality = _build_quality(
        manifest,
        collector_status,
        baseline_before,
        baseline_after,
        features,
    )

    row = {
        "schema_version": (
            DATASET_ROW_V2_SCHEMA_VERSION
        ),
        "sample_id": manifest["experiment_id"],
        "metadata": {
            "experiment_id": (
                manifest["experiment_id"]
            ),
            "scenario_id": manifest["scenario_id"],
            "variant_id": manifest["variant_id"],
            "split_group_id": (
                manifest["split_group_id"]
            ),
            "topology_id": evidence["topology_id"],
            "direction": evidence["direction"],
            "route_observer_node": (
                evidence["route_observer_node"]
            ),
            "transit_node": evidence["transit_node"],
            "collected_at_utc": (
                evidence["collected_at_utc"]
            ),
        },
        "features": features,
        "labels": labels,
        "quality": quality,
    }

    validate_dataset_row_v2(row)
    return row


def build_dataset_row(
    experiment_directory: Path,
) -> dict[str, Any]:
    """Build the canonical Dataset Row v2 for a new experiment."""

    return build_dataset_row_v2(
        experiment_directory
    )


def migrate_dataset_row_v1_to_v2(
    row: dict[str, Any],
    *,
    direction: str,
    route_observer_node: str,
    transit_node: str,
) -> dict[str, Any]:
    """Explicitly migrate one historical P1 row to Dataset Row v2."""

    validate_dataset_row_v1(row)

    migration_context = {
        "topology_id": row["metadata"][
            "topology_id"
        ],
        "direction": direction,
        "route_observer_node": route_observer_node,
        "transit_node": transit_node,
    }

    if migration_context != LEGACY_V1_CONTEXT:
        raise DatasetContractError(
            "Dataset Row v1 migration is defined only "
            "for the historical TOP_01, "
            "hosta_to_hostb, r1/r2 context."
        )

    metadata = copy.deepcopy(row["metadata"])
    metadata.update({
        "direction": direction,
        "route_observer_node": (
            route_observer_node
        ),
        "transit_node": transit_node,
    })

    migrated = {
        "schema_version": (
            DATASET_ROW_V2_SCHEMA_VERSION
        ),
        "sample_id": row["sample_id"],
        "metadata": metadata,
        "features": {
            V1_TO_V2_FEATURE_NAMES[name]: value
            for name, value
            in row["features"].items()
        },
        "labels": copy.deepcopy(row["labels"]),
        "quality": copy.deepcopy(row["quality"]),
    }

    validate_dataset_row_v2(migrated)
    return migrated


def write_dataset_row(
    experiment_directory: Path,
    output_path: Path,
    *,
    schema_version: int = DATASET_SCHEMA_VERSION,
) -> dict[str, Any]:
    if (
        schema_version
        == DATASET_ROW_V1_SCHEMA_VERSION
    ):
        row = build_dataset_row_v1(
            experiment_directory
        )
    elif (
        schema_version
        == DATASET_ROW_V2_SCHEMA_VERSION
    ):
        row = build_dataset_row_v2(
            experiment_directory
        )
    elif (
        schema_version
        == DATASET_ROW_V3_SCHEMA_VERSION
    ):
        try:
            row = build_dataset_row_v3(
                experiment_directory
            )
        except DatasetRowV3ContractError as error:
            raise DatasetContractError(
                f"Cannot build Dataset Row v3: {error}"
            ) from error
    else:
        raise DatasetContractError(
            "Unsupported dataset schema version."
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_path.write_text(
        json.dumps(
            row,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return row


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build one leakage-safe dataset row "
            "from a completed experiment."
        )
    )

    parser.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--schema-version",
        type=int,
        choices=(
            DATASET_ROW_V1_SCHEMA_VERSION,
            DATASET_ROW_V2_SCHEMA_VERSION,
            DATASET_ROW_V3_SCHEMA_VERSION,
        ),
        default=DATASET_SCHEMA_VERSION,
        help=(
            "Dataset row contract to emit. "
            "New exports default to version 2."
        ),
    )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        row = write_dataset_row(
            arguments.experiment_dir,
            arguments.output,
            schema_version=(
                arguments.schema_version
            ),
        )
    except (
        DatasetContractError,
        json.JSONDecodeError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1

    print(json.dumps(row, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
