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
from src.expansion.x2_r5_gate import (
    verify_x2_r5_receipt,
    verify_x2_r5_source_gate,
)


MANIFEST_PATH = Path(
    "plans/expansion/X3_R0_LAYER2_VLAN_RUNTIME_GATE_V1.json"
)
MANIFEST_SCHEMA_PATH = Path(
    "schemas/x3_layer2_vlan_runtime_gate_v1.schema.json"
)
TOPOLOGY_CONTEXT_PATH = Path(
    "labs/topologies/x3_r1_l2_vlan/topology_context_v1.json"
)
X0_MANIFEST_PATH = Path(
    "plans/expansion/X0_SCOPE_COMPATIBILITY_FREEZE_V1.json"
)
FEATURE_CATALOG_PATH = Path("plans/expansion/X1_FEATURE_CATALOG_V1.json")
X2_R5_RECEIPT_PATH = Path(
    "plans/expansion/X2_R5_ADDRESSING_EVIDENCE_RECEIPT_V1.json"
)
EXPECTED_PARENT_COMMIT = "7949418dca284a064165f77e2e40f626ea54daba"

EXPECTED_RUNTIME_FLAGS = (
    "containerlab_execution",
    "network_mutation",
    "new_evidence_collection",
    "dataset_generation",
    "model_fit_or_selection",
    "estimator_deserialization",
    "method_prediction",
    "metric_calculation",
    "report_only_test_access",
    "multiple_fault_execution",
)

EXPECTED_FEATURE_IDS = (
    "access_vlan_matches_expected",
    "vlan_exists_on_target",
    "vlan_allowed_on_trunk",
    "native_vlan_matches_peer",
    "fdb_location_matches_expected",
)

EXPECTED_FAULTS = (
    ("B2", "wrong_access_vlan", "X3_R1_WRONG_ACCESS_VLAN"),
    ("B3", "vlan_missing", "X3_R2_VLAN_MISSING"),
    (
        "B4",
        "vlan_not_allowed_on_trunk",
        "X3_R3_VLAN_NOT_ALLOWED_ON_TRUNK",
    ),
    ("B5", "native_vlan_mismatch", "X3_R4_NATIVE_VLAN_MISMATCH"),
)

EXPECTED_SIGNATURES = {
    "wrong_access_vlan": {
        "access_vlan_matches_expected": False,
        "vlan_exists_on_target": True,
        "vlan_allowed_on_trunk": True,
        "native_vlan_matches_peer": True,
        "fdb_location_matches_expected": False,
    },
    "vlan_missing": {
        "access_vlan_matches_expected": False,
        "vlan_exists_on_target": False,
        "vlan_allowed_on_trunk": False,
        "native_vlan_matches_peer": True,
        "fdb_location_matches_expected": False,
    },
    "vlan_not_allowed_on_trunk": {
        "access_vlan_matches_expected": True,
        "vlan_exists_on_target": True,
        "vlan_allowed_on_trunk": False,
        "native_vlan_matches_peer": True,
        "fdb_location_matches_expected": True,
    },
    "native_vlan_mismatch": {
        "access_vlan_matches_expected": True,
        "vlan_exists_on_target": True,
        "vlan_allowed_on_trunk": True,
        "native_vlan_matches_peer": False,
        "fdb_location_matches_expected": True,
    },
}

EXPECTED_BASELINE_SIGNATURE = {
    "access_vlan_matches_expected": True,
    "vlan_exists_on_target": True,
    "vlan_allowed_on_trunk": True,
    "native_vlan_matches_peer": True,
    "fdb_location_matches_expected": True,
}

EXPECTED_RELEASES = (
    "X3_R0_LAYER2_VLAN_DESIGN_GATE",
    "X3_R1_WRONG_ACCESS_VLAN",
    "X3_R2_VLAN_MISSING",
    "X3_R3_VLAN_NOT_ALLOWED_ON_TRUNK",
    "X3_R4_NATIVE_VLAN_MISMATCH",
    "X3_R5_LAYER2_VLAN_CLOSEOUT",
)

EXPECTED_SAFETY_INVARIANTS = (
    "DURABLE_RECOVERY_INTENT_BEFORE_MUTATION",
    "ATOMIC_MUTATION_JOURNAL",
    "BEST_EFFORT_RESTORATION",
    "IDEMPOTENT_CONFIRMED_RESTORATION",
    "FINAL_HEALTHY_STATE_VERIFIED",
    "SINGLE_FAULT_ISOLATION",
    "BASELINE_BEFORE_AND_AFTER",
    "CLEANUP_ZERO_CONTAINERS",
    "EXACT_VLAN_MEMBERSHIP_RESTORATION",
    "BOTH_TRUNK_ENDPOINTS_OBSERVED",
)

EXPECTED_NODES = (
    ("hosta", "host"),
    ("hostb", "host"),
    ("hostc", "host"),
    ("hostd", "host"),
    ("sw1", "switch"),
    ("sw2", "switch"),
)

EXPECTED_LINKS = (
    ("hosta_sw1", "access", ("hosta", "sw1"), (10,), 10),
    ("hostc_sw1", "access", ("hostc", "sw1"), (99,), 99),
    ("sw1_sw2", "trunk", ("sw1", "sw2"), (10, 99), 99),
    ("sw2_hostb", "access", ("sw2", "hostb"), (10,), 10),
    ("sw2_hostd", "access", ("sw2", "hostd"), (99,), 99),
)

EXPECTED_FLOWS = (
    ("tagged_vlan_10_flow", "hosta", "hostb", 10, "TAGGED"),
    (
        "native_vlan_99_flow",
        "hostc",
        "hostd",
        99,
        "UNTAGGED_NATIVE",
    ),
)


class X3GateError(ValueError):
    """Raised when the X3-R0 design or authorization boundary drifts."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X3GateError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X3GateError(f"Cannot read a valid JSON object: {path}") from error
    _require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_source_path(repository_root: Path, relative: str) -> Path:
    candidate = PurePosixPath(relative)
    _require(
        relative
        and not candidate.is_absolute()
        and ".." not in candidate.parts
        and candidate.as_posix() == relative,
        "An X3 source binding is not a canonical relative path.",
    )
    root = repository_root.resolve()
    resolved = (root / Path(relative)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise X3GateError("An X3 source binding escaped the repository.") from error
    _require(
        resolved.is_file() and not (root / relative).is_symlink(),
        f"An X3 source binding is unavailable: {relative}",
    )
    return resolved


def _validate_topology(context: Mapping[str, Any]) -> None:
    _require(
        context.get("context_id") == "x3_top_01_l2_vlan_context_v1"
        and context.get("topology_id") == "X3_TOP_01_L2_VLAN"
        and context.get("variant_id") == "x3_r0_design_only_v1",
        "X3 topology identity drifted.",
    )
    nodes = context.get("nodes")
    _require(isinstance(nodes, list), "X3 topology nodes are missing.")
    observed_nodes = tuple(
        (row.get("node_id"), row.get("role"))
        for row in nodes
        if isinstance(row, Mapping)
    )
    _require(observed_nodes == EXPECTED_NODES, "X3 topology nodes drifted.")

    links = context.get("links")
    _require(isinstance(links, list), "X3 topology links are missing.")
    observed_links = tuple(
        (
            row.get("link_id"),
            row.get("kind"),
            tuple(
                endpoint.get("node_id")
                for endpoint in row.get("endpoints", ())
                if isinstance(endpoint, Mapping)
            ),
            tuple(row.get("expected_vlans", ())),
            row.get("native_vlan"),
        )
        for row in links
        if isinstance(row, Mapping)
    )
    _require(observed_links == EXPECTED_LINKS, "X3 topology link design drifted.")
    roles = context.get("observation_roles")
    _require(
        isinstance(roles, Mapping)
        and roles.get("source") == "hosta"
        and roles.get("destination") == "hostb"
        and tuple(roles.get("observers", ())) == ("sw1", "sw2"),
        "X3 topology observation roles drifted.",
    )
    _require(
        set(context.get("capabilities", ()))
        == {
            "l2_vlan",
            "bridge_vlan_json",
            "bridge_fdb_json",
            "active_l2_probe",
        },
        "X3 topology capabilities drifted.",
    )


def validate_x3_manifest(
    manifest: Mapping[str, Any],
    schema: Mapping[str, Any] | None = None,
) -> None:
    if schema is not None:
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(manifest),
            key=lambda error: tuple(str(part) for part in error.path),
        )
        if errors:
            raise X3GateError(
                "X3-R0 manifest schema validation failed: "
                + errors[0].message
            )

    _require(
        manifest.get("gate_id")
        == "x3_r0_layer2_vlan_design_runtime_gate_v1"
        and manifest.get("status") == "ACCEPTED_DESIGN_ONLY",
        "X3-R0 identity or design-only status drifted.",
    )
    track = manifest.get("track")
    _require(
        isinstance(track, Mapping)
        and track.get("parent_gate") == "x2_r5_addressing_closeout_v1"
        and track.get("phase9_status") == "P9_R1_PAUSED_BY_USER"
        and track.get("current_release")
        == "X3_R0_LAYER2_VLAN_DESIGN_GATE"
        and track.get("next_release") == "X3_R1_WRONG_ACCESS_VLAN",
        "X3-R0 track boundary drifted.",
    )
    source = manifest.get("source_boundary")
    _require(
        isinstance(source, Mapping)
        and source.get("parent_commit") == EXPECTED_PARENT_COMMIT
        and source.get("extension_policy") == "APPEND_ONLY"
        and source.get("runtime_inherited") is False,
        "X3-R0 source boundary drifted.",
    )
    compatibility = manifest.get("compatibility")
    _require(
        isinstance(compatibility, Mapping)
        and compatibility.get("frozen_baseline_mutation_allowed") is False
        and compatibility.get("accepted_x2_mutation_allowed") is False
        and compatibility.get("accepted_result_mutation_allowed") is False
        and compatibility.get("api_v1_status") == "FROZEN_BASELINE"
        and compatibility.get("future_extended_api") == "/api/v2"
        and compatibility.get("truth_model") == "SINGLE_FAULT_ONLY",
        "X3-R0 compatibility boundary drifted.",
    )

    authorization = manifest.get("runtime_authorization")
    _require(
        isinstance(authorization, Mapping)
        and tuple(authorization) == EXPECTED_RUNTIME_FLAGS
        and not any(authorization.values()),
        "X3-R0 cannot authorize runtime or scientific execution.",
    )
    feature_boundary = manifest.get("feature_boundary")
    _require(
        isinstance(feature_boundary, Mapping)
        and feature_boundary.get("catalog_id") == "x1_feature_catalog_v1"
        and feature_boundary.get("collector_id") == "l2_vlan_state_collector"
        and feature_boundary.get("collector_version") == 1
        and feature_boundary.get("collector_status") == "DESIGN_ONLY"
        and tuple(feature_boundary.get("required_feature_ids", ()))
        == EXPECTED_FEATURE_IDS,
        "The X3 Layer 2/VLAN feature boundary drifted.",
    )
    _require(
        manifest.get("baseline_signature") == EXPECTED_BASELINE_SIGNATURE,
        "The X3 baseline signature drifted.",
    )

    slices = manifest.get("l2_vlan_scope")
    _require(isinstance(slices, list), "X3 Layer 2/VLAN slices are missing.")
    observed_faults = tuple(
        (
            row.get("fault_code"),
            row.get("fault_type"),
            row.get("implementation_release"),
        )
        for row in slices
        if isinstance(row, Mapping)
    )
    _require(observed_faults == EXPECTED_FAULTS, "X3 fault order drifted.")
    _require(
        tuple(row.get("order") for row in slices) == (1, 2, 3, 4),
        "X3 slice order drifted.",
    )
    signature_keys: set[tuple[tuple[str, bool], ...]] = set()
    for row in slices:
        assert isinstance(row, Mapping)
        fault_type = str(row["fault_type"])
        signature = row.get("fault_signature")
        _require(
            signature == EXPECTED_SIGNATURES[fault_type],
            f"The {fault_type} signature drifted.",
        )
        signature_key = tuple(sorted(signature.items()))
        _require(
            signature_key not in signature_keys,
            "Layer 2/VLAN fault signatures must remain disjoint.",
        )
        signature_keys.add(signature_key)
        _require(
            tuple(row.get("required_feature_ids", ()))
            == EXPECTED_FEATURE_IDS,
            f"The {fault_type} rule uses unbound evidence.",
        )
        _require(
            row.get("category") == "l2_vlan"
            and row.get("recovery_intent_required") is True
            and row.get("idempotent_restoration_required") is True
            and row.get("real_e2e_required") is True
            and len(row.get("excluded_confounders", ())) >= 4,
            f"The {fault_type} safety boundary drifted.",
        )

    topology = manifest.get("topology_design")
    _require(
        isinstance(topology, Mapping)
        and topology.get("context_path") == TOPOLOGY_CONTEXT_PATH.as_posix()
        and topology.get("topology_id") == "X3_TOP_01_L2_VLAN"
        and topology.get("status") == "DESIGN_ONLY"
        and topology.get("switch_plane")
        == "LINUX_BRIDGE_VLAN_FILTERING"
        and topology.get("node_count") == 6
        and topology.get("link_count") == 5
        and tuple(topology.get("baseline_vlans", ())) == (10, 99),
        "X3 topology design boundary drifted.",
    )
    flows = topology.get("flow_roles")
    _require(isinstance(flows, list), "X3 flow roles are missing.")
    observed_flows = tuple(
        (
            row.get("flow_id"),
            row.get("source"),
            row.get("destination"),
            row.get("vlan_id"),
            row.get("trunk_encoding"),
        )
        for row in flows
        if isinstance(row, Mapping)
    )
    _require(
        observed_flows == EXPECTED_FLOWS,
        "X3 tagged/native test-flow separation drifted.",
    )

    releases = manifest.get("release_sequence")
    _require(isinstance(releases, list), "X3 release sequence is missing.")
    _require(
        tuple(row.get("release_id") for row in releases) == EXPECTED_RELEASES
        and releases[0].get("status") == "ACCEPTED_DESIGN_ONLY"
        and all(row.get("status") == "PLANNED" for row in releases[1:])
        and not any(row.get("runtime_inherited") for row in releases),
        "X3 release order or non-inherited runtime boundary drifted.",
    )
    _require(
        tuple(manifest.get("safety_invariants", ()))
        == EXPECTED_SAFETY_INVARIANTS,
        "X3 safety invariants drifted.",
    )
    evidence = manifest.get("evidence_policy")
    acceptance = manifest.get("acceptance")
    _require(
        isinstance(evidence, Mapping)
        and evidence.get("evidence_contract") == "Evidence v4"
        and evidence.get("real_evidence_required_per_runtime_slice") is True
        and evidence.get("connectivity_only_classification_forbidden") is True
        and evidence.get("r0_creates_empirical_evidence") is False
        and evidence.get("accepted_x2_evidence_read_only") is True
        and evidence.get("report_only_test_access_allowed") is False,
        "X3-R0 evidence boundary drifted.",
    )
    _require(
        isinstance(acceptance, Mapping)
        and acceptance.get("new_runtime_executed") is False
        and acceptance.get("new_empirical_claim_created") is False
        and acceptance.get("topology_context_validated") is True
        and acceptance.get("infrastructure_e2e_required_for_r0") is False
        and acceptance.get("frozen_artifacts_unchanged") is True
        and acceptance.get("explicit_gate_before_each_runtime_release") is True,
        "X3-R0 acceptance boundary drifted.",
    )


def verify_x3_gate(repository_root: Path) -> dict[str, Any]:
    root = Path(repository_root)
    manifest = _load_json(root / MANIFEST_PATH)
    schema = _load_json(root / MANIFEST_SCHEMA_PATH)
    validate_x3_manifest(manifest, schema)

    bindings = manifest["source_bindings"]
    assert isinstance(bindings, list)
    _require(
        len(bindings) == 11
        and len({row["binding_id"] for row in bindings}) == len(bindings)
        and len({row["path"] for row in bindings}) == len(bindings),
        "X3 requires 11 unique source bindings.",
    )
    for row in bindings:
        path = _safe_source_path(root, str(row["path"]))
        _require(
            _sha256(path) == row["sha256"],
            f"X3 source binding drifted: {row['path']}",
        )

    _require(
        verify_scope_gate(root)["status"] == "ACCEPTED_DESIGN_ONLY"
        and verify_x1_gate(root)["status"] == "ACCEPTED_CONTRACT_ONLY",
        "An X0/X1 parent gate is not accepted.",
    )
    _require(
        verify_x2_r5_source_gate(root)["status"]
        == "ACCEPTED_SOURCE_CLOSEOUT",
        "The X2-R5 parent closeout is not accepted.",
    )
    receipt = verify_x2_r5_receipt(
        root / X2_R5_RECEIPT_PATH,
        repository_root=root,
        verify_materialized=False,
    )
    _require(
        receipt.get("summary", {}).get("run_count") == 4,
        "The X2-R5 evidence receipt drifted.",
    )

    x0 = _load_json(root / X0_MANIFEST_PATH)
    x0_rows = {
        row["fault_type"]: row
        for row in x0["taxonomy"]["fault_types"]
        if row["target_phase"] == "X3"
    }
    _require(
        set(x0_rows) == {fault for _, fault, _ in EXPECTED_FAULTS},
        "X3 scope drifted from the canonical X0 taxonomy.",
    )
    for code, fault_type, _ in EXPECTED_FAULTS:
        row = x0_rows[fault_type]
        _require(
            row["code"] == code
            and row["category"] == "l2_vlan"
            and row["implementation_status"] == "MISSING",
            f"X3 taxonomy binding drifted: {fault_type}",
        )

    feature_catalog = _load_json(root / FEATURE_CATALOG_PATH)
    try:
        feature_index = validate_feature_catalog_v1(
            feature_catalog,
            repository_root=root,
        )
    except ExpansionContractError as error:
        raise X3GateError(str(error)) from error
    for feature_id in EXPECTED_FEATURE_IDS:
        row = feature_index[feature_id]
        _require(
            row["domain"] == "l2_vlan"
            and row["target_phase"] == "X3"
            and row["lifecycle"] == "PLANNED_EXTENSION",
            f"X3 feature lifecycle drifted: {feature_id}",
        )
    registry = build_x1_registry(feature_index)
    owner = next(
        spec
        for spec in registry.specs
        if spec.collector_id == "l2_vlan_state_collector"
    )
    _require(
        owner.feature_ids == EXPECTED_FEATURE_IDS
        and owner.required_capabilities == ("l2_vlan",)
        and owner.implementation_status == "DESIGN_ONLY"
        and owner.runtime_authorized is False,
        "The X1 Layer 2/VLAN collector must remain design-only at X3-R0.",
    )

    context = _load_json(root / TOPOLOGY_CONTEXT_PATH)
    try:
        validate_topology_context_v1(context, repository_root=root)
    except ExpansionContractError as error:
        raise X3GateError(str(error)) from error
    _validate_topology(context)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the X3-R0 Layer 2/VLAN design and runtime gate."
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    manifest = verify_x3_gate(arguments.repository_root)
    print("x3_r0_gate=VERIFIED")
    print("parent_commit=7949418_EXACT_PASS")
    print("x2_closeout=4/4_RECEIPT_BOUND_PASS")
    print("l2_vlan_scope=4_DISJOINT_SINGLE_FAULT_SLICES_PASS")
    print("topology_context=6_NODES_5_LINKS_TWO_FLOWS_PASS")
    print("collector=l2_vlan_state_collector_v1_DESIGN_ONLY_PASS")
    print("runtime_authorization=10/10_FALSE_PASS")
    print("new_empirical_evidence=ABSENT_PASS")
    print(f"next_release={manifest['track']['next_release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
