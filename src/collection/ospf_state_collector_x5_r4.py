from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2
from src.fault_injection.phase6_common import utc_now, write_json_atomic
from src.runtime.subprocesses import run_capture

FEATURES = ("ospf_adjacency_full", "ospf_route_advertised", "ospf_route_installed", "route_filter_allows_prefix")
TARGET = {"router_id": "3.3.3.3", "address": "10.51.23.2", "interface": "eth2:10.51.23.1"}
CONTROL = {"router_id": "1.1.1.1", "address": "10.51.12.1", "interface": "eth1:10.51.12.2"}


def capture(command: list[str]) -> dict[str, object]:
    result = run_capture(command, timeout_seconds=90.0)
    return {"command": command, "return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def _neighbor_state(raw: str, identity: Mapping[str, str]) -> str | None:
    try:
        neighbors = json.loads(raw).get("neighbors", {})
    except json.JSONDecodeError:
        return None
    rows = neighbors.get(identity["router_id"], []) if isinstance(neighbors, Mapping) else []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, Mapping) and row.get("address") == identity["address"] and row.get("ifaceName") == identity["interface"]:
            return str(row.get("converged") or row.get("state") or "")
    return None


def target_state(r2_neighbor: Mapping[str, object]) -> dict[str, bool | str | None]:
    state = _neighbor_state(str(r2_neighbor.get("stdout", "")), TARGET)
    control = _neighbor_state(str(r2_neighbor.get("stdout", "")), CONTROL)
    return {"r2_r3_state": state, "r2_r3_full": state == "Full", "r1_r2_state": control, "r1_r2_full": control == "Full"}


def collect_x5_r4_evidence(root: Path, *, repository_root: Path) -> dict[str, object]:
    raw = root / "raw/v4/ospf_state_collector_targeted"
    raw.mkdir(parents=True)
    commands = {"neighbor_r2": ["docker", "exec", "clab-x5r1-r2", "vtysh", "-c", "show ip ospf neighbor json"], "neighbor_r1": ["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show ip ospf neighbor json"], "database": ["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show ip ospf database json"], "route": ["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show ip route 10.51.3.0/24 json"], "policy": ["docker", "exec", "clab-x5r1-r2", "vtysh", "-c", "show running-config"], "interface": ["docker", "exec", "clab-x5r1-r2", "ip", "link", "show", "eth2"], "static": ["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show running-config"], "acl": ["docker", "exec", "clab-x5r1-r1", "iptables", "-S"], "reachability": ["docker", "exec", "clab-x5r1-hosta", "ping", "-c", "1", "-W", "2", "10.51.3.2"]}
    records: dict[str, tuple[str, str, dict[str, object]]] = {}
    for name, command in commands.items():
        result = capture(command); path = raw / (name + ".json"); write_json_atomic(path, result)
        records[name] = (str(path.relative_to(root)), hashlib.sha256(path.read_bytes()).hexdigest(), result)
    state = target_state(records["neighbor_r2"][2])
    text = {name: str(row[2]["stdout"]) for name, row in records.items()}
    observed = all(row[2]["return_code"] == 0 for name, row in records.items() if name != "reachability")
    controls = {"target_r2_r3_non_full": not bool(state["r2_r3_full"]), "control_r1_r2_full": bool(state["r1_r2_full"]), "passive_eth2_present": "ip ospf passive" in text["policy"], "interface_healthy": "UP" in text["interface"], "no_static_override": "ip route 10.51.3.0/24" not in text["static"], "no_acl_block": "X5-R1-BLOCK" not in text["acl"], "route_absent": "ospf" not in text["route"].lower(), "target_lsa_absent": "3.3.3.3" not in text["database"], "reachability_failed": records["reachability"][2]["return_code"] != 0, **state}
    if not all(bool(controls[key]) for key in ("target_r2_r3_non_full", "control_r1_r2_full", "passive_eth2_present", "interface_healthy", "no_static_override", "no_acl_block", "route_absent", "target_lsa_absent", "reachability_failed")):
        raise RuntimeError("X5-R4 targeted C4 controls did not hold: " + json.dumps(controls, sort_keys=True))
    values = {"ospf_adjacency_full": bool(state["r2_r3_full"]), "ospf_route_advertised": not bool(controls["target_lsa_absent"]), "ospf_route_installed": not bool(controls["route_absent"]), "route_filter_allows_prefix": "X5-R2-SUPPRESS" not in text["policy"]}
    sources = {"ospf_adjacency_full": "neighbor_r2", "ospf_route_advertised": "database", "ospf_route_installed": "route", "route_filter_allows_prefix": "policy"}
    observations = {feature: {"value": value if observed else None, "value_type": "boolean", "availability": "observed" if observed else "collection_unavailable", "collector_id": "ospf_state_collector_targeted", "raw_artifact": records[sources[feature]][0], "raw_artifact_sha256": records[sources[feature]][1]} for feature, value in values.items()}
    evidence = {"schema_version": 4, "evidence_id": "x5_r4_targeted_ospf_adjacency:evidence:v4", "topology_context_id": "x5_top_01_ospf_dynamic_routing_context_v1", "collected_at_utc": utc_now(), "observation_path": {"direction": "hosta_to_hostb", "source_node": "hosta", "destination_node": "hostb", "observer_nodes": ["r1", "r2"]}, "collector_runs": [{"schema_version": 1, "collector_id": "ospf_state_collector_targeted", "collector_version": 2, "domain": "routing", "status": "completed" if observed else "partial", "started_at_utc": utc_now(), "completed_at_utc": utc_now(), "feature_ids": list(FEATURES), "raw_artifacts": [{"path": row[0], "sha256": row[1]} for row in records.values()], "errors": []}], "observations": observations, "compatibility": {"origin": "native_v4", "source_schema_version": None, "source_artifact_sha256": None}}
    catalog = json.loads((repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text()); validate_evidence_v4(evidence, catalog, repository_root=repository_root)
    write_json_atomic(root / "parsed/evidence_v4.json", evidence); write_json_atomic(root / "validation/targeted_adjacency_controls.json", controls)
    return evidence


def build_x5_r4_feature_vector(root: Path, evidence: Mapping[str, object], *, repository_root: Path) -> dict[str, object]:
    catalog_path = repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"; catalog = json.loads(catalog_path.read_text()); evidence_path = root / "parsed/evidence_v4.json"
    vector = {"schema_version": 2, "vector_id": str(evidence["evidence_id"]) + ":vector:v2", "catalog_id": catalog["catalog_id"], "evidence_id": evidence["evidence_id"], "values": {feature: {"value": evidence["observations"][feature]["value"], "availability": evidence["observations"][feature]["availability"]} for feature in FEATURES}, "mask_id": None, "provenance": {"evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(), "feature_catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest()}}
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root); write_json_atomic(root / "parsed/feature_vector_v2.json", vector); return vector
