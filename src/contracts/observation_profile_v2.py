from __future__ import annotations

import re
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Any

from src.contracts.observation_profile import (
    DIRECTION_PATTERN,
    IDENTIFIER_PATTERN,
    ObservationProfile,
    ObservationProfileContractError,
    validate_observation_profile,
)


OBSERVATION_PROFILE_V2_SCHEMA_VERSION = 2
SUPPORTED_FLOW_PROTOCOLS = {"icmp", "tcp", "udp"}
INTERFACE_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,14}$"
)
RULE_TAG_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"
)

REQUIRED_OBSERVATION_V2_FIELDS = {
    "schema_version",
    "direction",
    "source_node",
    "source_container",
    "source_address",
    "source_prefix",
    "source_gateway_address",
    "destination_address",
    "destination_prefix",
    "route_observer_node",
    "route_observer_container",
    "expected_next_hop",
    "observer_egress_interface",
    "transit_node",
    "transit_container",
    "flow_protocol",
    "flow_source_port",
    "flow_destination_port",
    "policy_backend",
    "policy_table",
    "policy_chain",
    "policy_rule_tag_prefix",
}

IDENTIFIER_FIELDS = (
    "source_node",
    "source_container",
    "route_observer_node",
    "route_observer_container",
    "transit_node",
    "transit_container",
)

STRING_FIELDS = (
    "direction",
    *IDENTIFIER_FIELDS,
    "source_address",
    "source_prefix",
    "source_gateway_address",
    "destination_address",
    "destination_prefix",
    "expected_next_hop",
    "observer_egress_interface",
    "flow_protocol",
    "policy_backend",
    "policy_table",
    "policy_chain",
    "policy_rule_tag_prefix",
)


@dataclass(frozen=True)
class ObservationProfileV2:
    schema_version: int
    topology_id: str
    direction: str
    source_node: str
    source_container: str
    source_address: str
    source_prefix: str
    source_gateway_address: str
    destination_address: str
    destination_prefix: str
    route_observer_node: str
    route_observer_container: str
    expected_next_hop: str
    observer_egress_interface: str
    transit_node: str
    transit_container: str
    flow_protocol: str
    flow_source_port: int | None
    flow_destination_port: int | None
    policy_backend: str
    policy_table: str
    policy_chain: str
    policy_rule_tag_prefix: str


def _ipv4_address(value: str, field_name: str) -> IPv4Address:
    try:
        return IPv4Address(value)
    except ValueError as error:
        raise ObservationProfileContractError(
            f"observation.{field_name} must be a valid IPv4 address."
        ) from error


def _ipv4_network(value: str, field_name: str) -> IPv4Network:
    try:
        return IPv4Network(value, strict=True)
    except ValueError as error:
        raise ObservationProfileContractError(
            f"observation.{field_name} must be a canonical "
            "IPv4 network prefix."
        ) from error


def _validate_ports(observation: dict[str, Any]) -> None:
    protocol = observation["flow_protocol"]
    ports = (
        observation["flow_source_port"],
        observation["flow_destination_port"],
    )

    if protocol == "icmp":
        if ports != (None, None):
            raise ObservationProfileContractError(
                "ICMP observation profiles require null flow ports."
            )
        return

    for field_name in (
        "flow_source_port",
        "flow_destination_port",
    ):
        value = observation[field_name]
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= 65535
        ):
            raise ObservationProfileContractError(
                f"observation.{field_name} must be an integer "
                "between 1 and 65535 for TCP or UDP."
            )


def _require_fault_target(
    fault: dict[str, Any],
    *,
    node: str,
    container: str,
) -> None:
    if fault.get("target_node") != node:
        raise ObservationProfileContractError(
            "fault.target_node does not match the Observation "
            "Profile v2 fault-location role."
        )
    if fault.get("target_container") != container:
        raise ObservationProfileContractError(
            "fault.target_container does not match the Observation "
            "Profile v2 fault-location role."
        )


def _require_parameter(
    parameters: dict[str, Any],
    name: str,
    expected: object,
) -> None:
    if parameters.get(name) != expected:
        raise ObservationProfileContractError(
            f"fault.parameters.{name} must match observation.{name}."
        )


def _validate_fault_alignment(
    scenario: dict[str, Any],
    profile: ObservationProfileV2,
) -> None:
    if scenario.get("kind", "fault") != "fault":
        return

    fault = scenario.get("fault")
    if not isinstance(fault, dict):
        raise ObservationProfileContractError(
            "Fault scenarios require a fault object."
        )
    parameters = fault.get("parameters")
    if not isinstance(parameters, dict):
        raise ObservationProfileContractError(
            "Fault scenarios require a parameters object."
        )

    fault_type = fault.get("type")
    if fault_type in {"missing_static_route", "wrong_next_hop"}:
        _require_fault_target(
            fault,
            node=profile.route_observer_node,
            container=profile.route_observer_container,
        )
        _require_parameter(
            parameters,
            "destination_prefix",
            profile.destination_prefix,
        )
        parameter_name = (
            "next_hop"
            if fault_type == "missing_static_route"
            else "correct_next_hop"
        )
        if parameters.get(parameter_name) != profile.expected_next_hop:
            raise ObservationProfileContractError(
                f"fault.parameters.{parameter_name} must match "
                "observation.expected_next_hop."
            )
        return

    if fault_type == "wrong_default_gateway":
        _require_fault_target(
            fault,
            node=profile.source_node,
            container=profile.source_container,
        )
        correct_gateway = parameters.get("correct_gateway")
        if correct_gateway != profile.source_gateway_address:
            raise ObservationProfileContractError(
                "fault.parameters.correct_gateway must match "
                "observation.source_gateway_address."
            )
        wrong_gateway = parameters.get("wrong_gateway")
        if not isinstance(wrong_gateway, str):
            raise ObservationProfileContractError(
                "fault.parameters.wrong_gateway must be an IPv4 address."
            )
        wrong_gateway_address = _ipv4_address(
            wrong_gateway,
            "wrong_gateway",
        )
        if (
            wrong_gateway_address
            not in IPv4Network(profile.source_prefix)
            or wrong_gateway == correct_gateway
        ):
            raise ObservationProfileContractError(
                "fault.parameters.wrong_gateway must be a different "
                "address inside observation.source_prefix."
            )
        return

    if fault_type == "interface_down":
        _require_fault_target(
            fault,
            node=profile.route_observer_node,
            container=profile.route_observer_container,
        )
        if (
            parameters.get("interface")
            != profile.observer_egress_interface
        ):
            raise ObservationProfileContractError(
                "fault.parameters.interface must match "
                "observation.observer_egress_interface."
            )
        return

    if fault_type == "acl_block":
        _require_fault_target(
            fault,
            node=profile.route_observer_node,
            container=profile.route_observer_container,
        )
        expected_parameters = {
            "source_address": profile.source_address,
            "destination_address": profile.destination_address,
            "protocol": profile.flow_protocol,
            "source_port": profile.flow_source_port,
            "destination_port": profile.flow_destination_port,
            "policy_backend": profile.policy_backend,
            "policy_table": profile.policy_table,
            "policy_chain": profile.policy_chain,
        }
        for name, expected in expected_parameters.items():
            if parameters.get(name) != expected:
                raise ObservationProfileContractError(
                    f"fault.parameters.{name} does not match the "
                    "Observation Profile v2 flow selector."
                )
        rule_tag = parameters.get("rule_tag")
        if (
            not isinstance(rule_tag, str)
            or not rule_tag.startswith(profile.policy_rule_tag_prefix)
            or not RULE_TAG_PATTERN.fullmatch(rule_tag)
        ):
            raise ObservationProfileContractError(
                "fault.parameters.rule_tag must use the frozen policy "
                "rule-tag prefix."
            )


def validate_observation_profile_v2(
    scenario: dict[str, Any],
) -> ObservationProfileV2:
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
    missing = REQUIRED_OBSERVATION_V2_FIELDS - set(observation)
    unexpected = set(observation) - REQUIRED_OBSERVATION_V2_FIELDS
    if missing:
        raise ObservationProfileContractError(
            "Missing Observation Profile v2 fields: "
            + ", ".join(sorted(missing))
        )
    if unexpected:
        raise ObservationProfileContractError(
            "Unexpected Observation Profile v2 fields: "
            + ", ".join(sorted(unexpected))
        )
    if observation["schema_version"] != 2:
        raise ObservationProfileContractError(
            "Unsupported observation schema_version."
        )

    for field_name in STRING_FIELDS:
        value = observation[field_name]
        if not isinstance(value, str) or not value:
            raise ObservationProfileContractError(
                f"observation.{field_name} must be a non-empty string."
            )
    for field_name in IDENTIFIER_FIELDS:
        if not IDENTIFIER_PATTERN.fullmatch(observation[field_name]):
            raise ObservationProfileContractError(
                f"observation.{field_name} must be a valid identifier."
            )
    if not DIRECTION_PATTERN.fullmatch(observation["direction"]):
        raise ObservationProfileContractError(
            "observation.direction must use the "
            "'source_to_destination' identifier format."
        )

    role_nodes = {
        observation["source_node"],
        observation["route_observer_node"],
        observation["transit_node"],
    }
    if len(role_nodes) != 3:
        raise ObservationProfileContractError(
            "Observation Profile v2 source, observer, and transit "
            "nodes must be different."
        )

    source_address = _ipv4_address(
        observation["source_address"],
        "source_address",
    )
    source_prefix = _ipv4_network(
        observation["source_prefix"],
        "source_prefix",
    )
    source_gateway = _ipv4_address(
        observation["source_gateway_address"],
        "source_gateway_address",
    )
    destination_address = _ipv4_address(
        observation["destination_address"],
        "destination_address",
    )
    destination_prefix = _ipv4_network(
        observation["destination_prefix"],
        "destination_prefix",
    )
    expected_next_hop = _ipv4_address(
        observation["expected_next_hop"],
        "expected_next_hop",
    )

    if source_address not in source_prefix:
        raise ObservationProfileContractError(
            "observation.source_address must belong to "
            "observation.source_prefix."
        )
    if source_gateway not in source_prefix or source_gateway == source_address:
        raise ObservationProfileContractError(
            "observation.source_gateway_address must be a different "
            "address inside observation.source_prefix."
        )
    if destination_address not in destination_prefix:
        raise ObservationProfileContractError(
            "observation.destination_address must belong to "
            "observation.destination_prefix."
        )
    if not INTERFACE_PATTERN.fullmatch(
        observation["observer_egress_interface"]
    ):
        raise ObservationProfileContractError(
            "observation.observer_egress_interface must be a valid "
            "Linux interface identifier."
        )
    if observation["flow_protocol"] not in SUPPORTED_FLOW_PROTOCOLS:
        raise ObservationProfileContractError(
            "observation.flow_protocol must be icmp, tcp, or udp."
        )
    _validate_ports(observation)
    if (
        observation["policy_backend"] != "iptables"
        or observation["policy_table"] != "filter"
        or observation["policy_chain"] != "FORWARD"
    ):
        raise ObservationProfileContractError(
            "Observation Profile v2 policy inspection is frozen to "
            "iptables/filter/FORWARD."
        )
    if not RULE_TAG_PATTERN.fullmatch(
        observation["policy_rule_tag_prefix"]
    ):
        raise ObservationProfileContractError(
            "observation.policy_rule_tag_prefix is invalid."
        )

    profile = ObservationProfileV2(
        schema_version=2,
        topology_id=topology_id,
        direction=observation["direction"],
        source_node=observation["source_node"],
        source_container=observation["source_container"],
        source_address=str(source_address),
        source_prefix=str(source_prefix),
        source_gateway_address=str(source_gateway),
        destination_address=str(destination_address),
        destination_prefix=str(destination_prefix),
        route_observer_node=observation["route_observer_node"],
        route_observer_container=(
            observation["route_observer_container"]
        ),
        expected_next_hop=str(expected_next_hop),
        observer_egress_interface=(
            observation["observer_egress_interface"]
        ),
        transit_node=observation["transit_node"],
        transit_container=observation["transit_container"],
        flow_protocol=observation["flow_protocol"],
        flow_source_port=observation["flow_source_port"],
        flow_destination_port=observation["flow_destination_port"],
        policy_backend=observation["policy_backend"],
        policy_table=observation["policy_table"],
        policy_chain=observation["policy_chain"],
        policy_rule_tag_prefix=(
            observation["policy_rule_tag_prefix"]
        ),
    )
    _validate_fault_alignment(scenario, profile)
    return profile


def validate_observation_profile_versioned(
    scenario: dict[str, Any],
) -> ObservationProfile | ObservationProfileV2:
    if not isinstance(scenario, dict):
        raise ObservationProfileContractError(
            "Scenario must be an object."
        )
    observation = scenario.get("observation")
    if not isinstance(observation, dict):
        raise ObservationProfileContractError(
            "Scenario requires an observation object."
        )
    schema_version = observation.get("schema_version")
    if schema_version == 1:
        return validate_observation_profile(scenario)
    if schema_version == 2:
        return validate_observation_profile_v2(scenario)
    raise ObservationProfileContractError(
        "Unsupported observation schema_version."
    )
