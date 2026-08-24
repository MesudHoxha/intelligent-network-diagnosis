from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, DhcpServerUnavailableScenario, X4DhcpServerUnavailableError
from src.fault_injection.phase6_common import sha256_file


class X4DhcpPoolMisconfigurationError(X4DhcpServerUnavailableError):
    """Raised when the bounded X4-R2 DHCP pool slice fails closed."""


@dataclass(frozen=True)
class DhcpPoolMisconfigurationScenario(DhcpServerUnavailableScenario):
    expected_pool_line: str
    controlled_empty_pool_line: str

    @property
    def recovery_identity(self) -> dict[str, object]:
        return {"scenario_id": self.scenario_id, "scenario_sha256": self.sha256, "fault_type": "dhcp_pool_misconfiguration", "target_node": self.destination_node, "target_container": self.destination_container, "expected_pool_line": self.expected_pool_line, "controlled_empty_pool_line": self.controlled_empty_pool_line}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise X4DhcpPoolMisconfigurationError(name + " is required.")
    return value


def load_dhcp_pool_misconfiguration_scenario(path: Path) -> DhcpPoolMisconfigurationScenario:
    try:
        document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise X4DhcpPoolMisconfigurationError("Cannot read X4-R2 scenario.") from error
    scenario = document.get("scenario") if isinstance(document, dict) else None
    if not isinstance(scenario, dict) or document.get("schema_version") != 1:
        raise X4DhcpPoolMisconfigurationError("X4-R2 scenario schema drifted.")
    topology, observation, fault, truth, restoration = (scenario.get(name) for name in ("topology", "observation", "fault", "ground_truth", "restoration"))
    if not all(isinstance(value, dict) for value in (topology, observation, fault, truth, restoration)):
        raise X4DhcpPoolMisconfigurationError("X4-R2 scenario binding is incomplete.")
    assert isinstance(topology, dict) and isinstance(observation, dict) and isinstance(fault, dict) and isinstance(truth, dict) and isinstance(restoration, dict)
    if scenario.get("id") != "X4_R2_DHCP_POOL_MISCONFIGURATION" or scenario.get("kind") != "fault" or scenario.get("truth_model") != "single_fault":
        raise X4DhcpPoolMisconfigurationError("X4-R2 identity drifted.")
    if fault.get("type") != "dhcp_pool_misconfiguration" or fault.get("injector") != "replace_expected_dhcp_scope_with_controlled_empty_pool" or restoration.get("method") != "restore_exact_dhcp_scope_and_lease_database":
        raise X4DhcpPoolMisconfigurationError("X4-R2 reviewed mutation mechanism drifted.")
    if truth.get("fault_type") != fault.get("type") or truth.get("affected_resource") != "dhcp_pool_scope":
        raise X4DhcpPoolMisconfigurationError("X4-R2 ground truth drifted.")
    expected = _text(observation.get("expected_pool_line"), "expected_pool_line"); empty = _text(observation.get("controlled_empty_pool_line"), "controlled_empty_pool_line")
    if expected != "dhcp-range=10.40.0.100,10.40.0.150,255.255.255.0,1h" or empty != "dhcp-range=10.40.0.0,static":
        raise X4DhcpPoolMisconfigurationError("X4-R2 pool identities drifted.")
    return DhcpPoolMisconfigurationScenario(Path(path), sha256_file(Path(path)), scenario, "X4_R2_DHCP_POOL_MISCONFIGURATION", _text(topology.get("id"), "topology.id"), _text(topology.get("context_id"), "topology.context_id"), _text(observation.get("source_node"), "source_node"), _text(observation.get("source_container"), "source_container"), _text(observation.get("source_interface"), "source_interface"), _text(observation.get("destination_node"), "destination_node"), _text(observation.get("destination_container"), "destination_container"), _text(observation.get("observer_container"), "observer_container"), _text(observation.get("dns_container"), "dns_container"), _text(observation.get("app_container"), "app_container"), _text(observation.get("expected_scope_prefix"), "expected_scope_prefix"), expected, empty)
