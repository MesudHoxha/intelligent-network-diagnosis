from unittest.mock import patch

from src.fault_injection.common import CommandResult
from src.fault_injection.wrong_next_hop import (
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
