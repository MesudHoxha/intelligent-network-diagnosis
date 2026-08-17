from __future__ import annotations

import json
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
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


class X2AddressingError(Phase6FaultInjectionError):
    """Raised when the scoped X2 addressing runtime fails closed."""


@dataclass(frozen=True)
class WrongIpScenario:
    path: Path
    sha256: str
    scenario: dict[str, Any]
    scenario_id: str
    topology_id: str
    topology_context_id: str
    source_node: str
    source_container: str
    source_interface: str
    expected_address: str
    expected_prefix: str
    expected_prefix_length: int
    expected_gateway: str
    destination_node: str
    destination_address: str
    duplicate_observer_node: str
    duplicate_observer_container: str
    duplicate_observer_interface: str
    wrong_address: str

    @property
    def expected_interface(self) -> str:
        return f"{self.expected_address}/{self.expected_prefix_length}"

    @property
    def wrong_interface(self) -> str:
        return f"{self.wrong_address}/{self.expected_prefix_length}"

    @property
    def recovery_identity(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_sha256": self.sha256,
            "fault_type": "wrong_ip_address",
            "target_node": self.source_node,
            "target_container": self.source_container,
            "source_interface": self.source_interface,
            "expected_interface": self.expected_interface,
            "wrong_interface": self.wrong_interface,
            "expected_gateway": self.expected_gateway,
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X2AddressingError(message)


def _required_string(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value), f"{label} is required.")
    return str(value)


def load_wrong_ip_scenario(path: Path) -> WrongIpScenario:
    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise X2AddressingError(f"Cannot read X2-R1 scenario: {path}") from error
    _require(isinstance(document, dict), "X2-R1 scenario must be an object.")
    _require(document.get("schema_version") == 1, "X2-R1 schema version drifted.")
    scenario = document.get("scenario")
    _require(isinstance(scenario, dict), "X2-R1 scenario object is missing.")
    assert isinstance(scenario, dict)
    _require(
        scenario.get("kind") == "fault"
        and scenario.get("truth_model") == "single_fault",
        "X2-R1 supports exactly one reviewed single fault.",
    )
    fault = scenario.get("fault")
    observation = scenario.get("observation")
    topology = scenario.get("topology")
    ground_truth = scenario.get("ground_truth")
    restoration = scenario.get("restoration")
    _require(isinstance(fault, dict), "X2-R1 fault binding is missing.")
    _require(isinstance(observation, dict), "X2-R1 observation binding is missing.")
    _require(isinstance(topology, dict), "X2-R1 topology binding is missing.")
    _require(isinstance(ground_truth, dict), "X2-R1 ground truth is missing.")
    _require(isinstance(restoration, dict), "X2-R1 restoration binding is missing.")
    assert isinstance(fault, dict)
    assert isinstance(observation, dict)
    assert isinstance(topology, dict)
    assert isinstance(ground_truth, dict)
    assert isinstance(restoration, dict)
    _require(
        fault.get("type") == "wrong_ip_address"
        and fault.get("injector") == "replace_exact_source_ipv4_address"
        and restoration.get("method") == "restore_exact_source_ipv4_address_and_routes",
        "X2-R1 fault or restoration mechanism drifted.",
    )
    _require(
        ground_truth.get("fault_type") == "wrong_ip_address"
        and ground_truth.get("fault_category") == "addressing"
        and ground_truth.get("fault_location") == fault.get("target_node"),
        "X2-R1 ground truth does not match the fault binding.",
    )
    parameters = fault.get("parameters")
    _require(isinstance(parameters, dict), "X2-R1 parameters are missing.")
    assert isinstance(parameters, dict)

    expected_address = _required_string(
        observation.get("expected_address"), "expected_address"
    )
    expected_prefix = _required_string(
        observation.get("expected_prefix"), "expected_prefix"
    )
    expected_prefix_length = observation.get("expected_prefix_length")
    _require(
        isinstance(expected_prefix_length, int)
        and not isinstance(expected_prefix_length, bool)
        and 0 <= expected_prefix_length <= 32,
        "expected_prefix_length is invalid.",
    )
    wrong_address = _required_string(parameters.get("wrong_address"), "wrong_address")
    expected_gateway = _required_string(
        observation.get("expected_gateway"), "expected_gateway"
    )
    try:
        expected_interface = IPv4Interface(
            f"{expected_address}/{expected_prefix_length}"
        )
        wrong_interface = IPv4Interface(
            f"{wrong_address}/{expected_prefix_length}"
        )
        network = IPv4Network(expected_prefix)
        IPv4Address(expected_gateway)
        IPv4Address(_required_string(
            observation.get("destination_address"), "destination_address"
        ))
    except ValueError as error:
        raise X2AddressingError("X2-R1 contains invalid IPv4 data.") from error
    _require(
        expected_interface.network == network
        and wrong_interface.network == network
        and expected_interface.ip != wrong_interface.ip,
        "Wrong IP must change only address identity inside the expected prefix.",
    )
    _require(
        parameters.get("correct_address") == expected_address
        and parameters.get("prefix_length") == expected_prefix_length
        and parameters.get("source_interface") == observation.get("source_interface"),
        "X2-R1 mutation parameters drifted from observation context.",
    )

    return WrongIpScenario(
        path=path,
        sha256=sha256_file(path),
        scenario=scenario,
        scenario_id=_required_string(scenario.get("id"), "scenario.id"),
        topology_id=_required_string(topology.get("id"), "topology.id"),
        topology_context_id=_required_string(
            topology.get("context_id"), "topology.context_id"
        ),
        source_node=_required_string(observation.get("source_node"), "source_node"),
        source_container=_required_string(
            observation.get("source_container"), "source_container"
        ),
        source_interface=_required_string(
            observation.get("source_interface"), "source_interface"
        ),
        expected_address=expected_address,
        expected_prefix=expected_prefix,
        expected_prefix_length=expected_prefix_length,
        expected_gateway=expected_gateway,
        destination_node=_required_string(
            observation.get("destination_node"), "destination_node"
        ),
        destination_address=_required_string(
            observation.get("destination_address"), "destination_address"
        ),
        duplicate_observer_node=_required_string(
            observation.get("duplicate_observer_node"), "duplicate_observer_node"
        ),
        duplicate_observer_container=_required_string(
            observation.get("duplicate_observer_container"),
            "duplicate_observer_container",
        ),
        duplicate_observer_interface=_required_string(
            observation.get("duplicate_observer_interface"),
            "duplicate_observer_interface",
        ),
        wrong_address=wrong_address,
    )


def load_json_rows(result: Mapping[str, object]) -> list[object] | None:
    if result.get("return_code") != 0:
        return None
    try:
        value = json.loads(str(result.get("stdout", "")))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, list) else None


def address_inventory(
    executor: Phase6Executor,
    binding: WrongIpScenario,
) -> tuple[Phase6CommandResult, tuple[str, ...]]:
    result = execute_checked(
        executor,
        binding.source_container,
        ["ip", "-j", "-4", "addr", "show", "dev", binding.source_interface],
    )
    rows = load_json_rows(result)
    addresses: list[str] = []
    if rows is not None:
        for row in rows:
            if not isinstance(row, dict):
                continue
            for item in row.get("addr_info", []):
                if (
                    isinstance(item, dict)
                    and item.get("family") == "inet"
                    and isinstance(item.get("local"), str)
                    and isinstance(item.get("prefixlen"), int)
                ):
                    addresses.append(f"{item['local']}/{item['prefixlen']}")
    return result, tuple(sorted(addresses))


def default_route_inventory(
    executor: Phase6Executor,
    binding: WrongIpScenario,
) -> tuple[Phase6CommandResult, tuple[tuple[str | None, str | None], ...]]:
    result = execute_checked(
        executor,
        binding.source_container,
        ["ip", "-j", "route", "show", "default"],
    )
    rows = load_json_rows(result)
    routes: list[tuple[str | None, str | None]] = []
    if rows is not None:
        for row in rows:
            if isinstance(row, dict) and row.get("dst", "default") == "default":
                gateway = row.get("gateway")
                interface = row.get("dev")
                routes.append(
                    (
                        gateway if isinstance(gateway, str) else None,
                        interface if isinstance(interface, str) else None,
                    )
                )
    return result, tuple(routes)


def ping_result(
    executor: Phase6Executor,
    container: str,
    address: str,
) -> tuple[Phase6CommandResult, bool | None]:
    result = execute_checked(
        executor,
        container,
        ["ping", "-c", "2", "-W", "1", address],
    )
    reachable = True if result["return_code"] == 0 else False if result["return_code"] == 1 else None
    return result, reachable


DEFAULT_EXECUTOR = docker_exec_result

