from __future__ import annotations

import json
from pathlib import Path

from src.collection.modular_registry import build_x1_registry
from src.contracts.expansion import validate_feature_catalog_v1
from src.expansion.scope_gate import verify_scope_gate
from src.expansion.x1_gate import verify_x1_gate
from src.expansion.x2_gate import EXPECTED_FEATURE_IDS, verify_x2_gate


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_x0_x1_and_x2_r0_gates_compose_read_only() -> None:
    assert verify_scope_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x1_gate(ROOT)["status"] == "ACCEPTED_CONTRACT_ONLY"
    assert verify_x2_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"


def test_x2_features_are_owned_once_by_the_design_only_addressing_collector() -> None:
    catalog = _load("plans/expansion/X1_FEATURE_CATALOG_V1.json")
    index = validate_feature_catalog_v1(catalog, repository_root=ROOT)
    registry = build_x1_registry(index)
    owner = next(
        spec
        for spec in registry.specs
        if spec.collector_id == "addressing_state_collector"
    )
    assert owner.feature_ids == EXPECTED_FEATURE_IDS
    assert owner.implementation_status == "DESIGN_ONLY"
    assert owner.runtime_authorized is False


def test_runtime_remains_false_across_all_three_expansion_gates() -> None:
    paths = (
        "plans/expansion/X0_SCOPE_COMPATIBILITY_FREEZE_V1.json",
        "plans/expansion/X1_EXTENDED_CONTRACTS_MODULAR_COLLECTION_V1.json",
        "plans/expansion/X2_R0_ADDRESSING_RUNTIME_GATE_V1.json",
    )
    for path in paths:
        authorization = _load(path)["runtime_authorization"]
        assert len(authorization) == 10
        assert not any(authorization.values())


def test_each_runtime_slice_requires_a_new_non_inherited_gate() -> None:
    manifest = _load("plans/expansion/X2_R0_ADDRESSING_RUNTIME_GATE_V1.json")
    releases = manifest["release_sequence"]
    assert all(row["runtime_inherited"] is False for row in releases)
    assert manifest["acceptance"]["explicit_gate_before_each_runtime_release"] is True
    assert all(row["real_e2e_required"] is True for row in manifest["addressing_scope"])
