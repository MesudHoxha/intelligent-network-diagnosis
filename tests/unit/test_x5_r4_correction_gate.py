"""Source-only X5-R4 correction tests; synthetic inputs are not runtime evidence."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from src.collection.ospf_state_collector_x5_r2 import build_x5_r2_feature_vector
from src.collection.ospf_state_collector_x5_r4 import target_state
from src.contracts.expansion import validate_evidence_v4
from src.expansion.x5_r4_gate import verify_x5_r4_gate
from src.fault_injection.phase6_common import write_json_atomic
from src.rules.ospf_rule_engine_x5_r4 import diagnose_route_suppression_v2_corrected


ROOT = Path(__file__).resolve().parents[2]
FEATURES = (
    "ospf_adjacency_full",
    "ospf_route_advertised",
    "ospf_route_installed",
    "route_filter_allows_prefix",
)


def _synthetic_source_vector(tmp_path: Path) -> dict[str, object]:
    """Build a valid, temporary vector solely for source-contract testing."""
    raw = tmp_path / "raw/v4/x5_r11_synthetic_source_test"
    records: dict[str, tuple[str, str]] = {}
    for feature in FEATURES:
        path = raw / (feature + ".json")
        write_json_atomic(path, {"synthetic_source_test_input": True, "feature": feature})
        relative = str(path.relative_to(tmp_path))
        records[feature] = (relative, hashlib.sha256(path.read_bytes()).hexdigest())
    values = {
        "ospf_adjacency_full": True,
        "ospf_route_advertised": False,
        "ospf_route_installed": False,
        "route_filter_allows_prefix": False,
    }
    evidence = {
        "schema_version": 4,
        "evidence_id": "x5_r11_synthetic_source_test_only:evidence:v4",
        "topology_context_id": "x5_r11_synthetic_source_test_only",
        "collected_at_utc": "2026-08-27T00:00:00+00:00",
        "observation_path": {
            "direction": "synthetic_source_to_synthetic_destination",
            "source_node": "synthetic_source",
            "destination_node": "synthetic_destination",
            "observer_nodes": ["synthetic_observer"],
        },
        "collector_runs": [{
            "schema_version": 1,
            "collector_id": "x5_r11_synthetic_source_test_collector",
            "collector_version": 1,
            "domain": "routing",
            "status": "completed",
            "started_at_utc": "2026-08-27T00:00:00+00:00",
            "completed_at_utc": "2026-08-27T00:00:00+00:00",
            "feature_ids": list(FEATURES),
            "raw_artifacts": [{"path": records[feature][0], "sha256": records[feature][1]} for feature in FEATURES],
            "errors": [],
        }],
        "observations": {
            feature: {
                "value": values[feature], "value_type": "boolean", "availability": "observed",
                "collector_id": "x5_r11_synthetic_source_test_collector",
                "raw_artifact": records[feature][0], "raw_artifact_sha256": records[feature][1],
            }
            for feature in FEATURES
        },
        "compatibility": {"origin": "native_v4", "source_schema_version": None, "source_artifact_sha256": None},
    }
    catalog = json.loads((ROOT / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text())
    validate_evidence_v4(evidence, catalog, repository_root=ROOT)
    write_json_atomic(tmp_path / "parsed/evidence_v4.json", evidence)
    return build_x5_r2_feature_vector(tmp_path, evidence, repository_root=ROOT)


def test_x5_r4_contract_is_hash_bound_and_preserves_historical_c4() -> None:
    assert verify_x5_r4_gate(ROOT)["corrections"]["x5_r2_marker"].endswith("NOT_AN_ATTACHED_FILTER")


def test_corrected_r2_unavailable_evidence_fails_closed(tmp_path: Path) -> None:
    vector = copy.deepcopy(_synthetic_source_vector(tmp_path))
    vector["values"]["ospf_route_installed"] = {"value": None, "availability": "collection_unavailable"}
    result = diagnose_route_suppression_v2_corrected(vector, repository_root=ROOT)
    assert result["status"] == "insufficient_evidence"
    assert result["evidence_assessment"]["completeness_ratio"] == 0.75


def test_targeted_adjacency_does_not_aggregate_another_full_neighbor() -> None:
    raw = {"stdout": json.dumps({"neighbors": {
        "3.3.3.3": [{"address": "10.51.23.2", "ifaceName": "eth2:10.51.23.1", "converged": "2-Way"}],
        "1.1.1.1": [{"address": "10.51.12.1", "ifaceName": "eth1:10.51.12.2", "converged": "Full"}],
    }})}
    assert target_state(raw) == {"r2_r3_state": "2-Way", "r2_r3_full": False, "r1_r2_state": "Full", "r1_r2_full": True}
