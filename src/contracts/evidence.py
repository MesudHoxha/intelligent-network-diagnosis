from __future__ import annotations

from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv4Network
from typing import Any

from src.contracts.observation_profile import (
    DIRECTION_PATTERN,
    IDENTIFIER_PATTERN,
)


EVIDENCE_SCHEMA_VERSION = 2

STRING_FIELDS = (
    "topology_id",
    "collected_at_utc",
    "direction",
    "route_observer_node",
    "transit_node",
    "destination_address",
    "destination_prefix",
)

TRISTATE_FIELDS = (
    "source_gateway_reachable",
    "destination_reachable",
    "route_to_destination_exists_on_observer",
    "route_next_hop_reachable_from_observer",
    "expected_next_hop_reachable_from_observer",
    "destination_reachable_from_transit",
)

REQUIRED_FIELDS = {
    "schema_version",
    *STRING_FIELDS,
    *TRISTATE_FIELDS,
    "route_next_hop_on_observer",
}


class EvidenceContractError(ValueError):
    """Raised when role-neutral Evidence v2 is invalid."""


def _validate_utc_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise EvidenceContractError(
            "collected_at_utc must be an ISO-8601 timestamp."
        ) from error

    if (
        parsed.tzinfo is None
        or parsed.utcoffset() != timedelta(0)
    ):
        raise EvidenceContractError(
            "collected_at_utc must include the UTC offset."
        )


def validate_evidence_v2(
    evidence: dict[str, Any],
) -> None:
    if not isinstance(evidence, dict):
        raise EvidenceContractError(
            "Evidence must be an object."
        )

    missing = REQUIRED_FIELDS - set(evidence)
    unexpected = set(evidence) - REQUIRED_FIELDS

    if missing:
        raise EvidenceContractError(
            "Missing Evidence v2 fields: "
            + ", ".join(sorted(missing))
        )

    if unexpected:
        raise EvidenceContractError(
            "Unexpected Evidence v2 fields: "
            + ", ".join(sorted(unexpected))
        )

    schema_version = evidence["schema_version"]

    if (
        isinstance(schema_version, bool)
        or schema_version != EVIDENCE_SCHEMA_VERSION
    ):
        raise EvidenceContractError(
            "Unsupported evidence schema_version."
        )

    for field_name in STRING_FIELDS:
        value = evidence[field_name]

        if not isinstance(value, str) or not value:
            raise EvidenceContractError(
                f"{field_name} must be a non-empty string."
            )

    if not IDENTIFIER_PATTERN.fullmatch(
        evidence["topology_id"]
    ):
        raise EvidenceContractError(
            "topology_id must be a valid identifier."
        )

    if not DIRECTION_PATTERN.fullmatch(
        evidence["direction"]
    ):
        raise EvidenceContractError(
            "direction must use the "
            "'source_to_destination' identifier format."
        )

    if (
        evidence["route_observer_node"]
        == evidence["transit_node"]
    ):
        raise EvidenceContractError(
            "route_observer_node and transit_node "
            "must be different."
        )

    for field_name in (
        "route_observer_node",
        "transit_node",
    ):
        if not IDENTIFIER_PATTERN.fullmatch(
            evidence[field_name]
        ):
            raise EvidenceContractError(
                f"{field_name} must be a valid identifier."
            )

    _validate_utc_timestamp(evidence["collected_at_utc"])

    try:
        destination_address = IPv4Address(
            evidence["destination_address"]
        )
    except ValueError as error:
        raise EvidenceContractError(
            "destination_address must be a valid IPv4 address."
        ) from error

    try:
        destination_prefix = IPv4Network(
            evidence["destination_prefix"],
            strict=True,
        )
    except ValueError as error:
        raise EvidenceContractError(
            "destination_prefix must be a canonical "
            "IPv4 network prefix."
        ) from error

    if destination_address not in destination_prefix:
        raise EvidenceContractError(
            "destination_address must belong to "
            "destination_prefix."
        )

    route_next_hop = evidence[
        "route_next_hop_on_observer"
    ]

    if route_next_hop is not None:
        if not isinstance(route_next_hop, str):
            raise EvidenceContractError(
                "route_next_hop_on_observer must be "
                "an IPv4 address or null."
            )

        try:
            IPv4Address(route_next_hop)
        except ValueError as error:
            raise EvidenceContractError(
                "route_next_hop_on_observer must be "
                "an IPv4 address or null."
            ) from error

    for field_name in TRISTATE_FIELDS:
        value = evidence[field_name]

        if (
            value is not True
            and value is not False
            and value is not None
        ):
            raise EvidenceContractError(
                f"{field_name} must be true, false, or null."
            )
