"""Native Evidence v4 materialization for the X6-R1.5 F1 successor."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from src.collection.x6_performance_collector import FEATURES
from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2
from src.orchestration.x6_r1_5_1_contract import canonical, digest, require
from src.orchestration.x6_r1_5_1_durable import save


def build_f1_artifacts(
    root: Path,
    values: Mapping[str, Mapping[str, object]],
    raw_files: Sequence[Path],
    fault_records: Sequence[Mapping[str, object]],
    *,
    repository_root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build deterministic artifacts from a bound, independently reconstructable cohort."""
    require(len(raw_files) == 3 and len(fault_records) > 0, "fault artifact source inventory")
    require(
        all(row.get("window") in {"F01", "F02", "F03"} for row in fault_records),
        "fault artifact command scope",
    )
    ordered = sorted(fault_records, key=lambda row: int(row["order"]))
    require(
        [int(row["order"]) for row in ordered]
        == list(range(int(ordered[0]["order"]), int(ordered[-1]["order"]) + 1)),
        "fault artifact command continuity",
    )
    started_at = str(ordered[0]["started"]["utc"])
    completed_at = str(ordered[-1]["completed"]["utc"])
    catalog_path = repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    artifacts = [
        {
            "path": str(path.relative_to(root)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in raw_files
    ]
    collector_id = "performance_collector_v1"
    primary = artifacts[0]
    observations = {
        name: {
            "value": values[name]["value"],
            "value_type": next(
                row["value_type"] for row in catalog["features"] if row["feature_id"] == name
            ),
            "availability": values[name]["availability"],
            "collector_id": collector_id,
            "raw_artifact": primary["path"],
            "raw_artifact_sha256": primary["sha256"],
        }
        for name in FEATURES
    }
    evidence = {
        "schema_version": 4,
        "evidence_id": "x6_r1_5_1_packet_loss:evidence:v4",
        "topology_context_id": "X6_TOP_01_CONTROLLED_PERFORMANCE_PATH",
        "collected_at_utc": completed_at,
        "observation_path": {
            "direction": "hosta_to_hostb",
            "source_node": "hosta",
            "destination_node": "hostb",
            "observer_nodes": ["r2", "r3"],
        },
        "collector_runs": [
            {
                "schema_version": 1,
                "collector_id": collector_id,
                "collector_version": 1,
                "domain": "performance",
                "status": "completed",
                "started_at_utc": started_at,
                "completed_at_utc": completed_at,
                "feature_ids": list(FEATURES),
                "raw_artifacts": artifacts,
                "errors": [],
            }
        ],
        "observations": observations,
        "compatibility": {
            "origin": "native_v4",
            "source_schema_version": None,
            "source_artifact_sha256": None,
        },
    }
    validate_evidence_v4(evidence, catalog, repository_root=repository_root)
    vector = {
        "schema_version": 2,
        "vector_id": "x6_r1_5_1_packet_loss:vector:v2",
        "catalog_id": catalog["catalog_id"],
        "evidence_id": evidence["evidence_id"],
        "values": {
            name: {
                "value": values[name]["value"],
                "availability": values[name]["availability"],
            }
            for name in FEATURES
        },
        "mask_id": None,
        "provenance": {
            "evidence_sha256": digest(canonical(evidence)),
            "feature_catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        },
    }
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    return evidence, vector


def materialize_f1_evidence(
    root: Path,
    values: Mapping[str, Mapping[str, object]],
    raw_files: Sequence[Path],
    fault_records: Sequence[Mapping[str, object]],
    *,
    repository_root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Materialize schema-valid F1 evidence from the bound three-window cohort."""
    evidence, vector = build_f1_artifacts(
        root, values, raw_files, fault_records, repository_root=repository_root
    )
    evidence_path = root / "parsed/evidence_v4.json"
    save(evidence_path, evidence, exclusive=True)
    require(digest(evidence_path.read_bytes()) == vector["provenance"]["evidence_sha256"], "evidence persistence drift")
    save(root / "parsed/feature_vector_v2.json", vector, exclusive=True)
    return evidence, vector
