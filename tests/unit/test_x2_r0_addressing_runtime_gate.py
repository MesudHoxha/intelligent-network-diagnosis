from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.expansion import x2_gate
from src.expansion.x2_gate import (
    EXPECTED_FAULTS,
    EXPECTED_FEATURE_IDS,
    EXPECTED_RELEASES,
    EXPECTED_RUNTIME_FLAGS,
    EXPECTED_SAFETY_INVARIANTS,
    EXPECTED_SIGNATURES,
    X2GateError,
    validate_x2_manifest,
    verify_x2_gate,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    ROOT / "plans/expansion/X2_R0_ADDRESSING_RUNTIME_GATE_V1.json"
)
SCHEMA_PATH = ROOT / "schemas/x2_addressing_runtime_gate_v1.schema.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_x2_r0_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA_PATH))


def test_x2_r0_manifest_and_repository_gate_verify() -> None:
    manifest = _load(MANIFEST_PATH)
    validate_x2_manifest(manifest, _load(SCHEMA_PATH))
    verified = verify_x2_gate(ROOT)
    assert verified["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verified["track"]["next_release"] == "X2_R1_WRONG_IP_ADDRESS"


def test_x2_scope_is_exact_and_ordered() -> None:
    slices = _load(MANIFEST_PATH)["addressing_scope"]
    assert tuple(
        (
            row["fault_code"],
            row["fault_type"],
            row["category"],
            row["implementation_release"],
        )
        for row in slices
    ) == EXPECTED_FAULTS
    assert tuple(row["order"] for row in slices) == (1, 2, 3, 4)


def test_addressing_signatures_are_exact_and_disjoint() -> None:
    slices = _load(MANIFEST_PATH)["addressing_scope"]
    signatures = []
    for row in slices:
        expected = EXPECTED_SIGNATURES[row["fault_type"]]
        assert row["fault_signature"] == expected
        assert set(row["required_feature_ids"]) == set(expected)
        signatures.append(tuple(sorted(expected.items())))
    assert len(signatures) == len(set(signatures)) == 4


def test_wrong_ip_changes_identity_without_conflating_prefix() -> None:
    signature = EXPECTED_SIGNATURES["wrong_ip_address"]
    assert signature == {
        "source_address_matches_expected": False,
        "source_prefix_matches_expected": True,
        "source_default_route_present": True,
        "duplicate_address_detected": False,
    }


def test_wrong_mask_preserves_address_identity() -> None:
    signature = EXPECTED_SIGNATURES["wrong_subnet_mask"]
    assert signature["source_address_matches_expected"] is True
    assert signature["source_prefix_matches_expected"] is False
    assert signature["source_default_route_present"] is True


def test_missing_default_route_is_not_wrong_default_gateway() -> None:
    manifest = _load(MANIFEST_PATH)
    row = next(
        value
        for value in manifest["addressing_scope"]
        if value["fault_type"] == "missing_default_route"
    )
    assert row["fault_signature"]["source_default_route_present"] is False
    assert "wrong_default_gateway" in row["excluded_confounders"]
    assert row["injector_mechanism"] == "delete_exact_source_default_route"


def test_duplicate_ip_requires_active_and_temporal_evidence() -> None:
    manifest = _load(MANIFEST_PATH)
    duplicate = manifest["addressing_scope"][-1]
    assert duplicate["required_evidence_modes"] == [
        "ACTIVE_DUPLICATE_CHECK",
        "TEMPORAL_NEIGHBOR_OBSERVATION",
    ]
    assert duplicate["fault_signature"]["duplicate_address_detected"] is True
    assert (
        duplicate["fault_signature"][
            "duplicate_address_mac_churn_detected"
        ]
        is True
    )


def test_every_slice_requires_recovery_restoration_and_real_e2e() -> None:
    for row in _load(MANIFEST_PATH)["addressing_scope"]:
        assert row["recovery_intent_required"] is True
        assert row["idempotent_restoration_required"] is True
        assert row["real_e2e_required"] is True
        assert len(row["excluded_confounders"]) >= 2


def test_feature_boundary_is_the_exact_x1_addressing_set() -> None:
    boundary = _load(MANIFEST_PATH)["feature_boundary"]
    assert tuple(boundary["required_feature_ids"]) == EXPECTED_FEATURE_IDS
    assert boundary["collector_status"] == "DESIGN_ONLY"


def test_release_order_is_small_and_runtime_is_not_inherited() -> None:
    releases = _load(MANIFEST_PATH)["release_sequence"]
    assert tuple(row["release_id"] for row in releases) == EXPECTED_RELEASES
    assert releases[0]["status"] == "ACCEPTED_DESIGN_ONLY"
    assert all(row["status"] == "PLANNED" for row in releases[1:])
    assert not any(row["runtime_inherited"] for row in releases)


def test_x2_r0_runtime_authorization_is_completely_false() -> None:
    authorization = _load(MANIFEST_PATH)["runtime_authorization"]
    assert tuple(authorization) == EXPECTED_RUNTIME_FLAGS
    assert not any(authorization.values())


def test_x2_r0_creates_no_runtime_or_empirical_claim() -> None:
    manifest = _load(MANIFEST_PATH)
    assert manifest["evidence_policy"]["r0_creates_empirical_evidence"] is False
    assert manifest["acceptance"]["new_runtime_executed"] is False
    assert manifest["acceptance"]["new_empirical_claim_created"] is False
    assert manifest["acceptance"]["infrastructure_e2e_required_for_r0"] is False


def test_source_bindings_are_unique_and_hash_bound() -> None:
    bindings = _load(MANIFEST_PATH)["source_bindings"]
    assert len(bindings) == len({row["binding_id"] for row in bindings}) == 8
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
        "duplicate_signal",
        "signature_conflation",
        "release_order",
        "accepted_result_mutation",
    ],
)
def test_semantic_gate_fails_closed_on_design_drift(mutation: str) -> None:
    manifest = copy.deepcopy(_load(MANIFEST_PATH))
    if mutation == "status":
        manifest["status"] = "RUNTIME_AUTHORIZED"
    elif mutation == "runtime_authorization":
        manifest["runtime_authorization"]["network_mutation"] = True
    elif mutation == "duplicate_signal":
        del manifest["addressing_scope"][-1]["fault_signature"][
            "duplicate_address_mac_churn_detected"
        ]
        manifest["addressing_scope"][-1]["required_feature_ids"].remove(
            "duplicate_address_mac_churn_detected"
        )
    elif mutation == "signature_conflation":
        manifest["addressing_scope"][1]["fault_signature"] = copy.deepcopy(
            manifest["addressing_scope"][0]["fault_signature"]
        )
    elif mutation == "release_order":
        manifest["release_sequence"][1:3] = reversed(
            manifest["release_sequence"][1:3]
        )
    else:
        manifest["compatibility"]["accepted_result_mutation_allowed"] = True

    with pytest.raises(X2GateError):
        validate_x2_manifest(manifest, _load(SCHEMA_PATH))


def test_repository_gate_rejects_source_hash_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = copy.deepcopy(_load(MANIFEST_PATH))
    manifest["source_bindings"][0]["sha256"] = "0" * 64
    original_load = x2_gate._load_json

    def load(path: Path):
        if path == ROOT / x2_gate.MANIFEST_PATH:
            return manifest
        return original_load(path)

    monkeypatch.setattr(x2_gate, "_load_json", load)
    with pytest.raises(X2GateError, match="source binding drifted"):
        verify_x2_gate(ROOT)


def test_x2_gate_imports_no_runtime_mutation_or_model_modules() -> None:
    source = (ROOT / "src/expansion/x2_gate.py").read_text(encoding="utf-8")
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


def test_central_documents_record_x2_r0_and_keep_p9_paused() -> None:
    paths = (
        "docs/DECISIONS.md",
        "docs/MASTER_CONTEXT.md",
        "docs/ROADMAP.md",
        "docs/STATUS.md",
        "docs/X2_R0_ADDRESSING_RUNTIME_GATE.md",
        "docs/HANDOFF_X2_R0.md",
    )
    for relative in paths:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "X2-R0" in text
        assert "P9-R1" in text
    assert "D-100" in (ROOT / "docs/DECISIONS.md").read_text(
        encoding="utf-8"
    )
