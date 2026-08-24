from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2, validate_topology_context_v1
from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, dhcp_lease_probe
from src.expansion.x4_dns_service_down import DnsServiceDownScenario, X4DnsServiceDownError, load_dns_service_down_scenario
from src.fault_injection.phase6_common import Phase6Executor, execute_checked, sha256_file, utc_now, write_json_atomic


ROOT = Path(__file__).resolve().parents[2]
RAW = Path("raw/v4/service_state_collector_v3")
EVIDENCE = Path("parsed/evidence_v4.json")
VECTOR = Path("parsed/feature_vector_v2.json")
FEATURE_IDS = ("dhcp_server_reachable", "dhcp_lease_obtained", "dhcp_lease_matches_expected_scope", "dns_server_reachable", "dns_query_succeeds", "dns_answer_matches_expected", "service_process_running", "service_port_reachable", "service_flow_blocked_by_policy")


def _raw(root: Path, name: str, value: object) -> tuple[str, str]:
    relative = str(RAW / (name + ".json")); path = root / relative
    write_json_atomic(path, value)
    return relative, sha256_file(path)


def _result(executor: Phase6Executor, container: str, command: list[str]) -> dict[str, object]:
    return execute_checked(executor, container, command)


def _obs(value: bool | None, availability: str, raw: tuple[str, str], collector_id: str = "service_state_collector_v3") -> dict[str, object]:
    return {"value": value, "value_type": "boolean", "availability": availability, "collector_id": collector_id, "raw_artifact": raw[0], "raw_artifact_sha256": raw[1]}


def _binary(result: Mapping[str, object]) -> tuple[bool | None, str]:
    code = result.get("return_code")
    if code == 0: return True, "observed"
    if code in (1, 2, 9): return False, "observed"
    return None, "collection_unavailable"


def _dhcp_state(result: Mapping[str, object], expected_prefix: str) -> tuple[bool | None, bool | None, str]:
    code = result.get("return_code"); text = str(result.get("stdout", "")) + str(result.get("stderr", ""))
    if code == 0:
        lease = "bound to" in text
        return lease, lease and expected_prefix in text, "observed"
    if code == 2 or (code == 1 and "No DHCPOFFERS received" in text): return False, False, "observed"
    return None, None, "collection_unavailable"


def _dns_query_state(result: Mapping[str, object], expected_answer: str) -> tuple[bool | None, bool | None, str]:
    code = result.get("return_code"); text = str(result.get("stdout", "")) + str(result.get("stderr", ""))
    if code == 0:
        answer = expected_answer in str(result.get("stdout", "")).split()
        return answer, answer, "observed"
    if code in (1, 9): return False, False, "observed"
    return None, None, "collection_unavailable"


def collect_dns_service_down_evidence_v4(output_directory: Path, scenario_path: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR, repository_root: Path = ROOT) -> dict[str, object]:
    output = Path(output_directory)
    if (output / EVIDENCE).exists() or (output / RAW).exists(): raise X4DnsServiceDownError("X4-R3 Evidence v4 output already exists.")
    binding: DnsServiceDownScenario = load_dns_service_down_scenario(scenario_path); started = utc_now()
    dhcp = dhcp_lease_probe(binding, executor); dhcp_raw = _raw(output, "dhcp_fresh_lease_exchange", {"schema_version": 1, "probe_id": "dhcp_control_fresh_lease_exchange", "command_result": dhcp})
    dns_ping = _result(executor, binding.source_container, ["ping", "-c", "1", "-W", "1", binding.dns_server_address]); dns_ping_raw = _raw(output, "dns_network_reachability", {"schema_version": 1, "probe_id": "dns_host_network_reachability_not_dns_endpoint", "command_result": dns_ping})
    dns_query = _result(executor, binding.source_container, ["sh", "-eu", "-c", "dig +time=2 +tries=1 @" + binding.dns_server_address + " " + binding.expected_dns_name + " A +short"]); dns_raw = _raw(output, "dns_query_response", {"schema_version": 1, "probe_id": "real_dns_query_and_response", "command_result": dns_query})
    process = _result(executor, binding.destination_container, ["sh", "-eu", "-c", "test -s /run/x4-dns.pid && kill -0 \"$(cat /run/x4-dns.pid)\""]); process_raw = _raw(output, "dns_process_state", {"schema_version": 1, "command_result": process})
    port = _result(executor, binding.destination_container, ["sh", "-eu", "-c", "ss -lun | grep -q ':53'"]); port_raw = _raw(output, "dns_udp_53_listener", {"schema_version": 1, "command_result": port})
    app_process = _result(executor, binding.app_container, ["sh", "-c", "pgrep -f 'http.server 8080'"]); app_process_raw = _raw(output, "application_process", {"schema_version": 1, "command_result": app_process})
    app_port = _result(executor, binding.observer_container, ["nc", "-z", "-w", "2", "10.40.0.4", "8080"]); app_port_raw = _raw(output, "application_port", {"schema_version": 1, "command_result": app_port})
    policy = _result(executor, binding.observer_container, ["iptables", "-S"]); policy_raw = _raw(output, "service_policy", {"schema_version": 1, "command_result": policy})
    dhcp_lease, dhcp_scope, dhcp_availability = _dhcp_state(dhcp, binding.expected_scope_prefix)
    ping_value, ping_availability = _binary(dns_ping); query_value, answer_value, query_availability = _dns_query_state(dns_query, binding.expected_dns_answer)
    process_value, process_availability = _binary(process); port_value, port_availability = _binary(port)
    app_process_value, app_process_availability = _binary(app_process); app_port_value, app_port_availability = _binary(app_port); policy_value, policy_availability = _binary(policy)
    observations = {
        "dhcp_server_reachable": _obs(dhcp_lease, dhcp_availability, dhcp_raw),
        "dhcp_lease_obtained": _obs(dhcp_lease, dhcp_availability, dhcp_raw),
        "dhcp_lease_matches_expected_scope": _obs(dhcp_scope, dhcp_availability, dhcp_raw),
        "dns_server_reachable": _obs(ping_value, ping_availability, dns_ping_raw),
        "dns_query_succeeds": _obs(query_value, query_availability, dns_raw),
        "dns_answer_matches_expected": _obs(answer_value, query_availability, dns_raw),
        "service_process_running": _obs(process_value, process_availability, process_raw),
        "service_port_reachable": _obs(port_value, port_availability, port_raw),
        "service_flow_blocked_by_policy": _obs(None if policy_availability != "observed" else "X4-R1-SERVICE-BLOCK" in str(policy["stdout"]), policy_availability, policy_raw, "service_policy_state_collector"),
    }
    service_availability = (dhcp_availability, ping_availability, query_availability, process_availability, port_availability, app_process_availability, app_port_availability)
    raw_artifacts = [{"path": p, "sha256": h} for p, h in (dhcp_raw, dns_ping_raw, dns_raw, process_raw, port_raw, app_process_raw, app_port_raw)]
    completed = utc_now(); errors = [] if all(value == "observed" for value in service_availability) else ["A DNS/DHCP/service collection command was unavailable."]
    evidence = {"schema_version": 4, "evidence_id": binding.scenario_id.lower() + ":evidence:v4", "topology_context_id": binding.topology_context_id, "collected_at_utc": completed, "observation_path": {"direction": "client_to_dns_server", "source_node": binding.source_node, "destination_node": binding.destination_node, "observer_nodes": ["observer"]}, "collector_runs": [{"schema_version": 1, "collector_id": "service_state_collector_v3", "collector_version": 3, "domain": "services", "status": "completed" if not errors else "partial", "started_at_utc": started, "completed_at_utc": completed, "feature_ids": list(FEATURE_IDS[:-1]), "raw_artifacts": raw_artifacts, "errors": errors}, {"schema_version": 1, "collector_id": "service_policy_state_collector", "collector_version": 1, "domain": "security", "status": "completed" if policy_availability == "observed" else "partial", "started_at_utc": started, "completed_at_utc": completed, "feature_ids": ["service_flow_blocked_by_policy"], "raw_artifacts": [{"path": policy_raw[0], "sha256": policy_raw[1]}], "errors": [] if policy_availability == "observed" else ["Policy collection unavailable."]}], "observations": observations, "compatibility": {"origin": "native_v4", "source_schema_version": None, "source_artifact_sha256": None}}
    context = json.loads((repository_root / binding.scenario["topology"]["context_file"]).read_text(encoding="utf-8")); catalog = json.loads((repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text(encoding="utf-8"))
    validate_topology_context_v1(context, repository_root=repository_root)
    if context["context_id"] != binding.topology_context_id or context["observation_roles"] != {"source": "client", "destination": "dns_server", "observers": ["observer"]}: raise X4DnsServiceDownError("X4-R3 must bind the distinct client-to-DNS-server context.")
    validate_evidence_v4(evidence, catalog, repository_root=repository_root); write_json_atomic(output / EVIDENCE, evidence)
    return evidence


def build_service_feature_vector_v2_r3(output_directory: Path, evidence: Mapping[str, object], *, repository_root: Path = ROOT) -> dict[str, object]:
    output = Path(output_directory); evidence_path = output / EVIDENCE
    if not evidence_path.is_file() or (output / VECTOR).exists(): raise X4DnsServiceDownError("X4-R3 Evidence v4 persistence/vector output boundary failed.")
    catalog_path = repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"; catalog = json.loads(catalog_path.read_text(encoding="utf-8")); observations = evidence.get("observations")
    if not isinstance(observations, Mapping): raise X4DnsServiceDownError("X4-R3 evidence observations missing.")
    vector = {"schema_version": 2, "vector_id": str(evidence["evidence_id"]) + ":vector:v2", "catalog_id": catalog["catalog_id"], "evidence_id": evidence["evidence_id"], "values": {name: {"value": row["value"], "availability": row["availability"]} for name, row in observations.items() if isinstance(row, Mapping)}, "mask_id": None, "provenance": {"evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(), "feature_catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest()}}
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root); write_json_atomic(output / VECTOR, vector)
    return vector
