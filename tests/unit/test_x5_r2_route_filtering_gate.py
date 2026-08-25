from pathlib import Path

from src.expansion.x5_r2_gate import SIGNATURE, verify_x5_r2_gate


def test_x5_r2_route_filtering_gate_is_hash_bound() -> None:
    plan = verify_x5_r2_gate(Path(__file__).resolve().parents[2])
    assert plan["slice"]["signature"] == SIGNATURE
    assert plan["slice"]["rule_id"] == "R_X5_OSPF_002"
    assert len(plan["source_bindings"]) == 8
