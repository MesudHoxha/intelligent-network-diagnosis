from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DATASET_SCHEMA_VERSION = 1

TRISTATE_VALUES = {
    "true",
    "false",
    "unavailable",
}

FEATURE_NAMES = (
    "source_gateway_reachable",
    "destination_reachable",
    "route_to_destination_exists_on_r1",
    "route_next_hop_present_on_r1",
    "route_next_hop_reachable_from_r1",
    "transit_next_hop_reachable",
    "destination_reachable_from_r2",
)

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


def extract_features(
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

    if route_exists is None:
        next_hop_present = "unavailable"
    elif route_exists is False:
        next_hop_present = "false"
    elif route_exists is True:
        next_hop = evidence_value(
            "route_next_hop_on_r1"
        )

        if next_hop is not None and not isinstance(
            next_hop,
            str,
        ):
            raise DatasetContractError(
                "route_next_hop_on_r1 must be "
                "a string or null."
            )

        next_hop_present = (
            "true"
            if isinstance(next_hop, str)
            and next_hop.strip()
            else "false"
        )
    else:
        raise DatasetContractError(
            "route_to_destination_exists_on_r1 "
            "must be true, false, or null."
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


def validate_dataset_row(
    row: dict[str, Any],
) -> None:
    expected_sections = {
        "schema_version",
        "sample_id",
        "metadata",
        "features",
        "labels",
        "quality",
    }

    if set(row) != expected_sections:
        raise DatasetContractError(
            "Dataset row does not match "
            "the version-1 contract."
        )

    if (
        row["schema_version"]
        != DATASET_SCHEMA_VERSION
    ):
        raise DatasetContractError(
            "Unsupported dataset schema version."
        )

    features = row["features"]

    if (
        not isinstance(features, dict)
        or set(features) != set(FEATURE_NAMES)
    ):
        raise DatasetContractError(
            "Features do not match "
            "the version-1 whitelist."
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

    metadata = row["metadata"]

    if (
        not isinstance(metadata, dict)
        or row["sample_id"]
        != metadata.get("experiment_id")
    ):
        raise DatasetContractError(
            "sample_id must equal "
            "metadata.experiment_id."
        )


def build_dataset_row(
    experiment_directory: Path,
) -> dict[str, Any]:
    manifest = read_json(
        experiment_directory / "manifest.json"
    )
    evidence = read_json(
        experiment_directory
        / "parsed"
        / "evidence.json"
    )
    ground_truth = read_json(
        experiment_directory
        / "ground_truth.json"
    )
    collector_status = read_json(
        experiment_directory
        / "collector_status.json"
    )
    baseline_before = read_json(
        experiment_directory
        / "validation"
        / "baseline_before.json"
    )
    baseline_after = read_json(
        experiment_directory
        / "validation"
        / "baseline_after.json"
    )

    experiment_id = manifest.get("experiment_id")
    scenario_id = manifest.get("scenario_id")
    topology_id = evidence.get("topology_id")

    for name, value in (
        ("experiment_id", experiment_id),
        ("scenario_id", scenario_id),
        ("topology_id", topology_id),
    ):
        if not isinstance(value, str) or not value:
            raise DatasetContractError(
                f"{name} must be a non-empty string."
            )

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
            topology_id != "TOP_01"
            or route_observer_node != "r1"
            or transit_node != "r2"
        ):
            raise DatasetContractError(
                "Dataset Row v1 supports role-neutral evidence "
                "only for the legacy TOP_01 r1/r2 binding. "
                "Define Dataset Row v2 before exporting other "
                "topologies or observation directions."
            )

    variant_id = manifest.get(
        "variant_id",
        "canonical",
    )

    if (
        not isinstance(variant_id, str)
        or not variant_id
    ):
        raise DatasetContractError(
            "variant_id must be a non-empty string."
        )

    split_group_id = manifest.get(
        "split_group_id",
        (
            f"{topology_id}:"
            f"{scenario_id}:"
            f"{variant_id}"
        ),
    )

    features = extract_features(evidence)
    labels = extract_labels(ground_truth)

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

    row = {
        "schema_version": DATASET_SCHEMA_VERSION,
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

    validate_dataset_row(row)
    return row


def write_dataset_row(
    experiment_directory: Path,
    output_path: Path,
) -> dict[str, Any]:
    row = build_dataset_row(
        experiment_directory
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

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        row = write_dataset_row(
            arguments.experiment_dir,
            arguments.output,
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
