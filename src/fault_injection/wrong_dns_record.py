from __future__ import annotations

from pathlib import Path

from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, dhcp_lease_probe
from src.expansion.x4_wrong_dns_record import X4WrongDnsRecordError, load_wrong_dns_record_scenario
from src.fault_injection.phase6_common import Phase6Executor, execute_checked, load_json_object, utc_now, write_json_atomic


DNS_RESTART = "if [ -s /run/x4-dns.pid ]; then kill \"$(cat /run/x4-dns.pid)\" 2>/dev/null || true; fi; rm -f /run/x4-dns.pid; dnsmasq --conf-file=/etc/x4-dns/dnsmasq.conf --pid-file=/run/x4-dns.pid; sleep 1; test -s /run/x4-dns.pid && kill -0 \"$(cat /run/x4-dns.pid)\""


def _all(checks: dict[str, object]) -> bool:
    return all(isinstance(value, dict) and value.get("passed") is True for value in checks.values())


def _identity(record: dict[str, object], binding) -> bool:
    return all(record.get(key) == value for key, value in binding.recovery_identity.items())


def _query(binding, executor: Phase6Executor) -> tuple[dict[str, object], str | None]:
    result = execute_checked(executor, binding.source_container, ["sh", "-eu", "-c", "dig +norecurse +time=2 +tries=1 @" + binding.dns_server_address + " " + binding.expected_dns_name + " A +short"])
    if result["return_code"] != 0: return result, None
    answers = str(result["stdout"]).split()
    return result, answers[0] if answers else None


def _dhcp_healthy(binding, executor: Phase6Executor) -> tuple[dict[str, object], bool]:
    result = dhcp_lease_probe(binding, executor); text = str(result["stdout"]) + str(result["stderr"])
    return result, result["return_code"] == 0 and "bound to" in text and binding.expected_scope_prefix in text


def _checks(binding, executor: Phase6Executor, *, expected_record_line: str, expected_answer: str) -> dict[str, object]:
    configuration = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "cat /etc/x4-dns/dnsmasq.conf; dnsmasq --test --conf-file=/etc/x4-dns/dnsmasq.conf"])
    process = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "test -s /run/x4-dns.pid && kill -0 \"$(cat /run/x4-dns.pid)\""])
    listener = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "ss -lun | grep -q ':53'"])
    reachable = execute_checked(executor, binding.source_container, ["ping", "-c", "1", "-W", "1", binding.dns_server_address])
    query, answer = _query(binding, executor); dhcp, dhcp_ok = _dhcp_healthy(binding, executor)
    app_process = execute_checked(executor, binding.app_container, ["sh", "-c", "pgrep -f 'http.server 8080'"])
    app_port = execute_checked(executor, binding.observer_container, ["nc", "-z", "-w", "2", "10.40.0.4", "8080"])
    policy = execute_checked(executor, binding.observer_container, ["iptables", "-S"])
    return {"direct_dns_configuration": {"passed": configuration["return_code"] == 0 and expected_record_line in str(configuration["stdout"]), "command_result": configuration, "expected_record_line": expected_record_line}, "dns_process_state": {"passed": process["return_code"] == 0, "command_result": process}, "dns_udp_53_listener": {"passed": listener["return_code"] == 0, "command_result": listener}, "dns_host_network_reachability": {"passed": reachable["return_code"] == 0, "command_result": reachable, "not_dns_answer_classifier": True}, "fresh_direct_authoritative_dns_answer": {"passed": answer == expected_answer, "command_result": query, "direct_endpoint_no_client_cache": True}, "dhcp_control_fresh_lease": {"passed": dhcp_ok, "command_result": dhcp}, "application_process_control": {"passed": app_process["return_code"] == 0, "command_result": app_process}, "application_port_control": {"passed": app_port["return_code"] == 0, "command_result": app_port}, "service_policy_control": {"passed": policy["return_code"] == 0 and "X4-R1-SERVICE-BLOCK" not in str(policy["stdout"]), "command_result": policy}}


def restore_wrong_dns_record(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_wrong_dns_record_scenario(scenario_path); output = Path(output_directory); record_path = output / "restoration_record.json"
    if record_path.is_file():
        existing = load_json_object(record_path)
        if _identity(existing, binding) and existing.get("status") == "RESTORATION_CONFIRMED": return existing
    intent_path = output / "recovery_intent.json"
    if not intent_path.is_file() or not _identity(load_json_object(intent_path), binding): raise X4WrongDnsRecordError("X4-R4 restoration requires matching durable recovery intent.")
    command = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "test -f /tmp/x4-r4-dnsmasq.conf.backup; cp /tmp/x4-r4-dnsmasq.conf.backup /etc/x4-dns/dnsmasq.conf; dnsmasq --test --conf-file=/etc/x4-dns/dnsmasq.conf; " + DNS_RESTART])
    checks = _checks(binding, executor, expected_record_line=binding.expected_record_line, expected_answer=binding.expected_dns_answer) if command["return_code"] == 0 else {}; confirmed = command["return_code"] == 0 and _all(checks)
    record = {"schema_version": 1, **binding.recovery_identity, "completed_at_utc": utc_now(), "restoration_command": command, "postconditions": checks, "status": "RESTORATION_CONFIRMED" if confirmed else "RESTORATION_FAILED"}
    write_json_atomic(record_path, record)
    if not confirmed: raise X4WrongDnsRecordError("X4-R4 exact DNS record/service restoration was not confirmed.")
    return record


def inject_wrong_dns_record(scenario_path: Path, output_directory: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR) -> dict[str, object]:
    binding = load_wrong_dns_record_scenario(scenario_path); output = Path(output_directory)
    if any((output / name).exists() for name in ("preconditions.json", "recovery_intent.json", "injection_record.json", "restoration_record.json")): raise X4WrongDnsRecordError("X4-R4 mutation output already exists.")
    output.mkdir(parents=True, exist_ok=True); preconditions = _checks(binding, executor, expected_record_line=binding.expected_record_line, expected_answer=binding.expected_dns_answer); write_json_atomic(output / "preconditions.json", preconditions)
    if not _all(preconditions): raise X4WrongDnsRecordError("X4-R4 DNS/image/DHCP/application preflight failed; no mutation attempted.")
    intent = {"schema_version": 1, **binding.recovery_identity, "status": "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED", "created_at_utc": utc_now(), "backup_path": "/tmp/x4-r4-dnsmasq.conf.backup", "cache_policy": "restart_dnsmasq_then_query_direct_endpoint_with_dig_norecurse"}
    write_json_atomic(output / "recovery_intent.json", intent)
    try:
        command = execute_checked(executor, binding.destination_container, ["sh", "-eu", "-c", "cp /etc/x4-dns/dnsmasq.conf /tmp/x4-r4-dnsmasq.conf.backup; sed -i 's|" + binding.expected_record_line + "|" + binding.controlled_wrong_record_line + "|' /etc/x4-dns/dnsmasq.conf; dnsmasq --test --conf-file=/etc/x4-dns/dnsmasq.conf; " + DNS_RESTART])
        checks = _checks(binding, executor, expected_record_line=binding.controlled_wrong_record_line, expected_answer=binding.controlled_wrong_dns_answer) if command["return_code"] == 0 else {}; confirmed = command["return_code"] == 0 and _all(checks)
        record = {"schema_version": 1, **binding.recovery_identity, "completed_at_utc": utc_now(), "mutation_command": command, "postconditions": checks, "status": "FAULT_CONFIRMED" if confirmed else "FAULT_NOT_CONFIRMED"}
        write_json_atomic(output / "injection_record.json", record)
        if not confirmed: raise X4WrongDnsRecordError("X4-R4 controlled wrong DNS record was not confirmed.")
        return record
    except BaseException:
        restore_wrong_dns_record(scenario_path, output, executor=executor)
        raise
