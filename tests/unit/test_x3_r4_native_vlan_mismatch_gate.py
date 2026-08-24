from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.expansion.x3_r4_gate import EXPECTED_RUNTIME, EXPECTED_SAFETY, EXPECTED_SIGNATURE, X3R4GateError, validate_x3_r4_manifest, verify_x3_r4_gate


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "plans/expansion/X3_R4_NATIVE_VLAN_MISMATCH_V1.json"
SCHEMA = ROOT / "schemas/x3_r4_native_vlan_mismatch_gate_v1.schema.json"

def _load(path: Path) -> dict[str, object]: return json.loads(path.read_text(encoding="utf-8"))

def test_schema_gate_and_native_context_verify() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA))
    manifest = verify_x3_r4_gate(ROOT)
    assert manifest["track"]["next_release"] == "X3_R5_LAYER2_VLAN_CLOSEOUT"
    assert manifest["slice"]["topology_context_path"].endswith("topology_context_native_flow_v1.json")

def test_exact_boundary_signature_and_hashes() -> None:
    manifest = _load(MANIFEST)
    assert manifest["runtime_authorization"] == EXPECTED_RUNTIME and sum(EXPECTED_RUNTIME.values()) == 4
    assert manifest["slice"]["signature"] == EXPECTED_SIGNATURE
    assert tuple(manifest["safety"]["invariants"]) == EXPECTED_SAFETY
    assert len(manifest["source_bindings"]) == 15
    for row in manifest["source_bindings"]:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]

@pytest.mark.parametrize("mutation", ["runtime", "parent", "signature", "safety", "dataset"])
def test_semantic_gate_rejects_boundary_drift(mutation: str) -> None:
    manifest = copy.deepcopy(_load(MANIFEST))
    if mutation == "runtime": manifest["runtime_authorization"]["metric_calculation"] = True
    elif mutation == "parent": manifest["source_boundary"]["parent_commit"] = "0" * 40
    elif mutation == "signature": manifest["slice"]["signature"]["native_vlan_matches_peer"] = True
    elif mutation == "safety": manifest["safety"]["invariants"].pop()
    else: manifest["acceptance"]["dataset_row_created"] = True
    with pytest.raises(X3R4GateError): validate_x3_r4_manifest(manifest, _load(SCHEMA))
