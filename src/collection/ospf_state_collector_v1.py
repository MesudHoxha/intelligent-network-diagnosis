from __future__ import annotations

import hashlib, json
from pathlib import Path
from typing import Any

from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2
from src.fault_injection.phase6_common import utc_now, write_json_atomic
from src.runtime.subprocesses import run_capture

FEATURES = ("ospf_adjacency_full", "ospf_route_advertised", "ospf_route_installed", "route_filter_allows_prefix")

def _run(command: list[str]) -> dict[str, object]:
    result = run_capture(command, timeout_seconds=20.0)
    return {"command": command, "return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}

def collect_ospf_adjacency_evidence_v4(output: Path, *, repository_root: Path) -> dict[str, object]:
    output = Path(output); raw_dir = output / "raw/v4/ospf_state_collector"; raw_dir.mkdir(parents=True)
    commands = {
        "neighbor": ["docker", "exec", "clab-x5r1-r2", "vtysh", "-c", "show ip ospf neighbor json"],
        "database": ["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show ip ospf database json"],
        "route": ["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show ip route 10.51.3.0/24 json"],
        "policy": ["docker", "exec", "clab-x5r1-r2", "vtysh", "-c", "show running-config"],
        "interface": ["docker", "exec", "clab-x5r1-r2", "ip", "link", "show", "eth2"],
        "static": ["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show running-config"],
        "acl": ["docker", "exec", "clab-x5r1-r1", "iptables", "-S"],
        "reachability": ["docker", "exec", "clab-x5r1-hosta", "ping", "-c", "1", "-W", "2", "10.51.3.2"],
    }
    raw: dict[str, tuple[str, str, dict[str, object]]] = {}
    for name, command in commands.items():
        value = _run(command); path = raw_dir / (name + ".json"); write_json_atomic(path, value); raw[name] = (str(path.relative_to(output)), hashlib.sha256(path.read_bytes()).hexdigest(), value)
    text = {name: str(value[2]["stdout"]) for name, value in raw.items()}
    # A failed active end-to-end probe is the expected effectiveness control
    # after the adjacency mutation; it is not a collector failure.
    observed = all(value[2]["return_code"] == 0 for name, value in raw.items() if name != "reachability")
    values = {"ospf_adjacency_full": "Full" in text["neighbor"], "ospf_route_advertised": "10.51.3.0" in text["database"], "ospf_route_installed": "ospf" in text["route"].lower(), "route_filter_allows_prefix": "X5-R2-SUPPRESS" not in text["policy"]}
    observations = {name: {"value": value if observed else None, "value_type": "boolean", "availability": "observed" if observed else "collection_unavailable", "collector_id": "ospf_state_collector", "raw_artifact": raw["neighbor" if name == "ospf_adjacency_full" else "database" if name == "ospf_route_advertised" else "route" if name == "ospf_route_installed" else "policy"][0], "raw_artifact_sha256": raw["neighbor" if name == "ospf_adjacency_full" else "database" if name == "ospf_route_advertised" else "route" if name == "ospf_route_installed" else "policy"][1]} for name, value in values.items()}
    evidence = {"schema_version": 4, "evidence_id": "x5_r1_ospf_adjacency_failure:evidence:v4", "topology_context_id": "x5_top_01_ospf_dynamic_routing_context_v1", "collected_at_utc": utc_now(), "observation_path": {"direction": "hosta_to_hostb", "source_node": "hosta", "destination_node": "hostb", "observer_nodes": ["r1", "r2"]}, "collector_runs": [{"schema_version": 1, "collector_id": "ospf_state_collector", "collector_version": 1, "domain": "routing", "status": "completed" if observed else "partial", "started_at_utc": utc_now(), "completed_at_utc": utc_now(), "feature_ids": list(FEATURES), "raw_artifacts": [{"path": item[0], "sha256": item[1]} for item in raw.values()], "errors": []}], "observations": observations, "compatibility": {"origin": "native_v4", "source_schema_version": None, "source_artifact_sha256": None}}
    catalog = json.loads((repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text())
    validate_evidence_v4(evidence, catalog, repository_root=repository_root); write_json_atomic(output / "parsed/evidence_v4.json", evidence); return evidence

def build_ospf_feature_vector_v2(output: Path, evidence: dict[str, object], *, repository_root: Path) -> dict[str, object]:
    evidence_path = output / "parsed/evidence_v4.json"; catalog_path = repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"; catalog = json.loads(catalog_path.read_text())
    vector = {"schema_version": 2, "vector_id": str(evidence["evidence_id"]) + ":vector:v2", "catalog_id": catalog["catalog_id"], "evidence_id": evidence["evidence_id"], "values": {key: {"value": evidence["observations"][key]["value"], "availability": evidence["observations"][key]["availability"]} for key in FEATURES}, "mask_id": None, "provenance": {"evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(), "feature_catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest()}}
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root); write_json_atomic(output / "parsed/feature_vector_v2.json", vector); return vector
