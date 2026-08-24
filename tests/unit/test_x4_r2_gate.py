from __future__ import annotations

from pathlib import Path

from src.expansion.x4_r2_gate import verify_x4_r2_gate


def test_x4_r2_source_gate_binds_d1_d2_context_and_image() -> None:
    manifest = verify_x4_r2_gate(Path(__file__).resolve().parents[2])
    assert manifest["slice"]["fault_code"] == "D2"
    assert manifest["topology_runtime"]["image"] == "ind-x4-dhcp:0.2"
