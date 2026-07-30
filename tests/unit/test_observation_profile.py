from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from src.contracts.observation_profile import (
    ObservationProfileContractError,
    validate_observation_profile,
)


def canonical_scenario() -> dict[str, object]:
    return {
        "id": "C1_MISSING_STATIC_ROUTE",
        "kind": "fault",
        "observation": {
            "schema_version": 1,
            "direction": "hosta_to_hostb",
            "source_container": "clab-top01-hosta",
            "source_gateway_address": "10.10.1.1",
            "destination_address": "10.10.2.10",
            "destination_prefix": "10.10.2.0/24",
            "route_observer_node": "r1",
            "route_observer_container": "clab-top01-r1",
            "expected_next_hop": "10.10.12.2",
            "transit_node": "r2",
            "transit_container": "clab-top01-r2",
        },
        "fault": {
            "type": "missing_static_route",
            "target_node": "r1",
            "target_container": "clab-top01-r1",
            "parameters": {
                "destination_prefix": "10.10.2.0/24",
                "next_hop": "10.10.12.2",
            },
        },
    }


def observation(
    scenario: dict[str, object],
) -> dict[str, object]:
    value = scenario["observation"]
    assert isinstance(value, dict)
    return value


def fault_parameters(
    scenario: dict[str, object],
) -> dict[str, object]:
    fault = scenario["fault"]
    assert isinstance(fault, dict)
    parameters = fault["parameters"]
    assert isinstance(parameters, dict)
    return parameters


def test_accepts_canonical_profile() -> None:
    profile = validate_observation_profile(
        canonical_scenario()
    )

    assert profile.schema_version == 1
    assert profile.direction == "hosta_to_hostb"
    assert profile.destination_address == "10.10.2.10"
    assert profile.destination_prefix == "10.10.2.0/24"
    assert profile.expected_next_hop == "10.10.12.2"


@pytest.mark.parametrize(
    "scenario_path",
    [
        Path(
            "scenarios/routing/"
            "N0_NORMAL_OPERATION.yml"
        ),
        Path(
            "scenarios/routing/"
            "C1_MISSING_STATIC_ROUTE.yml"
        ),
        Path(
            "scenarios/routing/"
            "C2_WRONG_NEXT_HOP.yml"
        ),
    ],
)
def test_canonical_scenario_files_have_valid_profiles(
    scenario_path: Path,
) -> None:
    document = yaml.safe_load(
        scenario_path.read_text(encoding="utf-8")
    )

    validate_observation_profile(document["scenario"])


def test_rejects_missing_observation() -> None:
    scenario = canonical_scenario()
    del scenario["observation"]

    with pytest.raises(
        ObservationProfileContractError,
        match="requires an observation object",
    ):
        validate_observation_profile(scenario)


def test_rejects_unexpected_observation_field() -> None:
    scenario = canonical_scenario()
    observation(scenario)["fallback_address"] = (
        "10.10.2.10"
    )

    with pytest.raises(
        ObservationProfileContractError,
        match="Unexpected observation fields",
    ):
        validate_observation_profile(scenario)


def test_rejects_reverse_direction() -> None:
    scenario = canonical_scenario()
    observation(scenario)["direction"] = "hostb_to_hosta"

    with pytest.raises(
        ObservationProfileContractError,
        match="only HostA to HostB",
    ):
        validate_observation_profile(scenario)


def test_rejects_other_route_observer() -> None:
    scenario = canonical_scenario()
    observation(scenario)["route_observer_node"] = "r2"

    with pytest.raises(
        ObservationProfileContractError,
        match="route_observer_node 'r1'",
    ):
        validate_observation_profile(scenario)


def test_rejects_other_transit_node() -> None:
    scenario = canonical_scenario()
    observation(scenario)["transit_node"] = "r1"

    with pytest.raises(
        ObservationProfileContractError,
        match="transit_node 'r2'",
    ):
        validate_observation_profile(scenario)


def test_rejects_destination_outside_prefix() -> None:
    scenario = canonical_scenario()
    observation(scenario)["destination_address"] = (
        "10.10.22.10"
    )

    with pytest.raises(
        ObservationProfileContractError,
        match="must belong",
    ):
        validate_observation_profile(scenario)


def test_rejects_noncanonical_destination_prefix() -> None:
    scenario = canonical_scenario()
    observation(scenario)["destination_prefix"] = (
        "10.10.2.10/24"
    )

    with pytest.raises(
        ObservationProfileContractError,
        match="canonical IPv4 network prefix",
    ):
        validate_observation_profile(scenario)


def test_rejects_fault_destination_mismatch() -> None:
    scenario = canonical_scenario()
    fault_parameters(scenario)["destination_prefix"] = (
        "10.10.22.0/24"
    )

    with pytest.raises(
        ObservationProfileContractError,
        match="destination_prefix must match",
    ):
        validate_observation_profile(scenario)


def test_rejects_fault_target_node_mismatch() -> None:
    scenario = canonical_scenario()
    fault = scenario["fault"]
    assert isinstance(fault, dict)
    fault["target_node"] = "r2"

    with pytest.raises(
        ObservationProfileContractError,
        match="fault.target_node must match",
    ):
        validate_observation_profile(scenario)


def test_rejects_fault_target_container_mismatch(
) -> None:
    scenario = canonical_scenario()
    fault = scenario["fault"]
    assert isinstance(fault, dict)
    fault["target_container"] = "clab-top01-r2"

    with pytest.raises(
        ObservationProfileContractError,
        match="fault.target_container must match",
    ):
        validate_observation_profile(scenario)


def test_rejects_missing_route_next_hop_mismatch(
) -> None:
    scenario = canonical_scenario()
    fault_parameters(scenario)["next_hop"] = (
        "10.10.12.3"
    )

    with pytest.raises(
        ObservationProfileContractError,
        match=r"fault\.parameters\.next_hop",
    ):
        validate_observation_profile(scenario)


def test_wrong_next_hop_uses_correct_next_hop(
) -> None:
    scenario = deepcopy(canonical_scenario())
    fault = scenario["fault"]
    assert isinstance(fault, dict)
    fault["type"] = "wrong_next_hop"
    parameters = fault_parameters(scenario)
    del parameters["next_hop"]
    parameters["correct_next_hop"] = "10.10.12.2"
    parameters["wrong_next_hop"] = "10.10.12.254"

    profile = validate_observation_profile(scenario)

    assert profile.expected_next_hop == "10.10.12.2"


def test_rejects_wrong_next_hop_correct_hop_mismatch(
) -> None:
    scenario = deepcopy(canonical_scenario())
    fault = scenario["fault"]
    assert isinstance(fault, dict)
    fault["type"] = "wrong_next_hop"
    parameters = fault_parameters(scenario)
    del parameters["next_hop"]
    parameters["correct_next_hop"] = "10.10.12.3"
    parameters["wrong_next_hop"] = "10.10.12.254"

    with pytest.raises(
        ObservationProfileContractError,
        match=r"fault\.parameters\.correct_next_hop",
    ):
        validate_observation_profile(scenario)
