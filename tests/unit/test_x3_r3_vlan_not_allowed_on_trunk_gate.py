from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.expansion import x3_r3_gate
from src.expansion.x3_r3_gate import (
    EXPECTED_RUNTIME,
    EXPECTED_SAFETY,
    EXPECTED_SIGNATURE,
    X3R3GateError,
    validate_x3_r3_manifest,
    verify_x3_r3_gate,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "plans/expansion/X3_R3_VLAN_NOT_ALLOWED_ON_TRUNK_V1.json"
SCHEMA = ROOT / "schemas/x3_r3_vlan_not_allowed_on_trunk_gate_v1.schema.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_and_repository_gate_verify() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA))
    manifest = verify_x3_r3_gate(ROOT)
    assert manifest["status"] == "IMPLEMENTED_RUNTIME_SLICE"
    assert manifest["track"]["next_release"] == "X3_R4_NATIVE_VLAN_MISMATCH"


def test_runtime_scope_is_exact_and_not_inherited() -> None:
    manifest = _load(MANIFEST)
    assert manifest["runtime_authorization"] == EXPECTED_RUNTIME
    assert sum(EXPECTED_RUNTIME.values()) == 4
    assert manifest["source_boundary"]["runtime_inherited"] is False


def test_signature_and_safety_are_exact() -> None:
    manifest = _load(MANIFEST)
    assert manifest["slice"]["signature"] == EXPECTED_SIGNATURE
    assert tuple(manifest["safety"]["invariants"]) == EXPECTED_SAFETY
    assert manifest["slice"]["excluded_confounders"] == [
        "interface_down",
        "wrong_access_vlan",
        "vlan_missing",
        "native_vlan_mismatch",
    ]


def test_source_bindings_are_exact_unique_and_hash_bound() -> None:
    bindings = _load(MANIFEST)["source_bindings"]
    assert len(bindings) == 14
    assert len({row["binding_id"] for row in bindings}) == 14
    assert len({row["path"] for row in bindings}) == 14
    for row in bindings:
        path = ROOT / row["path"]
        assert path.is_file()
        assert not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]


def test_topology_is_real_two_switch_design_with_both_flows() -> None:
    topology = (ROOT / "labs/topologies/x3_r1_l2_vlan/topology.clab.yml").read_text(
        encoding="utf-8"
    )
    assert "name: x3r1" in topology
    assert "ip link add br0 type bridge vlan_filtering 1" in topology
    assert topology.count("bridge vlan add dev eth3 vid 10") == 2
    assert topology.count("bridge vlan add dev eth3 vid 99 pvid untagged") == 2
    assert "10.30.10.10/24" in topology and "10.30.10.20/24" in topology
    assert "10.30.99.10/24" in topology and "10.30.99.20/24" in topology


def test_collector_and_acceptance_boundaries_are_explicit() -> None:
    manifest = _load(MANIFEST)
    collector = manifest["collector_activation"]
    assert collector["collector_id"] == "l2_vlan_state_collector"
    assert collector["collector_version"] == 3
    assert collector["both_switches_observed"] is True
    assert collector["active_effectiveness_probe_required"] is True
    acceptance = manifest["acceptance"]
    assert acceptance["real_evidence_required"] is True
    assert acceptance["real_infrastructure_e2e_required"] is True
    assert acceptance["dataset_row_created"] is False
    assert acceptance["model_operation_performed"] is False
    assert acceptance["metric_created"] is False


@pytest.mark.parametrize(
    "mutation",
    ["runtime", "parent", "signature", "safety", "dataset"],
)
def test_semantic_gate_rejects_boundary_drift(mutation: str) -> None:
    manifest = copy.deepcopy(_load(MANIFEST))
    if mutation == "runtime":
        manifest["runtime_authorization"]["metric_calculation"] = True
    elif mutation == "parent":
        manifest["source_boundary"]["parent_commit"] = "0" * 40
    elif mutation == "signature":
        manifest["slice"]["signature"]["vlan_allowed_on_trunk"] = True
    elif mutation == "safety":
        manifest["safety"]["invariants"].pop()
    else:
        manifest["acceptance"]["dataset_row_created"] = True
    with pytest.raises(X3R3GateError):
        validate_x3_r3_manifest(manifest, _load(SCHEMA))


def test_repository_gate_rejects_source_hash_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = copy.deepcopy(_load(MANIFEST))
    manifest["source_bindings"][0]["sha256"] = "0" * 64
    original = x3_r3_gate._load

    def load(path: Path):
        if path == ROOT / x3_r3_gate.MANIFEST_PATH:
            return manifest
        return original(path)

    monkeypatch.setattr(x3_r3_gate, "_load", load)
    with pytest.raises(X3R3GateError, match="source binding drifted"):
        verify_x3_r3_gate(ROOT)


def test_runtime_modules_import_no_ml_dataset_or_report_code() -> None:
    blocked = ("joblib", "sklearn", "src.ml", "src.dataset", "src.evaluation", "src.phase8")
    paths = (
        "src/expansion/x3_vlan_not_allowed_on_trunk.py",
        "src/fault_injection/vlan_not_allowed_on_trunk.py",
        "src/collection/l2_vlan_state_collector_v3.py",
        "src/rules/l2_vlan_rule_engine_x3_r3.py",
        "src/orchestration/x3_vlan_not_allowed_on_trunk_experiment_runner.py",
    )
    for relative in paths:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        assert not any(
            name == prefix or name.startswith(prefix + ".")
            for name in modules
            for prefix in blocked
        )


def test_real_lifecycle_is_explicit_opt_in() -> None:
    text = (
        ROOT / "tests/e2e/test_x3_r3_vlan_not_allowed_on_trunk_containerlab.py"
    ).read_text(encoding="utf-8")
    assert "IND_RUN_X3_R3_E2E" in text
