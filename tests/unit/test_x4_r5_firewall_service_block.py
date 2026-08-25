from pathlib import Path

from src.collection.service_state_collector_v5 import _binary
from src.expansion.x4_firewall_service_block import load_firewall_service_block_scenario
from src.rules.service_security_rule_engine_x4_r1 import SIGNATURE as D1_SIGNATURE
from src.rules.service_security_rule_engine_x4_r2 import D2_SIGNATURE
from src.rules.service_security_rule_engine_x4_r3 import D3_SIGNATURE
from src.rules.service_security_rule_engine_x4_r4 import D4_SIGNATURE
from src.rules.service_security_rule_engine_x4_r5 import D5_SIGNATURE, diagnose_dhcp_dns_service_security_v2_r5

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/expansion/X4_R5_FIREWALL_SERVICE_BLOCK.yml"

def _vector(values):
    return {"schema_version": 2, "vector_id": "x4-r5-test", "catalog_id": "x1_feature_catalog_v1", "evidence_id": "x4-r5-test-evidence", "values": {name: {"value": value, "availability": "observed"} for name, value in values.items()}, "mask_id": None, "provenance": {"evidence_sha256": "0" * 64, "feature_catalog_sha256": "3dba72e83d7e17767ab0851a24541aa7d2d8b789dcf04a5aeb726ff48e9518e4"}}

def test_d5_reuses_exact_client_application_context_and_image():
    binding = load_firewall_service_block_scenario(SCENARIO)
    assert (binding.source_node, binding.destination_node) == ("client", "app_server")
    assert binding.topology_context_id == "x4_top_01_dhcp_dns_service_security_context_v1"
    text = (ROOT / binding.scenario["topology"]["file"]).read_text(encoding="utf-8")
    assert "image: ind-x4-dhcp:0.2" in text and "cap-add: [NET_ADMIN]" in text

def test_d5_signature_is_exact_and_preserves_d1_through_d4():
    assert D5_SIGNATURE == {"dhcp_server_reachable": True, "dhcp_lease_obtained": True, "dhcp_lease_matches_expected_scope": True, "dns_server_reachable": True, "dns_query_succeeds": True, "dns_answer_matches_expected": True, "service_process_running": True, "service_port_reachable": False, "service_flow_blocked_by_policy": True}
    assert diagnose_dhcp_dns_service_security_v2_r5(_vector(D1_SIGNATURE))["prediction"]["fault_type"] == "dhcp_server_unavailable"
    assert diagnose_dhcp_dns_service_security_v2_r5(_vector(D2_SIGNATURE))["prediction"]["fault_type"] == "dhcp_pool_misconfiguration"
    assert diagnose_dhcp_dns_service_security_v2_r5(_vector(D3_SIGNATURE))["prediction"]["fault_type"] == "dns_service_down"
    assert diagnose_dhcp_dns_service_security_v2_r5(_vector(D4_SIGNATURE))["prediction"]["fault_type"] == "wrong_dns_record"
    assert diagnose_dhcp_dns_service_security_v2_r5(_vector(D5_SIGNATURE))["prediction"]["fault_type"] == "firewall_service_block"

def test_completed_blocked_probe_is_not_collection_failure():
    assert _binary({"return_code": 1}) == (False, "observed")
    assert _binary({"return_code": 127}) == (None, "collection_unavailable")
