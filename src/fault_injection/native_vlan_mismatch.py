from __future__ import annotations

from pathlib import Path
from typing import Any

from src.expansion.x3_native_vlan_mismatch import (
    DEFAULT_EXECUTOR, NativeVlanMismatchScenario, X3NativeVlanMismatchError,
    bridge_vlan_inventory, is_pvid_untagged, is_tagged,
    load_native_vlan_mismatch_scenario, ping_result, vlan_membership,
)
from src.fault_injection.phase6_common import Phase6Executor, execute_checked, load_json_object, utc_now, write_json_atomic


RECOVERY_INTENT_NAME = "recovery_intent.json"
INJECTION_RECORD_NAME = "injection_record.json"
RESTORATION_RECORD_NAME = "restoration_record.json"


def _check(passed: bool, command_result: dict[str, object], observed: object) -> dict[str, object]:
    return {"passed": bool(passed), "observed": observed, "command_result": command_result}


def _all(checks: dict[str, dict[str, object]]) -> bool:
    return bool(checks) and all(row.get("passed") is True for row in checks.values())


def _identity(record: dict[str, Any], binding: NativeVlanMismatchScenario) -> bool:
    return all(record.get(key) == value for key, value in binding.recovery_identity.items())


def _require_intent(output: Path, binding: NativeVlanMismatchScenario) -> None:
    intent = output / RECOVERY_INTENT_NAME
    if not intent.is_file():
        raise X3NativeVlanMismatchError("X3-R4 restoration requires a matching durable recovery intent.")
    record = load_json_object(intent)
    if not _identity(record, binding) or record.get("status") != "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED":
        raise X3NativeVlanMismatchError("X3-R4 recovery intent does not match the reviewed scenario.")


def _ensure_new(output: Path) -> None:
    existing = [name for name in ("preconditions.json", RECOVERY_INTENT_NAME, INJECTION_RECORD_NAME, RESTORATION_RECORD_NAME, "ground_truth.json") if (output / name).exists()]
    if existing:
        raise X3NativeVlanMismatchError("X3-R4 mutation output already exists: " + ", ".join(existing))


def _memberships(binding: NativeVlanMismatchScenario, executor: Phase6Executor) -> tuple[dict[str, object], object, object]:
    target_result, target = bridge_vlan_inventory(executor, binding.target_switch_container)
    peer_result, peer = bridge_vlan_inventory(executor, binding.peer_switch_container)
    return {"target": target_result, "peer": peer_result}, target, peer


def _baseline_checks(binding: NativeVlanMismatchScenario, executor: Phase6Executor) -> dict[str, dict[str, object]]:
    results, target, peer = _memberships(binding, executor)
    target_access = vlan_membership(target, binding.target_access_interface, binding.expected_vlan)
    target_native = vlan_membership(target, binding.trunk_interface, binding.expected_vlan)
    peer_native = vlan_membership(peer, binding.trunk_interface, binding.expected_vlan)
    target_tagged = vlan_membership(target, binding.trunk_interface, binding.tagged_control_vlan)
    peer_tagged = vlan_membership(peer, binding.trunk_interface, binding.tagged_control_vlan)
    native_result, native_ok = ping_result(executor, binding.source_container, binding.destination_address)
    tagged_result, tagged_ok = ping_result(executor, binding.tagged_source_container, binding.tagged_destination_address)
    return {
        "native_access_vlan_is_exact_pvid_untagged": _check(is_pvid_untagged(target_access), results["target"], target),
        "expected_native_vlan_exists_on_target": _check(target_native is not None, results["target"], target),
        "tagged_vlan_10_is_preserved_on_both_trunks": _check(is_tagged(target_tagged) and is_tagged(peer_tagged), results["peer"], {"sw1": target, "sw2": peer}),
        "native_vlan_matches_on_both_trunk_endpoints": _check(is_pvid_untagged(target_native) and is_pvid_untagged(peer_native), results["peer"], {"sw1": target, "sw2": peer}),
        "native_flow_reachable": _check(native_ok, native_result, native_ok),
        "tagged_control_flow_reachable": _check(tagged_ok, tagged_result, tagged_ok),
    }


def _fault_checks(binding: NativeVlanMismatchScenario, executor: Phase6Executor) -> dict[str, dict[str, object]]:
    results, target, peer = _memberships(binding, executor)
    target_access = vlan_membership(target, binding.target_access_interface, binding.expected_vlan)
    target_expected = vlan_membership(target, binding.trunk_interface, binding.expected_vlan)
    peer_expected = vlan_membership(peer, binding.trunk_interface, binding.expected_vlan)
    target_mismatch = vlan_membership(target, binding.trunk_interface, binding.mismatched_native_vlan)
    target_tagged = vlan_membership(target, binding.trunk_interface, binding.tagged_control_vlan)
    peer_tagged = vlan_membership(peer, binding.trunk_interface, binding.tagged_control_vlan)
    native_result, native_ok = ping_result(executor, binding.source_container, binding.destination_address)
    tagged_result, tagged_ok = ping_result(executor, binding.tagged_source_container, binding.tagged_destination_address)
    return {
        "native_access_vlan_is_preserved": _check(is_pvid_untagged(target_access), results["target"], target),
        "expected_native_vlan_is_retained_as_tagged": _check(is_tagged(target_expected) and is_pvid_untagged(peer_expected), results["peer"], {"sw1": target, "sw2": peer}),
        "controlled_native_vlan_is_target_pvid": _check(is_pvid_untagged(target_mismatch), results["target"], target),
        "tagged_vlan_10_is_preserved_on_both_trunks": _check(is_tagged(target_tagged) and is_tagged(peer_tagged), results["peer"], {"sw1": target, "sw2": peer}),
        "native_flow_is_broken": _check(not native_ok, native_result, native_ok),
        "tagged_control_flow_remains_healthy": _check(tagged_ok, tagged_result, tagged_ok),
    }


def _write_intent(output: Path, binding: NativeVlanMismatchScenario) -> None:
    write_json_atomic(output / RECOVERY_INTENT_NAME, {"schema_version": 1, **binding.recovery_identity, "status": "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED", "created_at_utc": utc_now()})


def restore_native_vlan_mismatch(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_native_vlan_mismatch_scenario(scenario_path)
    output = Path(output_directory)
    record_path = output / RESTORATION_RECORD_NAME
    if record_path.is_file():
        existing = load_json_object(record_path)
        if _identity(existing, binding) and existing.get("status") == "RESTORATION_CONFIRMED":
            return existing
    _require_intent(output, binding)
    started = utc_now()
    command = execute_checked(executor, binding.target_switch_container, ["sh", "-eu", "-c", f"bridge vlan del dev {binding.trunk_interface} vid {binding.mismatched_native_vlan} 2>/dev/null || true; bridge vlan del dev {binding.trunk_interface} vid {binding.expected_vlan} 2>/dev/null || true; bridge vlan add dev {binding.trunk_interface} vid {binding.expected_vlan} pvid untagged"])
    checks = _baseline_checks(binding, executor) if command["return_code"] == 0 else {}
    confirmed = command["return_code"] == 0 and _all(checks)
    record = {"schema_version": 1, **binding.recovery_identity, "started_at_utc": started, "completed_at_utc": utc_now(), "restoration_command": command, "postconditions": checks, "postconditions_passed": _all(checks), "status": "RESTORATION_CONFIRMED" if confirmed else "RESTORATION_FAILED"}
    write_json_atomic(record_path, record)
    if not confirmed:
        raise X3NativeVlanMismatchError("X3-R4 exact native VLAN restoration was not confirmed.")
    return record


def inject_native_vlan_mismatch(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_native_vlan_mismatch_scenario(scenario_path)
    output = Path(output_directory)
    _ensure_new(output)
    output.mkdir(parents=True, exist_ok=True)
    preconditions = _baseline_checks(binding, executor)
    write_json_atomic(output / "preconditions.json", preconditions)
    if not _all(preconditions):
        raise X3NativeVlanMismatchError("X3-R4 baseline failed; no mutation was attempted.")
    _write_intent(output, binding)
    try:
        started = utc_now()
        command = execute_checked(executor, binding.target_switch_container, ["sh", "-eu", "-c", f"bridge vlan del dev {binding.trunk_interface} vid {binding.expected_vlan}; bridge vlan add dev {binding.trunk_interface} vid {binding.expected_vlan}; bridge vlan add dev {binding.trunk_interface} vid {binding.mismatched_native_vlan} pvid untagged"])
        checks = _fault_checks(binding, executor) if command["return_code"] == 0 else {}
        confirmed = command["return_code"] == 0 and _all(checks)
        record = {"schema_version": 1, **binding.recovery_identity, "started_at_utc": started, "completed_at_utc": utc_now(), "mutation_command": command, "mutation_applied": command["return_code"] == 0, "postconditions": checks, "postconditions_passed": _all(checks), "status": "FAULT_CONFIRMED" if confirmed else "FAULT_NOT_CONFIRMED"}
        write_json_atomic(output / INJECTION_RECORD_NAME, record)
        write_json_atomic(output / "ground_truth.json", binding.scenario["ground_truth"])
        if not confirmed:
            raise X3NativeVlanMismatchError("X3-R4 fault postconditions were not confirmed.")
        return record
    except BaseException as primary:
        try:
            restore_native_vlan_mismatch(scenario_path, output, executor=executor)
        except BaseException as restoration:
            raise X3NativeVlanMismatchError("X3-R4 injection and restoration both failed.") from restoration
        raise primary
