import json
from pathlib import Path

import pytest

import src.expansion.x6_r1_failure_terminalization as terminal
from src.expansion.x6_r1_1_failure_audit import audit_baseline_after
import src.expansion.x6_r1_1_gate as x6_r1_1_gate
from src.expansion.x6_r1_1_gate import X6R11GateError, verify_x6_r1_1
from src.expansion.x6_r1_failure_terminalization import EXPECTED_ACCEPTANCE_ARTIFACTS, terminalize_x6_r1_failure
from tests.accepted_runtime import require_materialized_receipts


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "plans/expansion/X6_R1_1_FAILED_PILOT_FAILURE_RECEIPT_V1.json"


def _root(tmp_path: Path) -> Path:
    (tmp_path / "mutation").mkdir(); (tmp_path / "validation").mkdir(); (tmp_path / "raw").mkdir()
    (tmp_path / "mutation/action_journal.json").write_text(json.dumps({"actions": [{"status": "COMMAND_ACCEPTED"}]}))
    (tmp_path / "mutation/mutation_effectiveness.json").write_text(json.dumps({"status": "MUTATION_EFFECTIVE"}))
    (tmp_path / "mutation/restoration_record.json").write_text(json.dumps({"status": "RESTORATION_CONFIRMED"}))
    (tmp_path / "mutation/standalone_replay.json").write_text(json.dumps({"status": "STANDALONE_REPLAY_CONFIRMED"}))
    (tmp_path / "validation/baseline_before.json").write_text(json.dumps({"status": "BASELINE_VALID"}))
    (tmp_path / "validation/baseline_after.json").write_text(json.dumps({"status": "BASELINE_INVALID_AFTER"}))
    (tmp_path / "raw/probe.json").write_text("raw")
    return tmp_path


def test_baseline_after_terminalization_is_atomic_diagnostic_and_idempotent(tmp_path: Path) -> None:
    root = _root(tmp_path)
    error = RuntimeError("X6-R1 baseline-after did not return within frozen thresholds")
    first = terminalize_x6_r1_failure(root, terminal_phase="baseline_after_validation", last_successful_phase="restoration_and_standalone_replay", error=error, cleanup_status="RESTORATION_AND_REPLAY_COMPLETED")
    second = terminalize_x6_r1_failure(root, terminal_phase="ignored", last_successful_phase="ignored", error=RuntimeError("ignored"), cleanup_status="ignored")
    assert first == second
    assert first["terminal_lifecycle_status"] == "DIAGNOSTIC_NON_AUTHORITATIVE"
    assert first["baseline_after_status"] == "BASELINE_INVALID_AFTER"
    assert first["mutation"] == {"attempted": True, "command_accepted": True, "effective": True}
    assert set(first["missing_expected_artifacts"]) == set(EXPECTED_ACCEPTANCE_ARTIFACTS)
    assert not any((root / item).exists() for item in EXPECTED_ACCEPTANCE_ARTIFACTS)


def test_mutation_rejection_and_recovery_failure_remain_diagnostic(tmp_path: Path) -> None:
    root = _root(tmp_path)
    (root / "mutation/action_journal.json").write_text(json.dumps({"actions": [{"status": "FAILED"}]}))
    result = terminalize_x6_r1_failure(root, terminal_phase="recovery_or_replay", last_successful_phase="pre_mutation", error=RuntimeError("mutation command rejected"), cleanup_status="RECOVERY_OR_REPLAY_FAILED")
    assert result["mutation"]["attempted"] is True and result["mutation"]["command_accepted"] is False
    assert result["restoration"]["status"] == "RESTORATION_CONFIRMED"


def test_terminal_write_failure_is_not_a_fabricated_terminal_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(terminal, "write_json_atomic", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        terminalize_x6_r1_failure(root, terminal_phase="baseline_after_validation", last_successful_phase="recovery", error=RuntimeError("original"), cleanup_status="complete")
    assert not (root / "validation/terminal_lifecycle_v1.json").exists()


def test_source_gate_and_archive_free_behavior() -> None:
    result = verify_x6_r1_1(ROOT)
    assert result["materialized"] in {"32/32_HASH_BOUND_PASS", "SKIPPED_PRIVATE_ARCHIVE_ABSENT"}


def _receipt_gate_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, materialize_empty_run: bool) -> Path:
    plan = json.loads((ROOT / "plans/expansion/X6_R1_1_FAILED_PILOT_TERMINALIZATION_AND_BASELINE_RECOVERY_AUDIT_V1.json").read_text())
    receipt = json.loads(RECEIPT.read_text())
    run = tmp_path / receipt["relative_run_path"]
    if materialize_empty_run:
        run.mkdir(parents=True)
    digests = {row["path"]: row["sha256"] for row in plan["source_bindings"]}
    monkeypatch.setattr(x6_r1_1_gate, "verify_x6_r1_source", lambda _root: {})
    monkeypatch.setattr(x6_r1_1_gate, "_load", lambda path: receipt if path.name == RECEIPT.name else plan)
    monkeypatch.setattr(x6_r1_1_gate, "_digest", lambda path: digests.get(path.as_posix().removeprefix(tmp_path.as_posix() + "/"), "unavailable"))
    return tmp_path


def test_explicit_materialized_requirement_fails_when_single_run_archive_is_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _receipt_gate_root(tmp_path, monkeypatch, materialize_empty_run=False)
    with pytest.raises(X6R11GateError, match="required materialized consumed tree is absent"):
        verify_x6_r1_1(root, verify_materialized=True)


def test_present_but_incomplete_materialized_run_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _receipt_gate_root(tmp_path, monkeypatch, materialize_empty_run=True)
    with pytest.raises(X6R11GateError, match="materialized artifact drifted"):
        verify_x6_r1_1(root, verify_materialized=True)


@pytest.mark.accepted_runtime
def test_materialized_failure_receipt_and_read_only_audit() -> None:
    require_materialized_receipts(ROOT, RECEIPT)
    result = verify_x6_r1_1(ROOT, verify_materialized=True)
    audit = result["audit"]
    assert result["materialized"] == "32/32_HASH_BOUND_PASS"
    assert audit["recomputed_status"] == "BASELINE_INVALID_AFTER"
    assert audit["classification"] == "C_INSUFFICIENT_EVIDENCE"
