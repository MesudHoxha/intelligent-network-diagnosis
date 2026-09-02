from src.expansion.x6_r1_3_4_gate import verify_x6_r1_3_4


def test_x6_r1_3_4_source_gate_preserves_false_authorization() -> None:
    plan = verify_x6_r1_3_4()
    assert plan["runtime_scientific_authorization"] == {"containerlab": False, "measurement": False, "f1_revalidation": False, "f2": False, "f3": False, "f4": False, "dataset": False, "ml_hybrid": False, "api": False, "p9_r2": False}
