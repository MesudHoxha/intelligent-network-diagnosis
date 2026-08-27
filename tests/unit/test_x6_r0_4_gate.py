from pathlib import Path

from src.expansion.x6_r0_4_gate import verify_x6_r0_4_f1_runtime_parameter_freeze


ROOT = Path(__file__).resolve().parents[2]


def test_x6_r0_4_gate_freezes_f1_without_authorizing_other_work() -> None:
    plan = verify_x6_r0_4_f1_runtime_parameter_freeze(ROOT)
    assert len(plan["source_bindings"]) == 8
    assert not any(plan["current_release_authorization"].values())
    assert plan["next_release_authorization"]["x6_r1_source_implementation"] is True
    assert plan["next_release_authorization"]["x6_r1_controlled_runtime_pilot"] is True
    assert plan["track"]["next_release"] == "X6_R1_PACKET_LOSS"
