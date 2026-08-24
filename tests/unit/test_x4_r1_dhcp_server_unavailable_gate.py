from pathlib import Path
from src.expansion.x4_r1_gate import verify_x4_r1_gate

ROOT = Path(__file__).resolve().parents[2]

def test_x4_r1_gate_binds_exact_d1_boundary() -> None:
    manifest = verify_x4_r1_gate(ROOT)
    assert manifest["slice"]["fault_type"] == "dhcp_server_unavailable"
    assert manifest["topology_runtime"]["dhcp_context_id"] != "x4_top_01_dhcp_dns_service_security_context_v1"
