from src.collection.evidence_collector import (
    route_next_hop,
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
