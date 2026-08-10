from pathlib import Path

import yaml

from src.contracts.observation_profile_v2 import (
    validate_observation_profile_v2,
)


SCENARIOS = {
    "wrong_default_gateway": Path(
        "scenarios/routing/C3_WRONG_DEFAULT_GATEWAY_P6_TOP01.yml"
    ),
    "interface_down": Path(
        "scenarios/routing/C4_INTERFACE_DOWN_P6_TOP01.yml"
    ),
    "acl_block": Path(
        "scenarios/routing/C5_ACL_BLOCK_P6_TOP01.yml"
    ),
}


def test_three_reviewed_scenarios_validate_as_profile_v2() -> None:
    scenario_ids: set[str] = set()
    for fault_type, path in SCENARIOS.items():
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        scenario = document["scenario"]
        profile = validate_observation_profile_v2(scenario)

        assert scenario["fault"]["type"] == fault_type
        assert scenario["ground_truth"]["fault_type"] == fault_type
        assert profile.topology_id == "TOP_01"
        assert profile.direction == "hosta_to_hostb"
        assert profile.schema_version == 2
        scenario_ids.add(scenario["id"])

    assert len(scenario_ids) == 3


def test_fault_targets_match_frozen_roles() -> None:
    bindings = {
        fault_type: yaml.safe_load(path.read_text(encoding="utf-8"))[
            "scenario"
        ]
        for fault_type, path in SCENARIOS.items()
    }

    assert bindings["wrong_default_gateway"]["fault"][
        "target_node"
    ] == "hosta"
    assert bindings["interface_down"]["fault"]["target_node"] == "r1"
    assert bindings["interface_down"]["fault"]["parameters"][
        "interface"
    ] == "eth2"
    assert bindings["interface_down"]["fault"]["parameters"][
        "baseline_routes"
    ] == [
        {
            "prefix": "10.10.2.0/24",
            "next_hop": "10.10.12.2",
        },
        {
            "prefix": "10.10.22.0/24",
            "next_hop": "10.10.12.2",
        },
    ]
    assert bindings["acl_block"]["fault"]["target_node"] == "r1"
    assert bindings["acl_block"]["fault"]["parameters"][
        "rule_tag"
    ] == "IND-P6-R4-ACL-TOP01"


def test_p6_r4_setup_uses_default_without_changing_topology() -> None:
    setup = Path(
        "labs/topologies/top01_routed/scripts/prepare_p6_r4_profile.sh"
    ).read_text(encoding="utf-8")
    normalized = " ".join(setup.replace("\\\n", " ").split())
    topology = Path(
        "labs/topologies/top01_routed/topology.clab.yml"
    ).read_text(encoding="utf-8")

    assert 'ip route del "$DESTINATION_PREFIX" via "$EXPECTED_GATEWAY"' in (
        normalized
    )
    assert 'ip route replace default via "$EXPECTED_GATEWAY"' in normalized
    assert "10.10.2.0/24 via 10.10.1.1" in topology
    assert "10.10.1.254" not in topology
    assert "IND-P6" not in topology
