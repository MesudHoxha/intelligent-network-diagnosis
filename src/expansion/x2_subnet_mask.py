from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from pathlib import Path
from typing import Any

import yaml

from src.expansion.x2_addressing import X2AddressingError
from src.fault_injection.phase6_common import sha256_file


@dataclass(frozen=True)
class WrongSubnetMaskScenario:
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
    wrong_prefix_length: int
    expected_gateway: str
    destination_node: str
    destination_address: str
    duplicate_observer_node: str
    duplicate_observer_container: str
    duplicate_observer_interface: str

    @property
    def expected_interface(self) -> str:
        return f"{self.expected_address}/{self.expected_prefix_length}"

    @property
    def wrong_interface(self) -> str:
        return f"{self.expected_address}/{self.wrong_prefix_length}"

    @property
    def recovery_identity(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_sha256": self.sha256,
            "fault_type": "wrong_subnet_mask",
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


def _string(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value), f"{label} is required.")
    return str(value)


def load_wrong_subnet_mask_scenario(path: Path) -> WrongSubnetMaskScenario:
    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise X2AddressingError(f"Cannot read X2-R2 scenario: {path}") from error
    _require(isinstance(document, dict), "X2-R2 scenario must be an object.")
    _require(document.get("schema_version") == 1, "X2-R2 schema version drifted.")
    scenario = document.get("scenario")
    _require(isinstance(scenario, dict), "X2-R2 scenario object is missing.")
    assert isinstance(scenario, dict)
    _require(
        scenario.get("kind") == "fault"
        and scenario.get("truth_model") == "single_fault",
        "X2-R2 supports exactly one reviewed single fault.",
    )
    fault = scenario.get("fault")
    observation = scenario.get("observation")
    topology = scenario.get("topology")
    ground_truth = scenario.get("ground_truth")
    restoration = scenario.get("restoration")
    for value, label in (
        (fault, "fault"),
        (observation, "observation"),
        (topology, "topology"),
        (ground_truth, "ground_truth"),
        (restoration, "restoration"),
    ):
        _require(isinstance(value, dict), f"X2-R2 {label} binding is missing.")
    assert isinstance(fault, dict)
    assert isinstance(observation, dict)
    assert isinstance(topology, dict)
    assert isinstance(ground_truth, dict)
    assert isinstance(restoration, dict)
    _require(
        fault.get("type") == "wrong_subnet_mask"
        and fault.get("injector") == "replace_exact_source_prefix_length"
        and restoration.get("method")
        == "restore_exact_source_ipv4_address_and_routes",
        "X2-R2 fault or restoration mechanism drifted.",
    )
    _require(
        ground_truth.get("fault_type") == "wrong_subnet_mask"
        and ground_truth.get("fault_category") == "addressing"
        and ground_truth.get("fault_location") == fault.get("target_node"),
        "X2-R2 ground truth does not match the fault binding.",
    )
    parameters = fault.get("parameters")
    _require(isinstance(parameters, dict), "X2-R2 parameters are missing.")
    assert isinstance(parameters, dict)

    expected_address = _string(observation.get("expected_address"), "expected_address")
    expected_prefix = _string(observation.get("expected_prefix"), "expected_prefix")
    expected_length = observation.get("expected_prefix_length")
    wrong_length = parameters.get("wrong_prefix_length")
    _require(
        isinstance(expected_length, int)
        and not isinstance(expected_length, bool)
        and 0 <= expected_length <= 32,
        "expected_prefix_length is invalid.",
    )
    _require(
        isinstance(wrong_length, int)
        and not isinstance(wrong_length, bool)
        and 0 <= wrong_length <= 32
        and wrong_length != expected_length,
        "wrong_prefix_length must be a distinct valid prefix length.",
    )
    expected_gateway = _string(observation.get("expected_gateway"), "expected_gateway")
    destination_address = _string(
        observation.get("destination_address"), "destination_address"
    )
    try:
        expected_interface = IPv4Interface(f"{expected_address}/{expected_length}")
        wrong_interface = IPv4Interface(f"{expected_address}/{wrong_length}")
        expected_network = IPv4Network(expected_prefix)
        gateway = IPv4Address(expected_gateway)
        IPv4Address(destination_address)
    except ValueError as error:
        raise X2AddressingError("X2-R2 contains invalid IPv4 data.") from error
    _require(
        expected_interface.network == expected_network
        and expected_interface.ip == wrong_interface.ip
        and wrong_interface.network != expected_network
        and gateway in wrong_interface.network,
        "Wrong mask must preserve address identity and gateway reachability while changing prefix identity.",
    )
    _require(
        parameters.get("source_address") == expected_address
        and parameters.get("correct_prefix_length") == expected_length
        and parameters.get("source_interface") == observation.get("source_interface"),
        "X2-R2 mutation parameters drifted from observation context.",
    )

    return WrongSubnetMaskScenario(
        path=path,
        sha256=sha256_file(path),
        scenario=scenario,
        scenario_id=_string(scenario.get("id"), "scenario.id"),
        topology_id=_string(topology.get("id"), "topology.id"),
        topology_context_id=_string(topology.get("context_id"), "topology.context_id"),
        source_node=_string(observation.get("source_node"), "source_node"),
        source_container=_string(observation.get("source_container"), "source_container"),
        source_interface=_string(observation.get("source_interface"), "source_interface"),
        expected_address=expected_address,
        expected_prefix=expected_prefix,
        expected_prefix_length=expected_length,
        wrong_prefix_length=wrong_length,
        expected_gateway=expected_gateway,
        destination_node=_string(observation.get("destination_node"), "destination_node"),
        destination_address=destination_address,
        duplicate_observer_node=_string(
            observation.get("duplicate_observer_node"), "duplicate_observer_node"
        ),
        duplicate_observer_container=_string(
            observation.get("duplicate_observer_container"),
            "duplicate_observer_container",
        ),
        duplicate_observer_interface=_string(
            observation.get("duplicate_observer_interface"),
            "duplicate_observer_interface",
        ),
    )
