from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.collection.service_state_collector_v1 import _completed_dhcp, build_service_feature_vector_v2, collect_dhcp_server_unavailable_evidence_v4
from src.expansion.x4_dhcp_server_unavailable import X4DhcpServerUnavailableError, load_dhcp_server_unavailable_scenario
from src.fault_injection.dhcp_server_unavailable import inject_dhcp_server_unavailable, restore_dhcp_server_unavailable
from src.fault_injection.phase6_common import utc_now
from src.rules.service_security_rule_engine_x4_r1 import diagnose_dhcp_server_unavailable_v2


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/expansion/X4_R1_DHCP_SERVER_UNAVAILABLE.yml"


class FakeDhcpNetwork:
    def __init__(self) -> None: self.running = True; self.execution_failure = False
    def __call__(self, container: str, command: list[str]) -> dict[str, object]:
        command = list(command); rc, stdout, stderr = 0, "", ""
        if command[:2] == ["x4-dhcp-service", "status"]: rc = 0 if self.running else 1
        elif command[:2] == ["x4-dhcp-service", "stop"]: self.running = False
        elif command[:2] == ["x4-dhcp-service", "start"]: self.running = True
        elif command and command[0] == "sh" and "dhclient" in command[-1]:
            if self.execution_failure: rc, stderr = 127, "dhclient: not found"
            elif self.running: stdout = "bound to 10.40.0.100"
            else: rc, stderr = 2, "No DHCPOFFERS received"
        elif command and command[0] == "sh" and "dig +time=2" in command[-1]: stdout = "10.40.0.4"
        elif command[:1] == ["iptables"]: stdout = "-P INPUT ACCEPT\n"
        return {"command": ["docker", "exec", container, *command], "return_code": rc, "stdout": stdout, "stderr": stderr, "timestamp_utc": utc_now()}


def test_dhcp_context_is_distinct_and_client_to_dhcp_server() -> None:
    binding = load_dhcp_server_unavailable_scenario(SCENARIO)
    assert binding.topology_context_id == "x4_top_01_dhcp_dns_service_security_dhcp_flow_context_v1"
    assert (binding.source_node, binding.destination_node) == ("client", "dhcp_server")
    context = json.loads((ROOT / binding.scenario["topology"]["context_file"]).read_text(encoding="utf-8"))
    assert context["observation_roles"] == {"source": "client", "destination": "dhcp_server", "observers": ["observer"]}


def test_real_dhcp_service_fault_signature_and_idempotent_restoration(tmp_path: Path) -> None:
    network = FakeDhcpNetwork()
    injection = inject_dhcp_server_unavailable(SCENARIO, tmp_path / "mutation", executor=network)
    assert injection["status"] == "FAULT_CONFIRMED" and network.running is False
    evidence = collect_dhcp_server_unavailable_evidence_v4(tmp_path, SCENARIO, executor=network)
    assert {key: row["value"] for key, row in evidence["observations"].items()} == {"dhcp_server_reachable": False, "dhcp_lease_obtained": False, "dhcp_lease_matches_expected_scope": False, "dns_server_reachable": True, "dns_query_succeeds": True, "dns_answer_matches_expected": True, "service_process_running": True, "service_port_reachable": True, "service_flow_blocked_by_policy": False}
    assert all(row["availability"] == "observed" for row in evidence["observations"].values())
    vector = build_service_feature_vector_v2(tmp_path, evidence)
    assert diagnose_dhcp_server_unavailable_v2(vector)["prediction"]["fault_type"] == "dhcp_server_unavailable"
    restored = restore_dhcp_server_unavailable(SCENARIO, tmp_path / "mutation", executor=network)
    assert restored["status"] == "RESTORATION_CONFIRMED" and network.running is True
    assert restore_dhcp_server_unavailable(SCENARIO, tmp_path / "mutation", executor=network) == restored


def test_completed_negative_lease_is_observed_but_tool_failure_is_unavailable(tmp_path: Path) -> None:
    network = FakeDhcpNetwork(); network.running = False
    negative = collect_dhcp_server_unavailable_evidence_v4(tmp_path / "negative", SCENARIO, executor=network)
    assert negative["observations"]["dhcp_lease_obtained"]["value"] is False
    assert negative["observations"]["dhcp_lease_obtained"]["availability"] == "observed"
    failed = FakeDhcpNetwork(); failed.execution_failure = True
    unavailable = collect_dhcp_server_unavailable_evidence_v4(tmp_path / "unavailable", SCENARIO, executor=failed)
    for name in ("dhcp_server_reachable", "dhcp_lease_obtained", "dhcp_lease_matches_expected_scope"):
        assert unavailable["observations"][name]["value"] is None
        assert unavailable["observations"][name]["availability"] == "collection_unavailable"
        assert unavailable["observations"][name]["raw_artifact"] is not None
    vector = build_service_feature_vector_v2(tmp_path / "unavailable", unavailable)
    assert diagnose_dhcp_server_unavailable_v2(vector)["status"] == "insufficient_evidence"


def test_no_generic_connectivity_can_substitute_for_dhcp_protocol_evidence(tmp_path: Path) -> None:
    network = FakeDhcpNetwork(); network.running = False
    evidence = collect_dhcp_server_unavailable_evidence_v4(tmp_path, SCENARIO, executor=network)
    assert evidence["observations"]["dns_server_reachable"]["value"] is True
    assert evidence["observations"]["dhcp_server_reachable"]["value"] is False
    vector = build_service_feature_vector_v2(tmp_path, evidence); altered = copy.deepcopy(vector)
    altered["values"]["dhcp_server_reachable"]["value"] = True
    assert diagnose_dhcp_server_unavailable_v2(altered)["status"] == "abstained"


def test_no_offer_exit_code_is_completed_negative_but_other_client_failure_is_unavailable() -> None:
    assert _completed_dhcp({"return_code": 1, "stdout": "", "stderr": "No DHCPOFFERS received."}, "10.40.0.") == (False, "observed")
    assert _completed_dhcp({"return_code": 1, "stdout": "", "stderr": "dhclient configuration error"}, "10.40.0.") == (None, "collection_unavailable")


def test_unjournaled_restoration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(X4DhcpServerUnavailableError, match="durable recovery intent"):
        restore_dhcp_server_unavailable(SCENARIO, tmp_path, executor=FakeDhcpNetwork())
