from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any

import yaml

from src.expansion.x3_vlan_not_allowed_on_trunk import (
    DEFAULT_EXECUTOR,
    bridge_fdb_inventory,
    bridge_vlan_inventory,
    is_pvid_untagged,
    is_tagged,
    link_inventory,
    load_json_rows,
    ping_result,
    vlan_membership,
)
from src.fault_injection.phase6_common import Phase6FaultInjectionError, sha256_file


class X3NativeVlanMismatchError(Phase6FaultInjectionError):
    """Raised when the bounded X3-R4 native-VLAN slice fails closed."""


@dataclass(frozen=True)
class NativeVlanMismatchScenario:
    path: Path
    sha256: str
    scenario: dict[str, Any]
    scenario_id: str
    topology_id: str
    topology_context_id: str
    source_node: str
    source_container: str
    source_interface: str
    source_address: str
    destination_node: str
    destination_container: str
    destination_address: str
    tagged_source_container: str
    tagged_destination_address: str
    target_switch_node: str
    target_switch_container: str
    peer_switch_node: str
    peer_switch_container: str
    bridge: str
    target_access_interface: str
    trunk_interface: str
    expected_vlan: int
    tagged_control_vlan: int
    mismatched_native_vlan: int
    affected_resource: str

    @property
    def recovery_identity(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_sha256": self.sha256,
            "fault_type": "native_vlan_mismatch",
            "target_node": self.target_switch_node,
            "target_container": self.target_switch_container,
            "bridge": self.bridge,
            "trunk_interface": self.trunk_interface,
            "expected_vlan": self.expected_vlan,
            "mismatched_native_vlan": self.mismatched_native_vlan,
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X3NativeVlanMismatchError(message)


def _string(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value), f"{label} is required.")
    return str(value)


def _vlan(value: object, label: str) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 4094, f"{label} is invalid.")
    return int(value)


def load_native_vlan_mismatch_scenario(path: Path) -> NativeVlanMismatchScenario:
    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise X3NativeVlanMismatchError(f"Cannot read X3-R4 scenario: {path}") from error
    _require(isinstance(document, dict) and document.get("schema_version") == 1, "X3-R4 schema version drifted.")
    scenario = document.get("scenario")
    _require(isinstance(scenario, dict), "X3-R4 scenario is missing.")
    topology = scenario.get("topology")
    observation = scenario.get("observation")
    fault = scenario.get("fault")
    truth = scenario.get("ground_truth")
    restoration = scenario.get("restoration")
    _require(all(isinstance(value, dict) for value in (topology, observation, fault, truth, restoration)), "X3-R4 binding is missing.")
    assert isinstance(topology, dict) and isinstance(observation, dict) and isinstance(fault, dict) and isinstance(truth, dict) and isinstance(restoration, dict)
    parameters = fault.get("parameters")
    _require(isinstance(parameters, dict), "X3-R4 mutation parameters are missing.")
    expected = _vlan(observation.get("expected_vlan"), "expected_vlan")
    mismatch = _vlan(observation.get("mismatched_native_vlan"), "mismatched_native_vlan")
    tagged = _vlan(observation.get("tagged_control_vlan"), "tagged_control_vlan")
    _require(expected == 99 and mismatch == 98 and tagged == 10, "X3-R4 VLAN identities drifted.")
    _require(scenario.get("kind") == "fault" and scenario.get("truth_model") == "single_fault", "X3-R4 permits one reviewed single fault.")
    _require(fault.get("type") == "native_vlan_mismatch" and fault.get("injector") == "replace_native_pvid_on_one_trunk_endpoint_with_controlled_mismatch" and restoration.get("method") == "restore_exact_peer_native_pvid_and_tagging", "X3-R4 fault mechanism drifted.")
    _require(fault.get("target_node") == observation.get("target_switch_node") and fault.get("target_container") == observation.get("target_switch_container") and parameters.get("bridge") == observation.get("bridge") and parameters.get("trunk_interface") == observation.get("trunk_interface") and parameters.get("expected_vlan") == expected and parameters.get("mismatched_native_vlan") == mismatch, "X3-R4 mutation parameters drifted.")
    _require(truth.get("fault_category") == "l2_vlan" and truth.get("fault_type") == "native_vlan_mismatch" and truth.get("fault_location") == fault.get("target_node") and truth.get("affected_resource") == "eth3:native-vlan", "X3-R4 ground truth drifted.")
    for label in ("source_address", "destination_address", "tagged_destination_address"):
        try:
            IPv4Address(_string(observation.get(label), label))
        except ValueError as error:
            raise X3NativeVlanMismatchError("X3-R4 contains invalid IPv4 data.") from error
    return NativeVlanMismatchScenario(
        path=path, sha256=sha256_file(path), scenario=scenario,
        scenario_id=_string(scenario.get("id"), "scenario.id"), topology_id=_string(topology.get("id"), "topology.id"), topology_context_id=_string(topology.get("context_id"), "topology.context_id"),
        source_node=_string(observation.get("source_node"), "source_node"), source_container=_string(observation.get("source_container"), "source_container"), source_interface=_string(observation.get("source_interface"), "source_interface"), source_address=_string(observation.get("source_address"), "source_address"),
        destination_node=_string(observation.get("destination_node"), "destination_node"), destination_container=_string(observation.get("destination_container"), "destination_container"), destination_address=_string(observation.get("destination_address"), "destination_address"),
        tagged_source_container=_string(observation.get("tagged_source_container"), "tagged_source_container"), tagged_destination_address=_string(observation.get("tagged_destination_address"), "tagged_destination_address"),
        target_switch_node=_string(observation.get("target_switch_node"), "target_switch_node"), target_switch_container=_string(observation.get("target_switch_container"), "target_switch_container"), peer_switch_node=_string(observation.get("peer_switch_node"), "peer_switch_node"), peer_switch_container=_string(observation.get("peer_switch_container"), "peer_switch_container"),
        bridge=_string(observation.get("bridge"), "bridge"), target_access_interface=_string(observation.get("target_access_interface"), "target_access_interface"), trunk_interface=_string(observation.get("trunk_interface"), "trunk_interface"), expected_vlan=expected, tagged_control_vlan=tagged, mismatched_native_vlan=mismatch, affected_resource=_string(truth.get("affected_resource"), "affected_resource"),
    )


__all__ = [
    "DEFAULT_EXECUTOR", "NativeVlanMismatchScenario", "X3NativeVlanMismatchError",
    "bridge_fdb_inventory", "bridge_vlan_inventory", "is_pvid_untagged", "is_tagged",
    "link_inventory", "load_json_rows", "load_native_vlan_mismatch_scenario",
    "ping_result", "vlan_membership",
]
