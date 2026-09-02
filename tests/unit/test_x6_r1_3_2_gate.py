from pathlib import Path

from src.expansion.x6_r1_3_2_gate import verify_x6_r1_3_2


def test_x6_r1_3_2_preserves_non_authorizing_append_only_boundary() -> None:
    plan = verify_x6_r1_3_2(Path(__file__).resolve().parents[2])
    assert not any(plan["runtime_scientific_authorization"].values())
    assert plan["next_action"] == "X6_R1_4_BASELINE_ONLY_RUNTIME_AUTHORIZATION_REVIEW"
