from __future__ import annotations

from pathlib import Path

from src.expansion.x6_r0_3_gate import verify_x6_r0_3_f1_pre_runtime_validation


ROOT = Path(__file__).resolve().parents[2]


def test_x6_r0_3_gate_preserves_r0_2_and_authorizes_only_x6_r1_source_and_pilot() -> None:
    plan = verify_x6_r0_3_f1_pre_runtime_validation(ROOT)
    assert plan["historical_predecessor"] == {"x6_r0_2": "PRESERVED_PUBLISHED_SOURCE_ONLY_5_OF_5_BINDINGS"}
    assert len(plan["source_bindings"]) == 6
    assert not any(plan["current_release_authorization"].values())
    assert plan["next_release_authorization"]["x6_r1_source_implementation"] is True
    assert plan["next_release_authorization"]["x6_r1_controlled_runtime_pilot"] is True
    assert plan["track"]["next_release"] == "X6_R1_PACKET_LOSS"
