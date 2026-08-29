from __future__ import annotations

import tomllib
from pathlib import Path

from src.expansion.x6_r0_6_gate import verify_x6_r0_6


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PYTEST_REQUIREMENT = "pytest>=9,<10"


def test_test_extra_directly_declares_bounded_pytest_and_preserves_httpx() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    extras = project["project"]["optional-dependencies"]
    assert "test" in extras
    assert EXPECTED_PYTEST_REQUIREMENT in extras["test"]
    assert "httpx>=0.27,<1" in extras["test"]
    assert sum(item.startswith("pytest") for item in extras["test"]) == 1


def test_documented_clean_install_uses_test_extra() -> None:
    readme = (ROOT / "README.md").read_text()
    assert "python -m pip install -e '.[test]'" in readme
    assert "python -m pytest -q" in readme


def test_x6_r0_6_source_gate() -> None:
    result = verify_x6_r0_6(ROOT)
    assert result["release_id"] == "X6_R0_6_TEST_ENVIRONMENT_REPRODUCIBILITY_CORRECTION"
    assert len(result["source_bindings"]) == 4
    assert not any(result["runtime_scientific_authorization"].values())
