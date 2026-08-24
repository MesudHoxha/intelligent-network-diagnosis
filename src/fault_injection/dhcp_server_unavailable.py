from __future__ import annotations

from pathlib import Path

from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, X4DhcpServerUnavailableError, dhcp_lease_probe, load_dhcp_server_unavailable_scenario
from src.fault_injection.phase6_common import Phase6Executor, execute_checked, load_json_object, utc_now, write_json_atomic


def _checks(binding, executor: Phase6Executor, *, expect_available: bool) -> dict[str, object]:
    status = execute_checked(executor, binding.destination_container, ["x4-dhcp-service", "status"])
    lease = dhcp_lease_probe(binding, executor)
    text = str(lease["stdout"]) + str(lease["stderr"]); lease_ok = lease["return_code"] == 0 and (binding.expected_scope_prefix in text or "bound to" in text)
    return {"dhcp_service_state": {"passed": (status["return_code"] == 0) == expect_available, "command_result": status}, "real_dhcp_lease_exchange": {"passed": lease_ok == expect_available, "command_result": lease, "not_icmp": True}}


def _all(checks: dict[str, object]) -> bool:
    return all(isinstance(value, dict) and value.get("passed") is True for value in checks.values())


def _identity(record: dict[str, object], binding) -> bool:
    return all(record.get(key) == value for key, value in binding.recovery_identity.items())


def restore_dhcp_server_unavailable(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_dhcp_server_unavailable_scenario(scenario_path); output = Path(output_directory); record_path = output / "restoration_record.json"
    if record_path.is_file():
        existing = load_json_object(record_path)
        if _identity(existing, binding) and existing.get("status") == "RESTORATION_CONFIRMED": return existing
    intent_path = output / "recovery_intent.json"
    if not intent_path.is_file() or not _identity(load_json_object(intent_path), binding): raise X4DhcpServerUnavailableError("X4-R1 restoration requires matching durable recovery intent.")
    command = execute_checked(executor, binding.destination_container, ["x4-dhcp-service", "start"]); checks = _checks(binding, executor, expect_available=True) if command["return_code"] == 0 else {}; confirmed = command["return_code"] == 0 and _all(checks)
    record = {"schema_version": 1, **binding.recovery_identity, "completed_at_utc": utc_now(), "restoration_command": command, "postconditions": checks, "status": "RESTORATION_CONFIRMED" if confirmed else "RESTORATION_FAILED"}; write_json_atomic(record_path, record)
    if not confirmed: raise X4DhcpServerUnavailableError("X4-R1 DHCP restoration and valid lease were not confirmed.")
    return record


def inject_dhcp_server_unavailable(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_dhcp_server_unavailable_scenario(scenario_path); output = Path(output_directory)
    if any((output / name).exists() for name in ("preconditions.json", "recovery_intent.json", "injection_record.json", "restoration_record.json")): raise X4DhcpServerUnavailableError("X4-R1 mutation output already exists.")
    output.mkdir(parents=True, exist_ok=True); preconditions = _checks(binding, executor, expect_available=True); write_json_atomic(output / "preconditions.json", preconditions)
    if not _all(preconditions): raise X4DhcpServerUnavailableError("X4-R1 preflight/healthy DHCP baseline failed; no mutation attempted.")
    write_json_atomic(output / "recovery_intent.json", {"schema_version": 1, **binding.recovery_identity, "status": "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED", "created_at_utc": utc_now()})
    try:
        command = execute_checked(executor, binding.destination_container, ["x4-dhcp-service", "stop"]); checks = _checks(binding, executor, expect_available=False) if command["return_code"] == 0 else {}; confirmed = command["return_code"] == 0 and _all(checks)
        record = {"schema_version": 1, **binding.recovery_identity, "completed_at_utc": utc_now(), "mutation_command": command, "postconditions": checks, "status": "FAULT_CONFIRMED" if confirmed else "FAULT_NOT_CONFIRMED"}; write_json_atomic(output / "injection_record.json", record)
        if not confirmed: raise X4DhcpServerUnavailableError("X4-R1 DHCP service-unavailable fault was not confirmed.")
        return record
    except BaseException:
        restore_dhcp_server_unavailable(scenario_path, output, executor=executor); raise
