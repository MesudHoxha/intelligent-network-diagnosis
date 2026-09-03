"""Synthetic-only B2 recovery and materialized-verifier adversarial tests."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from src.expansion import x6_r1_3_5_materialized_verifier as verifier
from src.orchestration import x6_r1_3_5_authorization as authorization
from src.orchestration import x6_r1_3_5_baseline_lifecycle as lifecycle
from src.orchestration import x6_r1_3_5_baseline_provenance as provenance
from src.runtime.subprocesses import run_capture


IDENTITY = {"git_commit": "a" * 40, "git_tree": "b" * 40, "topology_sha256": "c" * 64, "image_id": "d"}


def _authorization() -> dict[str, object]:
    value = {
        "schema_version": 1,
        "authorization_id": "source-test-only",
        "scope": authorization.SCOPE,
        "source_identity": IDENTITY,
        "output_root": "run",
        "issued_ns": 1,
        "expires_ns": 9,
        "source_test_only": True,
        "prohibitions": {key: True for key in authorization.FALSE_VECTOR},
    }
    value["authorization_sha256"] = provenance.sha256(provenance.canonical_bytes(value))
    return value


def _executor(command: list[str]) -> dict[str, object]:
    if command == provenance.COMMANDS["qdisc"]:
        output = '[{"kind":"noqueue","handle":"0:"}]'
    elif command in (provenance.COMMANDS["filters"], provenance.COMMANDS["processes"], provenance.COMMANDS["namespaces"]):
        output = "[]"
    elif command in (provenance.COMMANDS["r2_tx"], provenance.COMMANDS["r3_rx"]):
        output = "1"
    elif command in (provenance.COMMANDS["r2_speed"], provenance.COMMANDS["r3_speed"]):
        output = "1000"
    else:
        output = "ok"
    return {"return_code": 0, "stdout": output, "stderr": ""}


def _build_b1_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "authorization.json"
    path.write_bytes(provenance.canonical_bytes(_authorization()))
    root = tmp_path / "run"
    recorder = lifecycle.initialize_b1(
        root,
        authorization_path=path,
        ledger_root=tmp_path / "ledger",
        run_id="run",
        output_root="run",
        identity=IDENTITY,
        now_ns=2,
    )
    values = {feature: {"availability": "observed", "value": 100 if feature == "throughput_mbps" else 0} for feature in lifecycle.NUMERIC_FEATURES}
    monkeypatch.setattr(lifecycle, "derive_window", lambda *args, **kwargs: values)
    lifecycle.collect_thirty(recorder, executor=_executor, speed_mbps=1000)
    lifecycle.finalize_inventory(root)
    return root


def _recover_in_child(root: Path) -> None:
    """Use the bounded wrapper and a test-only injected executor in another PID."""
    script = """
import sys
from pathlib import Path
from src.orchestration import x6_r1_3_5_baseline_lifecycle as l
from src.orchestration import x6_r1_3_5_baseline_provenance as p
def e(command):
    if command == p.COMMANDS['qdisc']: out = '[{\\"kind\\":\\"noqueue\\",\\"handle\\":\\"0:\\"}]'
    elif command in (p.COMMANDS['filters'], p.COMMANDS['processes'], p.COMMANDS['namespaces']): out = '[]'
    else: out = 'ok'
    return {'return_code': 0, 'stdout': out, 'stderr': ''}
l.recover(Path(sys.argv[1]), executor=e)
"""
    result = run_capture([sys.executable, "-c", script, str(root)], timeout_seconds=30, cwd=Path.cwd())
    assert result.returncode == 0, result.stderr


def test_b2_distinct_process_recovery_rebuilds_inventory_and_derives_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _build_b1_tree(tmp_path, monkeypatch)
    _recover_in_child(root)
    recovery = json.loads((root / "state/recovery.json").read_text())
    assert recovery["original_pid"] != recovery["recovery_pid"]
    result = verifier.derive_final_source_contract_terminal(root, run_id="run", output_root="run", identity=IDENTITY)
    assert result["terminal_status"] == "R1.3.5_SOURCE_CONTRACT_COMPLETE_FOR_AUTHORIZATION_REVIEW", result
    assert result["qualified"] is False


def test_b2_recovery_rejects_same_pid_and_missing_or_cross_run_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _build_b1_tree(tmp_path, monkeypatch)
    with pytest.raises(provenance.X6R135Error, match="distinct process"):
        lifecycle.recover(root, executor=_executor)
    _recover_in_child(root)
    recovery_path = root / "state/recovery.json"
    recovery = json.loads(recovery_path.read_text())
    recovery["run_id"] = "foreign"
    recovery_path.write_text(json.dumps(recovery))
    lifecycle.finalize_inventory(root)
    assert verifier.derive_final_source_contract_terminal(root, run_id="run", output_root="run", identity=IDENTITY)["terminal_status"] == "VERIFICATION_FAILED"


@pytest.mark.parametrize("mutation", ["cleanup_failed", "final_before_cleanup", "residual", "missing_recovery"])
def test_b2_raw_recovery_controls_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    root = _build_b1_tree(tmp_path, monkeypatch)
    _recover_in_child(root)
    inventory = json.loads((root / "state/command_inventory.json").read_text())
    recovery_rows = inventory["records"][-9:]
    if mutation == "missing_recovery":
        (root / "state/recovery.json").unlink()
    else:
        index = {"cleanup_failed": 4, "final_before_cleanup": 5, "residual": 5}[mutation]
        path = root / recovery_rows[index]["reference"]["path"]
        row = json.loads(path.read_text())
        if mutation == "cleanup_failed":
            row["return_code"] = 1
        elif mutation == "final_before_cleanup":
            row["started_monotonic_ns"] = 0
            row["completed_monotonic_ns"] = 0
            row["elapsed_ns"] = 0
        else:
            row["stdout"] = "clab-x6r1-r2"
        row["record_sha256"] = provenance.sha256(provenance.canonical_bytes({key: value for key, value in row.items() if key != "record_sha256"}))
        path.write_bytes(provenance.canonical_bytes(row))
        recovery_rows[index]["reference"]["sha256"] = provenance.sha256(path.read_bytes())
        (root / "state/command_inventory.json").write_bytes(provenance.canonical_bytes(inventory))
    lifecycle.finalize_inventory(root)
    result = verifier.derive_final_source_contract_terminal(root, run_id="run", output_root="run", identity=IDENTITY)
    expected = "CLEANUP_FAILED" if mutation == "cleanup_failed" else "VERIFICATION_FAILED"
    assert result["terminal_status"] == expected, result


def test_b2_repeated_replay_is_idempotent_and_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _build_b1_tree(tmp_path, monkeypatch)
    _recover_in_child(root)
    _recover_in_child(root)
    recovery = json.loads((root / "state/recovery.json").read_text())
    assert recovery["replay_count"] == 2
    assert verifier.verify_b2_artifacts(root, run_id="run", authorization_id="source-test-only")["replay_count"] == 2
