from __future__ import annotations

import ast
import copy
import json
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.expansion.scope_gate import (
    EXPECTED_BASELINE_CLASS_ORDER,
    EXPECTED_FAULT_TYPES,
    EXPECTED_PHASES,
    EXPECTED_PROTECTED_CONTRACTS,
    ExpansionScopeError,
    validate_scope_manifest,
    verify_scope_gate,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    ROOT / "plans/expansion/X0_SCOPE_COMPATIBILITY_FREEZE_V1.json"
)
SCHEMA_PATH = ROOT / "schemas/x0_scope_compatibility_freeze_v1.schema.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_x0_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA_PATH))


def test_x0_manifest_validates_against_schema_and_semantics() -> None:
    manifest = _load(MANIFEST_PATH)
    validate_scope_manifest(manifest, _load(SCHEMA_PATH))


def test_x0_tracked_gate_verifies_with_protected_contracts_present() -> None:
    manifest = verify_scope_gate(ROOT)
    assert manifest["gate_id"] == "x0_scope_compatibility_freeze_v1"
    assert manifest["status"] == "ACCEPTED_DESIGN_ONLY"


def test_document_taxonomy_discrepancy_is_resolved_explicitly() -> None:
    vision = _load(MANIFEST_PATH)["vision_source"]
    assert vision == {
        "document_role": "INTENDED_TECHNICAL_VISION_AND_SCOPE",
        "detailed_fault_type_count": 24,
        "prioritization_claimed_count": 23,
        "omitted_from_prioritization": ["vlan_missing"],
        "resolution": "INCLUDE_ALL_24_DETAILED_FAULT_TYPES",
    }


def test_canonical_fault_taxonomy_has_exact_domain_and_status_counts() -> None:
    rows = _load(MANIFEST_PATH)["taxonomy"]["fault_types"]
    assert len(rows) == 24
    assert Counter(row["category"] for row in rows) == {
        "addressing": 4,
        "l2_vlan": 5,
        "routing": 5,
        "services": 4,
        "security": 2,
        "performance": 4,
    }
    assert Counter(row["implementation_status"] for row in rows) == {
        "FROZEN_IMPLEMENTED": 5,
        "PARTIAL_MECHANISM_ONLY": 1,
        "MISSING": 18,
    }


def test_canonical_fault_rows_remain_exact_and_ordered() -> None:
    rows = _load(MANIFEST_PATH)["taxonomy"]["fault_types"]
    actual = tuple(
        (
            row["code"],
            row["fault_type"],
            row["category"],
            row["implementation_status"],
            row["target_phase"],
        )
        for row in rows
    )
    assert actual == EXPECTED_FAULT_TYPES


def test_phase6_baseline_class_order_and_contracts_are_immutable() -> None:
    baseline = _load(MANIFEST_PATH)["baseline_boundary"]
    assert tuple(baseline["immutable_class_order"]) == (
        EXPECTED_BASELINE_CLASS_ORDER
    )
    assert tuple(baseline["protected_contract_paths"]) == (
        EXPECTED_PROTECTED_CONTRACTS
    )
    assert baseline["accepted_artifact_mutation_allowed"] is False
    assert baseline["consumed_test_reuse_for_selection_allowed"] is False


def test_new_contracts_are_versioned_without_overwriting_v3() -> None:
    policy = _load(MANIFEST_PATH)["architecture_policy"]
    assert policy["new_single_fault_contracts"] == [
        "Topology Context v1",
        "Evidence v4",
        "Feature Catalog v1",
        "Feature Vector v2",
        "Dataset Row v4",
        "Diagnosis Result v2",
        "Evidence Mask Plan v2",
    ]
    assert policy["multiple_fault_contracts"] == [
        "Dataset Row v5",
        "Diagnosis Result v3",
    ]


def test_x0_to_x10_roadmap_is_ordered_and_not_prematurely_authorized() -> None:
    roadmap = _load(MANIFEST_PATH)["roadmap"]
    assert tuple((row["phase_id"], row["status"]) for row in roadmap) == (
        EXPECTED_PHASES
    )
    assert all(row["runtime_authorized_now"] is False for row in roadmap)
    assert all(
        row["future_runtime_requires_separate_gate"] is True
        for row in roadmap
    )


def test_priority_domains_and_objective_hybrid_boundary_remain_visible() -> None:
    manifest = _load(MANIFEST_PATH)
    roadmap_text = " ".join(
        row["title"] + " " + row["objective"]
        for row in manifest["roadmap"]
    ).lower()
    for required in ("vlan", "dhcp", "dns", "ospf", "performance", "multiple"):
        assert required in roadmap_text
    policy = manifest["architecture_policy"]
    assert policy["hybrid_claim_policy"] == (
        "OBJECTIVE_COMPARISON_NO_REQUIRED_WINNER"
    )


def test_multiple_fault_scope_is_bounded_and_identifiability_gated() -> None:
    pairs = _load(MANIFEST_PATH)["release_gates"][
        "multiple_fault_pair_policy"
    ]
    assert pairs == {
        "cartesian_product_allowed": False,
        "minimum_selected_pairs": 6,
        "maximum_selected_pairs": 10,
        "initial_pilot_pairs": 2,
        "identifiability_gate_required": True,
    }


def test_x0_runtime_authorization_is_completely_false() -> None:
    authorization = _load(MANIFEST_PATH)["runtime_authorization"]
    assert len(authorization) == 10
    assert not any(authorization.values())


def test_change_control_allows_evolution_but_not_baseline_drift() -> None:
    control = _load(MANIFEST_PATH)["change_control"]
    assert control["future_technical_changes_allowed"] is True
    assert control["frozen_baseline_changes_allowed"] is False
    assert control["scientific_result_changes_allowed"] is False
    assert "VERSIONED_CONTRACT_WHEN_SEMANTICS_CHANGE" in control[
        "required_conditions"
    ]
    assert "NO_REPORT_ONLY_TEST_LEAKAGE" in control["required_conditions"]


@pytest.mark.parametrize(
    "mutation",
    [
        "baseline_class_order",
        "missing_fault_type",
        "runtime_authorization",
    ],
)
def test_semantic_validator_fails_closed_on_scope_drift(
    mutation: str,
) -> None:
    manifest = copy.deepcopy(_load(MANIFEST_PATH))
    if mutation == "baseline_class_order":
        manifest["baseline_boundary"]["immutable_class_order"].reverse()
    elif mutation == "missing_fault_type":
        manifest["taxonomy"]["fault_types"].pop()
    else:
        manifest["runtime_authorization"]["network_mutation"] = True

    with pytest.raises(ExpansionScopeError):
        validate_scope_manifest(manifest)


def test_scope_gate_imports_no_runtime_or_model_execution_modules() -> None:
    source = (ROOT / "src/expansion/scope_gate.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots.isdisjoint(
        {"joblib", "sklearn", "subprocess", "docker", "src"}
    )


def test_central_documents_record_x0_and_keep_p9_r1_paused() -> None:
    decision = (ROOT / "docs/DECISIONS.md").read_text(encoding="utf-8")
    status = (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
    master = (ROOT / "docs/MASTER_CONTEXT.md").read_text(encoding="utf-8")
    handoff = (ROOT / "docs/HANDOFF_X0.md").read_text(encoding="utf-8")

    for text in (decision, status, roadmap, master, handoff):
        assert "X0" in text
        assert "P9-R1" in text
    assert "D-098" in decision
    assert "X1" in status
    assert "X10" in roadmap
