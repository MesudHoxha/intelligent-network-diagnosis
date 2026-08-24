from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

from src.fault_injection.phase6_common import Phase6Executor, Phase6FaultInjectionError, docker_exec_result, execute_checked, sha256_file


DEFAULT_EXECUTOR: Phase6Executor = docker_exec_result


class X4DhcpServerUnavailableError(Phase6FaultInjectionError):
    """Raised when the isolated X4-R1 DHCP service slice fails closed."""


@dataclass(frozen=True)
class DhcpServerUnavailableScenario:
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
    app_container: str
    expected_scope_prefix: str

    @property
    def recovery_identity(self) -> dict[str, object]:
        return {"scenario_id": self.scenario_id, "scenario_sha256": self.sha256, "fault_type": "dhcp_server_unavailable", "target_node": self.destination_node, "target_container": self.destination_container}


def _require(value: bool, message: str) -> None:
    if not value:
        raise X4DhcpServerUnavailableError(message)


def _text(value: object, label: str) -> str:
    _require(isinstance(value, str) and bool(value), label + " is required.")
    return str(value)


def load_dhcp_server_unavailable_scenario(path: Path) -> DhcpServerUnavailableScenario:
    try:
        document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise X4DhcpServerUnavailableError("Cannot read X4-R1 scenario.") from error
    scenario = document.get("scenario") if isinstance(document, dict) else None
    _require(isinstance(scenario, dict) and document.get("schema_version") == 1, "X4-R1 scenario schema drifted.")
    topology, observation, fault, truth, restoration = (scenario.get(name) for name in ("topology", "observation", "fault", "ground_truth", "restoration"))
    _require(all(isinstance(item, dict) for item in (topology, observation, fault, truth, restoration)), "X4-R1 scenario binding is incomplete.")
    assert isinstance(topology, dict) and isinstance(observation, dict) and isinstance(fault, dict) and isinstance(truth, dict) and isinstance(restoration, dict)
    _require(scenario.get("id") == "X4_R1_DHCP_SERVER_UNAVAILABLE" and scenario.get("kind") == "fault" and scenario.get("truth_model") == "single_fault", "X4-R1 scenario identity drifted.")
    _require(fault.get("type") == "dhcp_server_unavailable" and fault.get("injector") == "stop_real_dhcp_service_on_dhcp_server_only" and restoration.get("method") == "restart_same_real_dhcp_service_and_confirm_lease", "X4-R1 service mechanism drifted.")
    _require(truth.get("fault_type") == fault.get("type") and truth.get("fault_location") == fault.get("target_node") and truth.get("affected_resource") == "dhcp_service_endpoint_udp_67", "X4-R1 ground truth drifted.")
    return DhcpServerUnavailableScenario(Path(path), sha256_file(Path(path)), scenario, "X4_R1_DHCP_SERVER_UNAVAILABLE", _text(topology.get("id"), "topology.id"), _text(topology.get("context_id"), "topology.context_id"), _text(observation.get("source_node"), "source_node"), _text(observation.get("source_container"), "source_container"), _text(observation.get("source_interface"), "source_interface"), _text(observation.get("destination_node"), "destination_node"), _text(observation.get("destination_container"), "destination_container"), _text(observation.get("observer_container"), "observer_container"), _text(observation.get("dns_container"), "dns_container"), _text(observation.get("app_container"), "app_container"), _text(observation.get("expected_scope_prefix"), "expected_scope_prefix"))


def dhcp_lease_probe(binding: DhcpServerUnavailableScenario, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    # dhclient's timeout exit (2) is a completed negative protocol observation;
    # command-execution failures are classified separately by the collector.
    command: Sequence[str] = ["sh", "-eu", "-c", f"dhclient -r {binding.source_interface} >/dev/null 2>&1 || true; rm -f /tmp/x4-dhclient.leases /tmp/x4-dhclient.pid; dhclient -4 -1 -v -cf /etc/x4-dhcp/dhclient.conf -pf /tmp/x4-dhclient.pid -lf /tmp/x4-dhclient.leases {binding.source_interface}"]
    return execute_checked(executor, binding.source_container, command)
