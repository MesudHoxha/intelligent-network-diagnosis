from typing import Any

from src.rules.rule_engine import diagnose


def make_evidence(
    **overrides: object,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "topology_id": "TOP_01",
        "source_gateway_reachable": True,
        "destination_reachable": True,
        "route_to_destination_exists_on_r1": True,
        "route_next_hop_on_r1": "10.10.12.2",
        "route_next_hop_reachable_from_r1": True,
        "transit_next_hop_reachable": True,
        "destination_reachable_from_r2": True,
    }
    evidence.update(overrides)
    return evidence


def test_diagnose_recognizes_normal_operation() -> None:
    result = diagnose(make_evidence())

    assert result["status"] == "NO_FAULT_DETECTED"
    assert result["matched_rules"] == [
        "R_BASELINE_001"
    ]


def test_diagnose_recognizes_missing_route() -> None:
    evidence = make_evidence(
        destination_reachable=False,
        route_to_destination_exists_on_r1=False,
        route_next_hop_on_r1=None,
        route_next_hop_reachable_from_r1=None,
    )

    result = diagnose(evidence)

    assert result["status"] == "DIAGNOSIS_PRODUCED"
    assert result["diagnosis"]["fault_type"] == (
        "missing_static_route"
    )
    assert result["matched_rules"] == [
        "R_ROUTING_001"
    ]


def test_diagnose_recognizes_wrong_next_hop() -> None:
    evidence = make_evidence(
        destination_reachable=False,
        route_next_hop_on_r1="10.10.12.254",
        route_next_hop_reachable_from_r1=False,
    )

    result = diagnose(evidence)

    assert result["status"] == "DIAGNOSIS_PRODUCED"
    assert result["diagnosis"]["fault_type"] == (
        "wrong_next_hop"
    )
    assert result["diagnosis"]["observed_next_hop"] == (
        "10.10.12.254"
    )
    assert result["matched_rules"] == [
        "R_ROUTING_002"
    ]


def test_wrong_next_hop_requires_next_hop_evidence(
) -> None:
    evidence = make_evidence(
        destination_reachable=False,
        route_next_hop_on_r1=None,
        route_next_hop_reachable_from_r1=None,
    )

    result = diagnose(evidence)

    assert result["status"] == (
        "INSUFFICIENT_EVIDENCE"
    )
    assert result["missing_evidence"] == [
        "route_next_hop_on_r1",
        "route_next_hop_reachable_from_r1",
    ]
