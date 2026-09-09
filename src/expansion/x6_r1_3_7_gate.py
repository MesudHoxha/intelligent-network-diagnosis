"""R1.3.7 detached historical-snapshot validation.

The published R1.3.6 gate is intentionally left untouched.  Its historical
R1.3.5 helper assumes that its repository root is checked out at R1.3.5, so
this successor supplies that root by materialising a detached worktree.  No
current-worktree bytes are ever used as historical proof.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic_ns
from typing import Iterator, Mapping, Sequence

from src.runtime.subprocesses import run_capture


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R1_3_7_R1_3_6_PREDECESSOR_SNAPSHOT_VALIDATION_CORRECTION_V1.json")
R1_3_5 = "03af67568c9ee55398d2bf7f8d4f76091d7f73b5"
R1_3_6 = "bdf2fecb6c9042f36c8931175aa90bf91493433d"
FALSE_VECTOR = {
    "containerlab": False, "measurement": False, "f1_revalidation": False,
    "f2": False, "f3": False, "f4": False, "dataset": False,
    "ml_hybrid": False, "api": False, "p9_r2": False,
}
R1_3_6_INVENTORY = (
    "docs/DECISION_X6_R1_3_6.md",
    "docs/HANDOFF_X6_R1_3_6.md",
    "docs/STATUS_X6_R1_3_6.md",
    "plans/expansion/X6_R1_3_6_BASELINE_ONLY_PRODUCTION_PATH_INTEGRATION_COMPLETION_V1.json",
    "src/expansion/x6_r1_3_6_gate.py",
    "src/expansion/x6_r1_3_6_materialized_verifier.py",
    "src/orchestration/x6_r1_3_6_production_path.py",
    "src/orchestration/x6_r1_3_6_recovery.py",
    "tests/unit/test_x6_r1_3_6_gate.py",
    "tests/unit/test_x6_r1_3_6_production_path.py",
)
FROZEN_DIAGNOSTIC_NODES = (
    "tests/unit/test_x6_r1_3_6_gate.py::test_x6_r1_3_6_gate_preserves_disabled_historical_vector",
    "tests/unit/test_x6_r1_3_6_gate.py::test_historical_r1_3_5_gate_is_validated_only_in_its_exact_snapshot",
    "tests/unit/test_x6_r1_3_6_gate.py::test_historical_binding_validator_rejects_changed_historical_blob",
    "tests/unit/test_x6_r1_3_6_gate.py::test_historical_binding_validator_rejects_wrong_predecessor_and_successor_substitution",
    "tests/unit/test_x6_r1_3_6_gate.py::test_successor_gate_rejects_skipped_historical_gate",
    "tests/unit/test_x6_r1_3_6_gate.py::test_gate_binds_versioned_successor_decision_and_status_documents",
)
FROZEN_DIAGNOSTIC_NODE = FROZEN_DIAGNOSTIC_NODES[0]
FROZEN_DIAGNOSTIC_CLASSIFICATION = "R1_3_6_FROZEN_CURRENT_WORKTREE_TEST_RETAINED_AS_EXPECTED_DIAGNOSTIC"
FROZEN_DIAGNOSTIC_EXCEPTION = "ValueError: X6-R1.3.6 work must extend the accepted R1.3.5 predecessor"
FROZEN_DIAGNOSTIC_EXPECTATIONS: Mapping[str, Mapping[str, object]] = {
    FROZEN_DIAGNOSTIC_NODES[0]: {
        "failure_kind": "DIRECT_HISTORICAL_PRECONDITION_VALUE_ERROR",
        "expected_exception": FROZEN_DIAGNOSTIC_EXCEPTION,
        "required_fragments": (FROZEN_DIAGNOSTIC_EXCEPTION,),
    },
    FROZEN_DIAGNOSTIC_NODES[1]: {
        "failure_kind": "DIRECT_HISTORICAL_PRECONDITION_VALUE_ERROR",
        "expected_exception": FROZEN_DIAGNOSTIC_EXCEPTION,
        "required_fragments": (FROZEN_DIAGNOSTIC_EXCEPTION,),
    },
    FROZEN_DIAGNOSTIC_NODES[2]: {
        "failure_kind": "PYTEST_RAISES_ASSERTION_MISMATCH_FROM_EARLY_HISTORICAL_PRECONDITION_BEFORE_BLOB_CHECK",
        "expected_exception": "AssertionError: expected historical blob-integrity exception was not reached",
        "required_fragments": (
            "Expected regex: 'historical R1.3.5 binding drift'",
            "X6-R1.3.6 work must extend the accepted R1.3.5 predecessor",
        ),
    },
    FROZEN_DIAGNOSTIC_NODES[3]: {
        "failure_kind": "DIRECT_HISTORICAL_PRECONDITION_VALUE_ERROR_AFTER_WRONG_PREDECESSOR_ASSERTION",
        "expected_exception": FROZEN_DIAGNOSTIC_EXCEPTION,
        "required_fragments": (FROZEN_DIAGNOSTIC_EXCEPTION,),
    },
    FROZEN_DIAGNOSTIC_NODES[4]: {
        "failure_kind": "PYTEST_RAISES_ASSERTION_MISMATCH_FROM_EARLY_HISTORICAL_PRECONDITION",
        "expected_exception": "AssertionError: expected skipped-historical-gate exception was not reached",
        "required_fragments": (
            "Expected regex: 'historical gate required'",
            "X6-R1.3.6 work must extend the accepted R1.3.5 predecessor",
        ),
    },
    FROZEN_DIAGNOSTIC_NODES[5]: {
        "failure_kind": "DIRECT_HISTORICAL_PRECONDITION_VALUE_ERROR_BEFORE_DOCUMENT_BINDING_ASSERTIONS",
        "expected_exception": FROZEN_DIAGNOSTIC_EXCEPTION,
        "required_fragments": (FROZEN_DIAGNOSTIC_EXCEPTION,),
    },
}
ACCEPTANCE_PARTITION = {
    "successor_applicable": "ALL_COLLECTED_NODES_EXCEPT_EXACT_SIX_DIAGNOSTIC_NODES",
    "frozen_expected_diagnostics": list(FROZEN_DIAGNOSTIC_NODES),
    "diagnostic_cardinality": 6,
    "diagnostic_expected_exception": FROZEN_DIAGNOSTIC_EXCEPTION,
    "diagnostic_is_not_a_passing_acceptance_test": True,
    "union_requirement": "SUCCESSOR_APPLICABLE_PLUS_DIAGNOSTIC_EQUALS_COMPLETE_COLLECTED_UNIVERSE",
}


class X6R137ValidationError(ValueError):
    pass


def _fail(message: str) -> None:
    raise X6R137ValidationError("X6-R1.3.7: " + message)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _command(root: Path, argv: Sequence[str], *, timeout_seconds: int = 120, cwd: Path | None = None) -> tuple[str, dict[str, object]]:
    """Run a bounded argv-only command and retain an in-memory raw receipt."""
    if not argv or any(not isinstance(item, str) or not item for item in argv) or timeout_seconds <= 0:
        _fail("unbounded or malformed subprocess request")
    start_monotonic, start_utc = monotonic_ns(), datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = run_capture(list(argv), timeout_seconds=timeout_seconds, cwd=cwd)
    end_monotonic, end_utc = monotonic_ns(), datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    receipt = {
        "argv": list(argv), "cwd": str(cwd) if cwd else None,
        "timeout_seconds": timeout_seconds, "return_code": result.returncode,
        "stdout_sha256": _digest(result.stdout), "stderr_sha256": _digest(result.stderr),
        "started_at_utc": start_utc, "completed_at_utc": end_utc,
        "started_monotonic_ns": start_monotonic, "completed_monotonic_ns": end_monotonic,
        "shell": False,
    }
    if result.returncode != 0:
        _fail("subprocess failed: " + " ".join(argv))
    return result.stdout, receipt


def _git(root: Path, *args: str, receipts: list[dict[str, object]], cwd: Path | None = None) -> str:
    output, receipt = _command(root, ["git", "-C", str(root), *args], cwd=cwd)
    receipts.append(receipt)
    return output.strip()


def _assert_snapshot_identity(root: Path, snapshot: Path, commit: str, *, receipts: list[dict[str, object]]) -> dict[str, str]:
    if snapshot.resolve() == root.resolve() or not snapshot.is_dir() or snapshot.is_symlink():
        _fail("historical snapshot is absent, substituted, or not detached")
    head = _git(snapshot, "rev-parse", "HEAD", receipts=receipts)
    tree = _git(snapshot, "rev-parse", "HEAD^{tree}", receipts=receipts)
    expected_tree = _git(root, "rev-parse", commit + "^{tree}", receipts=receipts)
    status = _git(snapshot, "status", "--porcelain=v1", receipts=receipts)
    if head != commit or tree != expected_tree or status:
        _fail("historical snapshot identity, tree, or cleanliness drift")
    return {"commit": head, "tree": tree}


@contextmanager
def _detached_snapshot(root: Path, commit: str, *, receipts: list[dict[str, object]]) -> Iterator[Path]:
    """Create and remove an isolated exact Git worktree without touching root."""
    with tempfile.TemporaryDirectory(prefix="x6-r1-3-7-snapshot-") as temporary:
        snapshot = Path(temporary) / "snapshot"
        _git(root, "rev-parse", commit + "^{commit}", receipts=receipts)
        _git(root, "worktree", "add", "--detach", str(snapshot), commit, receipts=receipts)
        try:
            _assert_snapshot_identity(root, snapshot, commit, receipts=receipts)
            yield snapshot
        finally:
            # The target is known to be the child of this temporary directory;
            # worktree removal cannot target the caller's repository.
            try:
                _git(root, "worktree", "remove", "--force", str(snapshot), receipts=receipts)
            except X6R137ValidationError:
                _fail("detached snapshot cleanup failed")
            if snapshot.exists():
                _fail("detached snapshot cleanup left residual state")


def _validate_bindings(snapshot: Path, plan_path: str, release_id: str) -> dict[str, object]:
    path = snapshot / plan_path
    if not path.is_file() or path.is_symlink():
        _fail("historical plan is absent or unsafe")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise X6R137ValidationError("X6-R1.3.7: historical plan is malformed") from error
    if plan.get("release_id") != release_id or plan.get("runtime_scientific_authorization") != FALSE_VECTOR:
        _fail("historical plan identity or authorization vector drift")
    rows = plan.get("source_bindings")
    if not isinstance(rows, list) or not rows:
        _fail("historical plan binding set is incomplete")
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {"path", "sha256"} or not isinstance(row["path"], str) or not isinstance(row["sha256"], str):
            _fail("historical source binding schema drift")
        relative = Path(row["path"])
        target = snapshot / relative
        if relative.is_absolute() or ".." in relative.parts or not target.is_file() or target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != row["sha256"]:
            _fail("historical source binding drift: " + row["path"])
    return plan


def _assert_current_successor(root: Path, *, receipts: list[dict[str, object]]) -> None:
    head = _git(root, "rev-parse", "HEAD", receipts=receipts)
    parent = _git(root, "rev-parse", "HEAD^", receipts=receipts) if head != R1_3_6 else R1_3_6
    if head != R1_3_6 and parent != R1_3_6:
        _fail("current work does not extend R1.3.6 directly")
    # A pre-commit R1.3.7 working tree has HEAD at R1.3.6; after commit, its
    # direct parent must be R1.3.6.  Neither case is historical proof.


def validate_acceptance_partition(nodes: Sequence[str]) -> dict[str, object]:
    """Partition a collected universe without file-, marker-, or glob-based exclusion."""
    if not all(isinstance(node, str) and node for node in nodes) or len(nodes) != len(set(nodes)):
        _fail("collected node universe is malformed or duplicated")
    if not set(FROZEN_DIAGNOSTIC_NODES) <= set(nodes):
        _fail("frozen diagnostic node is absent from collected universe")
    applicable = tuple(node for node in nodes if node not in FROZEN_DIAGNOSTIC_NODES)
    diagnostic = FROZEN_DIAGNOSTIC_NODES
    if set(applicable) & set(diagnostic) or set(applicable) | set(diagnostic) != set(nodes) or len(diagnostic) != 6:
        _fail("acceptance partition is not exact and disjoint")
    return {"complete_nodes": len(nodes), "applicable_nodes": applicable, "diagnostic_nodes": diagnostic}


def _frozen_diagnostic_source_identity(root: Path) -> dict[str, str]:
    receipts: list[dict[str, object]] = []
    commit = _git(root, "rev-parse", R1_3_6 + "^{commit}", receipts=receipts)
    tree = _git(root, "rev-parse", R1_3_6 + "^{tree}", receipts=receipts)
    test_text, test_receipt = _command(root, ["git", "-C", str(root), "show", R1_3_6 + ":tests/unit/test_x6_r1_3_6_gate.py"])
    gate_text, gate_receipt = _command(root, ["git", "-C", str(root), "show", R1_3_6 + ":src/expansion/x6_r1_3_6_gate.py"])
    receipts.extend((test_receipt, gate_receipt))
    test_bytes, gate_bytes = test_text.encode("utf-8"), gate_text.encode("utf-8")
    return {"commit": commit, "tree": tree, "test_sha256": hashlib.sha256(test_bytes).hexdigest(), "gate_sha256": hashlib.sha256(gate_bytes).hexdigest()}


def verify_frozen_diagnostic_receipt(record_root: Path, root: Path = ROOT) -> dict[str, object]:
    """Verify one approved frozen R1.3.6 diagnostic by its exact failure path."""
    record_root = Path(record_root)
    receipt_path = record_root / "receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        _fail("frozen diagnostic receipt is absent or unsafe")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise X6R137ValidationError("X6-R1.3.7: frozen diagnostic receipt malformed") from error
    required = {"schema_version", "classification", "diagnostic_node_id", "failure_kind", "command_argv", "shell", "timeout_seconds", "source_identity", "started_at_utc", "completed_at_utc", "started_monotonic_ns", "completed_monotonic_ns", "return_code", "stdout_path", "stderr_path", "stdout_sha256", "stderr_sha256", "expected_exception"}
    if not isinstance(receipt, Mapping) or set(receipt) != required:
        _fail("frozen diagnostic receipt schema drift")
    node = receipt.get("diagnostic_node_id")
    expectation = FROZEN_DIAGNOSTIC_EXPECTATIONS.get(node) if isinstance(node, str) else None
    if receipt.get("schema_version") != 1 or receipt.get("classification") != FROZEN_DIAGNOSTIC_CLASSIFICATION or expectation is None or receipt.get("shell") is not False or receipt.get("expected_exception") != expectation["expected_exception"] or receipt.get("failure_kind") != expectation["failure_kind"]:
        _fail("frozen diagnostic receipt identity or classification drift")
    argv = receipt.get("command_argv")
    if not isinstance(argv, list) or len(argv) < 5 or argv[-4:] != ["-m", "pytest", "-q", node] or any(not isinstance(item, str) or not item for item in argv):
        _fail("frozen diagnostic command argv drift")
    if not isinstance(receipt.get("timeout_seconds"), int) or receipt["timeout_seconds"] <= 0 or receipt.get("return_code") != 1:
        _fail("frozen diagnostic command bound or expected return code drift")
    if receipt.get("source_identity") != _frozen_diagnostic_source_identity(Path(root)):
        _fail("frozen diagnostic source identity drift")
    for stamp in ("started_at_utc", "completed_at_utc"):
        if not isinstance(receipt.get(stamp), str) or not receipt[stamp].endswith("Z"):
            _fail("frozen diagnostic UTC timestamp drift")
    start, end = receipt.get("started_monotonic_ns"), receipt.get("completed_monotonic_ns")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in (start, end)) or end < start:
        _fail("frozen diagnostic monotonic timing drift")
    streams: dict[str, str] = {}
    for kind in ("stdout", "stderr"):
        relative = receipt.get(kind + "_path")
        path = record_root / str(relative)
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts or not path.is_file() or path.is_symlink():
            _fail("frozen diagnostic stream path drift")
        streams[kind] = path.read_text(encoding="utf-8")
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt.get(kind + "_sha256"):
            _fail("frozen diagnostic stream hash drift")
    combined = streams["stdout"] + "\n" + streams["stderr"]
    if node not in combined or not re.search(r"(?m)^.*1 failed.*in [0-9.]+s", combined) or "ERROR collecting" in combined or "Timeout" in combined or any(fragment not in combined for fragment in expectation["required_fragments"]):
        _fail("frozen diagnostic did not fail only with the preserved gate defect")
    return {"classification": FROZEN_DIAGNOSTIC_CLASSIFICATION, "diagnostic_node_id": node, "failure_kind": expectation["failure_kind"], "return_code": 1, "source_identity": receipt["source_identity"]}


def validate_r1_3_5_snapshot(root: Path = ROOT) -> dict[str, object]:
    receipts: list[dict[str, object]] = []
    with _detached_snapshot(root, R1_3_5, receipts=receipts) as snapshot:
        plan = _validate_bindings(snapshot, "plans/expansion/X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION_V1.json", "X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION")
        # The accepted historical gate runs only with the snapshot as cwd/root.
        _, gate_receipt = _command(root, [sys.executable, "-c", "from src.expansion.x6_r1_3_5_gate import verify_x6_r1_3_5; verify_x6_r1_3_5()"], timeout_seconds=900, cwd=snapshot)
        receipts.append(gate_receipt)
    return {"commit": R1_3_5, "plan": plan, "receipts": receipts}


def validate_r1_3_6_snapshot(root: Path = ROOT) -> dict[str, object]:
    receipts: list[dict[str, object]] = []
    with _detached_snapshot(root, R1_3_6, receipts=receipts) as snapshot:
        plan = _validate_bindings(snapshot, "plans/expansion/X6_R1_3_6_BASELINE_ONLY_PRODUCTION_PATH_INTEGRATION_COMPLETION_V1.json", "X6_R1_3_6_BASELINE_ONLY_PRODUCTION_PATH_INTEGRATION_COMPLETION")
        changed = _git(snapshot, "diff-tree", "--no-commit-id", "--name-only", "-r", R1_3_6, receipts=receipts).splitlines()
        if tuple(changed) != R1_3_6_INVENTORY:
            _fail("R1.3.6 committed inventory drift")
        if plan.get("future_authorization", {}).get("artifact") != "ABSENT":
            _fail("R1.3.6 snapshot created an authorization")
    return {"commit": R1_3_6, "plan": plan, "receipts": receipts}


def verify_x6_r1_3_7(root: Path = ROOT) -> dict[str, object]:
    receipts: list[dict[str, object]] = []
    _assert_current_successor(root, receipts=receipts)
    historical = validate_r1_3_5_snapshot(root)
    published = validate_r1_3_6_snapshot(root)
    plan_path = Path(root) / PLAN
    if not plan_path.is_file() or plan_path.is_symlink():
        _fail("R1.3.7 plan is absent or unsafe")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("release_id") != "X6_R1_3_7_R1_3_6_PREDECESSOR_SNAPSHOT_VALIDATION_CORRECTION" or plan.get("runtime_scientific_authorization") != FALSE_VECTOR:
        _fail("R1.3.7 identity or authorization vector drift")
    if plan.get("acceptance_partition") != ACCEPTANCE_PARTITION:
        _fail("R1.3.7 acceptance partition drift")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) < 5:
        _fail("R1.3.7 source binding set incomplete")
    for row in bindings:
        if not isinstance(row, Mapping) or set(row) != {"path", "sha256"} or not isinstance(row["path"], str) or not isinstance(row["sha256"], str):
            _fail("R1.3.7 source binding schema drift")
        relative = Path(row["path"])
        target = Path(root) / relative
        if relative.is_absolute() or ".." in relative.parts or not target.is_file() or target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != row["sha256"]:
            _fail("R1.3.7 source binding drift: " + row["path"])
    return {"release_id": plan["release_id"], "historical_r1_3_5": historical, "published_r1_3_6": published, "current_successor": R1_3_6, "local_receipts": receipts}
