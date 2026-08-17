from __future__ import annotations

import ast
import json
from pathlib import Path

from src.expansion.scope_gate import verify_scope_gate
from src.expansion.x1_gate import verify_x1_gate
from src.expansion.x2_gate import verify_x2_gate
from src.expansion.x2_r1_gate import verify_x2_r1_gate
from src.expansion.x2_r2_gate import verify_x2_r2_gate
from src.expansion.x2_r3_gate import EXPECTED_RUNTIME, verify_x2_r3_gate


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str) -> dict[str, object]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_x0_through_x2_r3_gates_compose_append_only() -> None:
    assert verify_scope_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x1_gate(ROOT)["status"] == "ACCEPTED_CONTRACT_ONLY"
    assert verify_x2_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x2_r1_gate(ROOT)["status"] == "IMPLEMENTED_RUNTIME_SLICE"
    assert verify_x2_r2_gate(ROOT)["status"] == "IMPLEMENTED_RUNTIME_SLICE"
    assert verify_x2_r3_gate(ROOT)["status"] == "IMPLEMENTED_RUNTIME_SLICE"


def test_runtime_is_scoped_to_missing_default_route_slice() -> None:
    manifest = _load("plans/expansion/X2_R3_MISSING_DEFAULT_ROUTE_V1.json")
    assert manifest["runtime_authorization"] == EXPECTED_RUNTIME
    assert sum(manifest["runtime_authorization"].values()) == 4
    assert manifest["slice"]["fault_type"] == "missing_default_route"
    assert manifest["track"]["next_release"] == "X2_R4_DUPLICATE_IP"


def test_previous_signatures_and_frozen_science_are_preserved() -> None:
    manifest = _load("plans/expansion/X2_R3_MISSING_DEFAULT_ROUTE_V1.json")
    compatibility = manifest["compatibility"]
    assert compatibility["x2_r1_gate"] == "UNCHANGED_AND_VERIFIED"
    assert compatibility["x2_r2_gate"] == "UNCHANGED_AND_VERIFIED"
    assert compatibility["phase6_evidence_v3"] == "UNCHANGED"
    assert compatibility["phase6_dataset_row_v3"] == "UNCHANGED"
    assert compatibility["accepted_results"] == "UNCHANGED"
    assert compatibility["api_v1"] == "UNCHANGED"
    assert manifest["slice"]["preserved_signature"]["fault_type"] == (
        "wrong_ip_address"
    )
    assert manifest["acceptance"]["dataset_row_created"] is False
    assert manifest["acceptance"]["model_operation_performed"] is False
    assert manifest["acceptance"]["metric_created"] is False


def test_x2_r3_runtime_imports_no_ml_dataset_or_report_only_modules() -> None:
    paths = (
        "src/collection/default_route_state_collector.py",
        "src/rules/addressing_rule_engine_x2_r3.py",
        "src/fault_injection/missing_default_route.py",
        "src/orchestration/x2_missing_default_route_experiment_runner.py",
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


def test_all_real_lifecycle_tests_remain_explicit_and_opt_in() -> None:
    paths_and_flags = (
        ("tests/e2e/test_phase6_containerlab_smoke.py", "IND_RUN_INFRA_E2E"),
        ("tests/e2e/test_x2_r1_wrong_ip_containerlab.py", "IND_RUN_X2_R1_E2E"),
        ("tests/e2e/test_x2_r2_wrong_subnet_mask_containerlab.py", "IND_RUN_X2_R2_E2E"),
        (
            "tests/e2e/test_x2_r3_missing_default_route_containerlab.py",
            "IND_RUN_X2_R3_E2E",
        ),
    )
    for relative, flag in paths_and_flags:
        path = ROOT / relative
        assert path.is_file()
        assert flag in path.read_text(encoding="utf-8")
