from __future__ import annotations

from pathlib import Path
from typing import Any

from src.expansion.x2_addressing import DEFAULT_EXECUTOR, X2AddressingError, address_inventory, default_route_inventory
from src.expansion.x2_duplicate_ip import DuplicateIPScenario, load_duplicate_ip_scenario
from src.fault_injection.phase6_common import Phase6Executor, execute_checked, load_json_object, utc_now, write_json_atomic

RECOVERY_INTENT_NAME = "recovery_intent.json"
INJECTION_RECORD_NAME = "injection_record.json"
RESTORATION_RECORD_NAME = "restoration_record.json"


def _identity(record: dict[str, Any], binding: DuplicateIPScenario) -> bool:
    return all(record.get(k) == v for k, v in binding.recovery_identity.items())


def _healthy(binding: DuplicateIPScenario, executor: Phase6Executor) -> tuple[bool, dict[str, object]]:
    addr_result, addresses = address_inventory(executor, binding)
    route_result, routes = default_route_inventory(executor, binding)
    checks = {
        "exact_source_interface_present": addresses == (binding.expected_interface,),
        "expected_default_route_present": routes == ((binding.expected_gateway, binding.source_interface),),
        "address_command": addr_result,
        "route_command": route_result,
    }
    return bool(checks["exact_source_interface_present"] and checks["expected_default_route_present"]), checks


def _claimant_state(binding: DuplicateIPScenario, executor: Phase6Executor) -> tuple[bool, dict[str, object]]:
    result = execute_checked(executor, binding.target_container, ["sh", "-c", f"ip -j addr show dev {binding.duplicate_interface} 2>/dev/null || true"])
    expected = binding.expected_address in str(result.get("stdout", ""))
    return expected, result


def restore_duplicate_ip(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_duplicate_ip_scenario(scenario_path)
    output_directory = Path(output_directory)
    restored = output_directory / RESTORATION_RECORD_NAME
    if restored.exists():
        record = load_json_object(restored)
        if _identity(record, binding) and record.get("status") == "RESTORATION_CONFIRMED":
            return record
    intent = output_directory / RECOVERY_INTENT_NAME
    if not intent.exists() or not _identity(load_json_object(intent), binding):
        raise X2AddressingError("X2-R4 restoration requires matching durable recovery intent.")
    command = execute_checked(executor, binding.target_container, ["sh", "-eu", "-c", f"ip netns del {binding.observer_namespace} 2>/dev/null || true; ip link del {binding.duplicate_interface} 2>/dev/null || true"])
    claimant, state = _claimant_state(binding, executor)
    healthy, baseline = _healthy(binding, executor)
    confirmed = command["return_code"] == 0 and not claimant and healthy
    record = {"schema_version": 1, **binding.recovery_identity, "completed_at_utc": utc_now(), "restoration_command": command, "claimant_state": state, "baseline": baseline, "status": "RESTORATION_CONFIRMED" if confirmed else "RESTORATION_FAILED"}
    write_json_atomic(restored, record)
    if not confirmed:
        raise X2AddressingError("X2-R4 duplicate claimant restoration was not confirmed.")
    return record


def inject_duplicate_ip(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_duplicate_ip_scenario(scenario_path)
    output_directory = Path(output_directory)
    if any((output_directory / n).exists() for n in (RECOVERY_INTENT_NAME, INJECTION_RECORD_NAME, RESTORATION_RECORD_NAME)):
        raise X2AddressingError("X2-R4 mutation output already exists.")
    output_directory.mkdir(parents=True, exist_ok=True)
    healthy, preconditions = _healthy(binding, executor)
    write_json_atomic(output_directory / "preconditions.json", preconditions)
    if not healthy:
        raise X2AddressingError("X2-R4 baseline failed; no mutation was attempted.")
    intent = {"schema_version": 1, **binding.recovery_identity, "status": "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED", "created_at_utc": utc_now()}
    write_json_atomic(output_directory / RECOVERY_INTENT_NAME, intent)
    duplicate_cidr = f"{binding.expected_address}/{binding.expected_prefix_length}"
    observer_peer = f"{binding.observer_interface}p"
    shell = (
        f"ip link add {binding.duplicate_interface} link {binding.parent_interface} type macvlan mode bridge; "
        f"ip link set {binding.duplicate_interface} address {binding.duplicate_mac}; "
        f"ip addr add {duplicate_cidr} dev {binding.duplicate_interface}; ip link set {binding.duplicate_interface} up; "
        f"ip netns add {binding.observer_namespace}; ip link add {observer_peer} link {binding.parent_interface} type macvlan mode bridge; "
        f"ip link set {observer_peer} netns {binding.observer_namespace}; "
        f"ip netns exec {binding.observer_namespace} ip link set {observer_peer} name {binding.observer_interface}; "
        f"ip netns exec {binding.observer_namespace} ip addr add {binding.observer_address} dev {binding.observer_interface}; "
        f"ip netns exec {binding.observer_namespace} ip link set lo up; ip netns exec {binding.observer_namespace} ip link set {binding.observer_interface} up"
    )
    try:
        command = execute_checked(executor, binding.target_container, ["sh", "-eu", "-c", shell])
        claimant, state = _claimant_state(binding, executor)
        source_healthy, source_state = _healthy(binding, executor)
        confirmed = command["return_code"] == 0 and claimant and source_healthy
        record = {"schema_version": 1, **binding.recovery_identity, "completed_at_utc": utc_now(), "mutation_command": command, "mutation_applied": command["return_code"] == 0, "claimant_state": state, "source_state": source_state, "status": "FAULT_CONFIRMED" if confirmed else "FAULT_NOT_CONFIRMED"}
        write_json_atomic(output_directory / INJECTION_RECORD_NAME, record)
        write_json_atomic(output_directory / "ground_truth.json", binding.scenario["ground_truth"])
        if not confirmed:
            raise X2AddressingError("X2-R4 duplicate claimant was not confirmed.")
        return record
    except BaseException as primary:
        try:
            restore_duplicate_ip(scenario_path, output_directory, executor=executor)
        except BaseException as restoration:
            raise X2AddressingError("X2-R4 injection and restoration failed.") from restoration
        raise primary
