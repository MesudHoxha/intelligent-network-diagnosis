from __future__ import annotations

from pathlib import Path

from src.expansion.x4_dhcp_pool_misconfiguration import X4DhcpPoolMisconfigurationError, load_dhcp_pool_misconfiguration_scenario
from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, dhcp_lease_probe
from src.fault_injection.phase6_common import Phase6Executor, execute_checked, load_json_object, utc_now, write_json_atomic


def _all(checks: dict[str, object]) -> bool:
    return all(isinstance(value, dict) and value.get("passed") is True for value in checks.values())


def _identity(record: dict[str, object], binding) -> bool:
    return all(record.get(key) == value for key, value in binding.recovery_identity.items())


def _lease_state(binding, executor: Phase6Executor) -> tuple[dict[str, object], bool]:
    lease = dhcp_lease_probe(binding, executor); text = str(lease["stdout"]) + str(lease["stderr"])
    return lease, lease["return_code"] == 0 and binding.expected_scope_prefix in text and "bound to" in text


def _checks(binding, executor: Phase6Executor, *, expected_pool_line: str, expect_lease: bool) -> dict[str, object]:
    endpoint = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "x4-dhcp-service status; ss -lun"])
    configuration = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "cat /etc/x4-dhcp/dnsmasq.conf"])
    lease, lease_ok = _lease_state(binding, executor)
    endpoint_ok = endpoint["return_code"] == 0 and (":67" in str(endpoint["stdout"]) or " 67 " in str(endpoint["stdout"]))
    return {"dhcp_endpoint_protocol_responsive": {"passed": endpoint_ok, "command_result": endpoint, "not_icmp": True}, "dhcp_pool_configuration_direct": {"passed": configuration["return_code"] == 0 and expected_pool_line in str(configuration["stdout"]), "command_result": configuration, "expected_pool_line": expected_pool_line}, "fresh_dhcp_lease_exchange": {"passed": lease_ok == expect_lease, "command_result": lease, "cached_lease_prevented": True}}


def _backup_and_mutate_command(binding) -> list[str]:
    return ["sh", "-eu", "-c", "cp /etc/x4-dhcp/dnsmasq.conf /tmp/x4-r2-dnsmasq.conf.backup; if [ -f /tmp/x4-dhcp.leases ]; then cp /tmp/x4-dhcp.leases /tmp/x4-r2-dhcp.leases.backup; touch /tmp/x4-r2-dhcp.leases.existed; else rm -f /tmp/x4-r2-dhcp.leases.existed; fi; sed -i 's|" + binding.expected_pool_line + "|" + binding.controlled_empty_pool_line + "|' /etc/x4-dhcp/dnsmasq.conf; : > /tmp/x4-dhcp.leases; x4-dhcp-service stop; x4-dhcp-service start"]


def _restore_command() -> list[str]:
    return ["sh", "-eu", "-c", "test -f /tmp/x4-r2-dnsmasq.conf.backup; cp /tmp/x4-r2-dnsmasq.conf.backup /etc/x4-dhcp/dnsmasq.conf; if [ -f /tmp/x4-r2-dhcp.leases.existed ]; then test -f /tmp/x4-r2-dhcp.leases.backup; cp /tmp/x4-r2-dhcp.leases.backup /tmp/x4-dhcp.leases; else rm -f /tmp/x4-dhcp.leases; fi; x4-dhcp-service stop; x4-dhcp-service start"]


def restore_dhcp_pool_misconfiguration(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_dhcp_pool_misconfiguration_scenario(scenario_path); output = Path(output_directory); record_path = output / "restoration_record.json"
    if record_path.is_file():
        existing = load_json_object(record_path)
        if _identity(existing, binding) and existing.get("status") == "RESTORATION_CONFIRMED": return existing
    intent_path = output / "recovery_intent.json"
    if not intent_path.is_file() or not _identity(load_json_object(intent_path), binding):
        raise X4DhcpPoolMisconfigurationError("X4-R2 restoration requires matching durable recovery intent.")
    command = execute_checked(executor, binding.destination_container, _restore_command())
    checks = _checks(binding, executor, expected_pool_line=binding.expected_pool_line, expect_lease=True) if command["return_code"] == 0 else {}
    confirmed = command["return_code"] == 0 and _all(checks)
    record = {"schema_version": 1, **binding.recovery_identity, "completed_at_utc": utc_now(), "restoration_command": command, "postconditions": checks, "status": "RESTORATION_CONFIRMED" if confirmed else "RESTORATION_FAILED"}
    write_json_atomic(record_path, record)
    if not confirmed: raise X4DhcpPoolMisconfigurationError("X4-R2 exact DHCP pool restoration and fresh valid lease were not confirmed.")
    return record


def inject_dhcp_pool_misconfiguration(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_dhcp_pool_misconfiguration_scenario(scenario_path); output = Path(output_directory)
    if any((output / name).exists() for name in ("preconditions.json", "recovery_intent.json", "injection_record.json", "restoration_record.json")):
        raise X4DhcpPoolMisconfigurationError("X4-R2 mutation output already exists.")
    output.mkdir(parents=True, exist_ok=True)
    preconditions = _checks(binding, executor, expected_pool_line=binding.expected_pool_line, expect_lease=True)
    write_json_atomic(output / "preconditions.json", preconditions)
    if not _all(preconditions): raise X4DhcpPoolMisconfigurationError("X4-R2 preflight/healthy DHCP baseline failed; no mutation attempted.")
    intent = {"schema_version": 1, **binding.recovery_identity, "status": "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED", "created_at_utc": utc_now(), "backup_paths": {"configuration": "/tmp/x4-r2-dnsmasq.conf.backup", "lease_database": "/tmp/x4-r2-dhcp.leases.backup", "lease_database_existed_marker": "/tmp/x4-r2-dhcp.leases.existed"}}
    write_json_atomic(output / "recovery_intent.json", intent)
    try:
        command = execute_checked(executor, binding.destination_container, _backup_and_mutate_command(binding))
        checks = _checks(binding, executor, expected_pool_line=binding.controlled_empty_pool_line, expect_lease=False) if command["return_code"] == 0 else {}
        confirmed = command["return_code"] == 0 and _all(checks)
        record = {"schema_version": 1, **binding.recovery_identity, "completed_at_utc": utc_now(), "mutation_command": command, "postconditions": checks, "status": "FAULT_CONFIRMED" if confirmed else "FAULT_NOT_CONFIRMED"}
        write_json_atomic(output / "injection_record.json", record)
        if not confirmed: raise X4DhcpPoolMisconfigurationError("X4-R2 DHCP pool-misconfiguration fault was not confirmed.")
        return record
    except BaseException:
        restore_dhcp_pool_misconfiguration(scenario_path, output, executor=executor)
        raise
