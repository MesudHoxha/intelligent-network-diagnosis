from __future__ import annotations

import json
from pathlib import Path

from src.collection.modular_registry import build_x1_registry
from src.contracts.expansion import (
    validate_feature_catalog_v1,
    validate_topology_context_v1,
)
from src.expansion.scope_gate import verify_scope_gate
from src.expansion.x1_gate import verify_x1_gate
from src.expansion.x2_r5_gate import (
    verify_x2_r5_receipt,
    verify_x2_r5_source_gate,
)
from src.expansion.x3_gate import EXPECTED_FEATURE_IDS, verify_x3_gate


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_x0_x1_x2_closeout_and_x3_r0_compose_read_only() -> None:
    assert verify_scope_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x1_gate(ROOT)["status"] == "ACCEPTED_CONTRACT_ONLY"
    assert (
        verify_x2_r5_source_gate(ROOT)["status"]
        == "ACCEPTED_SOURCE_CLOSEOUT"
    )
    receipt = verify_x2_r5_receipt(
        ROOT / "plans/expansion/X2_R5_ADDRESSING_EVIDENCE_RECEIPT_V1.json",
        repository_root=ROOT,
    )
    assert receipt["summary"]["run_count"] == 4
    assert verify_x3_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"


def test_x3_features_are_owned_once_by_design_only_l2_collector() -> None:
    catalog = _load("plans/expansion/X1_FEATURE_CATALOG_V1.json")
    index = validate_feature_catalog_v1(catalog, repository_root=ROOT)
    registry = build_x1_registry(index)
    owner = next(
        spec
        for spec in registry.specs
        if spec.collector_id == "l2_vlan_state_collector"
    )
    assert owner.feature_ids == EXPECTED_FEATURE_IDS
    assert owner.required_capabilities == ("l2_vlan",)
    assert owner.implementation_status == "DESIGN_ONLY"
    assert owner.runtime_authorized is False


def test_x3_topology_context_and_collector_capability_compose() -> None:
    context = _load(
        "labs/topologies/x3_r1_l2_vlan/topology_context_v1.json"
    )
    validate_topology_context_v1(context, repository_root=ROOT)
    catalog = _load("plans/expansion/X1_FEATURE_CATALOG_V1.json")
    index = validate_feature_catalog_v1(catalog, repository_root=ROOT)
    plan = build_x1_registry(index).plan(
        EXPECTED_FEATURE_IDS,
        context["capabilities"],
    )
    assert plan.collector_keys == ("l2_vlan_state_collector:v1",)
    assert plan.capability_gaps == {}
    assert plan.runtime_authorized is False


def test_runtime_remains_false_across_x0_x1_x2_closeout_and_x3() -> None:
    paths = (
        "plans/expansion/X0_SCOPE_COMPATIBILITY_FREEZE_V1.json",
        "plans/expansion/X1_EXTENDED_CONTRACTS_MODULAR_COLLECTION_V1.json",
        "plans/expansion/X2_R5_ADDRESSING_CLOSEOUT_V1.json",
        "plans/expansion/X3_R0_LAYER2_VLAN_RUNTIME_GATE_V1.json",
    )
    for path in paths:
        authorization = _load(path)["runtime_authorization"]
        assert len(authorization) == 10
        assert not any(authorization.values())


def test_each_x3_runtime_slice_requires_a_new_non_inherited_gate() -> None:
    manifest = _load(
        "plans/expansion/X3_R0_LAYER2_VLAN_RUNTIME_GATE_V1.json"
    )
    releases = manifest["release_sequence"]
    assert all(row["runtime_inherited"] is False for row in releases)
    assert manifest["source_boundary"]["runtime_inherited"] is False
    assert manifest["acceptance"]["explicit_gate_before_each_runtime_release"] is True
    assert all(row["real_e2e_required"] is True for row in manifest["l2_vlan_scope"])
