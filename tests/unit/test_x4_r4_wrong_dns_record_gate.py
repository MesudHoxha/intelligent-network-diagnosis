from __future__ import annotations

from pathlib import Path

from src.expansion.x4_r4_gate import verify_x4_r4_gate


def test_x4_r4_gate_binds_d4_record_context_image_and_preserved_rules() -> None:
    manifest = verify_x4_r4_gate(Path(__file__).resolve().parents[2])
    assert manifest["slice"]["fault_code"] == "D4"
    assert manifest["topology_runtime"]["image"] == "ind-x4-dhcp:0.2"
    assert manifest["slice"]["preserved_rules"] == ["R_X4_SERVICE_SECURITY_001", "R_X4_SERVICE_SECURITY_002", "R_X4_SERVICE_SECURITY_003"]
