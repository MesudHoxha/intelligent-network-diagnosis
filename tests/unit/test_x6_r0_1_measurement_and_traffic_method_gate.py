from pathlib import Path

from src.expansion.x6_r0_1_gate import verify_x6_r0_1_measurement_and_traffic_method_gate


ROOT = Path(__file__).resolve().parents[2]


def test_x6_r0_1_freezes_measurement_method_without_runtime_authorization() -> None:
    plan = verify_x6_r0_1_measurement_and_traffic_method_gate(ROOT)
    assert all(value is False for value in plan["runtime_authorization"].values())
    assert plan["tools_and_direct_observations"]["transport"]["baseline_window_count"] == 10


def test_x6_r0_1_keeps_numeric_features_separate_from_conditional_rule_predicates() -> None:
    plan = verify_x6_r0_1_measurement_and_traffic_method_gate(ROOT)
    numeric = plan["numeric_measurement_contract"]
    assert "raw numbers" in numeric["predicate_boundary"]
    assert "not future ML labels" in numeric["predicate_boundary"]
    assert all("conditional_predicates" in row for row in plan["fault_contexts"])


def test_x6_r0_1_requires_f3_bottleneck_and_f4_dual_effectiveness_proof() -> None:
    plan = verify_x6_r0_1_measurement_and_traffic_method_gate(ROOT)
    f3, f4 = plan["fault_contexts"][2:]
    assert f3["finite_bottleneck"]["counter_owner"].startswith("tc -s qdisc")
    assert len(f4["independent_effectiveness"]) == 2
