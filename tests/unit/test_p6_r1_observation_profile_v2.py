import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.contracts.observation_profile import (
    ObservationProfile,
    ObservationProfileContractError,
)
from src.contracts.observation_profile_v2 import (
    ObservationProfileV2,
    validate_observation_profile_v2,
    validate_observation_profile_versioned,
)


def scenario_v2(
    *,
    kind: str = "normal",
) -> dict[str, object]:
    scenario: dict[str, object] = {
        "id": "N0_NORMAL_OPERATION_P6",
        "kind": kind,
        "topology": {
            "id": "TOP_01",
            "file": "topology.yml",
        },
        "observation": {
            "schema_version": 2,
            "direction": "hosta_to_hostb",
            "source_node": "hosta",
            "source_container": "clab-top01-hosta",
            "source_address": "10.10.1.10",
            "source_prefix": "10.10.1.0/24",
            "source_gateway_address": "10.10.1.1",
            "destination_address": "10.10.2.10",
            "destination_prefix": "10.10.2.0/24",
            "route_observer_node": "r1",
            "route_observer_container": "clab-top01-r1",
            "expected_next_hop": "10.10.12.2",
            "observer_egress_interface": "eth2",
            "transit_node": "r2",
            "transit_container": "clab-top01-r2",
            "flow_protocol": "icmp",
            "flow_source_port": None,
            "flow_destination_port": None,
            "policy_backend": "iptables",
            "policy_table": "filter",
            "policy_chain": "FORWARD",
            "policy_rule_tag_prefix": "IND-P6",
        },
    }
    return scenario


def observation(scenario: dict[str, object]) -> dict[str, object]:
    value = scenario["observation"]
    assert isinstance(value, dict)
    return value


def test_accepts_observation_profile_v2() -> None:
    profile = validate_observation_profile_v2(scenario_v2())

    assert isinstance(profile, ObservationProfileV2)
    assert profile.source_node == "hosta"
    assert profile.source_prefix == "10.10.1.0/24"
    assert profile.observer_egress_interface == "eth2"
    assert profile.policy_chain == "FORWARD"


def test_json_schema_accepts_observation_object() -> None:
    schema = json.loads(
        Path("schemas/observation_profile_v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        observation(scenario_v2())
    )


def test_versioned_dispatch_preserves_profile_v1() -> None:
    import yaml

    document = yaml.safe_load(
        Path(
            "scenarios/routing/N0_NORMAL_OPERATION.yml"
        ).read_text(encoding="utf-8")
    )
    profile = validate_observation_profile_versioned(
        document["scenario"]
    )

    assert isinstance(profile, ObservationProfile)
    assert profile.schema_version == 1


def test_versioned_dispatch_accepts_profile_v2() -> None:
    profile = validate_observation_profile_versioned(scenario_v2())

    assert isinstance(profile, ObservationProfileV2)
    assert profile.schema_version == 2


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("schema_version", 3, "schema_version"),
        ("source_address", "10.20.1.10", "source_prefix"),
        ("source_gateway_address", "10.10.1.10", "different"),
        ("observer_egress_interface", "interface-too-long", "interface"),
        ("flow_protocol", "gre", "icmp, tcp, or udp"),
        ("policy_backend", "nftables", "iptables/filter/FORWARD"),
    ],
)
def test_rejects_invalid_profile_v2_values(
    field_name: str,
    value: object,
    message: str,
) -> None:
    scenario = scenario_v2()
    observation(scenario)[field_name] = value

    with pytest.raises(
        ObservationProfileContractError,
        match=message,
    ):
        validate_observation_profile_v2(scenario)


def test_rejects_unexpected_profile_field() -> None:
    scenario = scenario_v2()
    observation(scenario)["fault_type"] = "leakage"

    with pytest.raises(
        ObservationProfileContractError,
        match="Unexpected Observation Profile v2 fields",
    ):
        validate_observation_profile_v2(scenario)


def test_rejects_ports_for_icmp() -> None:
    scenario = scenario_v2()
    observation(scenario)["flow_destination_port"] = 443

    with pytest.raises(
        ObservationProfileContractError,
        match="ICMP",
    ):
        validate_observation_profile_v2(scenario)


def test_accepts_tcp_ports() -> None:
    scenario = scenario_v2()
    observation(scenario).update({
        "flow_protocol": "tcp",
        "flow_source_port": 40000,
        "flow_destination_port": 443,
    })

    profile = validate_observation_profile_v2(scenario)

    assert profile.flow_destination_port == 443


def test_wrong_default_gateway_alignment_is_role_safe() -> None:
    scenario = scenario_v2(kind="fault")
    scenario["id"] = "C3_WRONG_DEFAULT_GATEWAY"
    scenario["fault"] = {
        "type": "wrong_default_gateway",
        "target_node": "hosta",
        "target_container": "clab-top01-hosta",
        "parameters": {
            "correct_gateway": "10.10.1.1",
            "wrong_gateway": "10.10.1.254",
        },
    }

    profile = validate_observation_profile_v2(scenario)

    assert profile.source_gateway_address == "10.10.1.1"


def test_rejects_wrong_default_gateway_outside_source_prefix() -> None:
    scenario = scenario_v2(kind="fault")
    scenario["fault"] = {
        "type": "wrong_default_gateway",
        "target_node": "hosta",
        "target_container": "clab-top01-hosta",
        "parameters": {
            "correct_gateway": "10.10.1.1",
            "wrong_gateway": "10.20.1.254",
        },
    }

    with pytest.raises(
        ObservationProfileContractError,
        match="inside observation.source_prefix",
    ):
        validate_observation_profile_v2(scenario)


def test_acl_alignment_rejects_flow_selector_drift() -> None:
    scenario = scenario_v2(kind="fault")
    scenario["fault"] = {
        "type": "acl_block",
        "target_node": "r1",
        "target_container": "clab-top01-r1",
        "parameters": {
            "source_address": "10.10.1.10",
            "destination_address": "10.10.2.10",
            "protocol": "tcp",
            "source_port": None,
            "destination_port": None,
            "policy_backend": "iptables",
            "policy_table": "filter",
            "policy_chain": "FORWARD",
            "rule_tag": "IND-P6-ACL-001",
        },
    }

    with pytest.raises(
        ObservationProfileContractError,
        match="protocol",
    ):
        validate_observation_profile_v2(scenario)


def test_dispatch_rejects_unknown_version() -> None:
    scenario = deepcopy(scenario_v2())
    observation(scenario)["schema_version"] = 99

    with pytest.raises(
        ObservationProfileContractError,
        match="Unsupported observation schema_version",
    ):
        validate_observation_profile_versioned(scenario)
