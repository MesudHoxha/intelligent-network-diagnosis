from pathlib import Path

from src.expansion.x6_r1_3_1_gate import verify_x6_r1_3_1


def test_x6_r1_3_1_freezes_cohorts_without_runtime_authorization() -> None:
    plan = verify_x6_r1_3_1(Path(__file__).resolve().parents[2])
    assert plan["threshold_cohorts"]["construction"] == [f"C{index:02d}" for index in range(1, 11)]
    assert not any(plan["runtime_scientific_authorization"].values())
