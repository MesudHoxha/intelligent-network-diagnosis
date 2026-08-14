from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ipaddress import IPv4Address
from pathlib import Path, PurePosixPath
from typing import Callable, Sequence

import yaml

from src.contracts.evidence import EvidenceContractError
from src.contracts.evidence_v3 import (
    EVIDENCE_V3_FEATURE_NAMES,
    validate_evidence_v3,
)
from src.contracts.observation_profile_v2 import (
    ObservationProfileV2,
    validate_observation_profile_v2,
)
from src.runtime.subprocesses import run_capture


CommandResult = dict[str, object]
ProbeExecutor = Callable[[str, Sequence[str]], CommandResult]

RAW_DIRECTORY = PurePosixPath("raw/v3")
EVIDENCE_PATH = PurePosixPath("parsed/evidence.json")
STATUS_PATH = PurePosixPath("collector_status.json")
DOCKER_EXEC_TIMEOUT_SECONDS = 30.0


class EvidenceCollectorV3Error(RuntimeError):
    """Raised when the Evidence v3 collector cannot run safely."""


@dataclass(frozen=True)
class PersistedProbe:
    producer: str
    result: CommandResult
    relative_path: str
    sha256: str


@dataclass(frozen=True)
class ObserverRouteState:
    available: bool
    exists: bool | None
    next_hop: str | None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return (
        parsed.tzinfo is not None
        and parsed.utcoffset() == timedelta(0)
    )


def docker_exec_result(
    container: str,
    command: Sequence[str],
) -> CommandResult:
    full_command = ["docker", "exec", container, *command]
    try:
        process = run_capture(
            full_command,
            timeout_seconds=DOCKER_EXEC_TIMEOUT_SECONDS,
        )
    except OSError as error:
        return {
            "command": full_command,
            "return_code": 127,
            "stdout": "",
            "stderr": f"{type(error).__name__}: {error}",
            "timestamp_utc": utc_now(),
        }
    return {
        "command": full_command,
        "return_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "timestamp_utc": utc_now(),
    }


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _atomic_write_json(path: Path, value: object) -> str:
    payload = _json_bytes(value)
    _atomic_write_bytes(path, payload)
    return hashlib.sha256(payload).hexdigest()


def _safe_command_result(
    executor: ProbeExecutor,
    container: str,
    command: Sequence[str],
) -> CommandResult:
    expected_command = ["docker", "exec", container, *command]
    try:
        result = executor(container, command)
        if not isinstance(result, dict):
            raise TypeError("executor result must be an object")
        if result.get("command") != expected_command:
            raise ValueError("executor command does not match the probe")
        return_code = result.get("return_code")
        if isinstance(return_code, bool) or not isinstance(
            return_code, int
        ):
            raise TypeError("executor return_code must be an integer")
        stdout = result.get("stdout")
        stderr = result.get("stderr")
        if not isinstance(stdout, str) or not isinstance(stderr, str):
            raise TypeError("executor stdout and stderr must be strings")
        timestamp = result.get("timestamp_utc")
        if not _is_utc_timestamp(timestamp):
            raise ValueError("executor timestamp_utc must be UTC")
        return {
            "command": expected_command,
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "timestamp_utc": timestamp,
        }
    except Exception as error:
        return {
            "command": expected_command,
            "return_code": 125,
            "stdout": "",
            "stderr": (
                "collector_executor_failure: "
                f"{type(error).__name__}: {error}"
            ),
            "timestamp_utc": utc_now(),
        }


def _run_and_persist_probe(
    output_directory: Path,
    *,
    producer: str,
    container: str,
    command: Sequence[str],
    executor: ProbeExecutor,
) -> PersistedProbe:
    result = _safe_command_result(
        executor,
        container,
        command,
    )
    relative_path = str(
        RAW_DIRECTORY / f"{producer}.json"
    )
    artifact = {
        "schema_version": 1,
        "probe_id": producer,
        "container": container,
        **result,
    }
    digest = _atomic_write_json(
        output_directory / relative_path,
        artifact,
    )
    return PersistedProbe(
        producer=producer,
        result=result,
        relative_path=relative_path,
        sha256=digest,
    )


def _probe_provenance(
    probe: PersistedProbe | None,
    *,
    availability: str,
    producer: str | None = None,
) -> dict[str, object]:
    selected_producer = (
        producer
        if producer is not None
        else probe.producer
        if probe is not None
        else None
    )
    if selected_producer is None:
        raise EvidenceCollectorV3Error(
            "Probe provenance requires a producer."
        )
    if availability == "structurally_unavailable":
        return {
            "producer": selected_producer,
            "status": "not_applicable",
            "raw_artifact": None,
            "raw_artifact_sha256": None,
        }
    if probe is None:
        raise EvidenceCollectorV3Error(
            "Observed and failed probes require a raw artifact."
        )
    return {
        "producer": selected_producer,
        "status": (
            "completed"
            if availability == "observed"
            else "failed"
        ),
        "raw_artifact": probe.relative_path,
        "raw_artifact_sha256": probe.sha256,
    }


def _ping_value(result: CommandResult) -> bool | None:
    return_code = result["return_code"]
    if return_code == 0:
        return True
    if return_code == 1:
        return False
    return None


def _load_json_list(result: CommandResult) -> list[object] | None:
    if result["return_code"] != 0:
        return None
    try:
        value = json.loads(str(result["stdout"]))
    except json.JSONDecodeError:
        return None
    if not isinstance(value, list):
        return None
    return value


def parse_source_default_gateway(
    result: CommandResult,
) -> tuple[bool, str | None]:
    rows = _load_json_list(result)
    if rows is None:
        return False, None
    defaults = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("dst", "default") == "default"
    ]
    if not defaults:
        return True, None
    if len(defaults) != 1:
        return False, None
    gateway = defaults[0].get("gateway")
    if not isinstance(gateway, str):
        return False, None
    try:
        return True, str(IPv4Address(gateway))
    except ValueError:
        return False, None


def parse_observer_route(
    result: CommandResult,
    destination_prefix: str,
) -> ObserverRouteState:
    rows = _load_json_list(result)
    if rows is None:
        return ObserverRouteState(False, None, None)
    matching = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("dst") == destination_prefix
    ]
    if not matching:
        return ObserverRouteState(True, False, None)
    if len(matching) != 1:
        return ObserverRouteState(False, None, None)
    gateway = matching[0].get("gateway")
    if not isinstance(gateway, str):
        return ObserverRouteState(False, None, None)
    try:
        next_hop = str(IPv4Address(gateway))
    except ValueError:
        return ObserverRouteState(False, None, None)
    return ObserverRouteState(True, True, next_hop)


def parse_interface_oper_state(
    result: CommandResult,
    interface: str,
) -> tuple[bool, str | None]:
    rows = _load_json_list(result)
    if rows is None or len(rows) != 1:
        return False, None
    row = rows[0]
    if not isinstance(row, dict) or row.get("ifname") != interface:
        return False, None
    oper_state = row.get("operstate")
    if not isinstance(oper_state, str):
        return False, None
    normalized = oper_state.lower()
    if normalized not in {"up", "down"}:
        return False, None
    return True, normalized


def _single_option(
    tokens: list[str],
    option: str,
) -> str | None:
    indexes = [
        index
        for index, value in enumerate(tokens)
        if value == option
    ]
    if not indexes:
        return None
    if len(indexes) != 1 or indexes[0] + 1 >= len(tokens):
        raise ValueError(f"ambiguous iptables option: {option}")
    return tokens[indexes[0] + 1]


def _normalized_host_address(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        if value.endswith("/32"):
            value = value[:-3]
        return str(IPv4Address(value))
    except ValueError:
        return None


def _tagged_rule_uses_supported_shape(
    tokens: list[str],
    profile: ObservationProfileV2,
) -> bool:
    allowed_options = {
        "-A",
        "-s",
        "-d",
        "-p",
        "-m",
        "--sport",
        "--dport",
        "--comment",
        "-j",
    }
    unique_options = allowed_options - {"-m"}
    counts = {option: 0 for option in unique_options}
    modules: list[str] = []
    index = 0
    while index < len(tokens):
        option = tokens[index]
        if option not in allowed_options or index + 1 >= len(tokens):
            return False
        argument = tokens[index + 1]
        if option == "-m":
            modules.append(argument)
        else:
            counts[option] += 1
            if counts[option] > 1:
                return False
        index += 2
    allowed_modules = {"comment", profile.flow_protocol}
    return "comment" in modules and set(modules) <= allowed_modules


def parse_matching_block_rule(
    result: CommandResult,
    profile: ObservationProfileV2,
) -> tuple[bool, str | None]:
    if result["return_code"] != 0:
        return False, None
    matches: list[str] = []
    for raw_line in str(result["stdout"]).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            tokens = shlex.split(line)
        except ValueError:
            return False, None
        try:
            comment = _single_option(tokens, "--comment")
        except ValueError:
            return False, None
        if (
            comment is None
            or not comment.startswith(profile.policy_rule_tag_prefix)
        ):
            continue
        if not _tagged_rule_uses_supported_shape(tokens, profile):
            return False, None
        try:
            chain = _single_option(tokens, "-A")
            source = _single_option(tokens, "-s")
            destination = _single_option(tokens, "-d")
            protocol = _single_option(tokens, "-p")
            target = _single_option(tokens, "-j")
            source_port = _single_option(tokens, "--sport")
            destination_port = _single_option(tokens, "--dport")
        except ValueError:
            return False, None
        if not comment or any(
            character not in (
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                "abcdefghijklmnopqrstuvwxyz"
                "0123456789_.-"
            )
            for character in comment
        ):
            return False, None
        selector_matches = (
            chain == profile.policy_chain
            and _normalized_host_address(source)
            == profile.source_address
            and _normalized_host_address(destination)
            == profile.destination_address
            and protocol == profile.flow_protocol
            and target == "DROP"
        )
        if profile.flow_protocol == "icmp":
            selector_matches = (
                selector_matches
                and source_port is None
                and destination_port is None
            )
        else:
            selector_matches = (
                selector_matches
                and source_port == str(profile.flow_source_port)
                and destination_port
                == str(profile.flow_destination_port)
            )
        if selector_matches:
            matches.append(comment)
    if len(matches) > 1:
        return False, None
    return True, matches[0] if matches else None


def _feature_from_probe(
    probe: PersistedProbe,
    value: bool | None,
) -> tuple[bool | None, str, dict[str, object]]:
    availability = (
        "observed"
        if value is not None
        else "collection_unavailable"
    )
    return (
        value,
        availability,
        _probe_provenance(probe, availability=availability),
    )


def _ensure_new_output(output_directory: Path) -> None:
    conflicts = [
        output_directory / EVIDENCE_PATH,
        output_directory / STATUS_PATH,
        output_directory / RAW_DIRECTORY,
    ]
    existing = [str(path) for path in conflicts if path.exists()]
    if existing:
        raise EvidenceCollectorV3Error(
            "Evidence v3 output already exists: "
            + ", ".join(existing)
        )


def collect_evidence_v3(
    output_directory: Path,
    profile: ObservationProfileV2,
    *,
    executor: ProbeExecutor = docker_exec_result,
) -> dict[str, object]:
    if not isinstance(profile, ObservationProfileV2):
        raise EvidenceCollectorV3Error(
            "Evidence v3 collection requires Observation Profile v2."
        )
    output_directory = Path(output_directory)
    _ensure_new_output(output_directory)

    probe_specs = {
        "source_expected_gateway_ping_v3": (
            profile.source_container,
            ["ping", "-c", "2", "-W", "1", profile.source_gateway_address],
        ),
        "source_default_route_v3": (
            profile.source_container,
            ["ip", "-j", "route", "show", "default"],
        ),
        "source_destination_ping_v3": (
            profile.source_container,
            ["ping", "-c", "2", "-W", "1", profile.destination_address],
        ),
        "observer_destination_route_v3": (
            profile.route_observer_container,
            [
                "ip",
                "-j",
                "route",
                "show",
                "exact",
                profile.destination_prefix,
            ],
        ),
        "observer_expected_next_hop_ping_v3": (
            profile.route_observer_container,
            ["ping", "-c", "2", "-W", "1", profile.expected_next_hop],
        ),
        "observer_egress_link_v3": (
            profile.route_observer_container,
            [
                "ip",
                "-j",
                "link",
                "show",
                "dev",
                profile.observer_egress_interface,
            ],
        ),
        "transit_destination_ping_v3": (
            profile.transit_container,
            ["ping", "-c", "2", "-W", "1", profile.destination_address],
        ),
        "observer_forward_policy_v3": (
            profile.route_observer_container,
            [
                "iptables",
                "-w",
                "2",
                "-t",
                profile.policy_table,
                "-S",
                profile.policy_chain,
            ],
        ),
    }
    probes = {
        producer: _run_and_persist_probe(
            output_directory,
            producer=producer,
            container=container,
            command=command,
            executor=executor,
        )
        for producer, (container, command) in probe_specs.items()
    }

    route_probe = probes["observer_destination_route_v3"]
    route_state = parse_observer_route(
        route_probe.result,
        profile.destination_prefix,
    )
    installed_next_hop_probe: PersistedProbe | None = None
    if route_state.available and route_state.exists:
        if route_state.next_hop is None:
            raise EvidenceCollectorV3Error(
                "A present frozen P6 route requires an installed next-hop."
            )
        installed_next_hop_probe = _run_and_persist_probe(
            output_directory,
            producer="observer_installed_next_hop_ping_v3",
            container=profile.route_observer_container,
            command=[
                "ping",
                "-c",
                "2",
                "-W",
                "1",
                route_state.next_hop,
            ],
            executor=executor,
        )

    features: dict[str, bool | None] = {}
    availability: dict[str, str] = {}
    provenance: dict[str, dict[str, object]] = {}

    def record(
        feature_name: str,
        value: bool | None,
        state: str,
        probe: PersistedProbe | None,
        *,
        producer: str | None = None,
    ) -> None:
        features[feature_name] = value
        availability[feature_name] = state
        provenance[feature_name] = _probe_provenance(
            probe,
            availability=state,
            producer=producer,
        )

    gateway_ping = probes["source_expected_gateway_ping_v3"]
    gateway_value, gateway_state, gateway_provenance = (
        _feature_from_probe(
            gateway_ping,
            _ping_value(gateway_ping.result),
        )
    )
    features["source_expected_gateway_reachable"] = gateway_value
    availability["source_expected_gateway_reachable"] = gateway_state
    provenance["source_expected_gateway_reachable"] = gateway_provenance

    default_route_probe = probes["source_default_route_v3"]
    gateway_parse_available, installed_gateway = (
        parse_source_default_gateway(default_route_probe.result)
    )
    record(
        "source_default_gateway_matches_expected",
        (
            installed_gateway == profile.source_gateway_address
            if gateway_parse_available
            else None
        ),
        "observed"
        if gateway_parse_available
        else "collection_unavailable",
        default_route_probe,
    )

    source_destination_probe = probes["source_destination_ping_v3"]
    destination_value, destination_state, destination_provenance = (
        _feature_from_probe(
            source_destination_probe,
            _ping_value(source_destination_probe.result),
        )
    )
    features["destination_reachable"] = destination_value
    availability["destination_reachable"] = destination_state
    provenance["destination_reachable"] = destination_provenance

    if route_state.available:
        record(
            "route_to_destination_exists_on_observer",
            route_state.exists,
            "observed",
            route_probe,
        )
    else:
        record(
            "route_to_destination_exists_on_observer",
            None,
            "collection_unavailable",
            route_probe,
        )

    if route_state.available and route_state.exists is False:
        record(
            "route_next_hop_matches_expected",
            None,
            "structurally_unavailable",
            None,
            producer="observer_route_next_hop_match_v3",
        )
        record(
            "route_next_hop_reachable_from_observer",
            None,
            "structurally_unavailable",
            None,
            producer="observer_installed_next_hop_ping_v3",
        )
    elif route_state.available and route_state.exists is True:
        record(
            "route_next_hop_matches_expected",
            route_state.next_hop == profile.expected_next_hop,
            "observed",
            route_probe,
            producer="observer_route_next_hop_match_v3",
        )
        assert installed_next_hop_probe is not None
        installed_ping_value = _ping_value(
            installed_next_hop_probe.result
        )
        record(
            "route_next_hop_reachable_from_observer",
            installed_ping_value,
            "observed"
            if installed_ping_value is not None
            else "collection_unavailable",
            installed_next_hop_probe,
        )
    else:
        record(
            "route_next_hop_matches_expected",
            None,
            "collection_unavailable",
            route_probe,
            producer="observer_route_next_hop_match_v3",
        )
        record(
            "route_next_hop_reachable_from_observer",
            None,
            "collection_unavailable",
            route_probe,
            producer="observer_installed_next_hop_ping_v3",
        )

    expected_ping = probes["observer_expected_next_hop_ping_v3"]
    expected_value, expected_state, expected_provenance = (
        _feature_from_probe(
            expected_ping,
            _ping_value(expected_ping.result),
        )
    )
    features["expected_next_hop_reachable_from_observer"] = (
        expected_value
    )
    availability["expected_next_hop_reachable_from_observer"] = (
        expected_state
    )
    provenance["expected_next_hop_reachable_from_observer"] = (
        expected_provenance
    )

    link_probe = probes["observer_egress_link_v3"]
    link_available, oper_state = parse_interface_oper_state(
        link_probe.result,
        profile.observer_egress_interface,
    )
    record(
        "observer_egress_interface_oper_up",
        oper_state == "up" if link_available else None,
        "observed" if link_available else "collection_unavailable",
        link_probe,
    )

    transit_probe = probes["transit_destination_ping_v3"]
    transit_value, transit_state, transit_provenance = (
        _feature_from_probe(
            transit_probe,
            _ping_value(transit_probe.result),
        )
    )
    features["destination_reachable_from_transit"] = transit_value
    availability["destination_reachable_from_transit"] = transit_state
    provenance["destination_reachable_from_transit"] = (
        transit_provenance
    )

    policy_probe = probes["observer_forward_policy_v3"]
    policy_available, matching_rule = parse_matching_block_rule(
        policy_probe.result,
        profile,
    )
    record(
        "flow_blocked_by_policy",
        matching_rule is not None if policy_available else None,
        "observed" if policy_available else "collection_unavailable",
        policy_probe,
    )

    if tuple(features) != EVIDENCE_V3_FEATURE_NAMES:
        raise EvidenceCollectorV3Error(
            "Collector feature order drifted from Evidence v3."
        )

    evidence = {
        "schema_version": 3,
        "topology_id": profile.topology_id,
        "collected_at_utc": utc_now(),
        "direction": profile.direction,
        "source_node": profile.source_node,
        "route_observer_node": profile.route_observer_node,
        "transit_node": profile.transit_node,
        "source_address": profile.source_address,
        "source_prefix": profile.source_prefix,
        "destination_address": profile.destination_address,
        "destination_prefix": profile.destination_prefix,
        "source_expected_gateway_address": (
            profile.source_gateway_address
        ),
        "source_default_gateway_on_source": installed_gateway,
        "expected_next_hop": profile.expected_next_hop,
        "route_next_hop_on_observer": route_state.next_hop,
        "observer_egress_interface": profile.observer_egress_interface,
        "observer_egress_oper_state": oper_state,
        "flow_protocol": profile.flow_protocol,
        "flow_source_port": profile.flow_source_port,
        "flow_destination_port": profile.flow_destination_port,
        "policy_backend": profile.policy_backend,
        "policy_table": profile.policy_table,
        "policy_chain": profile.policy_chain,
        "matching_block_rule_id": matching_rule,
        "features": features,
        "availability": availability,
        "probes": provenance,
    }
    try:
        validate_evidence_v3(evidence)
    except EvidenceContractError as error:
        raise EvidenceCollectorV3Error(
            f"Collector produced invalid Evidence v3: {error}"
        ) from error

    _atomic_write_json(
        output_directory / EVIDENCE_PATH,
        evidence,
    )
    collector_status = {
        "collector": "RoleNeutralEvidenceCollectorV3",
        "status": "COLLECTION_COMPLETED",
        "evidence_schema_version": 3,
        "probe_artifact_count": len(
            list((output_directory / RAW_DIRECTORY).glob("*.json"))
        ),
        "observed_feature_count": sum(
            state == "observed" for state in availability.values()
        ),
        "structural_unavailable_count": sum(
            state == "structurally_unavailable"
            for state in availability.values()
        ),
        "collection_unavailable_count": sum(
            state == "collection_unavailable"
            for state in availability.values()
        ),
        "topology_id": profile.topology_id,
        "direction": profile.direction,
        "output_directory": str(output_directory),
    }
    _atomic_write_json(
        output_directory / STATUS_PATH,
        collector_status,
    )
    return evidence


def load_observation_profile_v2(
    scenario_path: Path,
) -> ObservationProfileV2:
    document = yaml.safe_load(
        scenario_path.read_text(encoding="utf-8")
    )
    if not isinstance(document, dict):
        raise EvidenceCollectorV3Error(
            "Scenario document must be a YAML object."
        )
    scenario = document.get("scenario")
    if not isinstance(scenario, dict):
        raise EvidenceCollectorV3Error(
            "Scenario document does not contain 'scenario'."
        )
    return validate_observation_profile_v2(scenario)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Collect role-neutral Evidence v3 from an explicitly "
            "versioned Observation Profile v2."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New experiment directory for Evidence v3 artifacts.",
    )
    parser.add_argument(
        "--scenario",
        type=Path,
        required=True,
        help="Scenario YAML containing Observation Profile v2.",
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        profile = load_observation_profile_v2(arguments.scenario)
        evidence = collect_evidence_v3(
            arguments.output,
            profile,
        )
    except (
        EvidenceCollectorV3Error,
        EvidenceContractError,
        OSError,
        ValueError,
        yaml.YAMLError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
