from __future__ import annotations

from ipaddress import ip_address, ip_network
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
    / "top03_asymmetric_return"
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
    / "P2_G05_SMOKE.yml"
)
SCENARIO_ROOT = REPOSITORY_ROOT / "scenarios" / "routing"
SCENARIO_NAMES = (
    "N0_NORMAL_OPERATION_TOP03_ASYMMETRIC_RETURN.yml",
    "C1_MISSING_STATIC_ROUTE_TOP03_ASYMMETRIC_RETURN.yml",
    "C2_WRONG_NEXT_HOP_TOP03_ASYMMETRIC_RETURN.yml",
)
FROZEN_GROUP_ID = "CTX_G05_TOP03_ASYMMETRIC_RETURN"
TOPOLOGY_REFERENCE = (
    "labs/topologies/top03_asymmetric_return/topology.clab.yml"
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


def test_topology_matches_frozen_g05_cycle() -> None:
    document = load_yaml(TOPOLOGY_PATH)

    assert document["name"] == "top03asym"

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
    }
    assert links == [
        {"endpoints": ["hosta:eth1", "r1:eth1"]},
        {"endpoints": ["r1:eth2", "r2:eth1"]},
        {"endpoints": ["r2:eth2", "r3:eth1"]},
        {"endpoints": ["r3:eth2", "hostb:eth1"]},
        {"endpoints": ["r3:eth3", "r4:eth1"]},
        {"endpoints": ["r4:eth2", "r1:eth3"]},
    ]


def test_topology_matches_frozen_routes_and_rp_filter() -> None:
    topology = load_yaml(TOPOLOGY_PATH)["topology"]
    assert isinstance(topology, dict)
    nodes = topology["nodes"]
    assert isinstance(nodes, dict)

    expected_commands = {
        "hosta": {
            "ip addr add 10.50.1.10/24 dev eth1",
            "ip route replace 10.50.3.0/24 via 10.50.1.1",
        },
        "r1": {
            "ip addr add 10.50.1.1/24 dev eth1",
            "ip addr add 10.50.12.1/29 dev eth2",
            "ip addr add 10.50.14.1/29 dev eth3",
            "ip route replace 10.50.3.0/24 via 10.50.12.2",
            "sysctl -w net.ipv4.conf.eth1.rp_filter=0",
            "sysctl -w net.ipv4.conf.eth2.rp_filter=0",
            "sysctl -w net.ipv4.conf.eth3.rp_filter=0",
        },
        "r2": {
            "ip addr add 10.50.12.2/29 dev eth1",
            "ip addr add 10.50.23.1/29 dev eth2",
            "ip route replace 10.50.1.0/24 via 10.50.12.1",
            "ip route replace 10.50.3.0/24 via 10.50.23.2",
        },
        "r3": {
            "ip addr add 10.50.23.2/29 dev eth1",
            "ip addr add 10.50.3.1/24 dev eth2",
            "ip addr add 10.50.34.1/29 dev eth3",
            "ip route replace 10.50.1.0/24 via 10.50.34.2",
        },
        "hostb": {
            "ip addr add 10.50.3.10/24 dev eth1",
            "ip route replace 10.50.1.0/24 via 10.50.3.1",
        },
        "r4": {
            "ip addr add 10.50.34.2/29 dev eth1",
            "ip addr add 10.50.14.2/29 dev eth2",
            "ip route replace 10.50.1.0/24 via 10.50.14.1",
            "ip route replace 10.50.3.0/24 via 10.50.34.1",
        },
    }

    for node_name, expected in expected_commands.items():
        commands = set(node_commands(nodes, node_name))
        assert expected <= commands

    expected_sysctls = {
        "net.ipv4.ip_forward": 1,
        "net.ipv4.conf.all.rp_filter": 0,
        "net.ipv4.conf.default.rp_filter": 0,
    }

    for router in ("r1", "r2", "r3", "r4"):
        node = nodes[router]
        assert isinstance(node, dict)
        assert node["sysctls"] == expected_sysctls

        commands = node_commands(nodes, router)
        interface_count = {
            "r1": 3,
            "r2": 2,
            "r3": 3,
            "r4": 2,
        }[router]
        for index in range(1, interface_count + 1):
            assert (
                "sysctl -w "
                f"net.ipv4.conf.eth{index}.rp_filter=0"
                in commands
            )


def test_g05_scenarios_share_frozen_observation_context() -> None:
    profiles = []
    fault_types = []

    for name in SCENARIO_NAMES:
        scenario = load_scenario(name)
        topology = scenario["topology"]
        ground_truth = scenario["ground_truth"]

        assert isinstance(topology, dict)
        assert isinstance(ground_truth, dict)
        assert topology == {
            "id": "TOP_03_ASYMMETRIC_RETURN",
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
            "TOP_03_ASYMMETRIC_RETURN",
            "hosta_to_hostb",
            "clab-top03asym-hosta",
            "10.50.1.1",
            "10.50.3.10",
            "10.50.3.0/24",
            "r2",
            "clab-top03asym-r2",
            "10.50.23.2",
            "r3",
            "clab-top03asym-r3",
        )
    }


def test_g05_fault_bindings_match_frozen_design() -> None:
    c1 = load_scenario(
        "C1_MISSING_STATIC_ROUTE_TOP03_ASYMMETRIC_RETURN.yml"
    )
    c2 = load_scenario(
        "C2_WRONG_NEXT_HOP_TOP03_ASYMMETRIC_RETURN.yml"
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
            == "clab-top03asym-r2"
        )
        assert ground_truth["fault_location"] == "r2"
        assert (
            ground_truth["affected_prefix"]
            == "10.50.3.0/24"
        )
        assert restoration["command"] == [
            "ip",
            "route",
            "replace",
            "10.50.3.0/24",
            "via",
            "10.50.23.2",
            "dev",
            "eth2",
        ]

    c1_parameters = c1["fault"]["parameters"]
    c2_parameters = c2["fault"]["parameters"]

    assert c1_parameters == {
        "destination_prefix": "10.50.3.0/24",
        "next_hop": "10.50.23.2",
    }
    assert c2_parameters == {
        "destination_prefix": "10.50.3.0/24",
        "correct_next_hop": "10.50.23.2",
        "wrong_next_hop": "10.50.23.6",
        "egress_interface": "eth2",
    }

    assert ip_address(
        c2_parameters["correct_next_hop"]
    ) in ip_network("10.50.23.0/29")
    assert ip_address(
        c2_parameters["wrong_next_hop"]
    ) in ip_network("10.50.23.0/29")


def test_g05_smoke_plan_has_one_complete_class_set() -> None:
    plan = load_batch_plan(
        PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )
    experiments = expand_batch_plan(plan)

    assert plan.batch_id == "P2_G05_SMOKE"
    assert plan.execution_order == "listed"
    assert plan.failure_policy == "stop"
    assert [item.entry_id for item in experiments] == [
        "n0_g05_asymmetric_return",
        "c1_g05_asymmetric_return",
        "c2_g05_asymmetric_return",
    ]
    assert [
        item.scenario_path.name
        for item in experiments
    ] == list(SCENARIO_NAMES)
    assert all(
        item.repetition_index == 1
        for item in experiments
    )


def test_g05_validator_covers_asymmetric_return_contract() -> None:
    validator = VALIDATOR_PATH.read_text(
        encoding="utf-8"
    )

    required_values = (
        "clab-top03asym-hosta",
        "clab-top03asym-r1",
        "clab-top03asym-r2",
        "clab-top03asym-r3",
        "clab-top03asym-r4",
        "clab-top03asym-hostb",
        "R1 forward route uses R2 toward HostB",
        "R2 observer route uses R3 toward HostB",
        "R3 return route uses R4 toward HostA",
        "R4 return route uses R1 toward HostA",
        "R3 return lookup excludes forward-only R2",
        "HostA reaches HostB over the selected forward path",
        "HostB reaches HostA over the distinct return path",
        "/proc/sys/net/ipv4/conf/all/rp_filter",
        "/proc/sys/net/ipv4/conf/eth3/rp_filter",
        "10.50.23.6",
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
    assert validator.count("run_check \\") == 52


def test_g05_is_materially_distinct_from_g01_to_g04() -> None:
    g05 = load_scenario(
        "N0_NORMAL_OPERATION_TOP03_ASYMMETRIC_RETURN.yml"
    )
    g05_profile = validate_observation_profile(g05)

    previous_names = (
        "N0_NORMAL_OPERATION.yml",
        "N0_NORMAL_OPERATION_TOP02_CHAIN.yml",
        "N0_NORMAL_OPERATION_TOP02_BRANCH.yml",
        "N0_NORMAL_OPERATION_TOP02_DUAL_TRANSIT.yml",
    )

    previous = [
        load_scenario(name)
        for name in previous_names
    ]

    assert all(
        item.get("split_group_id") != FROZEN_GROUP_ID
        for item in previous
    )
    assert all(
        item["topology"]["id"]
        != "TOP_03_ASYMMETRIC_RETURN"
        for item in previous
    )

    assert (
        g05_profile.route_observer_node,
        g05_profile.transit_node,
    ) == ("r2", "r3")

    topology = load_yaml(TOPOLOGY_PATH)["topology"]
    assert isinstance(topology, dict)
    nodes = topology["nodes"]
    assert isinstance(nodes, dict)

    r3_commands = set(node_commands(nodes, "r3"))
    r4_commands = set(node_commands(nodes, "r4"))

    assert (
        "ip route replace 10.50.1.0/24 via 10.50.34.2"
        in r3_commands
    )
    assert (
        "ip route replace 10.50.1.0/24 via 10.50.14.1"
        in r4_commands
    )
    assert (
        "ip route replace 10.50.3.0/24 via 10.50.34.1"
        in r4_commands
    )

    links = topology["links"]
    assert isinstance(links, list)
    assert {
        tuple(link["endpoints"])
        for link in links
    } >= {
        ("r3:eth3", "r4:eth1"),
        ("r4:eth2", "r1:eth3"),
    }
