from __future__ import annotations

from pathlib import Path
from typing import Mapping

from src.collection.l2_vlan_state_collector_v3 import (
    EVIDENCE_PATH, FEATURE_IDS, RAW_DIRECTORY, ROOT, _fdb_matches, _link_mac,
    _link_up, _load_object, _observation, _persist_raw, _vlan_exists,
    build_l2_vlan_feature_vector_v2,
)
from src.contracts.expansion import validate_evidence_v4, validate_topology_context_v1
from src.expansion.x3_native_vlan_mismatch import (
    DEFAULT_EXECUTOR, X3NativeVlanMismatchError, bridge_fdb_inventory,
    bridge_vlan_inventory, is_pvid_untagged, is_tagged, link_inventory,
    load_native_vlan_mismatch_scenario, ping_result, vlan_membership,
)
from src.fault_injection.phase6_common import Phase6Executor, utc_now, write_json_atomic


def _carries(vlan: Mapping[str, object] | None) -> bool:
    return vlan is not None and (is_tagged(vlan) or is_pvid_untagged(vlan))


def collect_native_vlan_mismatch_evidence_v4(
    output_directory: Path, scenario_path: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR,
    repository_root: Path = ROOT,
) -> dict[str, object]:
    binding = load_native_vlan_mismatch_scenario(scenario_path)
    output = Path(output_directory)
    if (output / EVIDENCE_PATH).exists() or (output / RAW_DIRECTORY).exists():
        raise X3NativeVlanMismatchError("X3-R4 Evidence v4 output already exists.")
    started = utc_now()
    sw1_result, sw1 = bridge_vlan_inventory(executor, binding.target_switch_container)
    sw2_result, sw2 = bridge_vlan_inventory(executor, binding.peer_switch_container)
    vlan_path, vlan_hash = _persist_raw(output, "bridge_vlan_state", {"schema_version": 1, "probe_id": "bridge_vlan_state_both_switches", "switches": [{"node_id": binding.target_switch_node, "container": binding.target_switch_container, "command_result": sw1_result}, {"node_id": binding.peer_switch_node, "container": binding.peer_switch_container, "command_result": sw2_result}]})
    source_link_result, source_links = link_inventory(executor, binding.source_container, binding.source_interface)
    target_link_result, target_links = link_inventory(executor, binding.target_switch_container, binding.target_access_interface)
    sw1_link_result, sw1_links = link_inventory(executor, binding.target_switch_container, binding.trunk_interface)
    sw2_link_result, sw2_links = link_inventory(executor, binding.peer_switch_container, binding.trunk_interface)
    source_mac = _link_mac(source_links)
    links = (source_links, target_links, sw1_links, sw2_links)
    links_complete = all(row is not None for row in links)
    links_up = all(_link_up(row) for row in links)
    interface_path, interface_hash = _persist_raw(output, "interface_state", {"schema_version": 1, "probe_id": "l2_interface_state", "source_mac": source_mac, "links_up": links_up, "command_results": [source_link_result, target_link_result, sw1_link_result, sw2_link_result]})
    native_result, native_ok = ping_result(executor, binding.source_container, binding.destination_address)
    tagged_result, tagged_ok = ping_result(executor, binding.tagged_source_container, binding.tagged_destination_address)
    active_path, active_hash = _persist_raw(output, "active_flow_probe", {"schema_version": 1, "probe_id": "native_and_tagged_flow_effectiveness", "native_flow": {"source_node": binding.source_node, "destination_node": binding.destination_node, "reachable": native_ok, "command_result": native_result}, "tagged_control_flow": {"source_node": "hosta", "destination_node": "hostb", "reachable": tagged_ok, "command_result": tagged_result}})
    sw1_fdb_result, sw1_fdb = bridge_fdb_inventory(executor, binding.target_switch_container, binding.bridge)
    sw2_fdb_result, sw2_fdb = bridge_fdb_inventory(executor, binding.peer_switch_container, binding.bridge)
    fdb_path, fdb_hash = _persist_raw(output, "bridge_fdb_state", {"schema_version": 1, "probe_id": "bridge_fdb_state_both_switches", "source_mac": source_mac, "switches": [{"node_id": binding.target_switch_node, "container": binding.target_switch_container, "command_result": sw1_fdb_result}, {"node_id": binding.peer_switch_node, "container": binding.peer_switch_container, "command_result": sw2_fdb_result}]})
    vlan_complete = sw1 is not None and sw2 is not None
    fdb_complete = source_mac is not None and sw1_fdb is not None and sw2_fdb is not None
    access = vlan_membership(sw1, binding.target_access_interface, binding.expected_vlan)
    target_expected = vlan_membership(sw1, binding.trunk_interface, binding.expected_vlan)
    peer_expected = vlan_membership(sw2, binding.trunk_interface, binding.expected_vlan)
    target_mismatch = vlan_membership(sw1, binding.trunk_interface, binding.mismatched_native_vlan)
    values = {
        "access_vlan_matches_expected": is_pvid_untagged(access) if vlan_complete else None,
        "vlan_exists_on_target": _vlan_exists(sw1, binding.expected_vlan) if vlan_complete else None,
        "vlan_allowed_on_trunk": _carries(target_expected) and _carries(peer_expected) if vlan_complete else None,
        "native_vlan_matches_peer": is_pvid_untagged(target_expected) and is_pvid_untagged(peer_expected) and target_mismatch is None if vlan_complete else None,
        "fdb_location_matches_expected": _fdb_matches(sw1_fdb, mac=source_mac, interface=binding.target_access_interface, vlan_id=binding.expected_vlan) if fdb_complete and source_mac is not None else None,
    }
    observations = {name: _observation(value, availability="observed" if (vlan_complete if name != "fdb_location_matches_expected" else fdb_complete) else "collection_unavailable", raw_path=fdb_path if name == "fdb_location_matches_expected" else vlan_path, raw_hash=fdb_hash if name == "fdb_location_matches_expected" else vlan_hash) for name, value in values.items()}
    active_complete = native_result["return_code"] in {0, 1, 2} and tagged_result["return_code"] in {0, 1, 2}
    complete = all(row["availability"] == "observed" for row in observations.values()) and links_complete and links_up and active_complete
    completed = utc_now()
    raw_artifacts = [{"path": path, "sha256": digest} for path, digest in ((vlan_path, vlan_hash), (interface_path, interface_hash), (active_path, active_hash), (fdb_path, fdb_hash))]
    evidence = {"schema_version": 4, "evidence_id": f"{binding.scenario_id.lower()}:evidence:v4", "topology_context_id": binding.topology_context_id, "collected_at_utc": completed, "observation_path": {"direction": binding.scenario["observation"]["direction"], "source_node": binding.source_node, "destination_node": binding.destination_node, "observer_nodes": [binding.target_switch_node, binding.peer_switch_node]}, "collector_runs": [{"schema_version": 1, "collector_id": "l2_vlan_state_collector", "collector_version": 4, "domain": "l2_vlan", "status": "completed" if complete else "partial", "started_at_utc": started, "completed_at_utc": completed, "feature_ids": list(FEATURE_IDS), "raw_artifacts": raw_artifacts, "errors": [] if complete else ["One or more X3-R4 observations are unavailable."]}], "observations": observations, "compatibility": {"origin": "native_v4", "source_schema_version": None, "source_artifact_sha256": None}}
    context = _load_object(repository_root / binding.scenario["topology"]["context_file"])
    catalog = _load_object(repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json")
    validate_topology_context_v1(context, repository_root=repository_root)
    roles = context["observation_roles"]
    if context["context_id"] != binding.topology_context_id or roles != {"source": binding.source_node, "destination": binding.destination_node, "observers": [binding.target_switch_node, binding.peer_switch_node]}:
        raise X3NativeVlanMismatchError("X3-R4 native-flow observation roles drifted from Topology Context v1.")
    validate_evidence_v4(evidence, catalog, repository_root=repository_root)
    write_json_atomic(output / EVIDENCE_PATH, evidence)
    return evidence


__all__ = ["build_l2_vlan_feature_vector_v2", "collect_native_vlan_mismatch_evidence_v4"]
