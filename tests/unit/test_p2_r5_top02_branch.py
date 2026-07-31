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
    / "top02_branch"
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
    / "P2_G03_SMOKE.yml"
)
SCENARIO_ROOT = REPOSITORY_ROOT / "scenarios" / "routing"
SCENARIO_NAMES = (
    "N0_NORMAL_OPERATION_TOP02_BRANCH.yml",
    "C1_MISSING_STATIC_ROUTE_TOP02_BRANCH.yml",
    "C2_WRONG_NEXT_HOP_TOP02_BRANCH.yml",
)
FROZEN_GROUP_ID = "CTX_G03_TOP02_BRANCH_MID"
TOPOLOGY_REFERENCE = (
    "labs/topologies/top02_branch/topology.clab.yml"
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


def test_topology_matches_frozen_g03_branched_graph() -> None:
    document = load_yaml(TOPOLOGY_PATH)

    assert document["name"] == "top02branch"

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
        "r4",
        "hostc",
    }
    assert links == [
        {"endpoints": ["hosta:eth1", "r1:eth1"]},
        {"endpoints": ["r1:eth2", "r2:eth1"]},
        {"endpoints": ["r2:eth2", "r3:eth1"]},
        {"endpoints": ["r3:eth2", "hostb:eth1"]},
        {"endpoints": ["r2:eth3", "r4:eth1"]},
        {"endpoints": ["r4:eth2", "hostc:eth1"]},
    ]


def test_topology_matches_frozen_address_and_route_plan() -> None:
    topology = load_yaml(TOPOLOGY_PATH)["topology"]
    assert isinstance(topology, dict)
    nodes = topology["nodes"]
    assert isinstance(nodes, dict)

    expected_commands = {
        "hosta": {
            "ip addr add 10.30.1.10/24 dev eth1",
            "ip route replace 10.30.3.0/24 via 10.30.1.1",
            "ip route replace 10.30.4.0/24 via 10.30.1.1",
        },
        "r1": {
            "ip addr add 10.30.1.1/24 dev eth1",
            "ip addr add 10.30.12.1/29 dev eth2",
            "ip route replace 10.30.3.0/24 via 10.30.12.2",
            "ip route replace 10.30.4.0/24 via 10.30.12.2",
        },
        "r2": {
            "ip addr add 10.30.12.2/29 dev eth1",
            "ip addr add 10.30.23.1/29 dev eth2",
            "ip addr add 10.30.24.1/29 dev eth3",
            "ip route replace 10.30.1.0/24 via 10.30.12.1",
            "ip route replace 10.30.3.0/24 via 10.30.23.2",
            "ip route replace 10.30.4.0/24 via 10.30.24.2",
        },
        "r3": {
            "ip addr add 10.30.23.2/29 dev eth1",
            "ip addr add 10.30.3.1/24 dev eth2",
            "ip route replace 10.30.1.0/24 via 10.30.23.1",
        },
        "hostb": {
            "ip addr add 10.30.3.10/24 dev eth1",
            "ip route replace 10.30.1.0/24 via 10.30.3.1",
        },
        "r4": {
            "ip addr add 10.30.24.2/29 dev eth1",
            "ip addr add 10.30.4.1/24 dev eth2",
            "ip route replace 10.30.1.0/24 via 10.30.24.1",
        },
        "hostc": {
            "ip addr add 10.30.4.10/24 dev eth1",
            "ip route replace 10.30.1.0/24 via 10.30.4.1",
        },
    }

    for node_name, expected in expected_commands.items():
        commands = set(node_commands(nodes, node_name))
        assert expected <= commands

    for router in ("r1", "r2", "r3", "r4"):
        node = nodes[router]
        assert isinstance(node, dict)
        assert node["sysctls"] == {
            "net.ipv4.ip_forward": 1
        }


def test_g03_scenarios_share_frozen_observation_context() -> None:
    profiles = []
    fault_types = []

    for name in SCENARIO_NAMES:
        scenario = load_scenario(name)
        topology = scenario["topology"]
        ground_truth = scenario["ground_truth"]

        assert isinstance(topology, dict)
        assert isinstance(ground_truth, dict)
        assert topology == {
            "id": "TOP_02_BRANCH",
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
            "TOP_02_BRANCH",
            "hosta_to_hostc",
            "clab-top02branch-hosta",
            "10.30.1.1",
            "10.30.4.10",
            "10.30.4.0/24",
            "r2",
            "clab-top02branch-r2",
            "10.30.24.2",
            "r4",
            "clab-top02branch-r4",
        )
    }


def test_g03_fault_bindings_match_frozen_design() -> None:
    c1 = load_scenario(
        "C1_MISSING_STATIC_ROUTE_TOP02_BRANCH.yml"
    )
    c2 = load_scenario(
        "C2_WRONG_NEXT_HOP_TOP02_BRANCH.yml"
    )

    for scenario in (c1, c2):
        fault = scenario["fault"]
        ground_truth = scenario["ground_truth"]
        restoration = scenario["restoration"]

        assert isinstance(fault, dict)
        assert isinstance(ground_truth, dict)
        assert isinstance(restoration, dict)
        assert fault["target_node"] == "r2"
        assert (
            fault["target_container"]
            == "clab-top02branch-r2"
        )
        assert ground_truth["fault_location"] == "r2"
        assert (
            ground_truth["affected_prefix"]
            == "10.30.4.0/24"
        )
        assert restoration["command"] == [
            "ip",
            "route",
            "replace",
            "10.30.4.0/24",
            "via",
            "10.30.24.2",
            "dev",
            "eth3",
        ]

    c1_parameters = c1["fault"]["parameters"]
    c2_parameters = c2["fault"]["parameters"]

    assert c1_parameters == {
        "destination_prefix": "10.30.4.0/24",
        "next_hop": "10.30.24.2",
    }
    assert c2_parameters == {
        "destination_prefix": "10.30.4.0/24",
        "correct_next_hop": "10.30.24.2",
        "wrong_next_hop": "10.30.24.6",
        "egress_interface": "eth3",
    }


def test_g03_smoke_plan_has_one_complete_class_set() -> None:
    plan = load_batch_plan(
        PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )
    experiments = expand_batch_plan(plan)

    assert plan.batch_id == "P2_G03_SMOKE"
    assert plan.execution_order == "listed"
    assert plan.failure_policy == "stop"
    assert [item.entry_id for item in experiments] == [
        "n0_g03_branch",
        "c1_g03_branch",
        "c2_g03_branch",
    ]
    assert [
        item.scenario_path.name
        for item in experiments
    ] == list(SCENARIO_NAMES)
    assert all(
        item.repetition_index == 1
        for item in experiments
    )


def test_g03_validator_covers_both_real_branches() -> None:
    validator = VALIDATOR_PATH.read_text(
        encoding="utf-8"
    )

    required_values = (
        "clab-top02branch-hosta",
        "clab-top02branch-r1",
        "clab-top02branch-r2",
        "clab-top02branch-r3",
        "clab-top02branch-hostb",
        "clab-top02branch-r4",
        "clab-top02branch-hostc",
        "10.30.23.2",
        "10.30.3.10",
        "10.30.24.2",
        "10.30.4.10",
        "10.30.24.6",
        "HostA reaches HostB through the independent branch",
        "HostA reaches HostC through the observed branch",
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
    assert validator.count("run_check \\") == 40


def test_g03_is_materially_distinct_from_g02() -> None:
    g02_scenario_path = (
        SCENARIO_ROOT
        / "N0_NORMAL_OPERATION_TOP02_CHAIN.yml"
    )
    g02 = load_yaml(g02_scenario_path)["scenario"]
    g03 = load_scenario(
        "N0_NORMAL_OPERATION_TOP02_BRANCH.yml"
    )

    assert isinstance(g02, dict)
    assert g02["split_group_id"] != g03["split_group_id"]

    g02_profile = validate_observation_profile(g02)
    g03_profile = validate_observation_profile(g03)

    assert (
        g02_profile.topology_id,
        g02_profile.route_observer_node,
        g02_profile.transit_node,
        g02_profile.direction,
    ) == (
        "TOP_02_CHAIN",
        "r1",
        "r2",
        "hosta_to_hostb",
    )
    assert (
        g03_profile.topology_id,
        g03_profile.route_observer_node,
        g03_profile.transit_node,
        g03_profile.direction,
    ) == (
        "TOP_02_BRANCH",
        "r2",
        "r4",
        "hosta_to_hostc",
    )

    topology = load_yaml(TOPOLOGY_PATH)["topology"]
    assert isinstance(topology, dict)
    nodes = topology["nodes"]
    assert isinstance(nodes, dict)

    r2_commands = set(node_commands(nodes, "r2"))
    assert {
        "ip route replace 10.30.3.0/24 via 10.30.23.2",
        "ip route replace 10.30.4.0/24 via 10.30.24.2",
    } <= r2_commands
