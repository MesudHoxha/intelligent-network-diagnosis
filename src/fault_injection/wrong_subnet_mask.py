from __future__ import annotations

from pathlib import Path
from typing import Any

from src.expansion.x2_addressing import (
    DEFAULT_EXECUTOR,
    X2AddressingError,
    address_inventory,
    default_route_inventory,
    ping_result,
)
from src.expansion.x2_subnet_mask import (
    WrongSubnetMaskScenario,
    load_wrong_subnet_mask_scenario,
)
from src.fault_injection.phase6_common import (
    Phase6Executor,
    execute_checked,
    load_json_object,
    utc_now,
    write_json_atomic,
)


RECOVERY_INTENT_NAME = "recovery_intent.json"
INJECTION_RECORD_NAME = "injection_record.json"
RESTORATION_RECORD_NAME = "restoration_record.json"


def _check(
    passed: bool,
    command_result: dict[str, object],
    observed: object,
) -> dict[str, object]:
    return {
        "passed": bool(passed),
        "observed": observed,
        "command_result": command_result,
    }


def _all_pass(checks: dict[str, dict[str, object]]) -> bool:
    return bool(checks) and all(row.get("passed") is True for row in checks.values())


def _identity_matches(
    record: dict[str, Any], binding: WrongSubnetMaskScenario
) -> bool:
    return all(record.get(name) == value for name, value in binding.recovery_identity.items())


def _require_identity(
    record: dict[str, Any],
    binding: WrongSubnetMaskScenario,
    label: str,
) -> None:
    if not _identity_matches(record, binding):
        raise X2AddressingError(f"{label} does not match the reviewed X2-R2 scenario.")


def _ensure_new_output(output_directory: Path) -> None:
    conflicts = [
        output_directory / "preconditions.json",
        output_directory / RECOVERY_INTENT_NAME,
        output_directory / INJECTION_RECORD_NAME,
        output_directory / RESTORATION_RECORD_NAME,
        output_directory / "ground_truth.json",
    ]
    existing = [str(path) for path in conflicts if path.exists()]
    if existing:
        raise X2AddressingError(
            "X2-R2 mutation output already exists: " + ", ".join(existing)
        )


def _state_checks(
    binding: WrongSubnetMaskScenario,
    executor: Phase6Executor,
    *,
    expected_interface: str,
) -> dict[str, dict[str, object]]:
    address_result, addresses = address_inventory(executor, binding)
    route_result, routes = default_route_inventory(executor, binding)
    gateway_result, gateway_reachable = ping_result(
        executor, binding.source_container, binding.expected_gateway
    )
    destination_result, destination_reachable = ping_result(
        executor, binding.source_container, binding.destination_address
    )
    return {
        "exact_source_interface_present": _check(
            addresses == (expected_interface,),
            address_result,
            list(addresses),
        ),
        "expected_default_route_present": _check(
            routes == ((binding.expected_gateway, binding.source_interface),),
            route_result,
            [list(row) for row in routes],
        ),
        "expected_gateway_reachable": _check(
            gateway_reachable is True,
            gateway_result,
            gateway_reachable,
        ),
        "destination_reachable": _check(
            destination_reachable is True,
            destination_result,
            destination_reachable,
        ),
    }


def _write_recovery_intent(
    output_directory: Path,
    binding: WrongSubnetMaskScenario,
) -> dict[str, object]:
    intent = {
        "schema_version": 1,
        **binding.recovery_identity,
        "status": "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED",
        "created_at_utc": utc_now(),
    }
    write_json_atomic(output_directory / RECOVERY_INTENT_NAME, intent)
    return intent


def _load_confirmed_restoration(
    output_directory: Path,
    binding: WrongSubnetMaskScenario,
) -> dict[str, Any] | None:
    path = output_directory / RESTORATION_RECORD_NAME
    if not path.exists():
        return None
    record = load_json_object(path)
    _require_identity(record, binding, "Restoration record")
    return record if record.get("status") == "RESTORATION_CONFIRMED" else None


def _require_recovery_authority(
    output_directory: Path,
    binding: WrongSubnetMaskScenario,
) -> None:
    intent_path = output_directory / RECOVERY_INTENT_NAME
    injection_path = output_directory / INJECTION_RECORD_NAME
    if intent_path.exists():
        intent = load_json_object(intent_path)
        _require_identity(intent, binding, "Recovery intent")
        if intent.get("status") != "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED":
            raise X2AddressingError("X2-R2 recovery intent has an invalid state.")
        return
    if injection_path.exists():
        record = load_json_object(injection_path)
        _require_identity(record, binding, "Injection record")
        if record.get("mutation_applied") is True:
            return
    raise X2AddressingError(
        "X2-R2 restoration requires a matching durable recovery intent."
    )


def restore_wrong_subnet_mask(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = DEFAULT_EXECUTOR,
) -> dict[str, object]:
    binding = load_wrong_subnet_mask_scenario(scenario_path)
    output_directory = Path(output_directory)
    existing = _load_confirmed_restoration(output_directory, binding)
    if existing is not None:
        return existing
    _require_recovery_authority(output_directory, binding)
    started = utc_now()
    command = execute_checked(
        executor,
        binding.source_container,
        [
            "sh",
            "-eu",
            "-c",
            (
                f"ip addr del {binding.wrong_interface} dev "
                f"{binding.source_interface} 2>/dev/null || true; "
                f"ip addr replace {binding.expected_interface} dev "
                f"{binding.source_interface}; "
                f"ip link set {binding.source_interface} up; "
                f"ip route replace default via {binding.expected_gateway} "
                f"dev {binding.source_interface}"
            ),
        ],
    )
    postconditions = (
        _state_checks(
            binding,
            executor,
            expected_interface=binding.expected_interface,
        )
        if command["return_code"] == 0
        else {}
    )
    confirmed = command["return_code"] == 0 and _all_pass(postconditions)
    record = {
        "schema_version": 1,
        **binding.recovery_identity,
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "restoration_command": command,
        "postconditions": postconditions,
        "postconditions_passed": _all_pass(postconditions),
        "status": "RESTORATION_CONFIRMED" if confirmed else "RESTORATION_FAILED",
    }
    write_json_atomic(output_directory / RESTORATION_RECORD_NAME, record)
    if not confirmed:
        raise X2AddressingError(
            "X2-R2 exact subnet-mask restoration was not confirmed."
        )
    return record


def inject_wrong_subnet_mask(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = DEFAULT_EXECUTOR,
) -> dict[str, object]:
    binding = load_wrong_subnet_mask_scenario(scenario_path)
    output_directory = Path(output_directory)
    _ensure_new_output(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    preconditions = _state_checks(
        binding,
        executor,
        expected_interface=binding.expected_interface,
    )
    write_json_atomic(output_directory / "preconditions.json", preconditions)
    if not _all_pass(preconditions):
        record = {
            "schema_version": 1,
            **binding.recovery_identity,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "preconditions": preconditions,
            "mutation_command": None,
            "mutation_applied": False,
            "postconditions": {},
            "status": "INVALID_BASELINE",
        }
        write_json_atomic(output_directory / INJECTION_RECORD_NAME, record)
        raise X2AddressingError(
            "X2-R2 wrong-mask preconditions failed; no mutation was attempted."
        )

    _write_recovery_intent(output_directory, binding)
    try:
        mutation_command = execute_checked(
            executor,
            binding.source_container,
            [
                "sh",
                "-eu",
                "-c",
                (
                    f"ip addr del {binding.expected_interface} dev "
                    f"{binding.source_interface}; "
                    f"ip addr add {binding.wrong_interface} dev "
                    f"{binding.source_interface}; "
                    f"ip link set {binding.source_interface} up; "
                    f"ip route replace default via {binding.expected_gateway} "
                    f"dev {binding.source_interface}"
                ),
            ],
        )
        postconditions = (
            _state_checks(
                binding,
                executor,
                expected_interface=binding.wrong_interface,
            )
            if mutation_command["return_code"] == 0
            else {}
        )
        confirmed = mutation_command["return_code"] == 0 and _all_pass(postconditions)
        record = {
            "schema_version": 1,
            **binding.recovery_identity,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "preconditions": preconditions,
            "preconditions_passed": True,
            "mutation_command": mutation_command,
            "mutation_applied": mutation_command["return_code"] == 0,
            "postconditions": postconditions,
            "postconditions_passed": _all_pass(postconditions),
            "status": "FAULT_CONFIRMED" if confirmed else "FAULT_NOT_CONFIRMED",
        }
        write_json_atomic(output_directory / INJECTION_RECORD_NAME, record)
        write_json_atomic(
            output_directory / "ground_truth.json",
            binding.scenario["ground_truth"],
        )
        if not confirmed:
            raise X2AddressingError("X2-R2 wrong subnet mask was not confirmed.")
        return record
    except BaseException as primary_error:
        try:
            restore_wrong_subnet_mask(
                scenario_path,
                output_directory,
                executor=executor,
            )
        except BaseException as restoration_error:
            raise X2AddressingError(
                "X2-R2 injection failed and best-effort restoration also failed."
            ) from restoration_error
        if isinstance(primary_error, Exception):
            raise primary_error
        raise
