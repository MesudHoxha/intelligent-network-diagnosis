from __future__ import annotations

import ast
import json
from pathlib import Path

from src.expansion.scope_gate import verify_scope_gate
from src.expansion.x1_gate import verify_x1_gate
from src.expansion.x2_gate import verify_x2_gate
from src.expansion.x2_r1_gate import EXPECTED_RUNTIME, verify_x2_r1_gate


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str) -> dict[str, object]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_x0_x1_x2_r0_and_x2_r1_gates_compose_append_only() -> None:
    assert verify_scope_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x1_gate(ROOT)["status"] == "ACCEPTED_CONTRACT_ONLY"
    assert verify_x2_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x2_r1_gate(ROOT)["status"] == "IMPLEMENTED_RUNTIME_SLICE"


def test_runtime_is_scoped_to_wrong_ip_only() -> None:
    manifest = _load("plans/expansion/X2_R1_WRONG_IP_ADDRESS_V1.json")
    assert manifest["runtime_authorization"] == EXPECTED_RUNTIME
    assert sum(manifest["runtime_authorization"].values()) == 4
    assert manifest["slice"]["fault_type"] == "wrong_ip_address"
    assert manifest["track"]["next_release"] == "X2_R2_WRONG_SUBNET_MASK"


def test_frozen_baseline_and_scientific_operations_remain_outside_x2_r1() -> None:
    manifest = _load("plans/expansion/X2_R1_WRONG_IP_ADDRESS_V1.json")
    compatibility = manifest["compatibility"]
    assert compatibility["phase6_evidence_v3"] == "UNCHANGED"
    assert compatibility["phase6_dataset_row_v3"] == "UNCHANGED"
    assert compatibility["accepted_results"] == "UNCHANGED"
    assert compatibility["api_v1"] == "UNCHANGED"
    assert manifest["acceptance"]["dataset_row_created"] is False
    assert manifest["acceptance"]["model_operation_performed"] is False
    assert manifest["acceptance"]["metric_created"] is False


def test_x2_r1_runtime_imports_no_ml_dataset_or_report_only_modules() -> None:
    paths = (
        "src/collection/addressing_state_collector.py",
        "src/rules/addressing_rule_engine_v2.py",
        "src/fault_injection/wrong_ip_address.py",
        "src/orchestration/x2_addressing_experiment_runner.py",
    )
    blocked = (
        "joblib",
        "sklearn",
        "src.ml",
        "src.dataset",
        "src.evaluation",
        "src.phase8",
    )
    for relative in paths:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any(
            name == prefix or name.startswith(prefix + ".")
            for name in imported
            for prefix in blocked
        )


def test_both_real_lifecycle_tests_remain_explicit_and_opt_in() -> None:
    old = ROOT / "tests/e2e/test_phase6_containerlab_smoke.py"
    new = ROOT / "tests/e2e/test_x2_r1_wrong_ip_containerlab.py"
    assert old.is_file() and new.is_file()
    assert "IND_RUN_INFRA_E2E" in old.read_text(encoding="utf-8")
    assert "IND_RUN_X2_R1_E2E" in new.read_text(encoding="utf-8")

