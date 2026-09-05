"""Append-only source gate for R1.3.6 production-path integration."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Callable

from src.orchestration.x6_r1_3_6_production_path import FUTURE_AUTHORIZATION_RELEASE, HISTORICAL_VECTOR, RELEASE_ID, SCHEDULE
from src.runtime.subprocesses import run_capture


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R1_3_6_BASELINE_ONLY_PRODUCTION_PATH_INTEGRATION_COMPLETION_V1.json")
PREDECESSOR = "03af67568c9ee55398d2bf7f8d4f76091d7f73b5"
HISTORICAL_PLAN = Path("plans/expansion/X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION_V1.json")
FROZEN_SHARED_DOCUMENTS = (Path("docs/STATUS.md"), Path("docs/DECISIONS.md"))


def _git(root: Path, *args: str) -> bytes:
    result = run_capture(["git", "-C", str(root), *args], timeout_seconds=60)
    if result.returncode:
        raise ValueError("X6-R1.3.6 historical Git object resolution failed")
    return result.stdout.encode("utf-8")


def _historical_blob(root: Path, commit: str, path: Path) -> bytes:
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("X6-R1.3.6 historical path escape")
    return _git(root, "show", f"{commit}:{path.as_posix()}")


def _validate_historical_r1_3_5_bindings(
    root: Path, commit: str = PREDECESSOR,
    blob_reader: Callable[[Path, str, Path], bytes] = _historical_blob,
) -> dict[str, object]:
    """Validate R1.3.5 using only bytes from its immutable Git tree."""
    if _git(root, "rev-parse", f"{commit}^{{commit}}").decode().strip() != commit:
        raise ValueError("X6-R1.3.6 historical predecessor object missing or substituted")
    if _git(root, "rev-parse", "HEAD").decode().strip() != commit:
        raise ValueError("X6-R1.3.6 work must extend the accepted R1.3.5 predecessor")
    try:
        plan = json.loads(blob_reader(root, commit, HISTORICAL_PLAN))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("X6-R1.3.6 historical plan malformed") from exc
    if plan.get("release_id") != "X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION":
        raise ValueError("X6-R1.3.6 historical plan identity drift")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) < 4:
        raise ValueError("X6-R1.3.6 historical binding set incomplete")
    for row in bindings:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("X6-R1.3.6 historical binding schema drift")
        path = Path(row["path"])
        if hashlib.sha256(blob_reader(root, commit, path)).hexdigest() != row["sha256"]:
            raise ValueError("X6-R1.3.6 historical R1.3.5 binding drift: " + row["path"])
    return plan


def _run_historical_r1_3_5_gate(root: Path, commit: str = PREDECESSOR) -> None:
    """Run the unmodified historical gate in a detached, exact Git worktree."""
    with tempfile.TemporaryDirectory(prefix="x6-r1-3-5-snapshot-") as directory:
        snapshot = Path(directory) / "tree"
        materialize = run_capture(["git", "-C", str(root), "worktree", "add", "--detach", str(snapshot), commit], timeout_seconds=60)
        if materialize.returncode:
            raise ValueError("X6-R1.3.6 historical snapshot materialization failed")
        try:
            if _git(snapshot, "rev-parse", "HEAD").decode().strip() != commit or _git(snapshot, "status", "--porcelain"):
                raise ValueError("X6-R1.3.6 historical snapshot is not clean and exact")
            gate = run_capture([sys.executable, "-c", "from src.expansion.x6_r1_3_5_gate import verify_x6_r1_3_5; verify_x6_r1_3_5()"], timeout_seconds=900, cwd=snapshot)
            if gate.returncode:
                raise ValueError("X6-R1.3.6 historical R1.3.5 gate failed in exact snapshot")
        finally:
            run_capture(["git", "-C", str(root), "worktree", "remove", "--force", str(snapshot)], timeout_seconds=60)


def _validate_frozen_shared_documents(root: Path, commit: str = PREDECESSOR) -> None:
    for path in FROZEN_SHARED_DOCUMENTS:
        if (root / path).read_bytes() != _historical_blob(root, commit, path):
            raise ValueError("X6-R1.3.6 frozen shared document drift: " + path.as_posix())


def verify_r1_3_5_predecessor_snapshot(root: Path = ROOT) -> dict[str, object]:
    plan = _validate_historical_r1_3_5_bindings(root)
    _run_historical_r1_3_5_gate(root)
    _validate_frozen_shared_documents(root)
    return plan


def verify_x6_r1_3_6(root: Path = ROOT) -> dict[str, object]:
    verify_r1_3_5_predecessor_snapshot(root)
    plan = json.loads((Path(root) / PLAN).read_text(encoding="utf-8"))
    if plan.get("release_id") != RELEASE_ID or plan.get("source_boundary") != "03af67568c9ee55398d2bf7f8d4f76091d7f73b5":
        raise ValueError("X6-R1.3.6 identity/boundary drift")
    if plan.get("runtime_scientific_authorization") != HISTORICAL_VECTOR or plan.get("future_authorization", {}).get("release_id") != FUTURE_AUTHORIZATION_RELEASE or plan["future_authorization"].get("artifact") != "ABSENT":
        raise ValueError("X6-R1.3.6 authorization separation drift")
    if plan.get("schedule") != SCHEDULE or plan.get("runtime_execution") is not False:
        raise ValueError("X6-R1.3.6 schedule/runtime boundary drift")
    if plan.get("predecessor_snapshot_validation") != {
        "predecessor_commit": PREDECESSOR,
        "r1_3_5_gate_context": "EXACT_CLEAN_GIT_SNAPSHOT",
        "historical_bindings": "VALIDATE_EXACT_HISTORICAL_BYTES",
        "cumulative_documents": "HISTORICAL_BYTES_PREFIX_PLUS_APPEND_ONLY_SUCCESSOR_CONTENT",
        "forbidden": ["WEAKEN", "SKIP", "MONKEYPATCH", "REWRITE_HISTORICAL_GATE"],
    }:
        raise ValueError("X6-R1.3.6 predecessor snapshot convention drift")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) < 5:
        raise ValueError("X6-R1.3.6 source bindings incomplete")
    for row in bindings:
        path = Path(root) / row["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("X6-R1.3.6 source binding drift: " + row["path"])
    return plan
