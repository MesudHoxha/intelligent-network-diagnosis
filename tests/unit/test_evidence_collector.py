from pathlib import Path
from unittest.mock import call, patch

from src.collection.evidence_collector import (
    collect_evidence,
    route_next_hop,
)
from src.contracts.observation_profile import (
    ObservationProfile,
)


def make_result(
    stdout: str,
    return_code: int = 0,
) -> dict[str, object]:
    return {
        "command": ["ip", "route", "show"],
        "return_code": return_code,
        "stdout": stdout,
        "stderr": "",
        "timestamp_utc": (
            "2026-07-28T00:00:00+00:00"
        ),
    }


def test_route_next_hop_extracts_gateway() -> None:
    result = make_result(
        "10.10.2.0/24 via 10.10.12.254 "
        "dev eth2 onlink"
    )

    assert route_next_hop(result) == "10.10.12.254"


def test_route_next_hop_returns_none_for_empty_route(
) -> None:
    assert route_next_hop(make_result("")) is None


def test_route_next_hop_returns_none_on_command_error(
) -> None:
    result = make_result(
        "command failed",
        return_code=2,
    )

    assert route_next_hop(result) is None


def secondary_profile() -> ObservationProfile:
    return ObservationProfile(
        schema_version=1,
        direction="hosta_to_hostb",
        source_container="clab-top01-hosta",
        source_gateway_address="10.10.1.1",
        destination_address="10.10.22.10",
        destination_prefix="10.10.22.0/24",
        route_observer_node="r1",
        route_observer_container="clab-top01-r1",
        expected_next_hop="10.10.12.2",
        transit_node="r2",
        transit_container="clab-top01-r2",
    )


@patch("src.collection.evidence_collector.ping_result")
@patch("src.collection.evidence_collector.route_result")
def test_collect_evidence_uses_observation_profile(
    mock_route_result,
    mock_ping_result,
    tmp_path: Path,
) -> None:
    mock_route_result.return_value = make_result(
        "10.10.22.0/24 via 10.10.12.2 dev eth2"
    )
    mock_ping_result.return_value = make_result("")

    collect_evidence(
        tmp_path,
        secondary_profile(),
    )

    mock_route_result.assert_called_once_with(
        "clab-top01-r1",
        "10.10.22.0/24",
    )
    assert mock_ping_result.call_args_list == [
        call("clab-top01-hosta", "10.10.1.1"),
        call("clab-top01-hosta", "10.10.22.10"),
        call("clab-top01-r1", "10.10.12.2"),
        call("clab-top01-r2", "10.10.22.10"),
        call("clab-top01-r1", "10.10.12.2"),
    ]
