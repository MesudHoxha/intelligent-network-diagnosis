import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.contracts.evidence import (
    EvidenceContractError,
    validate_evidence_v2,
)


def valid_evidence() -> dict[str, object]:
    return {
        "schema_version": 2,
        "topology_id": "TOP_02",
        "collected_at_utc": (
            "2026-07-30T12:00:00+00:00"
        ),
        "direction": "clienta_to_serviceb",
        "route_observer_node": "edge1",
        "transit_node": "core1",
        "destination_address": "10.20.2.10",
        "destination_prefix": "10.20.2.0/24",
        "source_gateway_reachable": True,
        "destination_reachable": False,
        "route_to_destination_exists_on_observer": False,
        "route_next_hop_on_observer": None,
        "route_next_hop_reachable_from_observer": None,
        "expected_next_hop_reachable_from_observer": True,
        "destination_reachable_from_transit": True,
    }


def test_accepts_role_neutral_evidence() -> None:
    validate_evidence_v2(valid_evidence())


def test_json_schema_accepts_role_neutral_evidence() -> None:
    schema = json.loads(
        Path(
            "schemas/evidence_v2.schema.json"
        ).read_text(encoding="utf-8")
    )

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(
        valid_evidence()
    )


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("schema_version", 1, "schema_version"),
        ("topology_id", "", "topology_id"),
        ("direction", "clienta-serviceb", "direction"),
        (
            "route_observer_node",
            "edge 1",
            "valid identifier",
        ),
        (
            "collected_at_utc",
            "2026-07-30T12:00:00",
            "UTC offset",
        ),
        (
            "destination_address",
            "10.30.2.10",
            "must belong",
        ),
        (
            "source_gateway_reachable",
            1,
            "true, false, or null",
        ),
        (
            "route_next_hop_on_observer",
            "not-an-ip",
            "IPv4 address or null",
        ),
    ],
)
def test_rejects_invalid_evidence_values(
    field_name: str,
    value: object,
    message: str,
) -> None:
    evidence = deepcopy(valid_evidence())
    evidence[field_name] = value

    with pytest.raises(
        EvidenceContractError,
        match=message,
    ):
        validate_evidence_v2(evidence)


def test_rejects_same_observer_and_transit() -> None:
    evidence = valid_evidence()
    evidence["transit_node"] = "edge1"

    with pytest.raises(
        EvidenceContractError,
        match="must be different",
    ):
        validate_evidence_v2(evidence)


def test_rejects_unexpected_field() -> None:
    evidence = valid_evidence()
    evidence["fault_type"] = "poisoned"

    with pytest.raises(
        EvidenceContractError,
        match="Unexpected Evidence v2 fields",
    ):
        validate_evidence_v2(evidence)
