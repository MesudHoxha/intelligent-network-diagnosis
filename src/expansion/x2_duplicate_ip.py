from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Interface, IPv4Network
from pathlib import Path
from typing import Any

import yaml

from src.expansion.x2_addressing import X2AddressingError
from src.fault_injection.phase6_common import sha256_file


@dataclass(frozen=True)
class DuplicateIPScenario:
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
    target_container: str
    parent_interface: str
    duplicate_interface: str
    duplicate_mac: str
    observer_namespace: str
    observer_interface: str
    observer_address: str

    @property
    def expected_interface(self) -> str:
        return f"{self.expected_address}/{self.expected_prefix_length}"

    @property
    def recovery_identity(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_sha256": self.sha256,
            "fault_type": "duplicate_ip",
            "target_container": self.target_container,
            "duplicate_interface": self.duplicate_interface,
            "observer_namespace": self.observer_namespace,
        }


def _need(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise X2AddressingError(f"X2-R4 {label} is required.")
    return value


def load_duplicate_ip_scenario(path: Path) -> DuplicateIPScenario:
    path = Path(path)
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise X2AddressingError(f"Cannot read X2-R4 scenario: {path}") from error
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise X2AddressingError("X2-R4 scenario contract drifted.")
    scenario = document.get("scenario")
    if not isinstance(scenario, dict):
        raise X2AddressingError("X2-R4 scenario object is missing.")
    fault, observation, topology = (scenario.get(k) for k in ("fault", "observation", "topology"))
    if not all(isinstance(v, dict) for v in (fault, observation, topology)):
        raise X2AddressingError("X2-R4 bindings are incomplete.")
    assert isinstance(fault, dict) and isinstance(observation, dict) and isinstance(topology, dict)
    parameters = fault.get("parameters")
    if fault.get("type") != "duplicate_ip" or not isinstance(parameters, dict):
        raise X2AddressingError("X2-R4 authorizes only duplicate_ip.")
    length = observation.get("expected_prefix_length")
    if not isinstance(length, int) or isinstance(length, bool):
        raise X2AddressingError("X2-R4 prefix length is invalid.")
    address = _need(observation.get("expected_address"), "expected_address")
    prefix = _need(observation.get("expected_prefix"), "expected_prefix")
    duplicate = _need(parameters.get("duplicate_address"), "duplicate_address")
    if IPv4Interface(f"{address}/{length}").network != IPv4Network(prefix):
        raise X2AddressingError("X2-R4 expected identity is inconsistent.")
    if IPv4Interface(duplicate) != IPv4Interface(f"{address}/{length}"):
        raise X2AddressingError("X2-R4 duplicate claimant must use the exact source IP/prefix.")
    return DuplicateIPScenario(
        path, sha256_file(path), scenario, _need(scenario.get("id"), "scenario.id"),
        _need(topology.get("id"), "topology.id"),
        _need(topology.get("context_id"), "topology.context_id"),
        _need(observation.get("source_node"), "source_node"),
        _need(observation.get("source_container"), "source_container"),
        _need(observation.get("source_interface"), "source_interface"), address, prefix,
        length, _need(observation.get("expected_gateway"), "expected_gateway"),
        _need(observation.get("destination_node"), "destination_node"),
        _need(observation.get("destination_address"), "destination_address"),
        _need(fault.get("target_container"), "target_container"),
        _need(parameters.get("parent_interface"), "parent_interface"),
        _need(parameters.get("duplicate_interface"), "duplicate_interface"),
        _need(parameters.get("duplicate_mac"), "duplicate_mac"),
        _need(parameters.get("observer_namespace"), "observer_namespace"),
        _need(parameters.get("observer_interface"), "observer_interface"),
        _need(parameters.get("observer_address"), "observer_address"),
    )
