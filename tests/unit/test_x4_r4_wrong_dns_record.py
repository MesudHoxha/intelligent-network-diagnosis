from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.collection.service_state_collector_v4 import _dns_query_state, build_service_feature_vector_v2_r4, collect_wrong_dns_record_evidence_v4
from src.expansion.x4_wrong_dns_record import X4WrongDnsRecordError, load_wrong_dns_record_scenario
from src.fault_injection.phase6_common import utc_now
from src.fault_injection.wrong_dns_record import inject_wrong_dns_record, restore_wrong_dns_record
from src.rules.service_security_rule_engine_x4_r1 import SIGNATURE as D1_SIGNATURE
from src.rules.service_security_rule_engine_x4_r2 import D2_SIGNATURE
from src.rules.service_security_rule_engine_x4_r3 import D3_SIGNATURE
from src.rules.service_security_rule_engine_x4_r4 import D4_SIGNATURE, diagnose_dhcp_dns_service_security_v2_r4


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/expansion/X4_R4_WRONG_DNS_RECORD.yml"


class FakeWrongDnsNetwork:
    def __init__(self) -> None:
        self.wrong_record = False; self.query_execution_failure = False
    def __call__(self, container: str, command: list[str]) -> dict[str, object]:
        command = list(command); rc, stdout, stderr = 0, "", ""; script = command[-1] if command and command[0] == "sh" else ""
        if command and command[0] == "sh" and "dhclient" in script: stdout = "bound to 10.40.0.100"
        elif command[:1] == ["ping"]: stdout = "1 packets transmitted, 1 received"
        elif command and command[0] == "sh" and "dig +norecurse" in script:
            if self.query_execution_failure: rc, stderr = 127, "dig: not found"
            else: stdout = "10.40.0." + ("99" if self.wrong_record else "4") + "\n"
        elif command and command[0] == "sh" and "cat /etc/x4-dns/dnsmasq.conf" in script:
            stdout = "address=/app.x4.test/10.40.0." + ("99" if self.wrong_record else "4") + "\n"
        elif command and command[0] == "sh" and "x4-r4-dnsmasq.conf.backup" in script and "sed -i" in script:
            self.wrong_record = True
        elif command and command[0] == "sh" and "x4-r4-dnsmasq.conf.backup" in script and "cp /tmp/x4-r4-dnsmasq.conf.backup" in script:
            self.wrong_record = False
        elif command and command[0] == "sh" and "test -s /run/x4-dns.pid" in script: pass
        elif command and command[0] == "sh" and "ss -lun | grep -q ':53'" in script: pass
        elif command and command[0] == "sh" and "pgrep -f 'http.server 8080'" in script: stdout = "12\n"
        elif command[:1] == ["iptables"]: stdout = "-P INPUT ACCEPT\n"
        return {"command": ["docker", "exec", container, *command], "return_code": rc, "stdout": stdout, "stderr": stderr, "timestamp_utc": utc_now()}


def _vector(values: dict[str, bool]) -> dict[str, object]:
    return {"schema_version": 2, "vector_id": "x4-r4-test", "catalog_id": "x1_feature_catalog_v1", "evidence_id": "x4-r4-test-evidence", "values": {name: {"value": value, "availability": "observed"} for name, value in values.items()}, "mask_id": None, "provenance": {"evidence_sha256": "0" * 64, "feature_catalog_sha256": "3dba72e83d7e17767ab0851a24541aa7d2d8b789dcf04a5aeb726ff48e9518e4"}}


def test_d4_reuses_accepted_dns_flow_context_and_image_with_direct_config_topology() -> None:
    binding = load_wrong_dns_record_scenario(SCENARIO)
    assert binding.topology_context_id == "x4_top_01_dhcp_dns_service_security_dns_flow_context_v1"
    assert (binding.source_node, binding.destination_node) == ("client", "dns_server")
    assert "image: ind-x4-dhcp:0.2" in (ROOT / binding.scenario["topology"]["file"]).read_text(encoding="utf-8")
    assert "/etc/x4-dns/dnsmasq.conf" in (ROOT / binding.scenario["topology"]["file"]).read_text(encoding="utf-8")


def test_d4_replaces_only_record_and_collects_direct_config_fresh_wrong_answer_then_restores(tmp_path: Path) -> None:
    network = FakeWrongDnsNetwork(); injection = inject_wrong_dns_record(SCENARIO, tmp_path / "mutation", executor=network)
    assert injection["status"] == "FAULT_CONFIRMED" and network.wrong_record is True
    evidence = collect_wrong_dns_record_evidence_v4(tmp_path, SCENARIO, executor=network)
    assert {key: row["value"] for key, row in evidence["observations"].items()} == D4_SIGNATURE
    assert "address=/app.x4.test/10.40.0.99" in json.loads((tmp_path / "raw/v4/service_state_collector_v4/dns_record_configuration.json").read_text(encoding="utf-8"))["command_result"]["stdout"]
    vector = build_service_feature_vector_v2_r4(tmp_path, evidence)
    assert diagnose_dhcp_dns_service_security_v2_r4(vector)["prediction"]["fault_type"] == "wrong_dns_record"
    restored = restore_wrong_dns_record(SCENARIO, tmp_path / "mutation", executor=network)
    assert restored["status"] == "RESTORATION_CONFIRMED" and network.wrong_record is False
    assert restore_wrong_dns_record(SCENARIO, tmp_path / "mutation", executor=network) == restored


def test_observed_wrong_answer_is_distinct_from_completed_no_answer_and_tool_failure(tmp_path: Path) -> None:
    assert _dns_query_state({"return_code": 0, "stdout": "10.40.0.99", "stderr": ""}, "10.40.0.4") == (True, False, "observed")
    assert _dns_query_state({"return_code": 0, "stdout": "", "stderr": ""}, "10.40.0.4") == (False, False, "observed")
    assert _dns_query_state({"return_code": 127, "stdout": "", "stderr": "dig: not found"}, "10.40.0.4") == (None, None, "collection_unavailable")
    network = FakeWrongDnsNetwork(); network.wrong_record = True; network.query_execution_failure = True
    evidence = collect_wrong_dns_record_evidence_v4(tmp_path, SCENARIO, executor=network)
    for name in ("dns_query_succeeds", "dns_answer_matches_expected"):
        assert evidence["observations"][name]["value"] is None
        assert evidence["observations"][name]["availability"] == "collection_unavailable"


def test_combined_engine_preserves_d1_through_d3_and_requires_exact_d4() -> None:
    assert diagnose_dhcp_dns_service_security_v2_r4(_vector(D1_SIGNATURE))["prediction"]["fault_type"] == "dhcp_server_unavailable"
    assert diagnose_dhcp_dns_service_security_v2_r4(_vector(D2_SIGNATURE))["prediction"]["fault_type"] == "dhcp_pool_misconfiguration"
    assert diagnose_dhcp_dns_service_security_v2_r4(_vector(D3_SIGNATURE))["prediction"]["fault_type"] == "dns_service_down"
    assert diagnose_dhcp_dns_service_security_v2_r4(_vector(D4_SIGNATURE))["prediction"]["fault_type"] == "wrong_dns_record"
    altered = copy.deepcopy(_vector(D4_SIGNATURE)); altered["values"]["service_process_running"]["value"] = False
    assert diagnose_dhcp_dns_service_security_v2_r4(altered)["status"] == "abstained"


def test_unjournaled_restoration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(X4WrongDnsRecordError, match="durable recovery intent"):
        restore_wrong_dns_record(SCENARIO, tmp_path, executor=FakeWrongDnsNetwork())
