from src.expansion.x6_r1_3_5_gate import verify_x6_r1_3_5
def test_x6_r1_3_5_gate_preserves_disabled_authorization() -> None:
    assert all(value is False for value in verify_x6_r1_3_5()["runtime_scientific_authorization"].values())
