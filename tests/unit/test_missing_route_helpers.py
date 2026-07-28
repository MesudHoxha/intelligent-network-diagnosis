from unittest.mock import patch

from src.fault_injection.common import (
    CommandResult,
    route_exists,
)


def make_result(stdout: str) -> CommandResult:
    return CommandResult(
        command=["docker", "exec", "container", "ip", "route"],
        return_code=0,
        stdout=stdout,
        stderr="",
    )


@patch("src.fault_injection.common.docker_exec")
def test_route_exists_returns_true_for_nonempty_output(
    mock_docker_exec,
) -> None:
    mock_docker_exec.return_value = make_result(
        "10.10.2.0/24 via 10.10.12.2 dev eth2"
    )

    assert route_exists(
        "clab-top01-r1",
        "10.10.2.0/24",
    ) is True


@patch("src.fault_injection.common.docker_exec")
def test_route_exists_returns_false_for_empty_output(
    mock_docker_exec,
) -> None:
    mock_docker_exec.return_value = make_result("")

    assert route_exists(
        "clab-top01-r1",
        "10.10.2.0/24",
    ) is False
