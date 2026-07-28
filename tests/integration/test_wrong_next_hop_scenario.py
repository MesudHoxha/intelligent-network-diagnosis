from pathlib import Path

import yaml


SCENARIO_PATH = Path(
    "scenarios/routing/C2_WRONG_NEXT_HOP.yml"
)


def test_wrong_next_hop_scenario_has_required_fields(
) -> None:
    document = yaml.safe_load(
        SCENARIO_PATH.read_text(encoding="utf-8")
    )
    scenario = document["scenario"]

    assert scenario["id"] == "C2_WRONG_NEXT_HOP"
    assert scenario["category"] == "routing"
    assert scenario["fault"]["type"] == (
        "wrong_next_hop"
    )
    assert scenario["fault"]["target_node"] == "r1"

    parameters = scenario["fault"]["parameters"]

    assert parameters["destination_prefix"] == (
        "10.10.2.0/24"
    )
    assert parameters["correct_next_hop"] == (
        "10.10.12.2"
    )
    assert parameters["wrong_next_hop"] == (
        "10.10.12.254"
    )
    assert parameters["egress_interface"] == "eth2"

    ground_truth = scenario["ground_truth"]

    assert ground_truth["fault_location"] == "r1"
    assert ground_truth["fault_type"] == (
        "wrong_next_hop"
    )
