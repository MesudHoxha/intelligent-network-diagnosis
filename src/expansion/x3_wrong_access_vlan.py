from __future__ import annotations

import json
from dataclasses import dataclass
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from src.fault_injection.phase6_common import (
    Phase6CommandResult,
    Phase6Executor,
    Phase6FaultInjectionError,
    docker_exec_result,
    execute_checked,
    sha256_file,
)


class X3WrongAccessVlanError(Phase6FaultInjectionError):
    """Raised when the scoped X3-R1 runtime fails closed."""


DEFAULT_EXECUTOR: Phase6Executor = docker_exec_result


@dataclass(frozen=True)
class WrongAccessVlanScenario:
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
    native_source_node: str
    native_source_container: str
    native_destination_node: str
    native_destination_address: str
    target_switch_node: str
    target_switch_container: str
    peer_switch_node: str
    peer_switch_container: str
    bridge: str
    target_access_interface: str
    peer_access_interface: str
    trunk_interface: str
    expected_vlan: int
    wrong_vlan: int
    native_vlan: int

    @property
    def recovery_identity(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_sha256": self.sha256,
            "fault_type": "wrong_access_vlan",
            "target_node": self.target_switch_node,
            "target_container": self.target_switch_container,
            "bridge": self.bridge,
            "access_interface": self.target_access_interface,
            "expected_vlan": self.expected_vlan,
            "wrong_vlan": self.wrong_vlan,
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X3WrongAccessVlanError(message)


def _string(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value), f"{label} is required.")
    return str(value)


def _vlan(value: object, label: str) -> int:
    _require(
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= 4094,
        f"{label} is invalid.",
    )
    return int(value)


def load_wrong_access_vlan_scenario(path: Path) -> WrongAccessVlanScenario:
    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise X3WrongAccessVlanError(f"Cannot read X3-R1 scenario: {path}") from error
    _require(isinstance(document, dict), "X3-R1 scenario must be an object.")
    _require(document.get("schema_version") == 1, "X3-R1 schema version drifted.")
    scenario = document.get("scenario")
    _require(isinstance(scenario, dict), "X3-R1 scenario object is missing.")
    assert isinstance(scenario, dict)
    _require(
        scenario.get("kind") == "fault"
        and scenario.get("truth_model") == "single_fault",
        "X3-R1 supports exactly one reviewed single fault.",
    )
    topology = scenario.get("topology")
    observation = scenario.get("observation")
    fault = scenario.get("fault")
    ground_truth = scenario.get("ground_truth")
    restoration = scenario.get("restoration")
    for value, label in (
        (topology, "topology"),
        (observation, "observation"),
        (fault, "fault"),
        (ground_truth, "ground_truth"),
        (restoration, "restoration"),
    ):
        _require(isinstance(value, dict), f"X3-R1 {label} binding is missing.")
    assert isinstance(topology, dict)
    assert isinstance(observation, dict)
    assert isinstance(fault, dict)
    assert isinstance(ground_truth, dict)
    assert isinstance(restoration, dict)
    parameters = fault.get("parameters")
    _require(isinstance(parameters, dict), "X3-R1 mutation parameters are missing.")
    assert isinstance(parameters, dict)

    expected_vlan = _vlan(observation.get("expected_vlan"), "expected_vlan")
    wrong_vlan = _vlan(parameters.get("wrong_vlan"), "wrong_vlan")
    native_vlan = _vlan(observation.get("native_vlan"), "native_vlan")
    _require(
        len({expected_vlan, wrong_vlan, native_vlan}) == 3,
        "Expected, wrong and native VLAN identities must be distinct.",
    )
    _require(
        fault.get("type") == "wrong_access_vlan"
        and fault.get("injector")
        == "replace_expected_access_pvid_with_controlled_wrong_vlan"
        and restoration.get("method")
        == "restore_exact_access_pvid_and_untagged_membership",
        "X3-R1 fault or restoration mechanism drifted.",
    )
    _require(
        fault.get("target_node") == observation.get("target_switch_node")
        and fault.get("target_container") == observation.get("target_switch_container")
        and parameters.get("bridge") == observation.get("bridge")
        and parameters.get("access_interface")
        == observation.get("target_access_interface")
        and parameters.get("expected_vlan") == expected_vlan,
        "X3-R1 mutation parameters drifted from observation context.",
    )
    _require(
        ground_truth.get("fault_category") == "l2_vlan"
        and ground_truth.get("fault_type") == "wrong_access_vlan"
        and ground_truth.get("fault_location") == fault.get("target_node"),
        "X3-R1 ground truth does not match the fault binding.",
    )
    source_address = _string(observation.get("source_address"), "source_address")
    destination_address = _string(
        observation.get("destination_address"), "destination_address"
    )
    native_destination_address = _string(
        observation.get("native_destination_address"),
        "native_destination_address",
    )
    try:
        IPv4Address(source_address)
        IPv4Address(destination_address)
        IPv4Address(native_destination_address)
    except ValueError as error:
        raise X3WrongAccessVlanError("X3-R1 contains invalid IPv4 data.") from error

    return WrongAccessVlanScenario(
        path=path,
        sha256=sha256_file(path),
        scenario=scenario,
        scenario_id=_string(scenario.get("id"), "scenario.id"),
        topology_id=_string(topology.get("id"), "topology.id"),
        topology_context_id=_string(topology.get("context_id"), "topology.context_id"),
        source_node=_string(observation.get("source_node"), "source_node"),
        source_container=_string(observation.get("source_container"), "source_container"),
        source_interface=_string(observation.get("source_interface"), "source_interface"),
        source_address=source_address,
        destination_node=_string(observation.get("destination_node"), "destination_node"),
        destination_container=_string(
            observation.get("destination_container"), "destination_container"
        ),
        destination_address=destination_address,
        native_source_node=_string(
            observation.get("native_source_node"), "native_source_node"
        ),
        native_source_container=_string(
            observation.get("native_source_container"),
            "native_source_container",
        ),
        native_destination_node=_string(
            observation.get("native_destination_node"),
            "native_destination_node",
        ),
        native_destination_address=native_destination_address,
        target_switch_node=_string(
            observation.get("target_switch_node"), "target_switch_node"
        ),
        target_switch_container=_string(
            observation.get("target_switch_container"), "target_switch_container"
        ),
        peer_switch_node=_string(
            observation.get("peer_switch_node"), "peer_switch_node"
        ),
        peer_switch_container=_string(
            observation.get("peer_switch_container"), "peer_switch_container"
        ),
        bridge=_string(observation.get("bridge"), "bridge"),
        target_access_interface=_string(
            observation.get("target_access_interface"), "target_access_interface"
        ),
        peer_access_interface=_string(
            observation.get("peer_access_interface"), "peer_access_interface"
        ),
        trunk_interface=_string(
            observation.get("trunk_interface"), "trunk_interface"
        ),
        expected_vlan=expected_vlan,
        wrong_vlan=wrong_vlan,
        native_vlan=native_vlan,
    )


def load_json_rows(result: Mapping[str, object]) -> list[object] | None:
    if result.get("return_code") != 0:
        return None
    try:
        value = json.loads(str(result.get("stdout", "")))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, list) else None


def bridge_vlan_inventory(
    executor: Phase6Executor,
    container: str,
    interface: str | None = None,
) -> tuple[Phase6CommandResult, list[object] | None]:
    command: list[str] = ["bridge", "-j", "vlan", "show"]
    if interface is not None:
        command.extend(["dev", interface])
    result = execute_checked(executor, container, command)
    return result, load_json_rows(result)


def bridge_fdb_inventory(
    executor: Phase6Executor,
    container: str,
    bridge: str,
) -> tuple[Phase6CommandResult, list[object] | None]:
    result = execute_checked(
        executor, container, ["bridge", "-j", "fdb", "show", "br", bridge]
    )
    return result, load_json_rows(result)


def link_inventory(
    executor: Phase6Executor,
    container: str,
    interface: str,
) -> tuple[Phase6CommandResult, list[object] | None]:
    result = execute_checked(executor, container, ["ip", "-j", "link", "show", "dev", interface])
    return result, load_json_rows(result)


def ping_result(
    executor: Phase6Executor,
    container: str,
    destination: str,
) -> tuple[Phase6CommandResult, bool]:
    result = execute_checked(executor, container, ["ping", "-c", "2", "-W", "1", destination])
    return result, result["return_code"] == 0


def vlan_membership(
    rows: Sequence[object] | None,
    interface: str,
    vlan_id: int,
) -> Mapping[str, object] | None:
    if rows is None:
        return None
    for row in rows:
        if not isinstance(row, Mapping) or row.get("ifname") != interface:
            continue
        for vlan in row.get("vlans", []):
            if isinstance(vlan, Mapping) and vlan.get("vlan") == vlan_id:
                return vlan
    return None


def is_pvid_untagged(vlan: Mapping[str, object] | None) -> bool:
    if vlan is None:
        return False
    flags = {str(value).upper() for value in vlan.get("flags", [])}
    return "PVID" in flags and "EGRESS UNTAGGED" in flags


def is_tagged(vlan: Mapping[str, object] | None) -> bool:
    if vlan is None:
        return False
    flags = {str(value).upper() for value in vlan.get("flags", [])}
    return "PVID" not in flags and "EGRESS UNTAGGED" not in flags
