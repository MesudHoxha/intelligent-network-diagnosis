from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, X4DhcpServerUnavailableError
from src.fault_injection.phase6_common import sha256_file


class X4DnsServiceDownError(X4DhcpServerUnavailableError):
    """Raised when the bounded canonical D3 DNS slice fails closed."""


@dataclass(frozen=True)
class DnsServiceDownScenario:
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
    dns_container: str
    dhcp_container: str
    app_container: str
    expected_scope_prefix: str
    compatibility_alias: str
    dns_server_address: str
    expected_dns_name: str
    expected_dns_answer: str

    @property
    def recovery_identity(self) -> dict[str, object]:
        return {"scenario_id": self.scenario_id, "compatibility_alias": self.compatibility_alias, "scenario_sha256": self.sha256, "fault_type": "dns_service_down", "target_node": self.destination_node, "target_container": self.destination_container, "dns_server_address": self.dns_server_address, "expected_dns_name": self.expected_dns_name, "expected_dns_answer": self.expected_dns_answer}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise X4DnsServiceDownError(name + " is required.")
    return value


def load_dns_service_down_scenario(path: Path) -> DnsServiceDownScenario:
    try:
        document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise X4DnsServiceDownError("Cannot read canonical X4-R3 D3 scenario.") from error
    scenario = document.get("scenario") if isinstance(document, dict) else None
    if not isinstance(scenario, dict) or document.get("schema_version") != 1:
        raise X4DnsServiceDownError("X4-R3 scenario schema drifted.")
    topology, observation, fault, truth, restoration = (scenario.get(name) for name in ("topology", "observation", "fault", "ground_truth", "restoration"))
    if not all(isinstance(value, dict) for value in (topology, observation, fault, truth, restoration)):
        raise X4DnsServiceDownError("X4-R3 scenario binding is incomplete.")
    assert isinstance(topology, dict) and isinstance(observation, dict) and isinstance(fault, dict) and isinstance(truth, dict) and isinstance(restoration, dict)
    if scenario.get("id") != "X4_R3_DNS_SERVICE_DOWN" or scenario.get("compatibility_alias") != "X4_R3_DNS_SERVICE_UNAVAILABLE" or scenario.get("kind") != "fault" or scenario.get("truth_model") != "single_fault":
        raise X4DnsServiceDownError("X4-R3 canonical/alias identity drifted.")
    if fault.get("type") != "dns_service_down" or fault.get("injector") != "stop_dns_service_on_dns_server_only" or restoration.get("method") != "restore_exact_dns_process_and_zone_state":
        raise X4DnsServiceDownError("X4-R3 reviewed DNS mutation mechanism drifted.")
    if truth.get("fault_type") != fault.get("type") or truth.get("affected_resource") != "dns_service_endpoint_udp_53":
        raise X4DnsServiceDownError("X4-R3 ground truth drifted.")
    address = _text(observation.get("dns_server_address"), "dns_server_address"); name = _text(observation.get("expected_dns_name"), "expected_dns_name"); answer = _text(observation.get("expected_dns_answer"), "expected_dns_answer")
    if (address, name, answer) != ("10.40.0.3", "app.x4.test", "10.40.0.4"):
        raise X4DnsServiceDownError("X4-R3 reviewed DNS identity drifted.")
    return DnsServiceDownScenario(Path(path), sha256_file(Path(path)), scenario, "X4_R3_DNS_SERVICE_DOWN", _text(topology.get("id"), "topology.id"), _text(topology.get("context_id"), "topology.context_id"), _text(observation.get("source_node"), "source_node"), _text(observation.get("source_container"), "source_container"), _text(observation.get("source_interface"), "source_interface"), _text(observation.get("destination_node"), "destination_node"), _text(observation.get("destination_container"), "destination_container"), _text(observation.get("observer_container"), "observer_container"), _text(observation.get("dns_container"), "dns_container"), _text(observation.get("dhcp_container"), "dhcp_container"), _text(observation.get("app_container"), "app_container"), _text(observation.get("expected_scope_prefix"), "expected_scope_prefix"), "X4_R3_DNS_SERVICE_UNAVAILABLE", address, name, answer)
