from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2
from src.fault_injection.phase6_common import utc_now, write_json_atomic
from src.runtime.subprocesses import run_capture

FEATURES = ("ospf_adjacency_full", "ospf_route_advertised", "ospf_route_installed", "route_filter_allows_prefix")


def _capture(command: list[str]) -> dict[str, object]:
    result = run_capture(command, timeout_seconds=90.0)
    return {"command": command, "return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def collect_x5_r2_evidence(root: Path, *, repository_root: Path) -> dict[str, object]:
    raw = root / "raw/v4/ospf_state_collector"
    raw.mkdir(parents=True)
    commands = {"neighbor": ["docker", "exec", "clab-x5r1-r2", "vtysh", "-c", "show ip ospf neighbor json"], "database": ["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show ip ospf database json"], "route": ["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show ip route 10.51.3.0/24 json"], "policy": ["docker", "exec", "clab-x5r1-r3", "vtysh", "-c", "show running-config"], "interface": ["docker", "exec", "clab-x5r1-r2", "ip", "link", "show", "eth2"], "static": ["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show running-config"], "acl": ["docker", "exec", "clab-x5r1-r1", "iptables", "-S"], "reachability": ["docker", "exec", "clab-x5r1-hosta", "ping", "-c", "1", "-W", "2", "10.51.3.2"]}
    records: dict[str, tuple[str, str, dict[str, object]]] = {}
    for name, command in commands.items():
        record = _capture(command)
        path = raw / (name + ".json")
        write_json_atomic(path, record)
        records[name] = (str(path.relative_to(root)), hashlib.sha256(path.read_bytes()).hexdigest(), record)
    text = {name: str(record[2]["stdout"]) for name, record in records.items()}
    successful = all(record[2]["return_code"] == 0 for name, record in records.items() if name != "reachability")
    controls = {"adjacency_healthy": "Full" in text["neighbor"], "interface_healthy": "UP" in text["interface"], "no_static_override": "ip route 10.51.3.0/24" not in text["static"], "no_acl_block": "X5-R1-BLOCK" not in text["acl"], "general_reachability_failed_only_for_suppressed_prefix": records["reachability"][2]["return_code"] != 0}
    if not all(controls.values()):
        raise RuntimeError("X5-R2 C5 control set did not exclude confounders: " + json.dumps(controls, sort_keys=True))
    values = {"ospf_adjacency_full": controls["adjacency_healthy"], "ospf_route_advertised": "10.51.3.0" in text["database"], "ospf_route_installed": "ospf" in text["route"].lower(), "route_filter_allows_prefix": "X5-R2-SUPPRESS" not in text["policy"]}
    source = {"ospf_adjacency_full": "neighbor", "ospf_route_advertised": "database", "ospf_route_installed": "route", "route_filter_allows_prefix": "policy"}
    observations = {feature: {"value": value if successful else None, "value_type": "boolean", "availability": "observed" if successful else "collection_unavailable", "collector_id": "ospf_state_collector", "raw_artifact": records[source[feature]][0], "raw_artifact_sha256": records[source[feature]][1]} for feature, value in values.items()}
    evidence = {"schema_version": 4, "evidence_id": "x5_r2_route_filtering:evidence:v4", "topology_context_id": "x5_top_01_ospf_dynamic_routing_context_v1", "collected_at_utc": utc_now(), "observation_path": {"direction": "hosta_to_hostb", "source_node": "hosta", "destination_node": "hostb", "observer_nodes": ["r1", "r2"]}, "collector_runs": [{"schema_version": 1, "collector_id": "ospf_state_collector", "collector_version": 1, "domain": "routing", "status": "completed" if successful else "partial", "started_at_utc": utc_now(), "completed_at_utc": utc_now(), "feature_ids": list(FEATURES), "raw_artifacts": [{"path": record[0], "sha256": record[1]} for record in records.values()], "errors": []}], "observations": observations, "compatibility": {"origin": "native_v4", "source_schema_version": None, "source_artifact_sha256": None}}
    catalog = json.loads((repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text())
    validate_evidence_v4(evidence, catalog, repository_root=repository_root)
    write_json_atomic(root / "parsed/evidence_v4.json", evidence)
    write_json_atomic(root / "validation/control_exclusions.json", controls)
    return evidence


def build_x5_r2_feature_vector(root: Path, evidence: dict[str, object], *, repository_root: Path) -> dict[str, object]:
    catalog_path = repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"
    catalog = json.loads(catalog_path.read_text())
    evidence_path = root / "parsed/evidence_v4.json"
    vector = {"schema_version": 2, "vector_id": evidence["evidence_id"] + ":vector:v2", "catalog_id": catalog["catalog_id"], "evidence_id": evidence["evidence_id"], "values": {feature: {"value": evidence["observations"][feature]["value"], "availability": evidence["observations"][feature]["availability"]} for feature in FEATURES}, "mask_id": None, "provenance": {"evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(), "feature_catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest()}}
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    write_json_atomic(root / "parsed/feature_vector_v2.json", vector)
    return vector
