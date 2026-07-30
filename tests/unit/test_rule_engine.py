from typing import Any

from src.rules.rule_engine import diagnose


def make_evidence(
    **overrides: object,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "topology_id": "TOP_01",
        "destination_address": "10.10.2.10",
        "destination_prefix": "10.10.2.0/24",
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


def make_role_neutral_evidence(
    **overrides: object,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "schema_version": 2,
        "topology_id": "TOP_02",
        "direction": "clienta_to_serviceb",
        "route_observer_node": "edge1",
        "transit_node": "core1",
        "destination_address": "10.20.2.10",
        "destination_prefix": "10.20.2.0/24",
        "source_gateway_reachable": True,
        "destination_reachable": True,
        "route_to_destination_exists_on_observer": True,
        "route_next_hop_on_observer": "10.20.12.2",
        "route_next_hop_reachable_from_observer": True,
        "expected_next_hop_reachable_from_observer": True,
        "destination_reachable_from_transit": True,
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
    assert result["diagnosis"]["affected_prefix"] == (
        "10.10.2.0/24"
    )


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
    assert result["diagnosis"]["affected_prefix"] == (
        "10.10.2.0/24"
    )


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


def test_missing_route_uses_alternate_destination_prefix(
) -> None:
    evidence = make_evidence(
        destination_address="10.10.22.10",
        destination_prefix="10.10.22.0/24",
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
    assert result["diagnosis"]["affected_prefix"] == (
        "10.10.22.0/24"
    )


def test_wrong_next_hop_uses_alternate_destination_prefix(
) -> None:
    evidence = make_evidence(
        destination_address="10.10.22.10",
        destination_prefix="10.10.22.0/24",
        destination_reachable=False,
        route_next_hop_on_r1="10.10.12.254",
        route_next_hop_reachable_from_r1=False,
    )

    result = diagnose(evidence)

    assert result["status"] == "DIAGNOSIS_PRODUCED"
    assert result["diagnosis"]["fault_type"] == (
        "wrong_next_hop"
    )
    assert result["diagnosis"]["affected_prefix"] == (
        "10.10.22.0/24"
    )


def test_diagnose_requires_destination_prefix(
) -> None:
    evidence = make_evidence()
    evidence.pop("destination_prefix")

    result = diagnose(evidence)

    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["missing_evidence"] == [
        "destination_prefix"
    ]


def test_role_neutral_missing_route_uses_observer_location(
) -> None:
    evidence = make_role_neutral_evidence(
        destination_reachable=False,
        route_to_destination_exists_on_observer=False,
        route_next_hop_on_observer=None,
        route_next_hop_reachable_from_observer=None,
    )

    result = diagnose(evidence)

    assert result["status"] == "DIAGNOSIS_PRODUCED"
    assert result["topology_id"] == "TOP_02"
    assert result["diagnosis"] == {
        "category": "routing",
        "fault_type": "missing_static_route",
        "location": "edge1",
        "affected_prefix": "10.20.2.0/24",
    }
    assert any(
        "edge1" in item
        for item in result["supporting_evidence"]
    )
    assert any(
        "core1" in item
        for item in result["supporting_evidence"]
    )


def test_role_neutral_wrong_next_hop_uses_observer_location(
) -> None:
    evidence = make_role_neutral_evidence(
        destination_reachable=False,
        route_next_hop_on_observer="10.20.12.254",
        route_next_hop_reachable_from_observer=False,
    )

    result = diagnose(evidence)

    assert result["status"] == "DIAGNOSIS_PRODUCED"
    assert result["diagnosis"]["fault_type"] == (
        "wrong_next_hop"
    )
    assert result["diagnosis"]["location"] == "edge1"
    assert result["diagnosis"]["observed_next_hop"] == (
        "10.20.12.254"
    )


def test_role_neutral_evidence_reports_neutral_missing_names(
) -> None:
    evidence = make_role_neutral_evidence(
        destination_reachable=False,
        route_next_hop_on_observer=None,
        route_next_hop_reachable_from_observer=None,
    )

    result = diagnose(evidence)

    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["missing_evidence"] == [
        "route_next_hop_on_observer",
        "route_next_hop_reachable_from_observer",
    ]


def test_role_neutral_evidence_requires_role_context(
) -> None:
    evidence = make_role_neutral_evidence()
    evidence.pop("route_observer_node")

    result = diagnose(evidence)

    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["missing_evidence"] == [
        "route_observer_node"
    ]


def test_rejects_unsupported_evidence_schema() -> None:
    evidence = make_role_neutral_evidence(
        schema_version=3
    )

    try:
        diagnose(evidence)
    except ValueError as error:
        assert "schema_version" in str(error)
    else:
        raise AssertionError(
            "Unsupported evidence schema was accepted."
        )
