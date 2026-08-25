from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.accepted_runtime import require_materialized_receipts


def _receipt(path: Path, relative_run_path: str) -> Path:
    path.write_text(json.dumps({"runs": [{"relative_run_path": relative_run_path}]}), encoding="utf-8")
    return path


def test_missing_ignored_archive_skips_explicitly(tmp_path: Path) -> None:
    receipt = _receipt(tmp_path / "receipt.json", "data/raw/missing-run")
    with pytest.raises(pytest.skip.Exception):
        require_materialized_receipts(tmp_path, receipt)


def test_materialized_ignored_archive_remains_mandatory(tmp_path: Path) -> None:
    (tmp_path / "data/raw/present-run").mkdir(parents=True)
    receipt = _receipt(tmp_path / "receipt.json", "data/raw/present-run")
    require_materialized_receipts(tmp_path, receipt)
