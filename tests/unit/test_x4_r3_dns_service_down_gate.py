from __future__ import annotations

from pathlib import Path

from src.expansion.x4_r3_gate import verify_x4_r3_gate


def test_x4_r3_gate_binds_canonical_d3_and_alias_to_one_slice() -> None:
    manifest = verify_x4_r3_gate(Path(__file__).resolve().parents[2])
    assert manifest["release_alias"]["canonical_release"] == "X4_R3_DNS_SERVICE_DOWN"
    assert manifest["release_alias"]["compatibility_alias"] == "X4_R3_DNS_SERVICE_UNAVAILABLE"
    assert manifest["slice"]["fault_type"] == "dns_service_down"
