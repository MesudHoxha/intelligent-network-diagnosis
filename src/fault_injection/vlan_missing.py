from __future__ import annotations

from pathlib import Path
from typing import Any

from src.expansion.x3_vlan_missing import (
    DEFAULT_EXECUTOR,
    VlanMissingScenario,
    X3VlanMissingError,
    bridge_vlan_inventory,
    is_pvid_untagged,
    is_tagged,
    load_vlan_missing_scenario,
    ping_result,
    vlan_membership,
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


def _identity_matches(record: dict[str, Any], binding: VlanMissingScenario) -> bool:
    return all(record.get(name) == value for name, value in binding.recovery_identity.items())


def _require_identity(
    record: dict[str, Any],
    binding: VlanMissingScenario,
    label: str,
) -> None:
    if not _identity_matches(record, binding):
        raise X3VlanMissingError(
            f"{label} does not match the reviewed X3-R2 scenario."
        )


def _ensure_new_output(output_directory: Path) -> None:
    names = (
        "preconditions.json",
        RECOVERY_INTENT_NAME,
        INJECTION_RECORD_NAME,
        RESTORATION_RECORD_NAME,
        "ground_truth.json",
    )
    existing = [str(output_directory / name) for name in names if (output_directory / name).exists()]
    if existing:
        raise X3VlanMissingError(
            "X3-R2 mutation output already exists: " + ", ".join(existing)
        )


def _target_membership_checks(
    binding: VlanMissingScenario,
    executor: Phase6Executor,
    *,
    faulted: bool,
) -> dict[str, dict[str, object]]:
    target_result, target_rows = bridge_vlan_inventory(
        executor, binding.target_switch_container
    )
    expected_access = vlan_membership(
        target_rows, binding.target_access_interface, binding.expected_vlan
    )
    expected_trunk = vlan_membership(
        target_rows, binding.trunk_interface, binding.expected_vlan
    )
    if faulted:
        return {
            "expected_access_vlan_is_absent": _check(
                expected_access is None, target_result, target_rows
            ),
            "expected_trunk_vlan_is_absent": _check(
                expected_trunk is None, target_result, target_rows
            ),
        }
    return {
        "expected_access_vlan_is_exact_pvid_untagged": _check(
            is_pvid_untagged(expected_access), target_result, target_rows
        ),
        "expected_trunk_vlan_is_exact_tagged": _check(
            is_tagged(expected_trunk), target_result, target_rows
        ),
    }


def _baseline_checks(
    binding: VlanMissingScenario,
    executor: Phase6Executor,
) -> dict[str, dict[str, object]]:
    checks = _target_membership_checks(binding, executor, faulted=False)
    peer_result, peer_rows = bridge_vlan_inventory(
        executor,
        binding.peer_switch_container,
        binding.peer_access_interface,
    )
    sw1_trunk_result, sw1_trunk_rows = bridge_vlan_inventory(
        executor,
        binding.target_switch_container,
        binding.trunk_interface,
    )
    sw2_trunk_result, sw2_trunk_rows = bridge_vlan_inventory(
        executor,
        binding.peer_switch_container,
        binding.trunk_interface,
    )
    tagged_result, tagged_reachable = ping_result(
        executor, binding.source_container, binding.destination_address
    )
    native_result, native_reachable = ping_result(
        executor,
        binding.native_source_container,
        binding.native_destination_address,
    )
    peer_access = vlan_membership(
        peer_rows, binding.peer_access_interface, binding.expected_vlan
    )
    sw1_tagged = vlan_membership(
        sw1_trunk_rows, binding.trunk_interface, binding.expected_vlan
    )
    sw2_tagged = vlan_membership(
        sw2_trunk_rows, binding.trunk_interface, binding.expected_vlan
    )
    sw1_native = vlan_membership(
        sw1_trunk_rows, binding.trunk_interface, binding.native_vlan
    )
    sw2_native = vlan_membership(
        sw2_trunk_rows, binding.trunk_interface, binding.native_vlan
    )
    checks.update(
        {
            "peer_access_vlan_is_exact": _check(
                is_pvid_untagged(peer_access), peer_result, peer_rows
            ),
            "expected_vlan_allowed_on_both_trunk_endpoints": _check(
                is_tagged(sw1_tagged) and is_tagged(sw2_tagged),
                sw1_trunk_result,
                {"sw1": sw1_trunk_rows, "sw2": sw2_trunk_rows},
            ),
            "native_vlan_matches_on_both_trunk_endpoints": _check(
                is_pvid_untagged(sw1_native) and is_pvid_untagged(sw2_native),
                sw2_trunk_result,
                {"sw1": sw1_trunk_rows, "sw2": sw2_trunk_rows},
            ),
            "tagged_flow_reachable": _check(
                tagged_reachable, tagged_result, tagged_reachable
            ),
            "native_flow_reachable": _check(
                native_reachable, native_result, native_reachable
            ),
        }
    )
    return checks


def _fault_checks(
    binding: VlanMissingScenario,
    executor: Phase6Executor,
) -> dict[str, dict[str, object]]:
    checks = _target_membership_checks(binding, executor, faulted=True)
    tagged_result, tagged_reachable = ping_result(
        executor, binding.source_container, binding.destination_address
    )
    native_result, native_reachable = ping_result(
        executor,
        binding.native_source_container,
        binding.native_destination_address,
    )
    checks.update(
        {
            "tagged_flow_is_broken": _check(
                not tagged_reachable, tagged_result, tagged_reachable
            ),
            "native_flow_remains_healthy": _check(
                native_reachable, native_result, native_reachable
            ),
        }
    )
    return checks


def _write_recovery_intent(
    output_directory: Path,
    binding: VlanMissingScenario,
) -> None:
    write_json_atomic(
        output_directory / RECOVERY_INTENT_NAME,
        {
            "schema_version": 1,
            **binding.recovery_identity,
            "status": "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED",
            "created_at_utc": utc_now(),
        },
    )


def _require_recovery_authority(
    output_directory: Path,
    binding: VlanMissingScenario,
) -> None:
    intent_path = output_directory / RECOVERY_INTENT_NAME
    if not intent_path.is_file():
        raise X3VlanMissingError(
            "X3-R2 restoration requires a matching durable recovery intent."
        )
    intent = load_json_object(intent_path)
    _require_identity(intent, binding, "Recovery intent")
    if intent.get("status") != "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED":
        raise X3VlanMissingError("X3-R2 recovery intent has an invalid state.")


def restore_vlan_missing(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = DEFAULT_EXECUTOR,
) -> dict[str, object]:
    binding = load_vlan_missing_scenario(scenario_path)
    output_directory = Path(output_directory)
    restored_path = output_directory / RESTORATION_RECORD_NAME
    if restored_path.is_file():
        existing = load_json_object(restored_path)
        _require_identity(existing, binding, "Restoration record")
        if existing.get("status") == "RESTORATION_CONFIRMED":
            return existing
    _require_recovery_authority(output_directory, binding)

    started = utc_now()
    command = execute_checked(
        executor,
        binding.target_switch_container,
        [
            "sh",
            "-eu",
            "-c",
            (
                f"bridge vlan del dev {binding.target_access_interface} "
                f"vid {binding.expected_vlan} 2>/dev/null || true; "
                f"bridge vlan add dev {binding.target_access_interface} "
                f"vid {binding.expected_vlan} pvid untagged; "
                f"bridge vlan del dev {binding.trunk_interface} "
                f"vid {binding.expected_vlan} 2>/dev/null || true; "
                f"bridge vlan add dev {binding.trunk_interface} "
                f"vid {binding.expected_vlan}"
            ),
        ],
    )
    postconditions = (
        _baseline_checks(binding, executor) if command["return_code"] == 0 else {}
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
    write_json_atomic(restored_path, record)
    if not confirmed:
        raise X3VlanMissingError(
            "X3-R2 exact access and trunk VLAN restoration was not confirmed."
        )
    return record


def inject_vlan_missing(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = DEFAULT_EXECUTOR,
) -> dict[str, object]:
    binding = load_vlan_missing_scenario(scenario_path)
    output_directory = Path(output_directory)
    _ensure_new_output(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    preconditions = _baseline_checks(binding, executor)
    write_json_atomic(output_directory / "preconditions.json", preconditions)
    if not _all_pass(preconditions):
        raise X3VlanMissingError("X3-R2 baseline failed; no mutation was attempted.")
    _write_recovery_intent(output_directory, binding)

    try:
        command = execute_checked(
            executor,
            binding.target_switch_container,
            [
                "sh",
                "-eu",
                "-c",
                (
                    f"bridge vlan del dev {binding.target_access_interface} "
                    f"vid {binding.expected_vlan}; "
                    f"bridge vlan del dev {binding.trunk_interface} "
                    f"vid {binding.expected_vlan}"
                ),
            ],
        )
        postconditions = (
            _fault_checks(binding, executor) if command["return_code"] == 0 else {}
        )
        confirmed = command["return_code"] == 0 and _all_pass(postconditions)
        record = {
            "schema_version": 1,
            **binding.recovery_identity,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "mutation_command": command,
            "mutation_applied": command["return_code"] == 0,
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
            raise X3VlanMissingError("X3-R2 fault postconditions were not confirmed.")
        return record
    except BaseException as primary:
        try:
            restore_vlan_missing(scenario_path, output_directory, executor=executor)
        except BaseException as restoration:
            raise X3VlanMissingError(
                "X3-R2 injection and restoration both failed."
            ) from restoration
        raise primary
