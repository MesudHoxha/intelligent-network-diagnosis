from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.collection.modular_registry import build_x1_registry
from src.contracts.expansion import ExpansionContractError, validate_feature_catalog_v1, validate_topology_context_v1
from src.expansion.scope_gate import verify_scope_gate
from src.expansion.x1_gate import verify_x1_gate
from src.expansion.x4_r6_gate import verify_x4_r6_source_gate
from src.phase9.p9_r1_gate import verify_p9_r1_gate


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path("plans/expansion/X5_R0_OSPF_DYNAMIC_ROUTING_RUNTIME_GATE_V1.json")
SCHEMA_PATH = Path("schemas/x5_ospf_dynamic_routing_runtime_gate_v1.schema.json")
TOPOLOGY_PATH = Path("labs/topologies/x5_r1_ospf_dynamic_routing/topology_context_v1.json")
FEATURE_CATALOG_PATH = Path("plans/expansion/X1_FEATURE_CATALOG_V1.json")
EXPECTED_PARENT_COMMIT = "50f0624679d7b1577d88d66ba87eb1c7390e80f0"
EXPECTED_FEATURE_IDS = (
    "ospf_adjacency_full", "ospf_route_advertised", "ospf_route_installed", "route_filter_allows_prefix",
)
EXPECTED_RUNTIME_FLAGS = (
    "containerlab_execution", "network_mutation", "new_evidence_collection", "dataset_generation",
    "model_fit_or_selection", "estimator_deserialization", "method_prediction", "metric_calculation",
    "report_only_test_access", "multiple_fault_execution",
)
EXPECTED_FAULTS = (
    ("C4", "dynamic_routing_adjacency_failure", "X5_R1_OSPF_ADJACENCY_FAILURE"),
    ("C5", "route_filtering_or_advertisement_problem", "X5_R2_ROUTE_FILTERING_OR_ADVERTISEMENT_PROBLEM"),
)
EXPECTED_SIGNATURES = {
    "dynamic_routing_adjacency_failure": dict(zip(EXPECTED_FEATURE_IDS, (False, False, False, True))),
    "route_filtering_or_advertisement_problem": dict(zip(EXPECTED_FEATURE_IDS, (True, False, False, False))),
}
EXPECTED_RELEASES = (
    "X5_R0_OSPF_DYNAMIC_ROUTING_DESIGN_GATE", "X5_R1_OSPF_ADJACENCY_FAILURE",
    "X5_R2_ROUTE_FILTERING_OR_ADVERTISEMENT_PROBLEM", "X5_R3_OSPF_DYNAMIC_ROUTING_CLOSEOUT",
)
EXPECTED_NODES = (("hosta", "host"), ("r1", "router"), ("r2", "router"), ("r3", "router"), ("hostb", "host"))
EXPECTED_LINKS = (("hosta_r1", ("hosta", "r1")), ("r1_r2", ("r1", "r2")), ("r2_r3", ("r2", "r3")), ("r3_hostb", ("r3", "hostb")))
EXPECTED_SAFETY = (
    "DURABLE_RECOVERY_INTENT_BEFORE_MUTATION", "ATOMIC_MUTATION_JOURNAL", "BEST_EFFORT_RESTORATION",
    "IDEMPOTENT_CONFIRMED_RESTORATION", "FINAL_HEALTHY_STATE_VERIFIED", "SINGLE_FAULT_ISOLATION",
    "BASELINE_BEFORE_AND_AFTER", "CLEANUP_ZERO_CONTAINERS", "EXACT_OSPF_AND_ROUTE_POLICY_RESTORATION",
    "DIRECT_STATE_NOT_CONNECTIVITY_ONLY_CLASSIFICATION",
)


class X5GateError(ValueError):
    """Raised when the append-only X5-R0 design boundary drifts."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X5GateError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X5GateError(f"Cannot read a valid JSON object: {path}") from error
    _require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_source_path(repository_root: Path, relative: str) -> Path:
    candidate = PurePosixPath(relative)
    _require(relative and not candidate.is_absolute() and ".." not in candidate.parts and candidate.as_posix() == relative, "An X5 source binding is not a canonical relative path.")
    root = repository_root.resolve()
    resolved = (root / Path(relative)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise X5GateError("An X5 source binding escaped the repository.") from error
    _require(resolved.is_file() and not (root / relative).is_symlink(), f"An X5 source binding is unavailable: {relative}")
    return resolved


def _validate_topology(context: Mapping[str, Any]) -> None:
    _require(context.get("context_id") == "x5_top_01_ospf_dynamic_routing_context_v1" and context.get("topology_id") == "X5_TOP_01_OSPF_DYNAMIC_ROUTING" and context.get("variant_id") == "x5_r0_design_only_v1", "X5 topology identity drifted.")
    nodes = context.get("nodes")
    _require(isinstance(nodes, list) and tuple((row.get("node_id"), row.get("role")) for row in nodes if isinstance(row, Mapping)) == EXPECTED_NODES, "X5 topology nodes drifted.")
    links = context.get("links")
    _require(isinstance(links, list) and tuple((row.get("link_id"), tuple(endpoint.get("node_id") for endpoint in row.get("endpoints", ()) if isinstance(endpoint, Mapping))) for row in links if isinstance(row, Mapping)) == EXPECTED_LINKS, "X5 topology links drifted.")
    roles = context.get("observation_roles")
    _require(isinstance(roles, Mapping) and roles.get("source") == "hosta" and roles.get("destination") == "hostb" and tuple(roles.get("observers", ())) == ("r1", "r2"), "X5 observation roles drifted.")
    _require(set(context.get("capabilities", ())) == {"ospf", "ospf_neighbor_inspection", "ospf_database_inspection", "ospf_route_inspection", "route_policy_inspection", "interface_state_inspection", "connectivity_control"}, "X5 topology capabilities drifted.")


def validate_x5_manifest(manifest: Mapping[str, Any], schema: Mapping[str, Any] | None = None) -> None:
    if schema is not None:
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda error: tuple(str(part) for part in error.path))
        if errors:
            raise X5GateError("X5-R0 manifest schema validation failed: " + errors[0].message)
    _require(manifest.get("gate_id") == "x5_r0_ospf_dynamic_routing_design_runtime_gate_v1" and manifest.get("status") == "ACCEPTED_DESIGN_ONLY", "X5-R0 identity or design-only status drifted.")
    track = manifest.get("track")
    _require(isinstance(track, Mapping) and track == {"parent_gate": "x4_r6_dhcp_dns_service_security_closeout_v1", "phase9_status": "P9_R1_ACCEPTED_P9_R2_PAUSED_BY_USER", "current_release": EXPECTED_RELEASES[0], "next_release": EXPECTED_RELEASES[1]}, "X5-R0 track boundary drifted.")
    _require(manifest.get("source_boundary") == {"parent_commit": EXPECTED_PARENT_COMMIT, "extension_policy": "APPEND_ONLY", "runtime_inherited": False}, "X5-R0 source boundary drifted.")
    compatibility = manifest.get("compatibility")
    _require(isinstance(compatibility, Mapping) and all(compatibility.get(key) is False for key in ("frozen_baseline_mutation_allowed", "accepted_x2_mutation_allowed", "accepted_x3_mutation_allowed", "accepted_x4_mutation_allowed", "accepted_result_mutation_allowed")) and compatibility.get("api_v1_status") == "FROZEN_BASELINE" and compatibility.get("future_extended_api") == "/api/v2" and compatibility.get("truth_model") == "SINGLE_FAULT_ONLY", "X5 compatibility boundary drifted.")
    authorization = manifest.get("runtime_authorization")
    _require(isinstance(authorization, Mapping) and tuple(authorization) == EXPECTED_RUNTIME_FLAGS and not any(authorization.values()), "X5-R0 cannot authorize runtime or scientific execution.")
    _require(manifest.get("baseline_signature") == dict(zip(EXPECTED_FEATURE_IDS, (True, True, True, True))), "X5 baseline signature drifted.")
    boundary = manifest.get("feature_boundary")
    _require(isinstance(boundary, Mapping) and boundary.get("catalog_id") == "x1_feature_catalog_v1" and tuple(boundary.get("required_feature_ids", ())) == EXPECTED_FEATURE_IDS, "X5 feature boundary drifted.")
    collector = boundary.get("collector_binding") if isinstance(boundary, Mapping) else None
    _require(isinstance(collector, Mapping) and collector == {"collector_id": "ospf_state_collector", "collector_version": 1, "collector_status": "DESIGN_ONLY", "feature_ids": list(EXPECTED_FEATURE_IDS)}, "X5 collector ownership drifted.")
    _require(tuple(boundary.get("control_evidence", ())) == ("INTERFACE_STATE_JSON", "STATIC_ROUTE_OVERRIDE_CONTROL", "POLICY_BLOCK_CONTROL", "CONNECTIVITY_CONTROL_PROBE"), "X5 control evidence drifted.")
    slices = manifest.get("ospf_dynamic_routing_scope")
    _require(isinstance(slices, list) and tuple((row.get("fault_code"), row.get("fault_type"), row.get("implementation_release")) for row in slices if isinstance(row, Mapping)) == EXPECTED_FAULTS and tuple(row.get("order") for row in slices) == (1, 2), "X5 fault order drifted.")
    signatures: set[tuple[tuple[str, bool], ...]] = set()
    for row in slices:
        assert isinstance(row, Mapping)
        signature = row.get("fault_signature")
        fault_type = row.get("fault_type")
        _require(signature == EXPECTED_SIGNATURES[fault_type], f"X5 signature drifted: {fault_type}")
        key = tuple(sorted(signature.items()))
        _require(key not in signatures, "X5 OSPF signatures must remain disjoint.")
        signatures.add(key)
        _require(tuple(row.get("required_feature_ids", ())) == EXPECTED_FEATURE_IDS and row.get("recovery_intent_required") is True and row.get("idempotent_restoration_required") is True and row.get("real_e2e_required") is True and len(row.get("excluded_confounders", ())) == 6, f"X5 slice safety or confounder boundary drifted: {fault_type}")
    topology = manifest.get("topology_design")
    _require(isinstance(topology, Mapping) and topology.get("context_path") == TOPOLOGY_PATH.as_posix() and topology.get("topology_id") == "X5_TOP_01_OSPF_DYNAMIC_ROUTING" and topology.get("status") == "DESIGN_ONLY" and topology.get("routing_plane") == "FRROUTING_OSPFV2" and topology.get("node_count") == 5 and topology.get("link_count") == 4, "X5 topology design boundary drifted.")
    releases = manifest.get("release_sequence")
    _require(isinstance(releases, list) and tuple(row.get("release_id") for row in releases) == EXPECTED_RELEASES and releases[0].get("status") == "ACCEPTED_DESIGN_ONLY" and all(row.get("status") == "PLANNED" and row.get("runtime_inherited") is False for row in releases[1:]), "X5 release order or non-inherited runtime boundary drifted.")
    _require(tuple(manifest.get("safety_invariants", ())) == EXPECTED_SAFETY, "X5 safety invariants drifted.")
    evidence, acceptance = manifest.get("evidence_policy"), manifest.get("acceptance")
    _require(isinstance(evidence, Mapping) and evidence.get("evidence_contract") == "Evidence v4" and evidence.get("raw_artifact_hash_required") is True and evidence.get("collector_provenance_required") is True and evidence.get("real_evidence_required_per_runtime_slice") is True and evidence.get("connectivity_only_classification_forbidden") is True and evidence.get("control_evidence_not_classifier") is True and evidence.get("r0_creates_empirical_evidence") is False and evidence.get("accepted_x4_evidence_read_only") is True and evidence.get("report_only_test_access_allowed") is False, "X5 evidence boundary drifted.")
    _require(isinstance(acceptance, Mapping) and acceptance.get("new_runtime_executed") is False and acceptance.get("new_empirical_claim_created") is False and acceptance.get("topology_context_validated") is True and acceptance.get("infrastructure_e2e_required_for_r0") is False and acceptance.get("frozen_artifacts_unchanged") is True and acceptance.get("explicit_gate_before_each_runtime_release") is True, "X5 acceptance boundary drifted.")


def verify_x5_gate(repository_root: Path = ROOT) -> dict[str, Any]:
    root = Path(repository_root)
    manifest, schema = _load_json(root / MANIFEST_PATH), _load_json(root / SCHEMA_PATH)
    validate_x5_manifest(manifest, schema)
    bindings = manifest["source_bindings"]
    assert isinstance(bindings, list)
    _require(len(bindings) == 13 and len({row["binding_id"] for row in bindings}) == 13 and len({row["path"] for row in bindings}) == 13, "X5 requires exactly 13 unique source bindings.")
    for row in bindings:
        path = _safe_source_path(root, str(row["path"]))
        _require(_sha256(path) == row["sha256"], f"X5 source binding drifted: {row['path']}")
    _require(verify_scope_gate(root)["status"] == "ACCEPTED_DESIGN_ONLY" and verify_x1_gate(root)["status"] == "ACCEPTED_CONTRACT_ONLY" and verify_x4_r6_source_gate(root)["status"] == "ACCEPTED_SOURCE_CLOSEOUT", "An X0/X1/X4 parent gate is not accepted.")
    verify_p9_r1_gate(root)
    x0 = _load_json(root / "plans/expansion/X0_SCOPE_COMPATIBILITY_FREEZE_V1.json")
    taxonomy = {row["fault_type"]: row for row in x0["taxonomy"]["fault_types"] if row["target_phase"] == "X5"}
    _require(set(taxonomy) == {fault for _, fault, _ in EXPECTED_FAULTS} and all(taxonomy[fault]["code"] == code and taxonomy[fault]["category"] == "routing" for code, fault, _ in EXPECTED_FAULTS), "X5 scope drifted from the canonical X0 taxonomy.")
    catalog = _load_json(root / FEATURE_CATALOG_PATH)
    try:
        index = validate_feature_catalog_v1(catalog, repository_root=root)
    except ExpansionContractError as error:
        raise X5GateError(str(error)) from error
    _require(all(index[name]["target_phase"] == "X5" and index[name]["lifecycle"] == "PLANNED_EXTENSION" for name in EXPECTED_FEATURE_IDS), "X5 features drifted from X1.")
    registry = build_x1_registry(index)
    plan = registry.plan(EXPECTED_FEATURE_IDS, ("ospf",))
    _require(plan.collector_keys == ("ospf_state_collector:v1",) and not plan.capability_gaps and plan.runtime_authorized is False, "X5 collector plan drifted or authorized runtime.")
    context = _load_json(root / TOPOLOGY_PATH)
    try:
        validate_topology_context_v1(context, repository_root=root)
    except ExpansionContractError as error:
        raise X5GateError(str(error)) from error
    _validate_topology(context)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the X5-R0 OSPF dynamic-routing design gate.")
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    args = parser.parse_args()
    plan = verify_x5_gate(args.repository_root)
    print("x5_r0_gate=VERIFIED\nospf_slices=2/2_DISJOINT_DESIGN_PASS\nfeature_ownership=4/4_X1_BOUND_PASS\nruntime_authorization=10/10_FALSE_PASS\nclaim_boundary=DESIGN_ONLY_NO_EMPIRICAL_CLAIM_PASS")
    print(f"next_release={plan['track']['next_release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
