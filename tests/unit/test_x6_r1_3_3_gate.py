from src.expansion.x6_r1_3_3_gate import verify_x6_r1_3_3
def test_x6_r1_3_3_source_gate() -> None:
    plan = verify_x6_r1_3_3()
    assert plan["future_authorization"]["real_authorization_record"] == "ABSENT"
