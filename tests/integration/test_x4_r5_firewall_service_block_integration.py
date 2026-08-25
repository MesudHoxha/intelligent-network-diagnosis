from pathlib import Path

from src.expansion.x4_firewall_service_block import load_firewall_service_block_scenario

ROOT = Path(__file__).resolve().parents[2]

def test_x4_r5_application_flow_provenance_is_not_dns_or_dhcp_flow():
    binding = load_firewall_service_block_scenario(ROOT / "scenarios/expansion/X4_R5_FIREWALL_SERVICE_BLOCK.yml")
    assert binding.scenario["observation"]["direction"] == "client_to_app_server"
    assert binding.scenario["topology"]["context_file"] == "labs/topologies/x4_r1_dhcp_dns_service/topology_context_v1.json"
