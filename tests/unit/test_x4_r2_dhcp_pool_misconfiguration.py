from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.collection.service_state_collector_v2 import _lease_state, build_service_feature_vector_v2_r2, collect_dhcp_pool_misconfiguration_evidence_v4
from src.expansion.x4_dhcp_pool_misconfiguration import X4DhcpPoolMisconfigurationError, load_dhcp_pool_misconfiguration_scenario
from src.fault_injection.dhcp_pool_misconfiguration import inject_dhcp_pool_misconfiguration, restore_dhcp_pool_misconfiguration
from src.fault_injection.phase6_common import utc_now
from src.rules.service_security_rule_engine_x4_r1 import SIGNATURE as D1_SIGNATURE
from src.rules.service_security_rule_engine_x4_r2 import D2_SIGNATURE, diagnose_dhcp_service_security_v2


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/expansion/X4_R2_DHCP_POOL_MISCONFIGURATION.yml"


class FakeDhcpPoolNetwork:
    def __init__(self) -> None:
        self.running = True; self.empty_pool = False; self.execution_failure = False
    def __call__(self, container: str, command: list[str]) -> dict[str, object]:
        command = list(command); rc, stdout, stderr = 0, "", ""; script = command[-1] if command and command[0] == "sh" else ""
        if command[:2] == ["x4-dhcp-service", "status"]: rc, stdout = (0, "running\nudp 0 0 0.0.0.0:67\n") if self.running else (1, "")
        elif command and command[0] == "sh" and "dhclient" in script:
            if self.execution_failure: rc, stderr = 127, "dhclient: not found"
            elif self.running and not self.empty_pool: stdout = "bound to 10.40.0.100"
            else: rc, stderr = 2, "No DHCPOFFERS received"
        elif command and command[0] == "sh" and "cat /etc/x4-dhcp/dnsmasq.conf" in script:
            stdout = "dhcp-range=" + ("10.40.0.0,static" if self.empty_pool else "10.40.0.100,10.40.0.150,255.255.255.0,1h") + "\n"
        elif command and command[0] == "sh" and "x4-dhcp-service status; ss -lun" in script:
            rc, stdout = (0, "running\nudp 0 0 0.0.0.0:67\n") if self.running else (1, "")
        elif command and command[0] == "sh" and "x4-r2-dnsmasq.conf.backup" in script and "sed -i" in script:
            self.empty_pool = True; self.running = True
        elif command and command[0] == "sh" and "x4-r2-dnsmasq.conf.backup" in script and "cp /tmp/x4-r2-dnsmasq.conf.backup" in script:
            self.empty_pool = False; self.running = True
        elif command and command[0] == "sh" and "dig +time=2" in script: stdout = "10.40.0.4"
        elif command[:1] == ["iptables"]: stdout = "-P INPUT ACCEPT\n"
        return {"command": ["docker", "exec", container, *command], "return_code": rc, "stdout": stdout, "stderr": stderr, "timestamp_utc": utc_now()}


def _vector(values: dict[str, bool]) -> dict[str, object]:
    return {"schema_version": 2, "vector_id": "x4-r2-test", "catalog_id": "x1_feature_catalog_v1", "evidence_id": "x4-r2-test-evidence", "values": {name: {"value": value, "availability": "observed"} for name, value in values.items()}, "mask_id": None, "provenance": {"evidence_sha256": "0" * 64, "feature_catalog_sha256": "3dba72e83d7e17767ab0851a24541aa7d2d8b789dcf04a5aeb726ff48e9518e4"}}


def test_d2_reuses_accepted_dhcp_context_and_image_boundary() -> None:
    binding = load_dhcp_pool_misconfiguration_scenario(SCENARIO)
    assert binding.topology_context_id == "x4_top_01_dhcp_dns_service_security_dhcp_flow_context_v1"
    assert (binding.source_node, binding.destination_node) == ("client", "dhcp_server")
    assert "image: ind-x4-dhcp:0.2" in (ROOT / binding.scenario["topology"]["file"]).read_text(encoding="utf-8")


def test_d2_fault_has_direct_configuration_and_fresh_negative_lease_then_restores(tmp_path: Path) -> None:
    network = FakeDhcpPoolNetwork(); injection = inject_dhcp_pool_misconfiguration(SCENARIO, tmp_path / "mutation", executor=network)
    assert injection["status"] == "FAULT_CONFIRMED" and network.running is True and network.empty_pool is True
    evidence = collect_dhcp_pool_misconfiguration_evidence_v4(tmp_path, SCENARIO, executor=network)
    assert {key: row["value"] for key, row in evidence["observations"].items()} == D2_SIGNATURE
    assert "dhcp-range=10.40.0.0,static" in json.loads((tmp_path / "raw/v4/service_state_collector_v2/dhcp_pool_configuration.json").read_text(encoding="utf-8"))["command_result"]["stdout"]
    vector = build_service_feature_vector_v2_r2(tmp_path, evidence)
    assert diagnose_dhcp_service_security_v2(vector)["prediction"]["fault_type"] == "dhcp_pool_misconfiguration"
    restored = restore_dhcp_pool_misconfiguration(SCENARIO, tmp_path / "mutation", executor=network)
    assert restored["status"] == "RESTORATION_CONFIRMED" and network.empty_pool is False
    assert restore_dhcp_pool_misconfiguration(SCENARIO, tmp_path / "mutation", executor=network) == restored


def test_completed_wrong_scope_and_no_lease_are_observed_but_execution_failure_is_unavailable(tmp_path: Path) -> None:
    assert _lease_state({"return_code": 0, "stdout": "bound to 10.41.0.100", "stderr": ""}, "10.40.0.") == (True, False, "observed")
    assert _lease_state({"return_code": 2, "stdout": "", "stderr": "No DHCPOFFERS received"}, "10.40.0.") == (False, False, "observed")
    assert _lease_state({"return_code": 127, "stdout": "", "stderr": "dhclient: not found"}, "10.40.0.") == (None, None, "collection_unavailable")
    network = FakeDhcpPoolNetwork(); network.execution_failure = True
    evidence = collect_dhcp_pool_misconfiguration_evidence_v4(tmp_path, SCENARIO, executor=network)
    for name in ("dhcp_lease_obtained", "dhcp_lease_matches_expected_scope"):
        assert evidence["observations"][name]["value"] is None
        assert evidence["observations"][name]["availability"] == "collection_unavailable"


def test_combined_engine_preserves_d1_and_requires_exact_d2_signature() -> None:
    assert diagnose_dhcp_service_security_v2(_vector(D1_SIGNATURE))["prediction"]["fault_type"] == "dhcp_server_unavailable"
    assert diagnose_dhcp_service_security_v2(_vector(D2_SIGNATURE))["prediction"]["fault_type"] == "dhcp_pool_misconfiguration"
    altered = copy.deepcopy(_vector(D2_SIGNATURE)); altered["values"]["dns_query_succeeds"]["value"] = False
    assert diagnose_dhcp_service_security_v2(altered)["status"] == "abstained"


def test_unjournaled_restoration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(X4DhcpPoolMisconfigurationError, match="durable recovery intent"):
        restore_dhcp_pool_misconfiguration(SCENARIO, tmp_path, executor=FakeDhcpPoolNetwork())
