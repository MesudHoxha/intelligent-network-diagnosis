from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.collection.service_state_collector_v3 import _dns_query_state, build_service_feature_vector_v2_r3, collect_dns_service_down_evidence_v4
from src.expansion.x4_dns_service_down import X4DnsServiceDownError, load_dns_service_down_scenario
from src.fault_injection.dns_service_down import inject_dns_service_down, restore_dns_service_down
from src.fault_injection.phase6_common import utc_now
from src.rules.service_security_rule_engine_x4_r1 import SIGNATURE as D1_SIGNATURE
from src.rules.service_security_rule_engine_x4_r2 import D2_SIGNATURE
from src.rules.service_security_rule_engine_x4_r3 import D3_SIGNATURE, diagnose_dhcp_dns_service_security_v2


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/expansion/X4_R3_DNS_SERVICE_DOWN.yml"


class FakeDnsNetwork:
    def __init__(self) -> None:
        self.dns_running = True; self.query_execution_failure = False
    def __call__(self, container: str, command: list[str]) -> dict[str, object]:
        command = list(command); rc, stdout, stderr = 0, "", ""; script = command[-1] if command and command[0] == "sh" else ""
        if command and command[0] == "sh" and "dhclient" in script: stdout = "bound to 10.40.0.100"
        elif command[:1] == ["ping"]: stdout = "1 packets transmitted, 1 received"
        elif command and command[0] == "sh" and "dig +time=2" in script:
            if self.query_execution_failure: rc, stderr = 127, "dig: not found"
            elif self.dns_running: stdout = "10.40.0.4\n"
            else: rc, stderr = 9, "connection timed out; no servers could be reached"
        elif command and command[0] == "sh" and "test -s /run/x4-dns.pid" in script and "dnsmasq --interface=eth1" not in script:
            rc = 0 if self.dns_running else 1
        elif command and command[0] == "sh" and "ss -lun | grep -q ':53'" in script:
            rc = 0 if self.dns_running else 1
        elif command and command[0] == "sh" and "dnsmasq --interface=eth1" in script:
            self.dns_running = True
        elif command and command[0] == "sh" and "rm -f /run/x4-dns.pid; sleep 1" in script:
            self.dns_running = False
        elif command and command[0] == "sh" and "pgrep -f 'http.server 8080'" in script: stdout = "12\n"
        elif command[:1] == ["nc"]: pass
        elif command[:1] == ["iptables"]: stdout = "-P INPUT ACCEPT\n"
        return {"command": ["docker", "exec", container, *command], "return_code": rc, "stdout": stdout, "stderr": stderr, "timestamp_utc": utc_now()}


def _vector(values: dict[str, bool]) -> dict[str, object]:
    return {"schema_version": 2, "vector_id": "x4-r3-test", "catalog_id": "x1_feature_catalog_v1", "evidence_id": "x4-r3-test-evidence", "values": {name: {"value": value, "availability": "observed"} for name, value in values.items()}, "mask_id": None, "provenance": {"evidence_sha256": "0" * 64, "feature_catalog_sha256": "3dba72e83d7e17767ab0851a24541aa7d2d8b789dcf04a5aeb726ff48e9518e4"}}


def test_canonical_d3_and_compatibility_alias_bind_one_dns_flow_context() -> None:
    binding = load_dns_service_down_scenario(SCENARIO)
    assert binding.scenario_id == "X4_R3_DNS_SERVICE_DOWN"
    assert binding.compatibility_alias == "X4_R3_DNS_SERVICE_UNAVAILABLE"
    assert (binding.source_node, binding.destination_node) == ("client", "dns_server")
    context = json.loads((ROOT / binding.scenario["topology"]["context_file"]).read_text(encoding="utf-8"))
    assert context["observation_roles"] == {"source": "client", "destination": "dns_server", "observers": ["observer"]}
    assert "image: ind-x4-dhcp:0.2" in (ROOT / binding.scenario["topology"]["file"]).read_text(encoding="utf-8")


def test_d3_stops_only_dns_and_collects_real_negative_query_then_restores(tmp_path: Path) -> None:
    network = FakeDnsNetwork(); injection = inject_dns_service_down(SCENARIO, tmp_path / "mutation", executor=network)
    assert injection["status"] == "FAULT_CONFIRMED" and network.dns_running is False
    evidence = collect_dns_service_down_evidence_v4(tmp_path, SCENARIO, executor=network)
    assert {key: row["value"] for key, row in evidence["observations"].items()} == D3_SIGNATURE
    assert evidence["observations"]["dns_server_reachable"]["value"] is True
    assert "no servers could be reached" in json.loads((tmp_path / "raw/v4/service_state_collector_v3/dns_query_response.json").read_text(encoding="utf-8"))["command_result"]["stderr"]
    vector = build_service_feature_vector_v2_r3(tmp_path, evidence)
    assert diagnose_dhcp_dns_service_security_v2(vector)["prediction"]["fault_type"] == "dns_service_down"
    restored = restore_dns_service_down(SCENARIO, tmp_path / "mutation", executor=network)
    assert restored["status"] == "RESTORATION_CONFIRMED" and network.dns_running is True
    assert restore_dns_service_down(SCENARIO, tmp_path / "mutation", executor=network) == restored


def test_completed_dns_negative_is_observed_but_tool_failure_is_unavailable(tmp_path: Path) -> None:
    assert _dns_query_state({"return_code": 9, "stdout": "", "stderr": "no servers could be reached"}, "10.40.0.4") == (False, False, "observed")
    assert _dns_query_state({"return_code": 0, "stdout": "10.40.9.9", "stderr": ""}, "10.40.0.4") == (False, False, "observed")
    assert _dns_query_state({"return_code": 127, "stdout": "", "stderr": "dig: not found"}, "10.40.0.4") == (None, None, "collection_unavailable")
    network = FakeDnsNetwork(); network.query_execution_failure = True
    evidence = collect_dns_service_down_evidence_v4(tmp_path, SCENARIO, executor=network)
    for name in ("dns_query_succeeds", "dns_answer_matches_expected"):
        assert evidence["observations"][name]["value"] is None
        assert evidence["observations"][name]["availability"] == "collection_unavailable"


def test_combined_engine_preserves_d1_d2_and_requires_exact_d3() -> None:
    assert diagnose_dhcp_dns_service_security_v2(_vector(D1_SIGNATURE))["prediction"]["fault_type"] == "dhcp_server_unavailable"
    assert diagnose_dhcp_dns_service_security_v2(_vector(D2_SIGNATURE))["prediction"]["fault_type"] == "dhcp_pool_misconfiguration"
    assert diagnose_dhcp_dns_service_security_v2(_vector(D3_SIGNATURE))["prediction"]["fault_type"] == "dns_service_down"
    altered = copy.deepcopy(_vector(D3_SIGNATURE)); altered["values"]["dns_server_reachable"]["value"] = False
    assert diagnose_dhcp_dns_service_security_v2(altered)["status"] == "abstained"


def test_unjournaled_restoration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(X4DnsServiceDownError, match="durable recovery intent"):
        restore_dns_service_down(SCENARIO, tmp_path, executor=FakeDnsNetwork())
