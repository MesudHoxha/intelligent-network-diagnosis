from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

from src.contracts.expansion import (
    validate_evidence_v4,
    validate_feature_vector_v2,
    validate_topology_context_v1,
)
from src.expansion.x3_vlan_not_allowed_on_trunk import (
    DEFAULT_EXECUTOR,
    VlanNotAllowedOnTrunkScenario,
    X3VlanNotAllowedOnTrunkError,
    bridge_fdb_inventory,
    bridge_vlan_inventory,
    is_pvid_untagged,
    link_inventory,
    load_vlan_not_allowed_on_trunk_scenario,
    ping_result,
    vlan_membership,
)
from src.fault_injection.phase6_common import (
    Phase6Executor,
    sha256_file,
    utc_now,
    write_json_atomic,
)


ROOT = Path(__file__).resolve().parents[2]
RAW_DIRECTORY = PurePosixPath("raw/v4/l2_vlan_state_collector")
EVIDENCE_PATH = PurePosixPath("parsed/evidence_v4.json")
VECTOR_PATH = PurePosixPath("parsed/feature_vector_v2.json")
FEATURE_IDS = (
    "access_vlan_matches_expected",
    "vlan_exists_on_target",
    "vlan_allowed_on_trunk",
    "native_vlan_matches_peer",
    "fdb_location_matches_expected",
)


def _load_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X3VlanNotAllowedOnTrunkError(f"Cannot read X3-R3 JSON object: {path}") from error
    if not isinstance(value, dict):
        raise X3VlanNotAllowedOnTrunkError(f"X3-R3 JSON artifact must be an object: {path}")
    return value


def _persist_raw(
    output_directory: Path,
    name: str,
    artifact: Mapping[str, object],
) -> tuple[str, str]:
    relative = str(RAW_DIRECTORY / f"{name}.json")
    path = output_directory / relative
    write_json_atomic(path, dict(artifact))
    return relative, sha256_file(path)


def _observation(
    value: bool | None,
    *,
    availability: str,
    raw_path: str,
    raw_hash: str,
) -> dict[str, object]:
    return {
        "value": value,
        "value_type": "boolean",
        "availability": availability,
        "collector_id": "l2_vlan_state_collector",
        "raw_artifact": raw_path,
        "raw_artifact_sha256": raw_hash,
    }


def _flags(vlan: Mapping[str, object] | None) -> set[str]:
    if vlan is None:
        return set()
    return {str(value).upper() for value in vlan.get("flags", [])}


def _is_tagged(vlan: Mapping[str, object] | None) -> bool:
    flags = _flags(vlan)
    return vlan is not None and "PVID" not in flags and "EGRESS UNTAGGED" not in flags


def _vlan_exists(rows: Sequence[object] | None, vlan_id: int) -> bool:
    if rows is None:
        return False
    return any(
        isinstance(vlan, Mapping) and vlan.get("vlan") == vlan_id
        for row in rows
        if isinstance(row, Mapping)
        for vlan in row.get("vlans", [])
    )


def _link_mac(rows: Sequence[object] | None) -> str | None:
    if rows is None or len(rows) != 1 or not isinstance(rows[0], Mapping):
        return None
    address = rows[0].get("address")
    return str(address).lower() if isinstance(address, str) else None


def _link_up(rows: Sequence[object] | None) -> bool:
    if rows is None or len(rows) != 1 or not isinstance(rows[0], Mapping):
        return False
    flags = {str(value).upper() for value in rows[0].get("flags", [])}
    return "UP" in flags


def _fdb_matches(
    rows: Sequence[object] | None,
    *,
    mac: str,
    interface: str,
    vlan_id: int,
) -> bool:
    if rows is None:
        return False
    return any(
        isinstance(row, Mapping)
        and str(row.get("mac", "")).lower() == mac
        # iproute2 emits ``ifname`` for ``bridge -j fdb show``.  Keep
        # ``dev`` compatibility for previously normalized executor output.
        and row.get("ifname", row.get("dev")) == interface
        and row.get("vlan") == vlan_id
        for row in rows
    )


def collect_vlan_not_allowed_on_trunk_evidence_v4(
    output_directory: Path,
    scenario_path: Path,
    *,
    executor: Phase6Executor = DEFAULT_EXECUTOR,
    repository_root: Path = ROOT,
) -> dict[str, object]:
    binding = load_vlan_not_allowed_on_trunk_scenario(scenario_path)
    output_directory = Path(output_directory)
    if (output_directory / EVIDENCE_PATH).exists() or (
        output_directory / RAW_DIRECTORY
    ).exists():
        raise X3VlanNotAllowedOnTrunkError("X3-R3 Evidence v4 output already exists.")

    started = utc_now()
    sw1_vlan_result, sw1_vlans = bridge_vlan_inventory(
        executor, binding.target_switch_container
    )
    sw2_vlan_result, sw2_vlans = bridge_vlan_inventory(
        executor, binding.peer_switch_container
    )
    vlan_path, vlan_hash = _persist_raw(
        output_directory,
        "bridge_vlan_state",
        {
            "schema_version": 1,
            "probe_id": "bridge_vlan_state_both_switches",
            "switches": [
                {
                    "node_id": binding.target_switch_node,
                    "container": binding.target_switch_container,
                    "command_result": sw1_vlan_result,
                },
                {
                    "node_id": binding.peer_switch_node,
                    "container": binding.peer_switch_container,
                    "command_result": sw2_vlan_result,
                },
            ],
        },
    )

    source_link_result, source_link_rows = link_inventory(
        executor, binding.source_container, binding.source_interface
    )
    target_link_result, target_link_rows = link_inventory(
        executor, binding.target_switch_container, binding.target_access_interface
    )
    sw1_trunk_link_result, sw1_trunk_link_rows = link_inventory(
        executor, binding.target_switch_container, binding.trunk_interface
    )
    sw2_trunk_link_result, sw2_trunk_link_rows = link_inventory(
        executor, binding.peer_switch_container, binding.trunk_interface
    )
    source_mac = _link_mac(source_link_rows)
    links_complete = all(
        rows is not None
        for rows in (
            source_link_rows,
            target_link_rows,
            sw1_trunk_link_rows,
            sw2_trunk_link_rows,
        )
    )
    links_up = all(
        _link_up(rows)
        for rows in (
            source_link_rows,
            target_link_rows,
            sw1_trunk_link_rows,
            sw2_trunk_link_rows,
        )
    )
    interface_path, interface_hash = _persist_raw(
        output_directory,
        "interface_state",
        {
            "schema_version": 1,
            "probe_id": "l2_interface_state",
            "source_mac": source_mac,
            "links_up": links_up,
            "command_results": [
                source_link_result,
                target_link_result,
                sw1_trunk_link_result,
                sw2_trunk_link_result,
            ],
        },
    )

    tagged_result, tagged_reachable = ping_result(
        executor, binding.source_container, binding.destination_address
    )
    native_result, native_reachable = ping_result(
        executor,
        binding.native_source_container,
        binding.native_destination_address,
    )
    active_path, active_hash = _persist_raw(
        output_directory,
        "active_flow_probe",
        {
            "schema_version": 1,
            "probe_id": "tagged_and_native_flow_effectiveness",
            "tagged_flow": {
                "source_node": binding.source_node,
                "destination_node": binding.destination_node,
                "reachable": tagged_reachable,
                "command_result": tagged_result,
            },
            "native_flow": {
                "source_node": binding.native_source_node,
                "destination_node": binding.native_destination_node,
                "reachable": native_reachable,
                "command_result": native_result,
            },
        },
    )

    sw1_fdb_result, sw1_fdb = bridge_fdb_inventory(
        executor, binding.target_switch_container, binding.bridge
    )
    sw2_fdb_result, sw2_fdb = bridge_fdb_inventory(
        executor, binding.peer_switch_container, binding.bridge
    )
    fdb_path, fdb_hash = _persist_raw(
        output_directory,
        "bridge_fdb_state",
        {
            "schema_version": 1,
            "probe_id": "bridge_fdb_state_both_switches",
            "source_mac": source_mac,
            "switches": [
                {
                    "node_id": binding.target_switch_node,
                    "container": binding.target_switch_container,
                    "command_result": sw1_fdb_result,
                },
                {
                    "node_id": binding.peer_switch_node,
                    "container": binding.peer_switch_container,
                    "command_result": sw2_fdb_result,
                },
            ],
        },
    )

    vlan_complete = sw1_vlans is not None and sw2_vlans is not None
    fdb_complete = source_mac is not None and sw1_fdb is not None and sw2_fdb is not None
    active_complete = tagged_result["return_code"] in {0, 1, 2} and native_result[
        "return_code"
    ] in {0, 1, 2}
    expected_access = vlan_membership(
        sw1_vlans, binding.target_access_interface, binding.expected_vlan
    )
    sw1_tagged = vlan_membership(
        sw1_vlans, binding.trunk_interface, binding.expected_vlan
    )
    sw2_tagged = vlan_membership(
        sw2_vlans, binding.trunk_interface, binding.expected_vlan
    )
    sw1_native = vlan_membership(
        sw1_vlans, binding.trunk_interface, binding.native_vlan
    )
    sw2_native = vlan_membership(
        sw2_vlans, binding.trunk_interface, binding.native_vlan
    )

    access_value = is_pvid_untagged(expected_access) if vlan_complete else None
    exists_value = _vlan_exists(sw1_vlans, binding.expected_vlan) if vlan_complete else None
    trunk_value = _is_tagged(sw1_tagged) and _is_tagged(sw2_tagged) if vlan_complete else None
    native_value = (
        is_pvid_untagged(sw1_native) and is_pvid_untagged(sw2_native)
        if vlan_complete
        else None
    )
    fdb_value = (
        _fdb_matches(
            sw1_fdb,
            mac=source_mac,
            interface=binding.target_access_interface,
            vlan_id=binding.expected_vlan,
        )
        if fdb_complete and source_mac is not None
        else None
    )

    observations = {
        "access_vlan_matches_expected": _observation(
            access_value,
            availability="observed" if vlan_complete else "collection_unavailable",
            raw_path=vlan_path,
            raw_hash=vlan_hash,
        ),
        "vlan_exists_on_target": _observation(
            exists_value,
            availability="observed" if vlan_complete else "collection_unavailable",
            raw_path=vlan_path,
            raw_hash=vlan_hash,
        ),
        "vlan_allowed_on_trunk": _observation(
            trunk_value,
            availability="observed" if vlan_complete else "collection_unavailable",
            raw_path=vlan_path,
            raw_hash=vlan_hash,
        ),
        "native_vlan_matches_peer": _observation(
            native_value,
            availability="observed" if vlan_complete else "collection_unavailable",
            raw_path=vlan_path,
            raw_hash=vlan_hash,
        ),
        "fdb_location_matches_expected": _observation(
            fdb_value,
            availability="observed" if fdb_complete else "collection_unavailable",
            raw_path=fdb_path,
            raw_hash=fdb_hash,
        ),
    }
    complete = (
        all(row["availability"] == "observed" for row in observations.values())
        and links_complete
        and links_up
        and active_complete
    )
    completed = utc_now()
    raw_artifacts = [
        {"path": vlan_path, "sha256": vlan_hash},
        {"path": interface_path, "sha256": interface_hash},
        {"path": active_path, "sha256": active_hash},
        {"path": fdb_path, "sha256": fdb_hash},
    ]
    run = {
        "schema_version": 1,
        "collector_id": "l2_vlan_state_collector",
        "collector_version": 3,
        "domain": "l2_vlan",
        "status": "completed" if complete else "partial",
        "started_at_utc": started,
        "completed_at_utc": completed,
        "feature_ids": list(FEATURE_IDS),
        "raw_artifacts": raw_artifacts,
        "errors": [] if complete else ["One or more X3-R3 observations are unavailable."],
    }
    evidence = {
        "schema_version": 4,
        "evidence_id": f"{binding.scenario_id.lower()}:evidence:v4",
        "topology_context_id": binding.topology_context_id,
        "collected_at_utc": completed,
        "observation_path": {
            "direction": binding.scenario["observation"]["direction"],
            "source_node": binding.source_node,
            "destination_node": binding.destination_node,
            "observer_nodes": [binding.target_switch_node, binding.peer_switch_node],
        },
        "collector_runs": [run],
        "observations": observations,
        "compatibility": {
            "origin": "native_v4",
            "source_schema_version": None,
            "source_artifact_sha256": None,
        },
    }
    context = _load_object(
        repository_root / binding.scenario["topology"]["context_file"]
    )
    catalog = _load_object(repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json")
    validate_topology_context_v1(context, repository_root=repository_root)
    if context["context_id"] != binding.topology_context_id:
        raise X3VlanNotAllowedOnTrunkError("X3-R3 topology context binding drifted.")
    roles = context["observation_roles"]
    if (
        roles["source"] != binding.source_node
        or roles["destination"] != binding.destination_node
        or roles["observers"] != [binding.target_switch_node, binding.peer_switch_node]
    ):
        raise X3VlanNotAllowedOnTrunkError("X3-R3 observation roles drifted from Topology Context v1.")
    validate_evidence_v4(evidence, catalog, repository_root=repository_root)
    write_json_atomic(output_directory / EVIDENCE_PATH, evidence)
    return evidence


def build_l2_vlan_feature_vector_v2(
    output_directory: Path,
    evidence: Mapping[str, object],
    *,
    repository_root: Path = ROOT,
) -> dict[str, object]:
    output_directory = Path(output_directory)
    evidence_path = output_directory / EVIDENCE_PATH
    vector_path = output_directory / VECTOR_PATH
    if not evidence_path.is_file():
        raise X3VlanNotAllowedOnTrunkError(
            "X3-R3 Evidence v4 must be persisted before vectorization."
        )
    if vector_path.exists():
        raise X3VlanNotAllowedOnTrunkError("X3-R3 Feature Vector v2 already exists.")
    observations = evidence.get("observations")
    if not isinstance(observations, Mapping):
        raise X3VlanNotAllowedOnTrunkError("X3-R3 Evidence v4 has no observations.")
    catalog_path = repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"
    catalog = _load_object(catalog_path)
    vector = {
        "schema_version": 2,
        "vector_id": f"{evidence['evidence_id']}:vector:v2",
        "catalog_id": catalog["catalog_id"],
        "evidence_id": evidence["evidence_id"],
        "values": {
            name: {
                "value": row["value"],
                "availability": row["availability"],
            }
            for name, row in observations.items()
            if isinstance(row, Mapping)
        },
        "mask_id": None,
        "provenance": {
            "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
            "feature_catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        },
    }
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    write_json_atomic(vector_path, vector)
    return vector
