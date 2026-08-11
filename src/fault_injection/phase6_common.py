from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

import yaml

from src.contracts.observation_profile import (
    ObservationProfileContractError,
)
from src.contracts.observation_profile_v2 import (
    ObservationProfileV2,
    validate_observation_profile_v2,
)
from src.fault_injection.common import FaultInjectionError


Phase6CommandResult = dict[str, object]
Phase6Executor = Callable[
    [str, Sequence[str]],
    Phase6CommandResult,
]


class Phase6FaultInjectionError(FaultInjectionError):
    """Raised when a Phase 6 mutation cannot be handled safely."""


@dataclass(frozen=True)
class Phase6Scenario:
    path: Path
    sha256: str
    scenario: dict[str, Any]
    profile: ObservationProfileV2
    fault: dict[str, Any]
    parameters: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def docker_exec_result(
    container: str,
    command: Sequence[str],
) -> Phase6CommandResult:
    full_command = ["docker", "exec", container, *command]
    try:
        process = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            check=False,
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


def execute_checked(
    executor: Phase6Executor,
    container: str,
    command: Sequence[str],
) -> Phase6CommandResult:
    expected_command = ["docker", "exec", container, *command]
    try:
        result = executor(container, command)
    except Exception as error:
        raise Phase6FaultInjectionError(
            "Phase 6 executor raised an exception: "
            f"{type(error).__name__}: {error}"
        ) from error
    if not isinstance(result, dict):
        raise Phase6FaultInjectionError(
            "Phase 6 executor must return an object."
        )
    if result.get("command") != expected_command:
        raise Phase6FaultInjectionError(
            "Phase 6 executor returned a mismatched command."
        )
    return_code = result.get("return_code")
    if isinstance(return_code, bool) or not isinstance(return_code, int):
        raise Phase6FaultInjectionError(
            "Phase 6 executor return_code must be an integer."
        )
    for name in ("stdout", "stderr", "timestamp_utc"):
        if not isinstance(result.get(name), str):
            raise Phase6FaultInjectionError(
                f"Phase 6 executor {name} must be a string."
            )
    try:
        timestamp = datetime.fromisoformat(str(result["timestamp_utc"]))
    except ValueError as error:
        raise Phase6FaultInjectionError(
            "Phase 6 executor timestamp_utc must be ISO-8601."
        ) from error
    if (
        timestamp.tzinfo is None
        or timestamp.utcoffset() != timezone.utc.utcoffset(timestamp)
    ):
        raise Phase6FaultInjectionError(
            "Phase 6 executor timestamp_utc must use UTC."
        )
    return {
        "command": expected_command,
        "return_code": return_code,
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "timestamp_utc": result["timestamp_utc"],
    }


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Phase6FaultInjectionError(
            f"Cannot read a valid Phase 6 JSON object: {path}"
        ) from error
    if not isinstance(value, dict):
        raise Phase6FaultInjectionError(
            f"Phase 6 JSON artifact must be an object: {path}"
        )
    return value


def require_new_mutation_output(output_directory: Path) -> None:
    conflicts = [
        output_directory / "preconditions.json",
        output_directory / "injection_record.json",
        output_directory / "restoration_record.json",
        output_directory / "ground_truth.json",
    ]
    existing = [str(path) for path in conflicts if path.exists()]
    if existing:
        raise Phase6FaultInjectionError(
            "Phase 6 mutation output already exists: "
            + ", ".join(existing)
        )


def load_phase6_scenario(
    scenario_path: Path,
    expected_fault_type: str,
) -> Phase6Scenario:
    scenario_path = Path(scenario_path)
    try:
        document = yaml.safe_load(
            scenario_path.read_text(encoding="utf-8")
        )
    except (OSError, yaml.YAMLError) as error:
        raise Phase6FaultInjectionError(
            f"Cannot read Phase 6 scenario: {scenario_path}"
        ) from error
    if not isinstance(document, dict):
        raise Phase6FaultInjectionError(
            "Phase 6 scenario document must be an object."
        )
    scenario = document.get("scenario")
    if not isinstance(scenario, dict):
        raise Phase6FaultInjectionError(
            "Phase 6 scenario requires a scenario object."
        )
    if scenario.get("kind") != "fault":
        raise Phase6FaultInjectionError(
            "Phase 6 injector requires scenario.kind=fault."
        )
    fault = scenario.get("fault")
    if not isinstance(fault, dict):
        raise Phase6FaultInjectionError(
            "Phase 6 fault scenario requires a fault object."
        )
    if fault.get("type") != expected_fault_type:
        raise Phase6FaultInjectionError(
            "Phase 6 scenario fault type does not match the injector."
        )
    expected_mechanisms = {
        "missing_static_route": (
            "delete_exact_destination_route",
            "replace_exact_destination_route",
        ),
        "wrong_next_hop": (
            "replace_destination_route_next_hop",
            "replace_exact_destination_route",
        ),
        "wrong_default_gateway": (
            "replace_source_default_gateway",
            "replace_expected_source_default_gateway",
        ),
        "interface_down": (
            "set_observer_egress_interface_down",
            "set_observer_egress_interface_up_and_revalidate",
        ),
        "acl_block": (
            "insert_exact_tagged_forward_drop_rule",
            "delete_exact_tagged_forward_drop_rule",
        ),
    }
    if expected_fault_type not in expected_mechanisms:
        raise Phase6FaultInjectionError(
            "The Phase 6 loader received an unsupported fault class."
        )
    expected_injector, expected_restoration = expected_mechanisms[
        expected_fault_type
    ]
    restoration = scenario.get("restoration")
    if (
        fault.get("injector") != expected_injector
        or not isinstance(restoration, dict)
        or restoration.get("method") != expected_restoration
    ):
        raise Phase6FaultInjectionError(
            "Phase 6 injection or restoration mechanism drifted from "
            "the frozen taxonomy."
        )
    parameters = fault.get("parameters")
    if not isinstance(parameters, dict):
        raise Phase6FaultInjectionError(
            "Phase 6 fault requires a parameters object."
        )
    ground_truth = scenario.get("ground_truth")
    if (
        not isinstance(ground_truth, dict)
        or ground_truth.get("fault_type") != expected_fault_type
        or ground_truth.get("fault_location")
        != fault.get("target_node")
    ):
        raise Phase6FaultInjectionError(
            "Phase 6 ground truth does not match the fault binding."
        )
    try:
        profile = validate_observation_profile_v2(scenario)
    except ObservationProfileContractError as error:
        raise Phase6FaultInjectionError(
            f"Invalid Observation Profile v2: {error}"
        ) from error
    return Phase6Scenario(
        path=scenario_path,
        sha256=sha256_file(scenario_path),
        scenario=scenario,
        profile=profile,
        fault=fault,
        parameters=parameters,
    )


def check(
    passed: bool,
    result: Phase6CommandResult,
    *,
    observed: object = None,
) -> dict[str, object]:
    return {
        "passed": bool(passed),
        "observed": observed,
        "command_result": result,
    }


def all_checks_pass(checks: dict[str, dict[str, object]]) -> bool:
    return bool(checks) and all(
        item.get("passed") is True for item in checks.values()
    )


def ping_check(
    executor: Phase6Executor,
    container: str,
    destination: str,
    *,
    expected: bool,
) -> dict[str, object]:
    result = execute_checked(
        executor,
        container,
        ["ping", "-c", "2", "-W", "1", destination],
    )
    reachable = (
        True
        if result["return_code"] == 0
        else False
        if result["return_code"] == 1
        else None
    )
    return check(reachable is expected, result, observed=reachable)


def parse_single_route(
    result: Phase6CommandResult,
    *,
    default: bool = False,
) -> tuple[bool, str | None, str | None]:
    if result["return_code"] != 0:
        return False, None, None
    try:
        rows = json.loads(str(result["stdout"]))
    except json.JSONDecodeError:
        return False, None, None
    if not isinstance(rows, list) or len(rows) != 1:
        return False, None, None
    row = rows[0]
    if not isinstance(row, dict):
        return False, None, None
    if default and row.get("dst", "default") != "default":
        return False, None, None
    gateway = row.get("gateway")
    interface = row.get("dev")
    if not isinstance(gateway, str) or not isinstance(interface, str):
        return False, None, None
    return True, gateway, interface


def default_route_check(
    executor: Phase6Executor,
    container: str,
    *,
    gateway: str,
    interface: str,
) -> dict[str, object]:
    result = execute_checked(
        executor,
        container,
        ["ip", "-j", "route", "show", "default"],
    )
    available, observed_gateway, observed_interface = (
        parse_single_route(result, default=True)
    )
    observed = {
        "gateway": observed_gateway,
        "interface": observed_interface,
    }
    return check(
        available
        and observed_gateway == gateway
        and observed_interface == interface,
        result,
        observed=observed,
    )


def effective_route_check(
    executor: Phase6Executor,
    container: str,
    destination: str,
    *,
    gateway: str,
    interface: str,
) -> dict[str, object]:
    result = execute_checked(
        executor,
        container,
        ["ip", "-j", "route", "get", destination],
    )
    available, observed_gateway, observed_interface = parse_single_route(
        result
    )
    observed = {
        "gateway": observed_gateway,
        "interface": observed_interface,
    }
    return check(
        available
        and observed_gateway == gateway
        and observed_interface == interface,
        result,
        observed=observed,
    )


def observer_route_check(
    executor: Phase6Executor,
    container: str,
    prefix: str,
    *,
    next_hop: str,
    interface: str,
) -> dict[str, object]:
    result = execute_checked(
        executor,
        container,
        ["ip", "-j", "route", "show", "exact", prefix],
    )
    available, observed_gateway, observed_interface = parse_single_route(
        result
    )
    observed = {
        "gateway": observed_gateway,
        "interface": observed_interface,
    }
    return check(
        available
        and observed_gateway == next_hop
        and observed_interface == interface,
        result,
        observed=observed,
    )


def observer_route_absent_check(
    executor: Phase6Executor,
    container: str,
    prefix: str,
) -> dict[str, object]:
    result = execute_checked(
        executor,
        container,
        ["ip", "-j", "route", "show", "exact", prefix],
    )
    rows: object = None
    if result["return_code"] == 0:
        try:
            rows = json.loads(str(result["stdout"]))
        except json.JSONDecodeError:
            rows = None
    absent = isinstance(rows, list) and len(rows) == 0
    route_exists = bool(rows) if isinstance(rows, list) else None
    return check(absent, result, observed={"route_exists": route_exists})


def interface_state_check(
    executor: Phase6Executor,
    container: str,
    interface: str,
    *,
    expected_up: bool,
) -> dict[str, object]:
    result = execute_checked(
        executor,
        container,
        ["ip", "-j", "link", "show", "dev", interface],
    )
    oper_state: str | None = None
    if result["return_code"] == 0:
        try:
            rows = json.loads(str(result["stdout"]))
        except json.JSONDecodeError:
            rows = None
        if (
            isinstance(rows, list)
            and len(rows) == 1
            and isinstance(rows[0], dict)
            and rows[0].get("ifname") == interface
            and isinstance(rows[0].get("operstate"), str)
        ):
            oper_state = str(rows[0]["operstate"]).lower()
    expected_state = "up" if expected_up else "down"
    return check(
        oper_state == expected_state,
        result,
        observed=oper_state,
    )


def build_record(
    binding: Phase6Scenario,
    *,
    started_at_utc: str,
    completed_at_utc: str,
    preconditions: dict[str, dict[str, object]],
    mutation_command: Phase6CommandResult | None,
    postconditions: dict[str, dict[str, object]],
    status: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "scenario_id": binding.scenario["id"],
        "scenario_sha256": binding.sha256,
        "fault_type": binding.fault["type"],
        "target_node": binding.fault["target_node"],
        "target_container": binding.fault["target_container"],
        "parameters": binding.parameters,
        "started_at_utc": started_at_utc,
        "completed_at_utc": completed_at_utc,
        "preconditions": preconditions,
        "preconditions_passed": all_checks_pass(preconditions),
        "mutation_command": mutation_command,
        "mutation_applied": (
            mutation_command is not None
            and mutation_command.get("return_code") == 0
        ),
        "postconditions": postconditions,
        "postconditions_passed": all_checks_pass(postconditions),
        "status": status,
    }


def require_restorable_record(
    output_directory: Path,
    binding: Phase6Scenario,
) -> dict[str, Any]:
    record = load_json_object(
        Path(output_directory) / "injection_record.json"
    )
    expected = {
        "scenario_id": binding.scenario["id"],
        "scenario_sha256": binding.sha256,
        "fault_type": binding.fault["type"],
        "target_node": binding.fault["target_node"],
        "target_container": binding.fault["target_container"],
        "parameters": binding.parameters,
    }
    if any(record.get(name) != value for name, value in expected.items()):
        raise Phase6FaultInjectionError(
            "Injection record does not match the reviewed scenario."
        )
    if record.get("mutation_applied") is not True:
        raise Phase6FaultInjectionError(
            "Injection record does not contain an applied mutation."
        )
    if record.get("status") not in {
        "FAULT_CONFIRMED",
        "FAULT_NOT_CONFIRMED",
    }:
        raise Phase6FaultInjectionError(
            "Injection record has an invalid restoration state."
        )
    return record
