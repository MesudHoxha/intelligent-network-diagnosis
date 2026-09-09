"""Adversarial source-only tests for detached R1.3.5/R1.3.6 validation."""
from __future__ import annotations

import inspect
import json
import hashlib
import sys
from pathlib import Path

import pytest

from src.expansion import x6_r1_3_7_gate as gate


def test_valid_detached_historical_and_published_paths() -> None:
    result = gate.verify_x6_r1_3_7()
    assert result["historical_r1_3_5"]["commit"] == gate.R1_3_5
    assert result["published_r1_3_6"]["commit"] == gate.R1_3_6
    assert result["current_successor"] == gate.R1_3_6


def test_current_worktree_cannot_be_substituted_for_historical_snapshot() -> None:
    with pytest.raises(gate.X6R137ValidationError, match="not detached"):
        gate._assert_snapshot_identity(gate.ROOT, gate.ROOT, gate.R1_3_5, receipts=[])


def test_wrong_historical_commit_or_tree_is_rejected() -> None:
    receipts: list[dict[str, object]] = []
    with gate._detached_snapshot(gate.ROOT, gate.R1_3_5, receipts=receipts) as snapshot:
        with pytest.raises(gate.X6R137ValidationError, match="identity, tree"):
            gate._assert_snapshot_identity(gate.ROOT, snapshot, gate.R1_3_6, receipts=[])


def test_wrong_r1_3_6_committed_inventory_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "R1_3_6_INVENTORY", ("substituted.txt",))
    with pytest.raises(gate.X6R137ValidationError, match="committed inventory"):
        gate.validate_r1_3_6_snapshot()


@pytest.mark.parametrize(
    ("commit", "plan_path"),
    [
        (gate.R1_3_5, "plans/expansion/X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION_V1.json"),
        (gate.R1_3_6, "plans/expansion/X6_R1_3_6_BASELINE_ONLY_PRODUCTION_PATH_INTEGRATION_COMPLETION_V1.json"),
    ],
)
def test_dirty_or_altered_snapshot_is_rejected_before_historical_proof(commit: str, plan_path: str) -> None:
    receipts: list[dict[str, object]] = []
    with gate._detached_snapshot(gate.ROOT, commit, receipts=receipts) as snapshot:
        plan = json.loads((snapshot / plan_path).read_text(encoding="utf-8"))
        binding = snapshot / plan["source_bindings"][0]["path"]
        binding.write_bytes(binding.read_bytes() + b"\nsubstitution")
        with pytest.raises(gate.X6R137ValidationError, match="cleanliness"):
            gate._assert_snapshot_identity(gate.ROOT, snapshot, commit, receipts=[])
        with pytest.raises(gate.X6R137ValidationError, match="source binding drift"):
            gate._validate_bindings(snapshot, plan_path, str(plan["release_id"]))


def test_non_descending_current_successor_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_git(_root, *args, receipts, cwd=None):
        if args == ("rev-parse", "HEAD"):
            return "f" * 40
        return "e" * 40
    monkeypatch.setattr(gate, "_git", fake_git)
    with pytest.raises(gate.X6R137ValidationError, match="does not extend"):
        gate._assert_current_successor(gate.ROOT, receipts=[])


def test_historical_validation_is_not_caller_json_or_copy_proof() -> None:
    signature = inspect.signature(gate.validate_r1_3_5_snapshot)
    assert tuple(signature.parameters) == ("root",)
    # A copied historical file at the current root has no detached Git identity.
    with pytest.raises(gate.X6R137ValidationError):
        gate._assert_snapshot_identity(gate.ROOT, gate.ROOT, gate.R1_3_5, receipts=[])


def test_snapshot_commands_are_bounded_argv_only_and_cleanup_is_isolated() -> None:
    source = inspect.getsource(gate)
    assert "run_capture" in source
    assert "shell=True" not in source
    assert "subprocess.run" not in source
    receipts: list[dict[str, object]] = []
    before = gate._git(gate.ROOT, "worktree", "list", "--porcelain", receipts=receipts)
    gate.validate_r1_3_6_snapshot()
    after = gate._git(gate.ROOT, "worktree", "list", "--porcelain", receipts=receipts)
    assert before == after


def test_snapshot_validation_establishes_identity_before_binding_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    original_identity = gate._assert_snapshot_identity
    original_bindings = gate._validate_bindings
    def noted_identity(*args, **kwargs):
        order.append("identity")
        return original_identity(*args, **kwargs)
    def noted_bindings(*args, **kwargs):
        order.append("bindings")
        return original_bindings(*args, **kwargs)
    monkeypatch.setattr(gate, "_assert_snapshot_identity", noted_identity)
    monkeypatch.setattr(gate, "_validate_bindings", noted_bindings)
    gate.validate_r1_3_6_snapshot()
    assert order.index("identity") < order.index("bindings")


def test_historical_vector_is_immutable_false() -> None:
    result = gate.validate_r1_3_6_snapshot()
    assert result["plan"]["runtime_scientific_authorization"] == gate.FALSE_VECTOR
    assert all(value is False for value in gate.FALSE_VECTOR.values())


def _diagnostic_receipt(root: Path, node: str = gate.FROZEN_DIAGNOSTIC_NODE) -> None:
    expectation = gate.FROZEN_DIAGNOSTIC_EXPECTATIONS[node]
    stdout = "".join((
        "FAILED " + node + "\n",
        "\n".join("E   " + fragment for fragment in expectation["required_fragments"]) + "\n",
        "============================== 1 failed in 0.01s ==============================\n",
    ))
    stderr = ""
    (root / "stdout.txt").write_text(stdout, encoding="utf-8")
    (root / "stderr.txt").write_text(stderr, encoding="utf-8")
    receipt = {
        "schema_version": 1,
        "classification": gate.FROZEN_DIAGNOSTIC_CLASSIFICATION,
        "diagnostic_node_id": node,
        "failure_kind": expectation["failure_kind"],
        "command_argv": [sys.executable, "-m", "pytest", "-q", node],
        "shell": False,
        "timeout_seconds": 120,
        "source_identity": gate._frozen_diagnostic_source_identity(gate.ROOT),
        "started_at_utc": "2026-09-05T00:00:00Z",
        "completed_at_utc": "2026-09-05T00:00:01Z",
        "started_monotonic_ns": 1,
        "completed_monotonic_ns": 2,
        "return_code": 1,
        "stdout_path": "stdout.txt",
        "stderr_path": "stderr.txt",
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        "expected_exception": expectation["expected_exception"],
    }
    (root / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


def test_acceptance_partition_is_exactly_six_preserved_diagnostics() -> None:
    universe = ("tests/unit/test_alpha.py::test_a", *gate.FROZEN_DIAGNOSTIC_NODES, "tests/unit/test_beta.py::test_b")
    partition = gate.validate_acceptance_partition(universe)
    assert partition["diagnostic_nodes"] == gate.FROZEN_DIAGNOSTIC_NODES
    assert set(partition["applicable_nodes"]) | set(partition["diagnostic_nodes"]) == set(universe)
    with pytest.raises(gate.X6R137ValidationError):
        gate.validate_acceptance_partition(("tests/unit/test_alpha.py::test_a",))
    with pytest.raises(gate.X6R137ValidationError):
        gate.validate_acceptance_partition((*gate.FROZEN_DIAGNOSTIC_NODES, gate.FROZEN_DIAGNOSTIC_NODE))


@pytest.mark.parametrize("node", gate.FROZEN_DIAGNOSTIC_NODES)
def test_frozen_diagnostic_receipt_is_independently_verified(tmp_path: Path, node: str) -> None:
    _diagnostic_receipt(tmp_path, node)
    verified = gate.verify_frozen_diagnostic_receipt(tmp_path)
    assert verified["diagnostic_node_id"] == node
    assert verified["failure_kind"] == gate.FROZEN_DIAGNOSTIC_EXPECTATIONS[node]["failure_kind"]
    assert verified["return_code"] == 1


@pytest.mark.parametrize("mutation", ["return", "exception", "hash", "source", "node"])
def test_frozen_diagnostic_receipt_rejects_wrong_outcome_or_binding(tmp_path: Path, mutation: str) -> None:
    _diagnostic_receipt(tmp_path)
    receipt_path = tmp_path / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if mutation == "return":
        receipt["return_code"] = 0
    elif mutation == "exception":
        (tmp_path / "stdout.txt").write_text("1 failed in 0.01s\n", encoding="utf-8")
        receipt["stdout_sha256"] = hashlib.sha256((tmp_path / "stdout.txt").read_bytes()).hexdigest()
    elif mutation == "hash":
        receipt["stdout_sha256"] = "0" * 64
    elif mutation == "source":
        receipt["source_identity"]["tree"] = "0" * 40
    else:
        receipt["diagnostic_node_id"] = "tests/unit/test_x6_r1_3_6_gate.py::test_other"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(gate.X6R137ValidationError):
        gate.verify_frozen_diagnostic_receipt(tmp_path)


def test_successor_rejects_skipped_historical_gate_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    original = gate._command

    def skipped(root: Path, argv, **kwargs):
        if argv[:2] == [sys.executable, "-c"] and "verify_x6_r1_3_5" in argv[2]:
            raise gate.X6R137ValidationError("X6-R1.3.7: historical gate execution was skipped")
        return original(root, argv, **kwargs)

    monkeypatch.setattr(gate, "_command", skipped)
    with pytest.raises(gate.X6R137ValidationError, match="historical gate execution was skipped"):
        gate.validate_r1_3_5_snapshot()


def test_versioned_document_bindings_are_required_and_shared_documents_excluded() -> None:
    published = gate.validate_r1_3_6_snapshot()["plan"]
    published_paths = {row["path"] for row in published["source_bindings"]}
    assert {"docs/DECISION_X6_R1_3_6.md", "docs/STATUS_X6_R1_3_6.md"} <= published_paths
    assert {"docs/DECISIONS.md", "docs/STATUS.md"}.isdisjoint(published_paths)
    current = json.loads((gate.ROOT / gate.PLAN).read_text(encoding="utf-8"))
    current_paths = {row["path"] for row in current["source_bindings"]}
    assert {"docs/DECISION_X6_R1_3_7.md", "docs/STATUS_X6_R1_3_7.md"} <= current_paths
    assert {"docs/DECISIONS.md", "docs/STATUS.md"}.isdisjoint(current_paths)


def test_historical_blob_integrity_is_checked_after_valid_snapshot_context() -> None:
    receipts: list[dict[str, object]] = []
    plan_path = "plans/expansion/X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION_V1.json"
    with gate._detached_snapshot(gate.ROOT, gate.R1_3_5, receipts=receipts) as snapshot:
        plan = gate._validate_bindings(
            snapshot,
            plan_path,
            "X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION",
        )
        bound = snapshot / plan["source_bindings"][0]["path"]
        assert bound.is_file()
        bound.write_bytes(bound.read_bytes() + b"\nR1.3.7 disposable blob substitution")
        with pytest.raises(gate.X6R137ValidationError, match="historical source binding drift"):
            gate._validate_bindings(
                snapshot,
                plan_path,
                "X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION",
            )
