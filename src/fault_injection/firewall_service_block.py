from __future__ import annotations

from pathlib import Path

from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, dhcp_lease_probe
from src.expansion.x4_firewall_service_block import FirewallServiceBlockError, load_firewall_service_block_scenario
from src.fault_injection.phase6_common import Phase6Executor, execute_checked, load_json_object, utc_now, write_json_atomic


def _all(checks: dict[str, object]) -> bool:
    return all(isinstance(value, dict) and value.get("passed") is True for value in checks.values())


def _identity(record: dict[str, object], binding) -> bool:
    return all(record.get(key) == value for key, value in binding.recovery_identity.items())


def _dhcp_healthy(binding, executor: Phase6Executor) -> tuple[dict[str, object], bool]:
    result = dhcp_lease_probe(binding, executor); text = str(result["stdout"]) + str(result["stderr"])
    return result, result["return_code"] == 0 and "bound to" in text and binding.expected_scope_prefix in text


def _dns_healthy(binding, executor: Phase6Executor) -> tuple[dict[str, object], bool]:
    result = execute_checked(executor, binding.source_container, ["sh", "-eu", "-c", "dig +norecurse +time=2 +tries=1 @" + binding.dns_server_address + " " + binding.expected_dns_name + " A +short"])
    return result, result["return_code"] == 0 and binding.expected_dns_answer in str(result["stdout"]).split()


def _rule(binding) -> list[str]:
    return ["-p", binding.service_protocol, "--dport", str(binding.service_port), "-m", "comment", "--comment", binding.firewall_comment, "-j", "DROP"]


def _checks(binding, executor: Phase6Executor, *, expected_blocked: bool) -> dict[str, object]:
    tool = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "command -v iptables; iptables -S INPUT"])
    process = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "pgrep -f http.server"])
    generic = execute_checked(executor, binding.source_container, ["ping", "-c", "1", "-W", "1", binding.app_server_address])
    service = execute_checked(executor, binding.source_container, ["nc", "-z", "-w", "2", binding.app_server_address, str(binding.service_port)])
    dhcp, dhcp_ok = _dhcp_healthy(binding, executor); dns, dns_ok = _dns_healthy(binding, executor)
    policy = execute_checked(executor, binding.destination_container, ["iptables", "-S", binding.firewall_chain])
    rule_present = binding.firewall_comment in str(policy["stdout"])
    return {"firewall_tool_and_direct_policy": {"passed": tool["return_code"] == 0, "command_result": tool}, "application_process": {"passed": process["return_code"] == 0, "command_result": process}, "generic_application_host_connectivity": {"passed": generic["return_code"] == 0, "command_result": generic, "effectiveness_only_not_classifier": True}, "client_application_service_probe": {"passed": (service["return_code"] != 0) == expected_blocked, "command_result": service, "expected_blocked": expected_blocked}, "dhcp_control_fresh_lease": {"passed": dhcp_ok, "command_result": dhcp}, "dns_control_direct_query": {"passed": dns_ok, "command_result": dns}, "exact_injected_policy_rule": {"passed": rule_present == expected_blocked, "command_result": policy, "expected_blocked": expected_blocked}}


def restore_firewall_service_block(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_firewall_service_block_scenario(scenario_path); output = Path(output_directory); record_path = output / "restoration_record.json"
    if record_path.is_file():
        existing = load_json_object(record_path)
        if _identity(existing, binding) and existing.get("status") == "RESTORATION_CONFIRMED": return existing
    intent_path = output / "recovery_intent.json"
    if not intent_path.is_file() or not _identity(load_json_object(intent_path), binding): raise FirewallServiceBlockError("X4-R5 restoration requires matching durable recovery intent.")
    rule = " ".join(_rule(binding)); command = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "while iptables -C " + binding.firewall_chain + " " + rule + "; do iptables -D " + binding.firewall_chain + " " + rule + "; done; ! iptables -S " + binding.firewall_chain + " | grep -q " + binding.firewall_comment])
    checks = _checks(binding, executor, expected_blocked=False) if command["return_code"] == 0 else {}; confirmed = command["return_code"] == 0 and _all(checks)
    record = {"schema_version": 1, **binding.recovery_identity, "completed_at_utc": utc_now(), "restoration_command": command, "postconditions": checks, "status": "RESTORATION_CONFIRMED" if confirmed else "RESTORATION_FAILED"}
    write_json_atomic(record_path, record)
    if not confirmed: raise FirewallServiceBlockError("X4-R5 exact firewall-rule restoration was not confirmed.")
    return record


def inject_firewall_service_block(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_firewall_service_block_scenario(scenario_path); output = Path(output_directory)
    if any((output / name).exists() for name in ("preconditions.json", "recovery_intent.json", "injection_record.json", "restoration_record.json")): raise FirewallServiceBlockError("X4-R5 mutation output already exists.")
    output.mkdir(parents=True, exist_ok=True); preconditions = _checks(binding, executor, expected_blocked=False); write_json_atomic(output / "preconditions.json", preconditions)
    if not _all(preconditions): raise FirewallServiceBlockError("X4-R5 firewall/DHCP/DNS/application preflight failed; no mutation attempted.")
    intent = {"schema_version": 1, **binding.recovery_identity, "status": "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED", "created_at_utc": utc_now(), "mutation_scope": "exact INPUT tcp/8080 DROP rule with unique comment only", "unrelated_firewall_state": "never_flushed_or_replaced"}
    write_json_atomic(output / "recovery_intent.json", intent)
    try:
        rule = " ".join(_rule(binding)); command = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "! iptables -C " + binding.firewall_chain + " " + rule + "; iptables -I " + binding.firewall_chain + " 1 " + rule + "; iptables -C " + binding.firewall_chain + " " + rule])
        checks = _checks(binding, executor, expected_blocked=True) if command["return_code"] == 0 else {}; confirmed = command["return_code"] == 0 and _all(checks)
        record = {"schema_version": 1, **binding.recovery_identity, "completed_at_utc": utc_now(), "mutation_command": command, "postconditions": checks, "status": "FAULT_CONFIRMED" if confirmed else "FAULT_NOT_CONFIRMED"}
        write_json_atomic(output / "injection_record.json", record)
        if not confirmed: raise FirewallServiceBlockError("X4-R5 controlled firewall service block was not confirmed.")
        return record
    except BaseException:
        restore_firewall_service_block(scenario_path, output, executor=executor)
        raise
