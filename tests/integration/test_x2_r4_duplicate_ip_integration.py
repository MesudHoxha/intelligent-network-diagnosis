from __future__ import annotations

import ast
from pathlib import Path

from src.expansion.scope_gate import verify_scope_gate
from src.expansion.x1_gate import verify_x1_gate
from src.expansion.x2_gate import verify_x2_gate
from src.expansion.x2_r1_gate import verify_x2_r1_gate
from src.expansion.x2_r2_gate import verify_x2_r2_gate
from src.expansion.x2_r3_gate import verify_x2_r3_gate
from src.expansion.x2_r4_gate import EXPECTED_RUNTIME, verify_x2_r4_gate

ROOT = Path(__file__).resolve().parents[2]


def test_x0_through_x2_r4_gates_compose() -> None:
    assert verify_scope_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x1_gate(ROOT)["status"] == "ACCEPTED_CONTRACT_ONLY"
    assert verify_x2_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x2_r1_gate(ROOT)["status"] == "IMPLEMENTED_RUNTIME_SLICE"
    assert verify_x2_r2_gate(ROOT)["status"] == "IMPLEMENTED_RUNTIME_SLICE"
    assert verify_x2_r3_gate(ROOT)["status"] == "IMPLEMENTED_RUNTIME_SLICE"
    assert verify_x2_r4_gate(ROOT)["status"] == "IMPLEMENTED_RUNTIME_SLICE"


def test_runtime_scope_is_exact() -> None:
    assert sum(EXPECTED_RUNTIME.values()) == 4
    assert EXPECTED_RUNTIME["dataset_generation"] is False
    assert EXPECTED_RUNTIME["multiple_fault_execution"] is False


def test_runtime_imports_no_ml_dataset_or_report_modules() -> None:
    blocked = ("joblib", "sklearn", "src.ml", "src.dataset", "src.evaluation", "src.phase8")
    for relative in ("src/collection/duplicate_ip_state_collector.py", "src/fault_injection/duplicate_ip.py", "src/orchestration/x2_duplicate_ip_experiment_runner.py", "src/rules/addressing_rule_engine_x2_r4.py"):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): names.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module: names.append(node.module)
        assert not any(name == prefix or name.startswith(prefix + ".") for name in names for prefix in blocked)


def test_real_lifecycle_is_explicit_opt_in() -> None:
    text = (ROOT / "tests/e2e/test_x2_r4_duplicate_ip_containerlab.py").read_text(encoding="utf-8")
    assert "IND_RUN_X2_R4_E2E" in text
