from __future__ import annotations

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Any


OBSERVATION_PROFILE_SCHEMA_VERSION = 1
SUPPORTED_DIRECTION = "hosta_to_hostb"
P1_ROUTE_OBSERVER_NODE = "r1"
P1_TRANSIT_NODE = "r2"

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

FAULT_NEXT_HOP_FIELDS = {
    "missing_static_route": "next_hop",
    "wrong_next_hop": "correct_next_hop",
}


class ObservationProfileContractError(ValueError):
    """Raised when Observation Profile v1 is invalid."""


@dataclass(frozen=True)
class ObservationProfile:
    schema_version: int
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

    direction = observation["direction"]

    if direction != SUPPORTED_DIRECTION:
        raise ObservationProfileContractError(
            "Observation Profile v1 supports only "
            "HostA to HostB direction."
        )

    route_observer_node = observation[
        "route_observer_node"
    ]

    if route_observer_node != P1_ROUTE_OBSERVER_NODE:
        raise ObservationProfileContractError(
            "Observation Profile v1 requires "
            "route_observer_node 'r1'."
        )

    transit_node = observation["transit_node"]

    if transit_node != P1_TRANSIT_NODE:
        raise ObservationProfileContractError(
            "Observation Profile v1 requires "
            "transit_node 'r2'."
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
