from pathlib import Path

from src.expansion.x6_r1_3_gate import verify_x6_r1_3


def test_x6_r1_3_is_source_only_and_non_authorizing() -> None:
    plan = verify_x6_r1_3(Path(__file__).resolve().parents[2])
    assert plan["numeric_limits_status"] == "UNRESOLVED_NO_RUNTIME_DERIVATION"
    assert not any(plan["runtime_scientific_authorization"].values())
