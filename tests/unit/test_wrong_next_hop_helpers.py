from pathlib import Path
from unittest.mock import call
from unittest.mock import patch

import yaml

from src.fault_injection.common import CommandResult
from src.fault_injection.wrong_next_hop import (
    inject_wrong_next_hop,
    route_uses_next_hop,
)


def make_result(stdout: str) -> CommandResult:
    return CommandResult(
        command=[
            "docker",
            "exec",
            "container",
            "ip",
            "route",
        ],
        return_code=0,
        stdout=stdout,
        stderr="",
    )


@patch(
    "src.fault_injection.wrong_next_hop.docker_exec"
)
def test_route_uses_next_hop_returns_true_for_match(
    mock_docker_exec,
) -> None:
    mock_docker_exec.return_value = make_result(
        "10.10.2.0/24 via 10.10.12.254 "
        "dev eth2 onlink"
    )

    assert route_uses_next_hop(
        "clab-top01-r1",
        "10.10.2.0/24",
        "10.10.12.254",
    ) is True


@patch(
    "src.fault_injection.wrong_next_hop.docker_exec"
)
def test_route_uses_next_hop_rejects_other_gateway(
    mock_docker_exec,
) -> None:
    mock_docker_exec.return_value = make_result(
        "10.10.2.0/24 via 10.10.12.2 dev eth2"
    )

    assert route_uses_next_hop(
        "clab-top01-r1",
        "10.10.2.0/24",
        "10.10.12.254",
    ) is False


def write_secondary_scenario(path: Path) -> None:
    document = {
        "schema_version": 1,
        "scenario": {
            "id": "C2_WRONG_NEXT_HOP",
            "kind": "fault",
            "topology": {
                "id": "TOP_01",
                "file": "topology.yml",
            },
            "observation": {
                "schema_version": 1,
                "direction": "hosta_to_hostb",
                "source_container": "clab-top01-hosta",
                "source_gateway_address": "10.10.1.1",
                "destination_address": "10.10.22.10",
                "destination_prefix": "10.10.22.0/24",
                "route_observer_node": "r1",
                "route_observer_container": (
                    "clab-top01-r1"
                ),
                "expected_next_hop": "10.10.12.2",
                "transit_node": "r2",
                "transit_container": "clab-top01-r2",
            },
            "fault": {
                "type": "wrong_next_hop",
                "target_node": "r1",
                "target_container": "clab-top01-r1",
                "parameters": {
                    "destination_prefix": "10.10.22.0/24",
                    "correct_next_hop": "10.10.12.2",
                    "wrong_next_hop": "10.10.12.254",
                    "egress_interface": "eth2",
                },
            },
            "ground_truth": {
                "fault_type": "wrong_next_hop",
            },
        },
    }
    path.write_text(
        yaml.safe_dump(document, sort_keys=False),
        encoding="utf-8",
    )


def test_wrong_next_hop_uses_observation_profile_addresses(
    tmp_path: Path,
) -> None:
    scenario_path = tmp_path / "scenario.yml"
    write_secondary_scenario(scenario_path)

    command_result = CommandResult(
        command=["docker", "exec", "clab-top01-r1"],
        return_code=0,
        stdout="",
        stderr="",
    )

    with (
        patch(
            "src.fault_injection.wrong_next_hop.route_exists",
            side_effect=[True, True],
        ),
        patch(
            "src.fault_injection.wrong_next_hop."
            "route_uses_next_hop",
            side_effect=[True, True, False],
        ),
        patch(
            "src.fault_injection.wrong_next_hop.ping_succeeds",
            side_effect=[
                True,
                True,
                False,
                False,
                True,
                True,
                False,
            ],
        ) as mock_ping,
        patch(
            "src.fault_injection.wrong_next_hop.docker_exec",
            return_value=command_result,
        ),
    ):
        record = inject_wrong_next_hop(
            scenario_path,
            tmp_path / "output",
        )

    assert record.status == "FAULT_CONFIRMED"
    assert mock_ping.call_args_list == [
        call("clab-top01-hosta", "10.10.22.10"),
        call("clab-top01-r1", "10.10.12.2"),
        call("clab-top01-r1", "10.10.12.254"),
        call("clab-top01-hosta", "10.10.22.10"),
        call("clab-top01-hosta", "10.10.1.1"),
        call("clab-top01-r1", "10.10.12.2"),
        call("clab-top01-r1", "10.10.12.254"),
    ]
