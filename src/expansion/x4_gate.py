from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.collection.modular_registry import build_x1_registry
from src.contracts.expansion import (
    ExpansionContractError,
    validate_feature_catalog_v1,
    validate_topology_context_v1,
)
from src.expansion.scope_gate import verify_scope_gate
from src.expansion.x1_gate import verify_x1_gate
from src.expansion.x3_r5_gate import verify_x3_r5_source_gate


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path("plans/expansion/X4_R0_DHCP_DNS_SERVICE_SECURITY_RUNTIME_GATE_V1.json")
SCHEMA_PATH = Path("schemas/x4_dhcp_dns_service_security_runtime_gate_v1.schema.json")
TOPOLOGY_PATH = Path("labs/topologies/x4_r1_dhcp_dns_service/topology_context_v1.json")
X0_MANIFEST_PATH = Path("plans/expansion/X0_SCOPE_COMPATIBILITY_FREEZE_V1.json")
FEATURE_CATALOG_PATH = Path("plans/expansion/X1_FEATURE_CATALOG_V1.json")
EXPECTED_PARENT_COMMIT = "2a763c6c6cd44f984ce08331e20d3e03445a0037"

EXPECTED_RUNTIME_FLAGS = (
    "containerlab_execution", "network_mutation", "new_evidence_collection",
    "dataset_generation", "model_fit_or_selection", "estimator_deserialization",
    "method_prediction", "metric_calculation", "report_only_test_access",
    "multiple_fault_execution",
)
EXPECTED_FEATURE_IDS = (
    "dhcp_server_reachable", "dhcp_lease_obtained",
    "dhcp_lease_matches_expected_scope", "dns_server_reachable",
    "dns_query_succeeds", "dns_answer_matches_expected",
    "service_process_running", "service_port_reachable",
    "service_flow_blocked_by_policy",
)
EXPECTED_COLLECTOR_BINDINGS = (
    ("service_state_collector", 1, "DESIGN_ONLY", EXPECTED_FEATURE_IDS[:8]),
    ("service_policy_state_collector", 1, "DESIGN_ONLY", EXPECTED_FEATURE_IDS[8:]),
)
EXPECTED_FAULTS = (
    ("D1", "dhcp_server_unavailable", "services", "X4_R1_DHCP_SERVER_UNAVAILABLE"),
    ("D2", "dhcp_pool_misconfiguration", "services", "X4_R2_DHCP_POOL_MISCONFIGURATION"),
    ("D3", "dns_service_down", "services", "X4_R3_DNS_SERVICE_DOWN"),
    ("D4", "wrong_dns_record", "services", "X4_R4_WRONG_DNS_RECORD"),
    ("E2", "firewall_service_block", "security", "X4_R5_FIREWALL_SERVICE_BLOCK"),
)
EXPECTED_SIGNATURES = {
    "dhcp_server_unavailable": dict(zip(EXPECTED_FEATURE_IDS, (False, False, False, True, True, True, True, True, False))),
    "dhcp_pool_misconfiguration": dict(zip(EXPECTED_FEATURE_IDS, (True, False, False, True, True, True, True, True, False))),
    "dns_service_down": dict(zip(EXPECTED_FEATURE_IDS, (True, True, True, True, False, False, False, False, False))),
    "wrong_dns_record": dict(zip(EXPECTED_FEATURE_IDS, (True, True, True, True, True, False, True, True, False))),
    "firewall_service_block": dict(zip(EXPECTED_FEATURE_IDS, (True, True, True, True, True, True, True, False, True))),
}
EXPECTED_BASELINE_SIGNATURE = dict(zip(EXPECTED_FEATURE_IDS, (True, True, True, True, True, True, True, True, False)))
EXPECTED_RELEASES = (
    "X4_R0_DHCP_DNS_SERVICE_SECURITY_DESIGN_GATE",
    "X4_R1_DHCP_SERVER_UNAVAILABLE",
    "X4_R2_DHCP_POOL_MISCONFIGURATION",
    "X4_R3_DNS_SERVICE_DOWN",
    "X4_R4_WRONG_DNS_RECORD",
    "X4_R5_FIREWALL_SERVICE_BLOCK",
    "X4_R6_DHCP_DNS_SERVICE_SECURITY_CLOSEOUT",
)
EXPECTED_SAFETY_INVARIANTS = (
    "DURABLE_RECOVERY_INTENT_BEFORE_MUTATION", "ATOMIC_MUTATION_JOURNAL",
    "BEST_EFFORT_RESTORATION", "IDEMPOTENT_CONFIRMED_RESTORATION",
    "FINAL_HEALTHY_STATE_VERIFIED", "SINGLE_FAULT_ISOLATION",
    "BASELINE_BEFORE_AND_AFTER", "CLEANUP_ZERO_CONTAINERS",
    "EXACT_SERVICE_CONFIGURATION_RESTORATION",
    "GENERIC_CONNECTIVITY_CONTROL_PRESERVED",
)
EXPECTED_NODES = (
    ("client", "host"), ("svc_switch", "switch"), ("dhcp_server", "service"),
    ("dns_server", "service"), ("app_server", "service"), ("observer", "observer"),
)
EXPECTED_LINKS = (
    ("client_svc_switch", "service", ("client", "svc_switch")),
    ("dhcp_server_svc_switch", "service", ("dhcp_server", "svc_switch")),
    ("dns_server_svc_switch", "service", ("dns_server", "svc_switch")),
    ("app_server_svc_switch", "service", ("app_server", "svc_switch")),
    ("observer_svc_switch", "service", ("observer", "svc_switch")),
)
EXPECTED_FLOWS = (
    ("dhcp_lease_flow", "client", "dhcp_server", "UDP", 67, "DHCP_EXCHANGE"),
    ("dns_query_flow", "client", "dns_server", "UDP", 53, "DNS_QUERY"),
    ("service_tcp_flow", "client", "app_server", "TCP", 8080, "SERVICE_FLOW"),
)


class X4GateError(ValueError):
    """Raised when the X4-R0 design or authorization boundary drifts."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X4GateError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X4GateError(f"Cannot read a valid JSON object: {path}") from error
    _require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_source_path(repository_root: Path, relative: str) -> Path:
    candidate = PurePosixPath(relative)
    _require(relative and not candidate.is_absolute() and ".." not in candidate.parts and candidate.as_posix() == relative, "An X4 source binding is not a canonical relative path.")
    root = repository_root.resolve()
    resolved = (root / Path(relative)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise X4GateError("An X4 source binding escaped the repository.") from error
    _require(resolved.is_file() and not (root / relative).is_symlink(), f"An X4 source binding is unavailable: {relative}")
    return resolved


def _validate_topology(context: Mapping[str, Any]) -> None:
    _require(context.get("context_id") == "x4_top_01_dhcp_dns_service_security_context_v1" and context.get("topology_id") == "X4_TOP_01_DHCP_DNS_SERVICE_SECURITY" and context.get("variant_id") == "x4_r0_design_only_v1", "X4 topology identity drifted.")
    nodes = context.get("nodes")
    _require(isinstance(nodes, list) and tuple((row.get("node_id"), row.get("role")) for row in nodes if isinstance(row, Mapping)) == EXPECTED_NODES, "X4 topology nodes drifted.")
    links = context.get("links")
    _require(isinstance(links, list) and tuple((row.get("link_id"), row.get("kind"), tuple(endpoint.get("node_id") for endpoint in row.get("endpoints", ()) if isinstance(endpoint, Mapping))) for row in links if isinstance(row, Mapping)) == EXPECTED_LINKS, "X4 topology links drifted.")
    roles = context.get("observation_roles")
    _require(isinstance(roles, Mapping) and roles.get("source") == "client" and roles.get("destination") == "app_server" and tuple(roles.get("observers", ())) == ("observer",), "X4 topology observation roles drifted.")
    _require(set(context.get("capabilities", ())) == {"service_observation", "service_policy", "dhcp_lease_exchange", "dns_query", "service_process_inspection", "service_port_probe", "service_policy_inspection"}, "X4 topology capabilities drifted.")


def validate_x4_manifest(manifest: Mapping[str, Any], schema: Mapping[str, Any] | None = None) -> None:
    if schema is not None:
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda error: tuple(str(part) for part in error.path))
        if errors:
            raise X4GateError("X4-R0 manifest schema validation failed: " + errors[0].message)
    _require(manifest.get("gate_id") == "x4_r0_dhcp_dns_service_security_design_runtime_gate_v1" and manifest.get("status") == "ACCEPTED_DESIGN_ONLY", "X4-R0 identity or design-only status drifted.")
    track = manifest.get("track")
    _require(isinstance(track, Mapping) and track.get("parent_gate") == "x3_r5_layer2_vlan_closeout_v1" and track.get("phase9_status") == "P9_R1_PAUSED_BY_USER" and track.get("current_release") == EXPECTED_RELEASES[0] and track.get("next_release") == EXPECTED_RELEASES[1], "X4-R0 track boundary drifted.")
    source = manifest.get("source_boundary")
    _require(isinstance(source, Mapping) and source.get("parent_commit") == EXPECTED_PARENT_COMMIT and source.get("extension_policy") == "APPEND_ONLY" and source.get("runtime_inherited") is False, "X4-R0 source boundary drifted.")
    compatibility = manifest.get("compatibility")
    _require(isinstance(compatibility, Mapping) and all(compatibility.get(key) is False for key in ("frozen_baseline_mutation_allowed", "accepted_x2_mutation_allowed", "accepted_x3_mutation_allowed", "accepted_result_mutation_allowed")) and compatibility.get("api_v1_status") == "FROZEN_BASELINE" and compatibility.get("future_extended_api") == "/api/v2" and compatibility.get("truth_model") == "SINGLE_FAULT_ONLY", "X4-R0 compatibility boundary drifted.")
    authorization = manifest.get("runtime_authorization")
    _require(isinstance(authorization, Mapping) and tuple(authorization) == EXPECTED_RUNTIME_FLAGS and not any(authorization.values()), "X4-R0 cannot authorize runtime or scientific execution.")
    feature_boundary = manifest.get("feature_boundary")
    _require(isinstance(feature_boundary, Mapping) and feature_boundary.get("catalog_id") == "x1_feature_catalog_v1" and tuple(feature_boundary.get("required_feature_ids", ())) == EXPECTED_FEATURE_IDS, "The X4 feature boundary drifted.")
    bindings = feature_boundary.get("collector_bindings") if isinstance(feature_boundary, Mapping) else None
    observed_bindings = tuple((row.get("collector_id"), row.get("collector_version"), row.get("collector_status"), tuple(row.get("feature_ids", ()))) for row in bindings if isinstance(row, Mapping)) if isinstance(bindings, list) else ()
    _require(observed_bindings == EXPECTED_COLLECTOR_BINDINGS, "X4 collector ownership drifted.")
    _require(manifest.get("baseline_signature") == EXPECTED_BASELINE_SIGNATURE, "The X4 baseline signature drifted.")
    slices = manifest.get("dhcp_dns_service_security_scope")
    _require(isinstance(slices, list), "X4 fault slices are missing.")
    observed_faults = tuple((row.get("fault_code"), row.get("fault_type"), row.get("category"), row.get("implementation_release")) for row in slices if isinstance(row, Mapping))
    _require(observed_faults == EXPECTED_FAULTS and tuple(row.get("order") for row in slices) == (1, 2, 3, 4, 5), "X4 fault order drifted.")
    signatures: set[tuple[tuple[str, bool], ...]] = set()
    for row in slices:
        assert isinstance(row, Mapping)
        fault_type = str(row["fault_type"])
        signature = row.get("fault_signature")
        _require(signature == EXPECTED_SIGNATURES[fault_type], f"The {fault_type} signature drifted.")
        signature_key = tuple(sorted(signature.items()))
        _require(signature_key not in signatures, "DHCP/DNS/service-security signatures must remain disjoint.")
        signatures.add(signature_key)
        _require(tuple(row.get("required_feature_ids", ())) == EXPECTED_FEATURE_IDS and row.get("recovery_intent_required") is True and row.get("idempotent_restoration_required") is True and row.get("real_e2e_required") is True and len(row.get("excluded_confounders", ())) == 4, f"The {fault_type} safety or evidence boundary drifted.")
    topology = manifest.get("topology_design")
    _require(isinstance(topology, Mapping) and topology.get("context_path") == TOPOLOGY_PATH.as_posix() and topology.get("topology_id") == "X4_TOP_01_DHCP_DNS_SERVICE_SECURITY" and topology.get("status") == "DESIGN_ONLY" and topology.get("switch_plane") == "LINUX_BRIDGE_SERVICE_SEGMENT" and topology.get("node_count") == 6 and topology.get("link_count") == 5 and topology.get("service_network") == "10.40.0.0/24", "X4 topology design boundary drifted.")
    flows = topology.get("flow_roles") if isinstance(topology, Mapping) else None
    observed_flows = tuple((row.get("flow_id"), row.get("source"), row.get("destination"), row.get("transport"), row.get("port"), row.get("classification_role")) for row in flows if isinstance(row, Mapping)) if isinstance(flows, list) else ()
    _require(observed_flows == EXPECTED_FLOWS, "X4 DHCP, DNS, and service flow separation drifted.")
    releases = manifest.get("release_sequence")
    _require(isinstance(releases, list) and tuple(row.get("release_id") for row in releases) == EXPECTED_RELEASES and releases[0].get("status") == "ACCEPTED_DESIGN_ONLY" and all(row.get("status") == "PLANNED" for row in releases[1:]) and not any(row.get("runtime_inherited") for row in releases), "X4 release order or non-inherited runtime boundary drifted.")
    _require(tuple(manifest.get("safety_invariants", ())) == EXPECTED_SAFETY_INVARIANTS, "X4 safety invariants drifted.")
    evidence = manifest.get("evidence_policy")
    acceptance = manifest.get("acceptance")
    _require(isinstance(evidence, Mapping) and evidence.get("evidence_contract") == "Evidence v4" and evidence.get("raw_artifact_hash_required") is True and evidence.get("collector_provenance_required") is True and evidence.get("real_evidence_required_per_runtime_slice") is True and evidence.get("effectiveness_only_evidence_not_classifier") is True and evidence.get("r0_creates_empirical_evidence") is False and evidence.get("accepted_x3_evidence_read_only") is True and evidence.get("report_only_test_access_allowed") is False, "X4-R0 evidence boundary drifted.")
    _require(isinstance(acceptance, Mapping) and acceptance.get("new_runtime_executed") is False and acceptance.get("new_empirical_claim_created") is False and acceptance.get("topology_context_validated") is True and acceptance.get("infrastructure_e2e_required_for_r0") is False and acceptance.get("frozen_artifacts_unchanged") is True and acceptance.get("explicit_gate_before_each_runtime_release") is True, "X4-R0 acceptance boundary drifted.")


def verify_x4_gate(repository_root: Path = ROOT) -> dict[str, Any]:
    root = Path(repository_root)
    manifest = _load_json(root / MANIFEST_PATH)
    schema = _load_json(root / SCHEMA_PATH)
    validate_x4_manifest(manifest, schema)
    bindings = manifest["source_bindings"]
    assert isinstance(bindings, list)
    _require(len(bindings) == 11 and len({row["binding_id"] for row in bindings}) == 11 and len({row["path"] for row in bindings}) == 11, "X4 requires exactly 11 unique source bindings.")
    for row in bindings:
        path = _safe_source_path(root, str(row["path"]))
        _require(_sha256(path) == row["sha256"], f"X4 source binding drifted: {row['path']}")
    _require(verify_scope_gate(root)["status"] == "ACCEPTED_DESIGN_ONLY" and verify_x1_gate(root)["status"] == "ACCEPTED_CONTRACT_ONLY" and verify_x3_r5_source_gate(root)["status"] == "ACCEPTED_SOURCE_CLOSEOUT", "An X0/X1/X3 parent gate is not accepted.")
    x0 = _load_json(root / X0_MANIFEST_PATH)
    rows = {row["fault_type"]: row for row in x0["taxonomy"]["fault_types"] if row["target_phase"] == "X4"}
    _require(set(rows) == {fault for _, fault, _, _ in EXPECTED_FAULTS}, "X4 scope drifted from the canonical X0 taxonomy.")
    for code, fault, category, _ in EXPECTED_FAULTS:
        _require(rows[fault]["code"] == code and rows[fault]["category"] == category and rows[fault]["implementation_status"] in {"MISSING", "PARTIAL_MECHANISM_ONLY"}, f"X4 taxonomy binding drifted: {fault}")
    catalog = _load_json(root / FEATURE_CATALOG_PATH)
    try:
        feature_index = validate_feature_catalog_v1(catalog, repository_root=root)
    except ExpansionContractError as error:
        raise X4GateError(str(error)) from error
    _require(all(feature_index[name]["target_phase"] == "X4" and feature_index[name]["lifecycle"] == "PLANNED_EXTENSION" for name in EXPECTED_FEATURE_IDS), "X4 features drifted from the X1 catalog.")
    registry = build_x1_registry(feature_index)
    plan = registry.plan(EXPECTED_FEATURE_IDS, ("service_observation", "service_policy"))
    _require(plan.collector_keys == ("service_policy_state_collector:v1", "service_state_collector:v1") and not plan.capability_gaps and plan.runtime_authorized is False, "X4 collector plan drifted or authorized runtime.")
    context = _load_json(root / TOPOLOGY_PATH)
    try:
        validate_topology_context_v1(context, repository_root=root)
    except ExpansionContractError as error:
        raise X4GateError(str(error)) from error
    _validate_topology(context)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the X4-R0 DHCP, DNS, and service-security design gate.")
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    args = parser.parse_args()
    plan = verify_x4_gate(args.repository_root)
    print("x4_r0_gate=VERIFIED\nservice_security_slices=5/5_DISJOINT_DESIGN_PASS\nfeature_ownership=9/9_X1_BOUND_PASS\nruntime_authorization=10/10_FALSE_PASS\nclaim_boundary=DESIGN_ONLY_NO_EMPIRICAL_CLAIM_PASS")
    print(f"next_release={plan['track']['next_release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
