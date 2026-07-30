import json
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
        topology_id="TOP_02",
        direction="clienta_to_serviceb",
        source_container="clab-top02-clienta",
        source_gateway_address="10.10.1.1",
        destination_address="10.10.22.10",
        destination_prefix="10.10.22.0/24",
        route_observer_node="edge1",
        route_observer_container="clab-top02-edge1",
        expected_next_hop="10.10.12.2",
        transit_node="core1",
        transit_container="clab-top02-core1",
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

    saved_evidence = json.loads(
        (
            tmp_path / "parsed" / "evidence.json"
        ).read_text(encoding="utf-8")
    )

    assert saved_evidence["destination_address"] == (
        "10.10.22.10"
    )
    assert saved_evidence["destination_prefix"] == (
        "10.10.22.0/24"
    )
    assert saved_evidence["schema_version"] == 2
    assert saved_evidence["topology_id"] == "TOP_02"
    assert saved_evidence["direction"] == (
        "clienta_to_serviceb"
    )
    assert saved_evidence["route_observer_node"] == "edge1"
    assert saved_evidence["transit_node"] == "core1"
    assert (
        saved_evidence[
            "route_to_destination_exists_on_observer"
        ]
        is True
    )
    assert (
        saved_evidence[
            "route_next_hop_on_observer"
        ]
        == "10.10.12.2"
    )
    assert "route_to_destination_exists_on_r1" not in (
        saved_evidence
    )

    mock_route_result.assert_called_once_with(
        "clab-top02-edge1",
        "10.10.22.0/24",
    )
    assert mock_ping_result.call_args_list == [
        call("clab-top02-clienta", "10.10.1.1"),
        call("clab-top02-clienta", "10.10.22.10"),
        call("clab-top02-edge1", "10.10.12.2"),
        call("clab-top02-core1", "10.10.22.10"),
        call("clab-top02-edge1", "10.10.12.2"),
    ]

    collector_status = json.loads(
        (
            tmp_path / "collector_status.json"
        ).read_text(encoding="utf-8")
    )

    assert collector_status["collector"] == (
        "RoleNeutralEvidenceCollector"
    )
    assert collector_status["topology_id"] == "TOP_02"
