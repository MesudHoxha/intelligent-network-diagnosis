"""Guard default X5 tests from accidentally depending on ignored runtime trees."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from src.expansion.x5_r11_gate import verify_x5_r11_clean_checkout_test_correction


ROOT = Path(__file__).resolve().parents[2]


def _path_parts(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name):
        return ["<name>"]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _path_parts(node.left) + _path_parts(node.right)
    return []


def _is_ignored_x5_path(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return ("data" + "/raw" + "/x5") in node.value
    parts = _path_parts(node)
    return any(parts[index:index + 2] == ["data", "raw"] and index + 2 < len(parts) and parts[index + 2].startswith("x5") for index in range(len(parts)))


def _accepted_runtime(function: ast.FunctionDef) -> bool:
    return any(isinstance(decorator, ast.Attribute) and decorator.attr == "accepted_runtime" for decorator in function.decorator_list)


def test_x5_r11_gate_keeps_the_correction_source_only() -> None:
    plan = verify_x5_r11_clean_checkout_test_correction(ROOT)
    assert all(value is False for value in plan["runtime_authorization"].values())


def test_default_collected_x5_unit_tests_do_not_read_ignored_runtime_roots() -> None:
    for path in sorted((ROOT / "tests/unit").glob("test_x5*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for function in (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)):
            reads_ignored_x5 = any(_is_ignored_x5_path(node) for node in ast.walk(function))
            assert not reads_ignored_x5 or _accepted_runtime(function), (
                "default-collected X5 test reads ignored runtime evidence without accepted_runtime gating: "
                + str(path.relative_to(ROOT)) + ":" + function.name
            )


def test_x5_r11_source_bindings_match_current_source() -> None:
    plan = verify_x5_r11_clean_checkout_test_correction(ROOT)
    for binding in plan["source_bindings"]:
        assert hashlib.sha256((ROOT / binding["path"]).read_bytes()).hexdigest() == binding["sha256"]
