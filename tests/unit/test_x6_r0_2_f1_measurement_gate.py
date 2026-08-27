from pathlib import Path

from src.expansion.x6_r0_2_gate import verify_x6_r0_2_f1_measurement_semantics


ROOT = Path(__file__).resolve().parents[2]


def test_x6_r0_2_preserves_historical_x6_and_authorizes_only_next_f1_release() -> None:
    plan = verify_x6_r0_2_f1_measurement_semantics(ROOT)
    assert all(value is False for value in plan["current_release_authorization"].values())
    assert plan["next_release_authorization"]["x6_r1_controlled_runtime_pilot"] is True
    assert plan["next_release_authorization"]["f2_high_latency"] is False


def test_x6_r0_2_freezes_nonquiet_probe_deterministic_thresholds_and_counter_separation() -> None:
    plan = verify_x6_r0_2_f1_measurement_semantics(ROOT)
    assert "-q" not in plan["probe_contract"]["flags"]
    assert plan["threshold_manifest_contract"]["post_hoc_override"] == "FORBIDDEN"
    assert plan["f1_qdisc_counter_contract"]["congestion_queue"]["handle"] == "20:"
