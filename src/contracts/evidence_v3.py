from __future__ import annotations

import re
from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv4Network
from pathlib import PurePosixPath
from typing import Any

from src.contracts.evidence import (
    EvidenceContractError,
    validate_evidence_v2,
)
from src.contracts.observation_profile import (
    DIRECTION_PATTERN,
    IDENTIFIER_PATTERN,
)
from src.contracts.observation_profile_v2 import (
    INTERFACE_PATTERN,
    SUPPORTED_FLOW_PROTOCOLS,
)


EVIDENCE_V3_SCHEMA_VERSION = 3
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

EVIDENCE_V3_FEATURE_NAMES = (
    "source_expected_gateway_reachable",
    "source_default_gateway_matches_expected",
    "destination_reachable",
    "route_to_destination_exists_on_observer",
    "route_next_hop_matches_expected",
    "route_next_hop_reachable_from_observer",
    "expected_next_hop_reachable_from_observer",
    "observer_egress_interface_oper_up",
    "destination_reachable_from_transit",
    "flow_blocked_by_policy",
)

AVAILABILITY_STATES = {
    "observed",
    "structurally_unavailable",
    "collection_unavailable",
}

STRUCTURALLY_UNAVAILABLE_FEATURES = {
    "route_next_hop_matches_expected",
    "route_next_hop_reachable_from_observer",
}

PROBE_STATUS_FOR_AVAILABILITY = {
    "observed": "completed",
    "structurally_unavailable": "not_applicable",
    "collection_unavailable": "failed",
}

REQUIRED_EVIDENCE_V3_FIELDS = {
    "schema_version",
    "topology_id",
    "collected_at_utc",
    "direction",
    "source_node",
    "route_observer_node",
    "transit_node",
    "source_address",
    "source_prefix",
    "destination_address",
    "destination_prefix",
    "source_expected_gateway_address",
    "source_default_gateway_on_source",
    "expected_next_hop",
    "route_next_hop_on_observer",
    "observer_egress_interface",
    "observer_egress_oper_state",
    "flow_protocol",
    "flow_source_port",
    "flow_destination_port",
    "policy_backend",
    "policy_table",
    "policy_chain",
    "matching_block_rule_id",
    "features",
    "availability",
    "probes",
}


def _validate_utc_timestamp(value: object) -> None:
    if not isinstance(value, str) or not value:
        raise EvidenceContractError(
            "collected_at_utc must be a non-empty timestamp."
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise EvidenceContractError(
            "collected_at_utc must be an ISO-8601 timestamp."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise EvidenceContractError(
            "collected_at_utc must include the UTC offset."
        )


def _ipv4_address(
    value: object,
    field_name: str,
    *,
    nullable: bool = False,
) -> IPv4Address | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise EvidenceContractError(
            f"{field_name} must be a valid IPv4 address"
            + (" or null." if nullable else ".")
        )
    try:
        return IPv4Address(value)
    except ValueError as error:
        raise EvidenceContractError(
            f"{field_name} must be a valid IPv4 address"
            + (" or null." if nullable else ".")
        ) from error


def _ipv4_network(value: object, field_name: str) -> IPv4Network:
    if not isinstance(value, str) or not value:
        raise EvidenceContractError(
            f"{field_name} must be a canonical IPv4 network prefix."
        )
    try:
        return IPv4Network(value, strict=True)
    except ValueError as error:
        raise EvidenceContractError(
            f"{field_name} must be a canonical IPv4 network prefix."
        ) from error


def _validate_relative_artifact(value: object) -> None:
    if not isinstance(value, str) or not value:
        raise EvidenceContractError(
            "probe.raw_artifact must be a non-empty relative path."
        )
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise EvidenceContractError(
            "probe.raw_artifact must be a normalized relative path."
        )


def _validate_ports(evidence: dict[str, Any]) -> None:
    protocol = evidence["flow_protocol"]
    ports = (
        evidence["flow_source_port"],
        evidence["flow_destination_port"],
    )
    if protocol == "icmp":
        if ports != (None, None):
            raise EvidenceContractError(
                "ICMP evidence requires null flow ports."
            )
        return
    for field_name in (
        "flow_source_port",
        "flow_destination_port",
    ):
        value = evidence[field_name]
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= 65535
        ):
            raise EvidenceContractError(
                f"{field_name} must be an integer between 1 and "
                "65535 for TCP or UDP."
            )


def _validate_feature_provenance(
    evidence: dict[str, Any],
) -> None:
    features = evidence["features"]
    availability = evidence["availability"]
    probes = evidence["probes"]
    expected = set(EVIDENCE_V3_FEATURE_NAMES)

    for field_name, value in (
        ("features", features),
        ("availability", availability),
        ("probes", probes),
    ):
        if not isinstance(value, dict) or set(value) != expected:
            raise EvidenceContractError(
                f"Evidence v3 {field_name} must match the frozen "
                "ten-feature whitelist."
            )

    for feature_name in EVIDENCE_V3_FEATURE_NAMES:
        feature_value = features[feature_name]
        state = availability[feature_name]
        probe = probes[feature_name]
        if state not in AVAILABILITY_STATES:
            raise EvidenceContractError(
                f"availability.{feature_name} has an invalid state."
            )
        if (
            state == "structurally_unavailable"
            and feature_name not in STRUCTURALLY_UNAVAILABLE_FEATURES
        ):
            raise EvidenceContractError(
                f"availability.{feature_name} cannot be structurally "
                "unavailable in the frozen P6 contract."
            )
        if not isinstance(probe, dict) or set(probe) != {
            "producer",
            "status",
            "raw_artifact",
            "raw_artifact_sha256",
        }:
            raise EvidenceContractError(
                f"probes.{feature_name} does not match the probe "
                "provenance contract."
            )
        producer = probe["producer"]
        if (
            not isinstance(producer, str)
            or not IDENTIFIER_PATTERN.fullmatch(producer)
        ):
            raise EvidenceContractError(
                f"probes.{feature_name}.producer must be an identifier."
            )
        expected_status = PROBE_STATUS_FOR_AVAILABILITY[state]
        if probe["status"] != expected_status:
            raise EvidenceContractError(
                f"probes.{feature_name}.status does not match "
                f"availability.{feature_name}."
            )

        if state == "observed":
            if feature_value is not True and feature_value is not False:
                raise EvidenceContractError(
                    f"features.{feature_name} must be boolean when "
                    "availability is observed."
                )
        else:
            if feature_value is not None:
                raise EvidenceContractError(
                    f"features.{feature_name} must be null when "
                    "availability is unavailable."
                )

        raw_artifact = probe["raw_artifact"]
        raw_sha256 = probe["raw_artifact_sha256"]
        if state == "structurally_unavailable":
            if raw_artifact is not None or raw_sha256 is not None:
                raise EvidenceContractError(
                    "Structurally unavailable probes cannot claim a "
                    "raw artifact."
                )
        else:
            _validate_relative_artifact(raw_artifact)
            if (
                not isinstance(raw_sha256, str)
                or not SHA256_PATTERN.fullmatch(raw_sha256)
            ):
                raise EvidenceContractError(
                    f"probes.{feature_name}.raw_artifact_sha256 must "
                    "be a lowercase SHA-256 digest."
                )


def _validate_derived_feature_alignment(
    evidence: dict[str, Any],
) -> None:
    features = evidence["features"]
    availability = evidence["availability"]

    if availability["source_default_gateway_matches_expected"] == "observed":
        expected = (
            evidence["source_default_gateway_on_source"]
            == evidence["source_expected_gateway_address"]
        )
        if features["source_default_gateway_matches_expected"] is not expected:
            raise EvidenceContractError(
                "source_default_gateway_matches_expected does not "
                "match the recorded installed and expected gateways."
            )

    if availability["route_next_hop_matches_expected"] == "observed":
        expected = (
            evidence["route_next_hop_on_observer"]
            == evidence["expected_next_hop"]
        )
        if features["route_next_hop_matches_expected"] is not expected:
            raise EvidenceContractError(
                "route_next_hop_matches_expected does not match the "
                "recorded installed and expected next-hops."
            )

    if availability["observer_egress_interface_oper_up"] == "observed":
        if evidence["observer_egress_oper_state"] is None:
            raise EvidenceContractError(
                "Observed interface state requires a raw up/down value."
            )
        expected = evidence["observer_egress_oper_state"] == "up"
        if features["observer_egress_interface_oper_up"] is not expected:
            raise EvidenceContractError(
                "observer_egress_interface_oper_up does not match the "
                "recorded operational state."
            )
    elif evidence["observer_egress_oper_state"] is not None:
        raise EvidenceContractError(
            "Unavailable interface state requires a null raw state."
        )

    if availability["flow_blocked_by_policy"] == "observed":
        expected = evidence["matching_block_rule_id"] is not None
        if features["flow_blocked_by_policy"] is not expected:
            raise EvidenceContractError(
                "flow_blocked_by_policy does not match the recorded "
                "matching block-rule identifier."
            )
    elif evidence["matching_block_rule_id"] is not None:
        raise EvidenceContractError(
            "Unavailable policy state cannot claim a matching block "
            "rule."
        )

    route_exists = features[
        "route_to_destination_exists_on_observer"
    ]
    route_exists_state = availability[
        "route_to_destination_exists_on_observer"
    ]
    if route_exists_state == "observed" and route_exists is False:
        for dependent in (
            "route_next_hop_matches_expected",
            "route_next_hop_reachable_from_observer",
        ):
            if availability[dependent] != "structurally_unavailable":
                raise EvidenceContractError(
                    "Absent observer routes require structural "
                    f"unavailability for {dependent}."
                )
        if evidence["route_next_hop_on_observer"] is not None:
            raise EvidenceContractError(
                "An absent observer route cannot record an installed "
                "next-hop."
            )
    if route_exists_state == "observed" and route_exists is True:
        if evidence["route_next_hop_on_observer"] is None:
            raise EvidenceContractError(
                "The frozen P6 observer route requires an installed "
                "next-hop when the route exists."
            )
        for dependent in (
            "route_next_hop_matches_expected",
            "route_next_hop_reachable_from_observer",
        ):
            if availability[dependent] == "structurally_unavailable":
                raise EvidenceContractError(
                    "Present observer routes cannot mark "
                    f"{dependent} structurally unavailable."
                )


def validate_evidence_v3(evidence: dict[str, Any]) -> None:
    if not isinstance(evidence, dict):
        raise EvidenceContractError("Evidence must be an object.")
    missing = REQUIRED_EVIDENCE_V3_FIELDS - set(evidence)
    unexpected = set(evidence) - REQUIRED_EVIDENCE_V3_FIELDS
    if missing:
        raise EvidenceContractError(
            "Missing Evidence v3 fields: "
            + ", ".join(sorted(missing))
        )
    if unexpected:
        raise EvidenceContractError(
            "Unexpected Evidence v3 fields: "
            + ", ".join(sorted(unexpected))
        )
    if evidence["schema_version"] != EVIDENCE_V3_SCHEMA_VERSION:
        raise EvidenceContractError(
            "Unsupported evidence schema_version."
        )

    for field_name in (
        "topology_id",
        "direction",
        "source_node",
        "route_observer_node",
        "transit_node",
        "observer_egress_interface",
        "flow_protocol",
        "policy_backend",
        "policy_table",
        "policy_chain",
    ):
        value = evidence[field_name]
        if not isinstance(value, str) or not value:
            raise EvidenceContractError(
                f"{field_name} must be a non-empty string."
            )
    for field_name in (
        "topology_id",
        "source_node",
        "route_observer_node",
        "transit_node",
    ):
        if not IDENTIFIER_PATTERN.fullmatch(evidence[field_name]):
            raise EvidenceContractError(
                f"{field_name} must be a valid identifier."
            )
    if not DIRECTION_PATTERN.fullmatch(evidence["direction"]):
        raise EvidenceContractError(
            "direction must use the 'source_to_destination' format."
        )
    if len({
        evidence["source_node"],
        evidence["route_observer_node"],
        evidence["transit_node"],
    }) != 3:
        raise EvidenceContractError(
            "source_node, route_observer_node, and transit_node must "
            "be different."
        )
    _validate_utc_timestamp(evidence["collected_at_utc"])

    source_address = _ipv4_address(
        evidence["source_address"],
        "source_address",
    )
    source_prefix = _ipv4_network(
        evidence["source_prefix"],
        "source_prefix",
    )
    destination_address = _ipv4_address(
        evidence["destination_address"],
        "destination_address",
    )
    destination_prefix = _ipv4_network(
        evidence["destination_prefix"],
        "destination_prefix",
    )
    expected_gateway = _ipv4_address(
        evidence["source_expected_gateway_address"],
        "source_expected_gateway_address",
    )
    installed_gateway = _ipv4_address(
        evidence["source_default_gateway_on_source"],
        "source_default_gateway_on_source",
        nullable=True,
    )
    _ipv4_address(
        evidence["expected_next_hop"],
        "expected_next_hop",
    )
    _ipv4_address(
        evidence["route_next_hop_on_observer"],
        "route_next_hop_on_observer",
        nullable=True,
    )
    if source_address not in source_prefix or expected_gateway not in source_prefix:
        raise EvidenceContractError(
            "Source address and expected gateway must belong to "
            "source_prefix."
        )
    if installed_gateway is not None and installed_gateway not in source_prefix:
        raise EvidenceContractError(
            "source_default_gateway_on_source must belong to "
            "source_prefix when present."
        )
    if source_address == expected_gateway:
        raise EvidenceContractError(
            "Source address and expected gateway must be different."
        )
    if destination_address not in destination_prefix:
        raise EvidenceContractError(
            "destination_address must belong to destination_prefix."
        )

    if not INTERFACE_PATTERN.fullmatch(
        evidence["observer_egress_interface"]
    ):
        raise EvidenceContractError(
            "observer_egress_interface must be a valid Linux "
            "interface identifier."
        )
    oper_state = evidence["observer_egress_oper_state"]
    if oper_state not in {"up", "down", None}:
        raise EvidenceContractError(
            "observer_egress_oper_state must be up, down, or null."
        )
    if evidence["flow_protocol"] not in SUPPORTED_FLOW_PROTOCOLS:
        raise EvidenceContractError(
            "flow_protocol must be icmp, tcp, or udp."
        )
    _validate_ports(evidence)
    if (
        evidence["policy_backend"] != "iptables"
        or evidence["policy_table"] != "filter"
        or evidence["policy_chain"] != "FORWARD"
    ):
        raise EvidenceContractError(
            "Evidence v3 policy provenance is frozen to "
            "iptables/filter/FORWARD."
        )
    rule_id = evidence["matching_block_rule_id"]
    if rule_id is not None and (
        not isinstance(rule_id, str)
        or not IDENTIFIER_PATTERN.fullmatch(rule_id)
    ):
        raise EvidenceContractError(
            "matching_block_rule_id must be an identifier or null."
        )

    _validate_feature_provenance(evidence)
    _validate_derived_feature_alignment(evidence)


def validate_evidence_versioned(evidence: dict[str, Any]) -> None:
    if not isinstance(evidence, dict):
        raise EvidenceContractError("Evidence must be an object.")
    schema_version = evidence.get("schema_version")
    if schema_version == 2:
        validate_evidence_v2(evidence)
        return
    if schema_version == 3:
        validate_evidence_v3(evidence)
        return
    raise EvidenceContractError(
        "Unsupported evidence schema_version."
    )
