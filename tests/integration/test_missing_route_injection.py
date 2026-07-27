from pathlib import Path

import yaml


SCENARIO_PATH = Path(
    "scenarios/routing/C1_MISSING_STATIC_ROUTE.yml"
)


def test_missing_route_scenario_has_required_fields() -> None:
    document = yaml.safe_load(
        SCENARIO_PATH.read_text(encoding="utf-8")
    )
    scenario = document["scenario"]

    assert scenario["id"] == "C1_MISSING_STATIC_ROUTE"
    assert scenario["category"] == "routing"
    assert scenario["fault"]["type"] == "missing_static_route"
    assert scenario["fault"]["target_node"] == "r1"

    parameters = scenario["fault"]["parameters"]

    assert parameters["destination_prefix"] == "10.10.2.0/24"
    assert parameters["next_hop"] == "10.10.12.2"

    ground_truth = scenario["ground_truth"]

    assert ground_truth["fault_location"] == "r1"
    assert ground_truth["fault_type"] == "missing_static_route"
