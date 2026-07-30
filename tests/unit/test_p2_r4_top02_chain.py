from __future__ import annotations

from pathlib import Path

import yaml

from src.batch.plan import (
    expand_batch_plan,
    load_batch_plan,
)
from src.contracts.observation_profile import (
    validate_observation_profile,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY_PATH = (
    REPOSITORY_ROOT
    / "labs"
    / "topologies"
    / "top02_chain"
    / "topology.clab.yml"
)
VALIDATOR_PATH = (
    TOPOLOGY_PATH.parent
    / "scripts"
    / "validate_baseline.sh"
)
PLAN_PATH = (
    REPOSITORY_ROOT
    / "plans"
    / "batches"
    / "P2_G02_SMOKE.yml"
)
SCENARIO_ROOT = REPOSITORY_ROOT / "scenarios" / "routing"
SCENARIO_NAMES = (
    "N0_NORMAL_OPERATION_TOP02_CHAIN.yml",
    "C1_MISSING_STATIC_ROUTE_TOP02_CHAIN.yml",
    "C2_WRONG_NEXT_HOP_TOP02_CHAIN.yml",
)
FROZEN_GROUP_ID = "CTX_G02_TOP02_CHAIN_3R"
TOPOLOGY_REFERENCE = (
    "labs/topologies/top02_chain/topology.clab.yml"
)


def load_yaml(path: Path) -> dict[str, object]:
    document = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )
    assert isinstance(document, dict)
    return document


def load_scenario(name: str) -> dict[str, object]:
    document = load_yaml(SCENARIO_ROOT / name)
    scenario = document["scenario"]
    assert isinstance(scenario, dict)
    return scenario


def node_commands(
    nodes: dict[str, object],
    node_name: str,
) -> list[str]:
    node = nodes[node_name]
    assert isinstance(node, dict)
    commands = node["exec"]
    assert isinstance(commands, list)
    assert all(isinstance(item, str) for item in commands)
    return commands


def test_topology_matches_frozen_g02_graph() -> None:
    document = load_yaml(TOPOLOGY_PATH)

    assert document["name"] == "top02chain"

    topology = document["topology"]
    assert isinstance(topology, dict)
    nodes = topology["nodes"]
    links = topology["links"]

    assert isinstance(nodes, dict)
    assert isinstance(links, list)
    assert set(nodes) == {
        "hosta",
        "r1",
        "r2",
        "r3",
        "hostb",
    }
    assert links == [
        {"endpoints": ["hosta:eth1", "r1:eth1"]},
        {"endpoints": ["r1:eth2", "r2:eth1"]},
        {"endpoints": ["r2:eth2", "r3:eth1"]},
        {"endpoints": ["r3:eth2", "hostb:eth1"]},
    ]


def test_topology_matches_frozen_address_and_route_plan() -> None:
    topology = load_yaml(TOPOLOGY_PATH)["topology"]
    assert isinstance(topology, dict)
    nodes = topology["nodes"]
    assert isinstance(nodes, dict)

    expected_commands = {
        "hosta": {
            "ip addr add 10.20.1.10/24 dev eth1",
            "ip route replace 10.20.3.0/24 via 10.20.1.1",
        },
        "r1": {
            "ip addr add 10.20.1.1/24 dev eth1",
            "ip addr add 10.20.12.1/29 dev eth2",
            "ip route replace 10.20.3.0/24 via 10.20.12.2",
        },
        "r2": {
            "ip addr add 10.20.12.2/29 dev eth1",
            "ip addr add 10.20.23.1/29 dev eth2",
            "ip route replace 10.20.1.0/24 via 10.20.12.1",
            "ip route replace 10.20.3.0/24 via 10.20.23.2",
        },
        "r3": {
            "ip addr add 10.20.23.2/29 dev eth1",
            "ip addr add 10.20.3.1/24 dev eth2",
            "ip route replace 10.20.1.0/24 via 10.20.23.1",
        },
        "hostb": {
            "ip addr add 10.20.3.10/24 dev eth1",
            "ip route replace 10.20.1.0/24 via 10.20.3.1",
            "ip route replace 10.20.23.0/29 via 10.20.3.1",
        },
    }

    for node_name, expected in expected_commands.items():
        commands = set(node_commands(nodes, node_name))
        assert expected <= commands

    for router in ("r1", "r2", "r3"):
        node = nodes[router]
        assert isinstance(node, dict)
        assert node["sysctls"] == {
            "net.ipv4.ip_forward": 1
        }


def test_g02_scenarios_share_frozen_observation_context() -> None:
    profiles = []
    fault_types = []

    for name in SCENARIO_NAMES:
        scenario = load_scenario(name)
        topology = scenario["topology"]
        ground_truth = scenario["ground_truth"]

        assert isinstance(topology, dict)
        assert isinstance(ground_truth, dict)
        assert topology == {
            "id": "TOP_02_CHAIN",
            "file": TOPOLOGY_REFERENCE,
        }
        assert (
            REPOSITORY_ROOT / topology["file"]
        ).is_file()
        assert scenario["variant_id"] == "canonical"
        assert scenario["split_group_id"] == FROZEN_GROUP_ID

        profiles.append(
            validate_observation_profile(scenario)
        )
        fault_types.append(ground_truth["fault_type"])

    assert fault_types == [
        "no_fault",
        "missing_static_route",
        "wrong_next_hop",
    ]

    assert {
        (
            profile.topology_id,
            profile.direction,
            profile.source_container,
            profile.source_gateway_address,
            profile.destination_address,
            profile.destination_prefix,
            profile.route_observer_node,
            profile.route_observer_container,
            profile.expected_next_hop,
            profile.transit_node,
            profile.transit_container,
        )
        for profile in profiles
    } == {
        (
            "TOP_02_CHAIN",
            "hosta_to_hostb",
            "clab-top02chain-hosta",
            "10.20.1.1",
            "10.20.3.10",
            "10.20.3.0/24",
            "r1",
            "clab-top02chain-r1",
            "10.20.12.2",
            "r2",
            "clab-top02chain-r2",
        )
    }


def test_g02_fault_bindings_match_frozen_design() -> None:
    c1 = load_scenario(
        "C1_MISSING_STATIC_ROUTE_TOP02_CHAIN.yml"
    )
    c2 = load_scenario(
        "C2_WRONG_NEXT_HOP_TOP02_CHAIN.yml"
    )

    for scenario in (c1, c2):
        fault = scenario["fault"]
        ground_truth = scenario["ground_truth"]
        restoration = scenario["restoration"]

        assert isinstance(fault, dict)
        assert isinstance(ground_truth, dict)
        assert isinstance(restoration, dict)
        assert fault["target_node"] == "r1"
        assert (
            fault["target_container"]
            == "clab-top02chain-r1"
        )
        assert ground_truth["fault_location"] == "r1"
        assert (
            ground_truth["affected_prefix"]
            == "10.20.3.0/24"
        )
        assert restoration["command"] == [
            "ip",
            "route",
            "replace",
            "10.20.3.0/24",
            "via",
            "10.20.12.2",
            "dev",
            "eth2",
        ]

    c1_parameters = c1["fault"]["parameters"]
    c2_parameters = c2["fault"]["parameters"]

    assert c1_parameters == {
        "destination_prefix": "10.20.3.0/24",
        "next_hop": "10.20.12.2",
    }
    assert c2_parameters == {
        "destination_prefix": "10.20.3.0/24",
        "correct_next_hop": "10.20.12.2",
        "wrong_next_hop": "10.20.12.6",
        "egress_interface": "eth2",
    }


def test_g02_smoke_plan_has_one_complete_class_set() -> None:
    plan = load_batch_plan(
        PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )
    experiments = expand_batch_plan(plan)

    assert plan.batch_id == "P2_G02_SMOKE"
    assert plan.execution_order == "listed"
    assert plan.failure_policy == "stop"
    assert [item.entry_id for item in experiments] == [
        "n0_g02_chain",
        "c1_g02_chain",
        "c2_g02_chain",
    ]
    assert [
        item.scenario_path.name
        for item in experiments
    ] == list(SCENARIO_NAMES)
    assert all(
        item.repetition_index == 1
        for item in experiments
    )


def test_g02_validator_covers_frozen_baseline() -> None:
    validator = VALIDATOR_PATH.read_text(
        encoding="utf-8"
    )

    required_values = (
        "clab-top02chain-hosta",
        "clab-top02chain-r1",
        "clab-top02chain-r2",
        "clab-top02chain-r3",
        "clab-top02chain-hostb",
        "10.20.1.10/24",
        "10.20.1.1/24",
        "10.20.12.1/29",
        "10.20.12.2/29",
        "10.20.23.1/29",
        "10.20.23.2/29",
        "10.20.3.1/24",
        "10.20.3.10/24",
        "10.20.12.6",
        "/proc/sys/net/ipv4/ip_forward",
        "Baseline status: VALID",
        "Baseline status: INVALID",
    )

    for value in required_values:
        assert value in validator

    assert (
        "test -n \"$(ip route show"
        not in validator
    )
    assert "grep -Eq" in validator
    assert validator.count("run_check \\") == 28
