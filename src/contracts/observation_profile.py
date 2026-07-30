from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Any


OBSERVATION_PROFILE_SCHEMA_VERSION = 1
IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"
)
DIRECTION_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_]*_to_[a-z0-9][a-z0-9_]*$"
)

REQUIRED_FIELDS = {
    "schema_version",
    "direction",
    "source_container",
    "source_gateway_address",
    "destination_address",
    "destination_prefix",
    "route_observer_node",
    "route_observer_container",
    "expected_next_hop",
    "transit_node",
    "transit_container",
}

STRING_FIELDS = (
    "direction",
    "source_container",
    "source_gateway_address",
    "destination_address",
    "destination_prefix",
    "route_observer_node",
    "route_observer_container",
    "expected_next_hop",
    "transit_node",
    "transit_container",
)

IDENTIFIER_FIELDS = (
    "source_container",
    "route_observer_node",
    "route_observer_container",
    "transit_node",
    "transit_container",
)

FAULT_NEXT_HOP_FIELDS = {
    "missing_static_route": "next_hop",
    "wrong_next_hop": "correct_next_hop",
}


class ObservationProfileContractError(ValueError):
    """Raised when Observation Profile v1 is invalid."""


@dataclass(frozen=True)
class ObservationProfile:
    schema_version: int
    topology_id: str
    direction: str
    source_container: str
    source_gateway_address: str
    destination_address: str
    destination_prefix: str
    route_observer_node: str
    route_observer_container: str
    expected_next_hop: str
    transit_node: str
    transit_container: str


def _validate_ipv4_address(
    value: str,
    field_name: str,
) -> IPv4Address:
    try:
        return IPv4Address(value)
    except ValueError as error:
        raise ObservationProfileContractError(
            f"observation.{field_name} must be a valid "
            "IPv4 address."
        ) from error


def _validate_ipv4_network(
    value: str,
    field_name: str,
) -> IPv4Network:
    try:
        return IPv4Network(value, strict=True)
    except ValueError as error:
        raise ObservationProfileContractError(
            f"observation.{field_name} must be a canonical "
            "IPv4 network prefix."
        ) from error


def _validate_fault_parameter_alignment(
    scenario: dict[str, Any],
    profile: ObservationProfile,
) -> None:
    scenario_kind = scenario.get("kind", "fault")

    if scenario_kind != "fault":
        return

    fault = scenario.get("fault")

    if not isinstance(fault, dict):
        raise ObservationProfileContractError(
            "Fault scenarios require a fault object."
        )

    fault_type = fault.get("type")
    next_hop_field = FAULT_NEXT_HOP_FIELDS.get(
        fault_type
    )

    if next_hop_field is None:
        return

    parameters = fault.get("parameters")

    if not isinstance(parameters, dict):
        raise ObservationProfileContractError(
            "Known routing faults require a parameters object."
        )

    if fault.get("target_node") != profile.route_observer_node:
        raise ObservationProfileContractError(
            "fault.target_node must match "
            "observation.route_observer_node."
        )

    if (
        fault.get("target_container")
        != profile.route_observer_container
    ):
        raise ObservationProfileContractError(
            "fault.target_container must match "
            "observation.route_observer_container."
        )

    fault_destination_prefix = parameters.get(
        "destination_prefix"
    )

    if (
        not isinstance(fault_destination_prefix, str)
        or not fault_destination_prefix
    ):
        raise ObservationProfileContractError(
            "fault.parameters.destination_prefix must be "
            "a non-empty string."
        )

    if (
        profile.destination_prefix
        != fault_destination_prefix
    ):
        raise ObservationProfileContractError(
            "observation.destination_prefix must match "
            "fault.parameters.destination_prefix."
        )

    fault_expected_next_hop = parameters.get(
        next_hop_field
    )

    if (
        not isinstance(fault_expected_next_hop, str)
        or not fault_expected_next_hop
    ):
        raise ObservationProfileContractError(
            f"fault.parameters.{next_hop_field} must be "
            "a non-empty string."
        )

    if (
        profile.expected_next_hop
        != fault_expected_next_hop
    ):
        raise ObservationProfileContractError(
            "observation.expected_next_hop must match "
            f"fault.parameters.{next_hop_field}."
        )


def validate_observation_profile(
    scenario: dict[str, Any],
) -> ObservationProfile:
    if not isinstance(scenario, dict):
        raise ObservationProfileContractError(
            "Scenario must be an object."
        )

    topology = scenario.get("topology")

    if not isinstance(topology, dict):
        raise ObservationProfileContractError(
            "Scenario requires a topology object."
        )

    topology_id = topology.get("id")

    if (
        not isinstance(topology_id, str)
        or not IDENTIFIER_PATTERN.fullmatch(topology_id)
    ):
        raise ObservationProfileContractError(
            "topology.id must be a non-empty identifier."
        )

    observation = scenario.get("observation")

    if not isinstance(observation, dict):
        raise ObservationProfileContractError(
            "Scenario requires an observation object."
        )

    missing = REQUIRED_FIELDS - set(observation)
    unexpected = set(observation) - REQUIRED_FIELDS

    if missing:
        raise ObservationProfileContractError(
            "Missing observation fields: "
            + ", ".join(sorted(missing))
        )

    if unexpected:
        raise ObservationProfileContractError(
            "Unexpected observation fields: "
            + ", ".join(sorted(unexpected))
        )

    schema_version = observation["schema_version"]

    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version
        != OBSERVATION_PROFILE_SCHEMA_VERSION
    ):
        raise ObservationProfileContractError(
            "Unsupported observation schema_version."
        )

    for field_name in STRING_FIELDS:
        value = observation[field_name]

        if not isinstance(value, str) or not value:
            raise ObservationProfileContractError(
                f"observation.{field_name} must be "
                "a non-empty string."
            )

    for field_name in IDENTIFIER_FIELDS:
        if not IDENTIFIER_PATTERN.fullmatch(
            observation[field_name]
        ):
            raise ObservationProfileContractError(
                f"observation.{field_name} must be "
                "a valid identifier."
            )

    direction = observation["direction"]

    if not DIRECTION_PATTERN.fullmatch(direction):
        raise ObservationProfileContractError(
            "observation.direction must use the "
            "'source_to_destination' identifier format."
        )

    route_observer_node = observation[
        "route_observer_node"
    ]

    transit_node = observation["transit_node"]

    if route_observer_node == transit_node:
        raise ObservationProfileContractError(
            "observation.route_observer_node and "
            "observation.transit_node must be different."
        )

    source_gateway_address = _validate_ipv4_address(
        observation["source_gateway_address"],
        "source_gateway_address",
    )
    destination_address = _validate_ipv4_address(
        observation["destination_address"],
        "destination_address",
    )
    destination_prefix = _validate_ipv4_network(
        observation["destination_prefix"],
        "destination_prefix",
    )
    expected_next_hop = _validate_ipv4_address(
        observation["expected_next_hop"],
        "expected_next_hop",
    )

    if destination_address not in destination_prefix:
        raise ObservationProfileContractError(
            "observation.destination_address must belong "
            "to observation.destination_prefix."
        )

    profile = ObservationProfile(
        schema_version=schema_version,
        topology_id=topology_id,
        direction=direction,
        source_container=observation[
            "source_container"
        ],
        source_gateway_address=str(
            source_gateway_address
        ),
        destination_address=str(destination_address),
        destination_prefix=str(destination_prefix),
        route_observer_node=route_observer_node,
        route_observer_container=observation[
            "route_observer_container"
        ],
        expected_next_hop=str(expected_next_hop),
        transit_node=transit_node,
        transit_container=observation[
            "transit_container"
        ],
    )

    _validate_fault_parameter_alignment(
        scenario,
        profile,
    )

    return profile
