from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Mapping

from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2, validate_topology_context_v1
from src.expansion.x4_dhcp_pool_misconfiguration import DhcpPoolMisconfigurationScenario, X4DhcpPoolMisconfigurationError, load_dhcp_pool_misconfiguration_scenario
from src.expansion.x4_dhcp_server_unavailable import DEFAULT_EXECUTOR, dhcp_lease_probe
from src.fault_injection.phase6_common import Phase6Executor, execute_checked, sha256_file, utc_now, write_json_atomic


ROOT = Path(__file__).resolve().parents[2]
RAW = Path("raw/v4/service_state_collector_v2")
EVIDENCE = Path("parsed/evidence_v4.json")
VECTOR = Path("parsed/feature_vector_v2.json")
FEATURE_IDS = ("dhcp_server_reachable", "dhcp_lease_obtained", "dhcp_lease_matches_expected_scope", "dns_server_reachable", "dns_query_succeeds", "dns_answer_matches_expected", "service_process_running", "service_port_reachable", "service_flow_blocked_by_policy")


def _raw(root: Path, name: str, value: object) -> tuple[str, str]:
    relative = str(RAW / (name + ".json")); path = root / relative
    write_json_atomic(path, value)
    return relative, sha256_file(path)


def _result(executor: Phase6Executor, container: str, command: list[str]) -> dict[str, object]:
    return execute_checked(executor, container, command)


def _obs(value: bool | None, availability: str, raw: tuple[str, str], collector_id: str = "service_state_collector_v2") -> dict[str, object]:
    return {"value": value, "value_type": "boolean", "availability": availability, "collector_id": collector_id, "raw_artifact": raw[0], "raw_artifact_sha256": raw[1]}


def _endpoint_state(result: Mapping[str, object]) -> tuple[bool | None, str]:
    if result.get("return_code") != 0:
        return None, "collection_unavailable"
    listener = str(result.get("stdout", "")) + str(result.get("stderr", ""))
    return (":67" in listener or " 67 " in listener), "observed"


def _lease_state(result: Mapping[str, object], expected_prefix: str) -> tuple[bool | None, bool | None, str]:
    code = result.get("return_code"); text = str(result.get("stdout", "")) + str(result.get("stderr", ""))
    if code == 0:
        match = re.search(r"bound to\s+([0-9]+(?:\.[0-9]+){3})", text, re.IGNORECASE)
        if not match:
            return None, None, "collection_unavailable"
        return True, match.group(1).startswith(expected_prefix), "observed"
    if code == 2 or (code == 1 and "No DHCPOFFERS received" in text):
        return False, False, "observed"
    return None, None, "collection_unavailable"


def collect_dhcp_pool_misconfiguration_evidence_v4(output_directory: Path, scenario_path: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR, repository_root: Path = ROOT) -> dict[str, object]:
    output = Path(output_directory)
    if (output / EVIDENCE).exists() or (output / RAW).exists():
        raise X4DhcpPoolMisconfigurationError("X4-R2 Evidence v4 output already exists.")
    binding: DhcpPoolMisconfigurationScenario = load_dhcp_pool_misconfiguration_scenario(scenario_path); started = utc_now()
    endpoint = _result(executor, binding.destination_container, ["sh", "-eu", "-c", "x4-dhcp-service status; ss -lun"])
    endpoint_raw = _raw(output, "dhcp_endpoint_protocol_state", {"schema_version": 1, "probe_id": "dhcp_service_endpoint_udp_67", "command_result": endpoint})
    configuration = _result(executor, binding.destination_container, ["sh", "-eu", "-c", "cat /etc/x4-dhcp/dnsmasq.conf"])
    configuration_raw = _raw(output, "dhcp_pool_configuration", {"schema_version": 1, "probe_id": "dhcp_pool_configuration_direct", "command_result": configuration, "expected_controlled_pool_line": binding.controlled_empty_pool_line})
    lease = dhcp_lease_probe(binding, executor)
    lease_raw = _raw(output, "dhcp_fresh_lease_exchange", {"schema_version": 1, "probe_id": "dhcp_fresh_lease_exchange", "command_result": lease})
    endpoint_value, endpoint_availability = _endpoint_state(endpoint)
    lease_value, scope_value, lease_availability = _lease_state(lease, binding.expected_scope_prefix)
    dns_ping = _result(executor, binding.observer_container, ["ping", "-c", "1", "-W", "1", "10.40.0.3"]); dns_ping_raw = _raw(output, "dns_network_probe", {"schema_version": 1, "command_result": dns_ping})
    dns_query = _result(executor, binding.observer_container, ["sh", "-c", "dig +time=2 +tries=1 @10.40.0.3 app.x4.test A +short"]); dns_raw = _raw(output, "dns_query", {"schema_version": 1, "command_result": dns_query})
    process = _result(executor, binding.app_container, ["sh", "-c", "pgrep -f 'http.server 8080'"]); process_raw = _raw(output, "service_process", {"schema_version": 1, "command_result": process})
    port = _result(executor, binding.observer_container, ["nc", "-z", "-w", "2", "10.40.0.4", "8080"]); port_raw = _raw(output, "service_port", {"schema_version": 1, "command_result": port})
    policy = _result(executor, binding.observer_container, ["iptables", "-S"]); policy_raw = _raw(output, "service_policy", {"schema_version": 1, "command_result": policy})
    dns_ok = dns_query["return_code"] == 0 and "10.40.0.4" in str(dns_query["stdout"])
    observations = {
        "dhcp_server_reachable": _obs(endpoint_value, endpoint_availability, endpoint_raw),
        "dhcp_lease_obtained": _obs(lease_value, lease_availability, lease_raw),
        "dhcp_lease_matches_expected_scope": _obs(scope_value, lease_availability, lease_raw),
        "dns_server_reachable": _obs(dns_ping["return_code"] == 0, "observed", dns_ping_raw),
        "dns_query_succeeds": _obs(dns_query["return_code"] == 0, "observed", dns_raw),
        "dns_answer_matches_expected": _obs(dns_ok, "observed", dns_raw),
        "service_process_running": _obs(process["return_code"] == 0, "observed", process_raw),
        "service_port_reachable": _obs(port["return_code"] == 0, "observed", port_raw),
        "service_flow_blocked_by_policy": _obs("X4-R1-SERVICE-BLOCK" in str(policy["stdout"]), "observed", policy_raw, "service_policy_state_collector"),
    }
    raw_artifacts = [{"path": p, "sha256": h} for p, h in (endpoint_raw, configuration_raw, lease_raw, dns_ping_raw, dns_raw, process_raw, port_raw)]
    completed = utc_now(); configuration_error = configuration["return_code"] != 0
    evidence = {"schema_version": 4, "evidence_id": binding.scenario_id.lower() + ":evidence:v4", "topology_context_id": binding.topology_context_id, "collected_at_utc": completed, "observation_path": {"direction": "client_to_dhcp_server", "source_node": binding.source_node, "destination_node": binding.destination_node, "observer_nodes": ["observer"]}, "collector_runs": [{"schema_version": 1, "collector_id": "service_state_collector_v2", "collector_version": 2, "domain": "services", "status": "completed" if endpoint_availability == "observed" and lease_availability == "observed" and not configuration_error else "partial", "started_at_utc": started, "completed_at_utc": completed, "feature_ids": list(FEATURE_IDS[:-1]), "raw_artifacts": raw_artifacts, "errors": (["DHCP endpoint or fresh-lease collection unavailable."] if endpoint_availability != "observed" or lease_availability != "observed" else []) + (["DHCP pool configuration collection unavailable."] if configuration_error else [])}, {"schema_version": 1, "collector_id": "service_policy_state_collector", "collector_version": 1, "domain": "security", "status": "completed", "started_at_utc": started, "completed_at_utc": completed, "feature_ids": ["service_flow_blocked_by_policy"], "raw_artifacts": [{"path": policy_raw[0], "sha256": policy_raw[1]}], "errors": []}], "observations": observations, "compatibility": {"origin": "native_v4", "source_schema_version": None, "source_artifact_sha256": None}}
    context = json.loads((repository_root / binding.scenario["topology"]["context_file"]).read_text(encoding="utf-8")); catalog = json.loads((repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text(encoding="utf-8"))
    validate_topology_context_v1(context, repository_root=repository_root)
    if context["context_id"] != binding.topology_context_id or context["observation_roles"] != {"source": "client", "destination": "dhcp_server", "observers": ["observer"]}:
        raise X4DhcpPoolMisconfigurationError("X4-R2 must use the accepted DHCP-flow Topology Context v1.")
    validate_evidence_v4(evidence, catalog, repository_root=repository_root); write_json_atomic(output / EVIDENCE, evidence)
    return evidence


def build_service_feature_vector_v2_r2(output_directory: Path, evidence: Mapping[str, object], *, repository_root: Path = ROOT) -> dict[str, object]:
    output = Path(output_directory); evidence_path = output / EVIDENCE
    if not evidence_path.is_file() or (output / VECTOR).exists():
        raise X4DhcpPoolMisconfigurationError("X4-R2 Evidence v4 persistence/vector output boundary failed.")
    catalog_path = repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"; catalog = json.loads(catalog_path.read_text(encoding="utf-8")); observations = evidence.get("observations")
    if not isinstance(observations, Mapping): raise X4DhcpPoolMisconfigurationError("X4-R2 evidence observations missing.")
    vector = {"schema_version": 2, "vector_id": str(evidence["evidence_id"]) + ":vector:v2", "catalog_id": catalog["catalog_id"], "evidence_id": evidence["evidence_id"], "values": {name: {"value": row["value"], "availability": row["availability"]} for name, row in observations.items() if isinstance(row, Mapping)}, "mask_id": None, "provenance": {"evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(), "feature_catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest()}}
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root); write_json_atomic(output / VECTOR, vector)
    return vector
