"""Explicit gating for ignored, accepted runtime archives.

Source-only checkouts intentionally do not carry ``data/raw`` evidence trees.
Receipt tests remain mandatory whenever those accepted trees are materialized.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def require_materialized_receipts(repository_root: Path, *receipt_paths: Path) -> None:
    """Skip only when an ignored accepted-runtime tree is genuinely absent."""
    missing: list[str] = []
    for receipt_path in receipt_paths:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        runs = receipt.get("runs", [])
        if not isinstance(runs, list):
            raise AssertionError("accepted-runtime receipt runs must be a list")
        for run in runs:
            if not isinstance(run, dict) or not isinstance(run.get("relative_run_path"), str):
                raise AssertionError("accepted-runtime receipt run path is invalid")
            relative = run["relative_run_path"]
            if not (repository_root / relative).is_dir():
                missing.append(relative)
    if missing:
        pytest.skip("accepted ignored runtime archive is not materialized: " + ", ".join(sorted(set(missing))))
