from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, X4DhcpServerUnavailableError
from src.fault_injection.phase6_common import sha256_file


class FirewallServiceBlockError(X4DhcpServerUnavailableError):
    """Raised when the bounded D5 firewall-policy slice fails closed."""


@dataclass(frozen=True)
class FirewallServiceBlockScenario:
    path: Path
    sha256: str
    scenario: dict[str, Any]
    scenario_id: str
    topology_id: str
    topology_context_id: str
    source_node: str
    source_container: str
    source_interface: str
    destination_node: str
    destination_container: str
    observer_container: str
    dhcp_container: str
    dns_container: str
    dns_server_address: str
    expected_dns_name: str
    expected_dns_answer: str
    expected_scope_prefix: str
    app_server_address: str
    service_protocol: str
    service_port: int
    firewall_chain: str
    firewall_comment: str

    @property
    def recovery_identity(self) -> dict[str, object]:
        return {"scenario_id": self.scenario_id, "scenario_sha256": self.sha256, "fault_type": "firewall_service_block", "target_node": self.destination_node, "target_container": self.destination_container, "service_protocol": self.service_protocol, "service_port": self.service_port, "firewall_chain": self.firewall_chain, "firewall_comment": self.firewall_comment}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value: raise FirewallServiceBlockError(name + " is required.")
    return value


def load_firewall_service_block_scenario(path: Path) -> FirewallServiceBlockScenario:
    try: document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error: raise FirewallServiceBlockError("Cannot read X4-R5 scenario.") from error
    scenario = document.get("scenario") if isinstance(document, dict) else None
    if not isinstance(scenario, dict) or document.get("schema_version") != 1: raise FirewallServiceBlockError("X4-R5 scenario schema drifted.")
    topology, observation, fault, truth, restoration = (scenario.get(name) for name in ("topology", "observation", "fault", "ground_truth", "restoration"))
    if not all(isinstance(value, dict) for value in (topology, observation, fault, truth, restoration)): raise FirewallServiceBlockError("X4-R5 scenario binding is incomplete.")
    assert isinstance(topology, dict) and isinstance(observation, dict) and isinstance(fault, dict) and isinstance(truth, dict) and isinstance(restoration, dict)
    if scenario.get("id") != "X4_R5_FIREWALL_SERVICE_BLOCK" or scenario.get("kind") != "fault" or scenario.get("truth_model") != "single_fault": raise FirewallServiceBlockError("X4-R5 identity drifted.")
    if fault.get("type") != "firewall_service_block" or fault.get("injector") != "insert_controlled_service_specific_firewall_rule" or restoration.get("method") != "remove_exact_injected_firewall_rule_and_verify_policy": raise FirewallServiceBlockError("X4-R5 reviewed mutation mechanism drifted.")
    if truth.get("fault_type") != fault.get("type") or truth.get("affected_resource") != "app_server_tcp_8080_policy": raise FirewallServiceBlockError("X4-R5 ground truth drifted.")
    address = _text(observation.get("dns_server_address"), "dns_server_address"); name = _text(observation.get("expected_dns_name"), "expected_dns_name"); expected = _text(observation.get("expected_dns_answer"), "expected_dns_answer"); scope = _text(observation.get("expected_scope_prefix"), "expected_scope_prefix"); app = _text(observation.get("app_server_address"), "app_server_address"); protocol = _text(observation.get("service_protocol"), "service_protocol"); chain = _text(observation.get("firewall_chain"), "firewall_chain"); comment = _text(observation.get("firewall_comment"), "firewall_comment"); port = observation.get("service_port")
    if (address, name, expected, scope, app, protocol, port, chain, comment) != ("10.40.0.3", "app.x4.test", "10.40.0.4", "10.40.0.", "10.40.0.4", "tcp", 8080, "INPUT", "X4-R5-SERVICE-BLOCK"): raise FirewallServiceBlockError("X4-R5 reviewed firewall identity drifted.")
    return FirewallServiceBlockScenario(Path(path), sha256_file(Path(path)), scenario, "X4_R5_FIREWALL_SERVICE_BLOCK", _text(topology.get("id"), "topology.id"), _text(topology.get("context_id"), "topology.context_id"), _text(observation.get("source_node"), "source_node"), _text(observation.get("source_container"), "source_container"), _text(observation.get("source_interface"), "source_interface"), _text(observation.get("destination_node"), "destination_node"), _text(observation.get("destination_container"), "destination_container"), _text(observation.get("observer_container"), "observer_container"), _text(observation.get("dhcp_container"), "dhcp_container"), _text(observation.get("dns_container"), "dns_container"), address, name, expected, scope, app, protocol, port, chain, comment)
