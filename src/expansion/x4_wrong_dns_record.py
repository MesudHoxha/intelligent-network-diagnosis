from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, X4DhcpServerUnavailableError
from src.fault_injection.phase6_common import sha256_file


class X4WrongDnsRecordError(X4DhcpServerUnavailableError):
    """Raised when the bounded D4 DNS-record slice fails closed."""


@dataclass(frozen=True)
class WrongDnsRecordScenario:
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
    app_container: str
    dns_server_address: str
    expected_dns_name: str
    expected_dns_answer: str
    controlled_wrong_dns_answer: str
    expected_scope_prefix: str
    expected_record_line: str
    controlled_wrong_record_line: str

    @property
    def recovery_identity(self) -> dict[str, object]:
        return {"scenario_id": self.scenario_id, "scenario_sha256": self.sha256, "fault_type": "wrong_dns_record", "target_node": self.destination_node, "target_container": self.destination_container, "expected_record_line": self.expected_record_line, "controlled_wrong_record_line": self.controlled_wrong_record_line}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value: raise X4WrongDnsRecordError(name + " is required.")
    return value


def load_wrong_dns_record_scenario(path: Path) -> WrongDnsRecordScenario:
    try: document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error: raise X4WrongDnsRecordError("Cannot read X4-R4 scenario.") from error
    scenario = document.get("scenario") if isinstance(document, dict) else None
    if not isinstance(scenario, dict) or document.get("schema_version") != 1: raise X4WrongDnsRecordError("X4-R4 scenario schema drifted.")
    topology, observation, fault, truth, restoration = (scenario.get(name) for name in ("topology", "observation", "fault", "ground_truth", "restoration"))
    if not all(isinstance(value, dict) for value in (topology, observation, fault, truth, restoration)): raise X4WrongDnsRecordError("X4-R4 scenario binding is incomplete.")
    assert isinstance(topology, dict) and isinstance(observation, dict) and isinstance(fault, dict) and isinstance(truth, dict) and isinstance(restoration, dict)
    if scenario.get("id") != "X4_R4_WRONG_DNS_RECORD" or scenario.get("kind") != "fault" or scenario.get("truth_model") != "single_fault": raise X4WrongDnsRecordError("X4-R4 identity drifted.")
    if fault.get("type") != "wrong_dns_record" or fault.get("injector") != "replace_expected_dns_record_with_controlled_wrong_answer" or restoration.get("method") != "restore_exact_dns_zone_record_and_service_state": raise X4WrongDnsRecordError("X4-R4 reviewed mutation mechanism drifted.")
    if truth.get("fault_type") != fault.get("type") or truth.get("affected_resource") != "dns_record_app_x4_test": raise X4WrongDnsRecordError("X4-R4 ground truth drifted.")
    address = _text(observation.get("dns_server_address"), "dns_server_address"); name = _text(observation.get("expected_dns_name"), "expected_dns_name"); expected = _text(observation.get("expected_dns_answer"), "expected_dns_answer"); wrong = _text(observation.get("controlled_wrong_dns_answer"), "controlled_wrong_dns_answer"); expected_line = _text(observation.get("expected_record_line"), "expected_record_line"); wrong_line = _text(observation.get("controlled_wrong_record_line"), "controlled_wrong_record_line")
    if (address, name, expected, wrong, expected_line, wrong_line) != ("10.40.0.3", "app.x4.test", "10.40.0.4", "10.40.0.99", "address=/app.x4.test/10.40.0.4", "address=/app.x4.test/10.40.0.99"): raise X4WrongDnsRecordError("X4-R4 reviewed DNS record identity drifted.")
    return WrongDnsRecordScenario(Path(path), sha256_file(Path(path)), scenario, "X4_R4_WRONG_DNS_RECORD", _text(topology.get("id"), "topology.id"), _text(topology.get("context_id"), "topology.context_id"), _text(observation.get("source_node"), "source_node"), _text(observation.get("source_container"), "source_container"), _text(observation.get("source_interface"), "source_interface"), _text(observation.get("destination_node"), "destination_node"), _text(observation.get("destination_container"), "destination_container"), _text(observation.get("observer_container"), "observer_container"), _text(observation.get("dhcp_container"), "dhcp_container"), _text(observation.get("app_container"), "app_container"), address, name, expected, wrong, _text(observation.get("expected_scope_prefix"), "expected_scope_prefix"), expected_line, wrong_line)
