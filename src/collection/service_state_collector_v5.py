from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2, validate_topology_context_v1
from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, dhcp_lease_probe
from src.expansion.x4_firewall_service_block import FirewallServiceBlockError, load_firewall_service_block_scenario
from src.fault_injection.phase6_common import Phase6Executor, execute_checked, sha256_file, utc_now, write_json_atomic

ROOT = Path(__file__).resolve().parents[2]
RAW = Path("raw/v4/service_state_collector_v5")
EVIDENCE = Path("parsed/evidence_v4.json")
VECTOR = Path("parsed/feature_vector_v2.json")
FEATURE_IDS = ("dhcp_server_reachable", "dhcp_lease_obtained", "dhcp_lease_matches_expected_scope", "dns_server_reachable", "dns_query_succeeds", "dns_answer_matches_expected", "service_process_running", "service_port_reachable", "service_flow_blocked_by_policy")

def _raw(root: Path, name: str, value: object) -> tuple[str, str]:
    relative = str(RAW / (name + ".json")); path = root / relative; write_json_atomic(path, value); return relative, sha256_file(path)

def _run(executor: Phase6Executor, container: str, command: list[str]) -> dict[str, object]: return execute_checked(executor, container, command)
def _obs(value: bool | None, availability: str, raw: tuple[str, str], collector: str = "service_state_collector_v5") -> dict[str, object]: return {"value": value, "value_type": "boolean", "availability": availability, "collector_id": collector, "raw_artifact": raw[0], "raw_artifact_sha256": raw[1]}
def _binary(result: Mapping[str, object]) -> tuple[bool | None, str]:
    code = result.get("return_code")
    if code == 0: return True, "observed"
    if code in (1, 2, 9): return False, "observed"
    return None, "collection_unavailable"
def _dhcp(result: Mapping[str, object], prefix: str) -> tuple[bool | None, bool | None, str]:
    text = str(result.get("stdout", "")) + str(result.get("stderr", "")); code = result.get("return_code")
    if code == 0:
        lease = "bound to" in text; return lease, lease and prefix in text, "observed"
    if code == 2 or (code == 1 and "No DHCPOFFERS received" in text): return False, False, "observed"
    return None, None, "collection_unavailable"
def _dns(result: Mapping[str, object], expected: str) -> tuple[bool | None, bool | None, str]:
    code = result.get("return_code"); answers = str(result.get("stdout", "")).split()
    if code == 0: return bool(answers), expected in answers, "observed"
    if code in (1, 9): return False, False, "observed"
    return None, None, "collection_unavailable"

def collect_firewall_service_block_evidence_v4(output_directory: Path, scenario_path: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR, repository_root: Path = ROOT) -> dict[str, object]:
    output = Path(output_directory)
    if (output / EVIDENCE).exists() or (output / RAW).exists(): raise FirewallServiceBlockError("X4-R5 Evidence v4 output already exists.")
    binding = load_firewall_service_block_scenario(scenario_path); started = utc_now()
    dhcp = dhcp_lease_probe(binding, executor); dhcp_raw = _raw(output, "dhcp_fresh_lease_exchange", {"probe_id": "dhcp_control_fresh_lease_exchange", "command_result": dhcp})
    dns_host = _run(executor, binding.source_container, ["ping", "-c", "1", "-W", "1", binding.dns_server_address]); dns_host_raw = _raw(output, "dns_network_reachability", {"probe_id": "dns_host_network_control", "command_result": dns_host})
    dns = _run(executor, binding.source_container, ["sh", "-eu", "-c", "dig +norecurse +time=2 +tries=1 @" + binding.dns_server_address + " " + binding.expected_dns_name + " A +short"]); dns_raw = _raw(output, "dns_direct_query_response", {"probe_id": "direct_authoritative_dns_control", "command_result": dns})
    process = _run(executor, binding.destination_container, ["sh", "-eu", "-c", "pgrep -f http.server"]); process_raw = _raw(output, "application_process", {"command_result": process})
    generic = _run(executor, binding.source_container, ["ping", "-c", "1", "-W", "1", binding.app_server_address]); generic_raw = _raw(output, "application_host_connectivity", {"probe_id": "generic_connectivity_effectiveness_only", "command_result": generic})
    service = _run(executor, binding.source_container, ["nc", "-z", "-w", "2", binding.app_server_address, str(binding.service_port)]); service_raw = _raw(output, "client_service_probe", {"probe_id": "real_client_tcp_service_probe", "command_result": service})
    policy = _run(executor, binding.destination_container, ["iptables", "-S", binding.firewall_chain]); policy_raw = _raw(output, "firewall_policy", {"probe_id": "direct_exact_firewall_policy_inspection", "command_result": policy, "exact_comment": binding.firewall_comment})
    lease, scope, dhcp_a = _dhcp(dhcp, binding.expected_scope_prefix); dns_host_v, dns_host_a = _binary(dns_host); dns_v, dns_answer, dns_a = _dns(dns, binding.expected_dns_answer); process_v, process_a = _binary(process); service_v, service_a = _binary(service); policy_v = None if policy.get("return_code") != 0 else binding.firewall_comment in str(policy.get("stdout", "")); policy_a = "observed" if policy.get("return_code") == 0 else "collection_unavailable"
    observations = {"dhcp_server_reachable": _obs(lease, dhcp_a, dhcp_raw), "dhcp_lease_obtained": _obs(lease, dhcp_a, dhcp_raw), "dhcp_lease_matches_expected_scope": _obs(scope, dhcp_a, dhcp_raw), "dns_server_reachable": _obs(dns_host_v, dns_host_a, dns_host_raw), "dns_query_succeeds": _obs(dns_v, dns_a, dns_raw), "dns_answer_matches_expected": _obs(dns_answer, dns_a, dns_raw), "service_process_running": _obs(process_v, process_a, process_raw), "service_port_reachable": _obs(service_v, service_a, service_raw), "service_flow_blocked_by_policy": _obs(policy_v, policy_a, policy_raw, "service_policy_state_collector")}
    raws = [dhcp_raw, dns_host_raw, dns_raw, process_raw, generic_raw, service_raw]; availabilities = (dhcp_a, dns_host_a, dns_a, process_a, service_a)
    evidence = {"schema_version": 4, "evidence_id": binding.scenario_id.lower() + ":evidence:v4", "topology_context_id": binding.topology_context_id, "collected_at_utc": utc_now(), "observation_path": {"direction": "client_to_app_server", "source_node": binding.source_node, "destination_node": binding.destination_node, "observer_nodes": ["observer"]}, "collector_runs": [{"schema_version": 1, "collector_id": "service_state_collector_v5", "collector_version": 5, "domain": "services", "status": "completed" if all(a == "observed" for a in availabilities) else "partial", "started_at_utc": started, "completed_at_utc": utc_now(), "feature_ids": list(FEATURE_IDS[:-1]), "raw_artifacts": [{"path": p, "sha256": h} for p, h in raws], "errors": [] if all(a == "observed" for a in availabilities) else ["A service collection command was unavailable."]}, {"schema_version": 1, "collector_id": "service_policy_state_collector", "collector_version": 1, "domain": "security", "status": "completed" if policy_a == "observed" else "partial", "started_at_utc": started, "completed_at_utc": utc_now(), "feature_ids": ["service_flow_blocked_by_policy"], "raw_artifacts": [{"path": policy_raw[0], "sha256": policy_raw[1]}], "errors": [] if policy_a == "observed" else ["Policy collection unavailable."]}], "observations": observations, "compatibility": {"origin": "native_v4", "source_schema_version": None, "source_artifact_sha256": None}}
    context = json.loads((repository_root / binding.scenario["topology"]["context_file"]).read_text(encoding="utf-8")); catalog = json.loads((repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text(encoding="utf-8")); validate_topology_context_v1(context, repository_root=repository_root)
    if context["context_id"] != binding.topology_context_id or context["observation_roles"] != {"source": "client", "destination": "app_server", "observers": ["observer"]}: raise FirewallServiceBlockError("X4-R5 must reuse the accepted client-to-application-server context.")
    validate_evidence_v4(evidence, catalog, repository_root=repository_root); write_json_atomic(output / EVIDENCE, evidence); return evidence

def build_service_feature_vector_v2_r5(output_directory: Path, evidence: Mapping[str, object], *, repository_root: Path = ROOT) -> dict[str, object]:
    output = Path(output_directory); evidence_path = output / EVIDENCE
    if not evidence_path.is_file() or (output / VECTOR).exists(): raise FirewallServiceBlockError("X4-R5 Evidence v4 persistence/vector output boundary failed.")
    catalog_path = repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"; catalog = json.loads(catalog_path.read_text(encoding="utf-8")); observations = evidence.get("observations")
    if not isinstance(observations, Mapping): raise FirewallServiceBlockError("X4-R5 evidence observations missing.")
    vector = {"schema_version": 2, "vector_id": str(evidence["evidence_id"]) + ":vector:v2", "catalog_id": catalog["catalog_id"], "evidence_id": evidence["evidence_id"], "values": {name: {"value": row["value"], "availability": row["availability"]} for name, row in observations.items() if isinstance(row, Mapping)}, "mask_id": None, "provenance": {"evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(), "feature_catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest()}}
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root); write_json_atomic(output / VECTOR, vector); return vector
