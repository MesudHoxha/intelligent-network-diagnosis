from pathlib import Path

import yaml

from src.contracts.observation_profile import (
    validate_observation_profile,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_ROOT = REPOSITORY_ROOT / "scenarios" / "routing"
PLAN_PATH = (
    REPOSITORY_ROOT
    / "plans"
    / "batches"
    / "P1_ROUTING_VARIANTS.yml"
)
TOPOLOGY_PATH = (
    REPOSITORY_ROOT
    / "labs"
    / "topologies"
    / "top01_routed"
    / "topology.clab.yml"
)

SCENARIO_PAIRS = (
    (
        "N0_NORMAL_OPERATION.yml",
        "N0_NORMAL_OPERATION_ALT_SUBNET.yml",
    ),
    (
        "C1_MISSING_STATIC_ROUTE.yml",
        "C1_MISSING_STATIC_ROUTE_ALT_SUBNET.yml",
    ),
    (
        "C2_WRONG_NEXT_HOP.yml",
        "C2_WRONG_NEXT_HOP_ALT_SUBNET.yml",
    ),
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


def test_secondary_profiles_are_valid_and_grouped() -> None:
    for canonical_name, alternate_name in SCENARIO_PAIRS:
        canonical = load_scenario(canonical_name)
        alternate = load_scenario(alternate_name)

        canonical_profile = validate_observation_profile(
            canonical
        )
        alternate_profile = validate_observation_profile(
            alternate
        )

        assert alternate["id"] == canonical["id"]
        assert canonical["variant_id"] == "canonical"
        assert (
            alternate["variant_id"]
            == "alternate_hostb_subnet"
        )
        canonical_split_group = canonical.get(
            "split_group_id",
            f"TOP_01:{canonical['id']}:canonical",
        )
        assert (
            alternate["split_group_id"]
            == canonical_split_group
        )
        assert (
            alternate_profile.direction
            == canonical_profile.direction
            == "hosta_to_hostb"
        )
        assert (
            alternate_profile.destination_address
            == "10.10.22.10"
        )
        assert (
            alternate_profile.destination_prefix
            == "10.10.22.0/24"
        )


def test_alternate_fault_artifacts_use_same_prefix() -> None:
    for name in (
        "C1_MISSING_STATIC_ROUTE_ALT_SUBNET.yml",
        "C2_WRONG_NEXT_HOP_ALT_SUBNET.yml",
    ):
        scenario = load_scenario(name)
        observation = scenario["observation"]
        fault = scenario["fault"]
        ground_truth = scenario["ground_truth"]
        restoration = scenario["restoration"]

        assert isinstance(observation, dict)
        assert isinstance(fault, dict)
        assert isinstance(ground_truth, dict)
        assert isinstance(restoration, dict)

        parameters = fault["parameters"]
        command = restoration["command"]

        assert isinstance(parameters, dict)
        assert isinstance(command, list)
        assert (
            parameters["destination_prefix"]
            == observation["destination_prefix"]
        )
        assert (
            ground_truth["affected_prefix"]
            == observation["destination_prefix"]
        )
        assert observation["destination_prefix"] in command


def test_p1_plan_contains_twelve_listed_experiments() -> None:
    document = load_yaml(PLAN_PATH)
    batch = document["batch"]
    assert isinstance(batch, dict)

    execution = batch["execution"]
    entries = batch["entries"]

    assert isinstance(execution, dict)
    assert isinstance(entries, list)
    assert execution == {
        "order": "listed",
        "failure_policy": "stop",
    }
    assert [entry["entry_id"] for entry in entries] == [
        "n0_canonical",
        "n0_alternate_hostb_subnet",
        "c1_canonical",
        "c1_alternate_hostb_subnet",
        "c2_canonical",
        "c2_alternate_hostb_subnet",
    ]
    assert all(entry["repetitions"] == 2 for entry in entries)
    assert sum(entry["repetitions"] for entry in entries) == 12

    for entry in entries:
        scenario_path = REPOSITORY_ROOT / entry["scenario_path"]
        assert scenario_path.is_file()


def test_topology_provides_alternate_hostb_subnet() -> None:
    document = load_yaml(TOPOLOGY_PATH)
    topology = document["topology"]
    assert isinstance(topology, dict)

    nodes = topology["nodes"]
    assert isinstance(nodes, dict)

    hosta_exec = nodes["hosta"]["exec"]
    r1_exec = nodes["r1"]["exec"]
    r2_exec = nodes["r2"]["exec"]
    hostb_exec = nodes["hostb"]["exec"]

    assert (
        "ip route replace 10.10.22.0/24 via 10.10.1.1"
        in hosta_exec
    )
    assert (
        "ip route replace 10.10.22.0/24 via 10.10.12.2"
        in r1_exec
    )
    assert "ip addr add 10.10.22.1/24 dev eth2" in r2_exec
    assert "ip addr add 10.10.22.10/24 dev eth1" in hostb_exec
