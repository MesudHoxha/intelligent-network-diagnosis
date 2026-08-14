from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Mapping

from src.contracts.evidence_v3 import validate_evidence_v3
from src.contracts.expansion import (
    ExpansionContractError,
    validate_evidence_v4,
    validate_feature_vector_v2,
)


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ADAPTER_ID = "evidence_v3_compatibility_adapter"


def _require_sha256(value: str, field_name: str) -> None:
    if not SHA256_PATTERN.fullmatch(value):
        raise ExpansionContractError(
            f"{field_name} must be a lowercase SHA-256 digest."
        )


def adapt_evidence_v3_to_v4(
    evidence_v3: Mapping[str, Any],
    *,
    evidence_id: str,
    topology_context_id: str,
    source_artifact_sha256: str,
    feature_catalog: Mapping[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    """Return a new v4 projection without mutating or writing the v3 source."""

    _require_sha256(source_artifact_sha256, "source_artifact_sha256")
    source_snapshot = copy.deepcopy(dict(evidence_v3))
    validate_evidence_v3(source_snapshot)

    raw_artifacts: dict[tuple[str, str], dict[str, str]] = {}
    observations: dict[str, dict[str, Any]] = {}
    collection_unavailable_count = 0
    for feature_id, value in source_snapshot["features"].items():
        availability = source_snapshot["availability"][feature_id]
        probe = source_snapshot["probes"][feature_id]
        raw_path = probe["raw_artifact"]
        raw_hash = probe["raw_artifact_sha256"]
        if isinstance(raw_path, str) and isinstance(raw_hash, str):
            raw_artifacts[(raw_path, raw_hash)] = {
                "path": raw_path,
                "sha256": raw_hash,
            }
        collection_unavailable_count += availability == "collection_unavailable"
        observations[feature_id] = {
            "value": value,
            "value_type": "boolean",
            "availability": availability,
            "collector_id": ADAPTER_ID,
            "raw_artifact": raw_path,
            "raw_artifact_sha256": raw_hash,
        }

    if collection_unavailable_count == len(observations):
        run_status = "failed"
        run_errors = ["All adapted Evidence v3 probes were unavailable."]
    elif collection_unavailable_count:
        run_status = "partial"
        run_errors = []
    else:
        run_status = "completed"
        run_errors = []

    direction = source_snapshot["direction"]
    destination_node = direction.split("_to_", maxsplit=1)[1]
    result: dict[str, Any] = {
        "schema_version": 4,
        "evidence_id": evidence_id,
        "topology_context_id": topology_context_id,
        "collected_at_utc": source_snapshot["collected_at_utc"],
        "observation_path": {
            "direction": direction,
            "source_node": source_snapshot["source_node"],
            "destination_node": destination_node,
            "observer_nodes": [
                source_snapshot["route_observer_node"],
                source_snapshot["transit_node"],
            ],
        },
        "collector_runs": [
            {
                "schema_version": 1,
                "collector_id": ADAPTER_ID,
                "collector_version": 1,
                "domain": "compatibility",
                "status": run_status,
                "started_at_utc": source_snapshot["collected_at_utc"],
                "completed_at_utc": source_snapshot["collected_at_utc"],
                "feature_ids": list(source_snapshot["features"]),
                "raw_artifacts": sorted(
                    raw_artifacts.values(), key=lambda row: row["path"]
                ),
                "errors": run_errors,
            }
        ],
        "observations": observations,
        "compatibility": {
            "origin": "read_only_v3_adapter",
            "source_schema_version": 3,
            "source_artifact_sha256": source_artifact_sha256,
        },
    }
    validate_evidence_v4(
        result,
        feature_catalog,
        repository_root=repository_root,
    )
    if dict(evidence_v3) != source_snapshot:
        raise ExpansionContractError("The read-only v3 adapter mutated its source.")
    return result


def project_feature_vector_v2(
    evidence_v4: Mapping[str, Any],
    *,
    vector_id: str,
    evidence_sha256: str,
    feature_catalog_sha256: str,
    feature_catalog: Mapping[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    """Project an unmasked Feature Vector v2 without persisting artifacts."""

    _require_sha256(evidence_sha256, "evidence_sha256")
    _require_sha256(feature_catalog_sha256, "feature_catalog_sha256")
    validate_evidence_v4(
        evidence_v4,
        feature_catalog,
        repository_root=repository_root,
    )
    observations = evidence_v4["observations"]
    assert isinstance(observations, Mapping)
    result: dict[str, Any] = {
        "schema_version": 2,
        "vector_id": vector_id,
        "catalog_id": feature_catalog["catalog_id"],
        "evidence_id": evidence_v4["evidence_id"],
        "values": {
            feature_id: {
                "value": observation["value"],
                "availability": observation["availability"],
            }
            for feature_id, observation in observations.items()
        },
        "mask_id": None,
        "provenance": {
            "evidence_sha256": evidence_sha256,
            "feature_catalog_sha256": feature_catalog_sha256,
        },
    }
    validate_feature_vector_v2(
        result,
        feature_catalog,
        repository_root=repository_root,
    )
    return result
