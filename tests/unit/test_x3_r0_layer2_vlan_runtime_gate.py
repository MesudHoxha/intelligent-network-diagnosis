from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.contracts.expansion import validate_topology_context_v1
from src.expansion import x3_gate
from src.expansion.x3_gate import (
    EXPECTED_BASELINE_SIGNATURE,
    EXPECTED_FAULTS,
    EXPECTED_FEATURE_IDS,
    EXPECTED_FLOWS,
    EXPECTED_LINKS,
    EXPECTED_NODES,
    EXPECTED_RELEASES,
    EXPECTED_RUNTIME_FLAGS,
    EXPECTED_SAFETY_INVARIANTS,
    EXPECTED_SIGNATURES,
    X3GateError,
    _validate_topology,
    validate_x3_manifest,
    verify_x3_gate,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    ROOT / "plans/expansion/X3_R0_LAYER2_VLAN_RUNTIME_GATE_V1.json"
)
SCHEMA_PATH = ROOT / "schemas/x3_layer2_vlan_runtime_gate_v1.schema.json"
TOPOLOGY_PATH = (
    ROOT / "labs/topologies/x3_r1_l2_vlan/topology_context_v1.json"
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_x3_r0_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA_PATH))


def test_x3_r0_manifest_and_repository_gate_verify() -> None:
    manifest = _load(MANIFEST_PATH)
    validate_x3_manifest(manifest, _load(SCHEMA_PATH))
    verified = verify_x3_gate(ROOT)
    assert verified["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verified["track"]["next_release"] == "X3_R1_WRONG_ACCESS_VLAN"


def test_x3_scope_is_exact_and_ordered() -> None:
    slices = _load(MANIFEST_PATH)["l2_vlan_scope"]
    assert tuple(
        (
            row["fault_code"],
            row["fault_type"],
            row["implementation_release"],
        )
        for row in slices
    ) == EXPECTED_FAULTS
    assert tuple(row["order"] for row in slices) == (1, 2, 3, 4)


def test_l2_vlan_signatures_are_exact_and_disjoint() -> None:
    manifest = _load(MANIFEST_PATH)
    assert manifest["baseline_signature"] == EXPECTED_BASELINE_SIGNATURE
    signatures = []
    for row in manifest["l2_vlan_scope"]:
        expected = EXPECTED_SIGNATURES[row["fault_type"]]
        assert row["fault_signature"] == expected
        assert tuple(row["required_feature_ids"]) == EXPECTED_FEATURE_IDS
        signatures.append(tuple(sorted(expected.items())))
    assert len(signatures) == len(set(signatures)) == 4


def test_wrong_access_vlan_is_not_a_trunk_or_native_fault() -> None:
    signature = EXPECTED_SIGNATURES["wrong_access_vlan"]
    assert signature["access_vlan_matches_expected"] is False
    assert signature["vlan_exists_on_target"] is True
    assert signature["vlan_allowed_on_trunk"] is True
    assert signature["native_vlan_matches_peer"] is True


def test_vlan_missing_has_direct_negative_vlan_inventory_evidence() -> None:
    signature = EXPECTED_SIGNATURES["vlan_missing"]
    assert signature["vlan_exists_on_target"] is False
    assert signature["access_vlan_matches_expected"] is False
    assert signature["vlan_allowed_on_trunk"] is False


def test_trunk_allow_fault_preserves_access_and_local_fdb_state() -> None:
    signature = EXPECTED_SIGNATURES["vlan_not_allowed_on_trunk"]
    assert signature["access_vlan_matches_expected"] is True
    assert signature["vlan_exists_on_target"] is True
    assert signature["vlan_allowed_on_trunk"] is False
    assert signature["fdb_location_matches_expected"] is True


def test_native_mismatch_requires_peer_comparison_and_separate_flow() -> None:
    manifest = _load(MANIFEST_PATH)
    row = manifest["l2_vlan_scope"][-1]
    assert row["fault_type"] == "native_vlan_mismatch"
    assert row["fault_signature"]["native_vlan_matches_peer"] is False
    assert "PEER_NATIVE_VLAN_COMPARISON" in row["required_evidence_modes"]
    assert tuple(
        (
            flow["flow_id"],
            flow["source"],
            flow["destination"],
            flow["vlan_id"],
            flow["trunk_encoding"],
        )
        for flow in manifest["topology_design"]["flow_roles"]
    ) == EXPECTED_FLOWS


def test_topology_context_is_valid_and_exact() -> None:
    context = _load(TOPOLOGY_PATH)
    validate_topology_context_v1(context, repository_root=ROOT)
    _validate_topology(context)
    assert tuple((row["node_id"], row["role"]) for row in context["nodes"]) == (
        EXPECTED_NODES
    )
    observed_links = tuple(
        (
            row["link_id"],
            row["kind"],
            tuple(endpoint["node_id"] for endpoint in row["endpoints"]),
            tuple(row["expected_vlans"]),
            row["native_vlan"],
        )
        for row in context["links"]
    )
    assert observed_links == EXPECTED_LINKS


def test_topology_uses_tagged_vlan_10_and_native_vlan_99() -> None:
    context = _load(TOPOLOGY_PATH)
    trunk = next(row for row in context["links"] if row["kind"] == "trunk")
    assert trunk["expected_vlans"] == [10, 99]
    assert trunk["native_vlan"] == 99
    design = _load(MANIFEST_PATH)["topology_design"]
    assert design["controlled_vlan_values"] == {
        "wrong_access_vlan": 20,
        "mismatched_native_vlan": 98,
    }


def test_every_slice_requires_recovery_restoration_and_real_e2e() -> None:
    for row in _load(MANIFEST_PATH)["l2_vlan_scope"]:
        assert row["recovery_intent_required"] is True
        assert row["idempotent_restoration_required"] is True
        assert row["real_e2e_required"] is True
        assert "interface_down" in row["excluded_confounders"]


def test_feature_boundary_is_the_exact_x1_l2_vlan_set() -> None:
    boundary = _load(MANIFEST_PATH)["feature_boundary"]
    assert tuple(boundary["required_feature_ids"]) == EXPECTED_FEATURE_IDS
    assert boundary["collector_id"] == "l2_vlan_state_collector"
    assert boundary["collector_status"] == "DESIGN_ONLY"


def test_release_order_is_small_and_runtime_is_not_inherited() -> None:
    releases = _load(MANIFEST_PATH)["release_sequence"]
    assert tuple(row["release_id"] for row in releases) == EXPECTED_RELEASES
    assert releases[0]["status"] == "ACCEPTED_DESIGN_ONLY"
    assert all(row["status"] == "PLANNED" for row in releases[1:])
    assert not any(row["runtime_inherited"] for row in releases)


def test_x3_r0_runtime_authorization_is_completely_false() -> None:
    authorization = _load(MANIFEST_PATH)["runtime_authorization"]
    assert tuple(authorization) == EXPECTED_RUNTIME_FLAGS
    assert not any(authorization.values())


def test_x3_r0_creates_no_runtime_or_empirical_claim() -> None:
    manifest = _load(MANIFEST_PATH)
    assert manifest["evidence_policy"]["r0_creates_empirical_evidence"] is False
    assert manifest["acceptance"]["new_runtime_executed"] is False
    assert manifest["acceptance"]["new_empirical_claim_created"] is False
    assert manifest["acceptance"]["infrastructure_e2e_required_for_r0"] is False
    assert "that the X3 topology has executed" in (
        manifest["claim_boundary"]["does_not_prove"]
    )


def test_source_bindings_are_unique_and_hash_bound() -> None:
    bindings = _load(MANIFEST_PATH)["source_bindings"]
    assert len(bindings) == len({row["binding_id"] for row in bindings}) == 11
    assert len({row["path"] for row in bindings}) == 11
    for row in bindings:
        path = ROOT / row["path"]
        assert path.is_file()
        assert not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]


def test_safety_invariants_are_exact() -> None:
    assert tuple(_load(MANIFEST_PATH)["safety_invariants"]) == (
        EXPECTED_SAFETY_INVARIANTS
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "status",
        "runtime_authorization",
        "signature_conflation",
        "release_order",
        "accepted_x2_mutation",
        "connectivity_only",
        "flow_conflation",
    ],
)
def test_semantic_gate_fails_closed_on_design_drift(mutation: str) -> None:
    manifest = copy.deepcopy(_load(MANIFEST_PATH))
    if mutation == "status":
        manifest["status"] = "RUNTIME_AUTHORIZED"
    elif mutation == "runtime_authorization":
        manifest["runtime_authorization"]["network_mutation"] = True
    elif mutation == "signature_conflation":
        manifest["l2_vlan_scope"][1]["fault_signature"] = copy.deepcopy(
            manifest["l2_vlan_scope"][0]["fault_signature"]
        )
    elif mutation == "release_order":
        manifest["release_sequence"][1:3] = reversed(
            manifest["release_sequence"][1:3]
        )
    elif mutation == "accepted_x2_mutation":
        manifest["compatibility"]["accepted_x2_mutation_allowed"] = True
    elif mutation == "connectivity_only":
        manifest["evidence_policy"][
            "connectivity_only_classification_forbidden"
        ] = False
    else:
        manifest["topology_design"]["flow_roles"][1] = copy.deepcopy(
            manifest["topology_design"]["flow_roles"][0]
        )

    with pytest.raises(X3GateError):
        validate_x3_manifest(manifest, _load(SCHEMA_PATH))


def test_repository_gate_rejects_source_hash_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = copy.deepcopy(_load(MANIFEST_PATH))
    manifest["source_bindings"][0]["sha256"] = "0" * 64
    original_load = x3_gate._load_json

    def load(path: Path):
        if path == ROOT / x3_gate.MANIFEST_PATH:
            return manifest
        return original_load(path)

    monkeypatch.setattr(x3_gate, "_load_json", load)
    with pytest.raises(X3GateError, match="source binding drifted"):
        verify_x3_gate(ROOT)


def test_topology_semantics_fail_closed_on_native_vlan_drift() -> None:
    context = copy.deepcopy(_load(TOPOLOGY_PATH))
    context["links"][2]["native_vlan"] = 98
    with pytest.raises(X3GateError, match="link design drifted"):
        _validate_topology(context)


def test_x3_gate_imports_no_runtime_mutation_or_model_modules() -> None:
    source = (ROOT / "src/expansion/x3_gate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert not any(
        name == blocked or name.startswith(blocked + ".")
        for name in modules
        for blocked in (
            "subprocess",
            "docker",
            "joblib",
            "sklearn",
            "src.fault_injection",
            "src.orchestration",
        )
    )


def test_central_documents_record_x3_r0_and_keep_p9_paused() -> None:
    paths = (
        "docs/DECISIONS.md",
        "docs/MASTER_CONTEXT.md",
        "docs/ROADMAP.md",
        "docs/STATUS.md",
        "docs/X3_R0_LAYER2_VLAN_RUNTIME_GATE.md",
        "docs/HANDOFF_X3_R0.md",
    )
    for relative in paths:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "X3-R0" in text
        assert "P9-R1" in text
    assert "D-X3-R0" in (ROOT / "docs/DECISIONS.md").read_text(
        encoding="utf-8"
    )
