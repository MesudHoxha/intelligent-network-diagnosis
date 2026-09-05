"""R1.3.6 source-only production-path and adversarial enforcement tests."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from src.expansion import x6_r1_3_6_materialized_verifier as verifier
from src.orchestration import x6_r1_3_6_production_path as path
from src.orchestration import x6_r1_3_6_recovery as recovery
from src.runtime.subprocesses import run_capture


IDENTITY = {"git_commit": "a" * 40, "git_tree": "b" * 40, "topology_path": path.TOPOLOGY, "topology_sha256": "c" * 64, "dockerfile_path": path.DOCKERFILE, "dockerfile_sha256": "d" * 64, "source_hashes": {}, "r1_3_6_tracked_hashes": {path.TOPOLOGY: "c" * 64, path.DOCKERFILE: "d" * 64, "src/orchestration/x6_r1_3_6_production_path.py": "e" * 64, "src/expansion/x6_r1_3_6_materialized_verifier.py": "f" * 64}}


@pytest.fixture(autouse=True)
def _source_test_measurements(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {feature: {"availability": "observed", "value": 100 if feature == "throughput_mbps" else 0} for feature in path.NUMERIC_FEATURES}
    monkeypatch.setattr(path, "derive_window", lambda *args, **kwargs: values)


class FakeTiming:
    def __init__(self) -> None: self.value = 7_000_000_000
    def monotonic(self) -> int: return self.value
    def wait(self, seconds: int) -> None: self.value += seconds * 1_000_000_000


def _authorization(*, source_test_only: bool = True) -> dict[str, object]:
    value = {"schema_version": 1, "release_id": path.FUTURE_AUTHORIZATION_RELEASE, "authorization_id": "r1-4-future-test", "scope": path.SCOPE, "source_identity": IDENTITY, "tracked_source_hashes": IDENTITY["r1_3_6_tracked_hashes"], "output_root": "out", "run_id": "run", "issued_ns": 1, "expires_ns": 999999999999, "source_test_only": source_test_only, "historical_authorization": path.HISTORICAL_VECTOR, "schedule": path.SCHEDULE, "traffic": path.TRAFFIC, "ownership": path.OWNERSHIP, "prohibitions": path.PROHIBITIONS}
    value["authorization_sha256"] = path.sha256(path.canonical_bytes(value)); return value


def _executor(timing: FakeTiming):
    def execute(argv: list[str]) -> dict[str, object]:
        if argv == path.COMMANDS["iperf"]: timing.wait(20); output = "{}"
        elif argv == path.COMMANDS["qdisc"]: output = '[{"kind":"noqueue","handle":"0:"}]'
        elif argv in (path.COMMANDS["filters"], path.COMMANDS["processes"], path.COMMANDS["namespaces"]): output = "[]"
        elif argv in (path.COMMANDS["r2_tx"], path.COMMANDS["r3_rx"]): output = "1"
        elif argv in (path.COMMANDS["r2_speed"], path.COMMANDS["r3_speed"]): output = "1000"
        else: output = "ok"
        return {"return_code": 0, "stdout": output, "stderr": ""}
    return execute


def _tree(tmp_path: Path) -> tuple[Path, FakeTiming]:
    timing = FakeTiming(); raw = path.canonical_bytes(_authorization())
    path.execute_source_test_core(authorization_bytes=raw, run_root=tmp_path / "run", run_id="run", output_root="out", identity=IDENTITY, executor=_executor(timing), timing=timing, now_ns=2)
    return tmp_path / "run", timing


def _recover_in_child(root: Path, timing_value: int) -> None:
    script = """
import sys
from pathlib import Path
from src.orchestration import x6_r1_3_6_recovery as r
from src.orchestration import x6_r1_3_6_production_path as p
identity = eval(sys.argv[2], {\"__builtins__\": {}})
def execute(argv):
    if argv == p.COMMANDS['qdisc']: out='[{\"kind\":\"noqueue\",\"handle\":\"0:\"}]'
    elif argv in (p.COMMANDS['filters'], p.COMMANDS['processes'], p.COMMANDS['namespaces']): out='[]'
    elif argv in (p.COMMANDS['r2_tx'], p.COMMANDS['r3_rx']): out='1'
    elif argv in (p.COMMANDS['r2_speed'], p.COMMANDS['r3_speed']): out='1000'
    else: out='ok'
    return {\"return_code\":0,\"stdout\":out,\"stderr\":\"\"}
state=r.prevalidate_recovery(Path(sys.argv[1]), identity=identity, allow_source_test=True)
r.recover_core(Path(sys.argv[1]), prevalidated=state, executor=execute)
"""
    result = run_capture([sys.executable, "-c", script, str(root), repr(IDENTITY)], timeout_seconds=30, cwd=Path.cwd())
    assert result.returncode == 0, result.stderr


def test_production_rejects_absent_and_test_only_authorization_before_commands(tmp_path: Path) -> None:
    with pytest.raises(path.X6R136Error):
        path.validate_authorization(_authorization(source_test_only=True), identity=IDENTITY, run_id="run", output_root="out", now_ns=2, allow_source_test=False)
    result = run_capture([sys.executable, "-m", "src.orchestration.x6_r1_3_6_production_path"], timeout_seconds=30, cwd=Path.cwd())
    assert result.returncode != 0 and not (tmp_path / "run").exists()


def test_source_test_core_materializes_actual_relationships_and_freezes_c10(tmp_path: Path) -> None:
    root, _ = _tree(tmp_path)
    assert (root / "state" / "threshold_freeze.json").is_file()
    c10 = json.loads((root / "raw/windows/C10.json").read_text())
    c11 = json.loads((root / "raw/windows/C11.json").read_text())
    assert c11["timing"]["actual_start_ns"] >= c10["timing"]["actual_end_ns"] + 5_000_000_000
    assert c10["timing"]["actual_start_ns"] != 9 * 25_000_000_000
    assert len(list((root / "raw/windows").glob("*.json"))) == 30


@pytest.mark.parametrize("mutation", ["ordering", "duration", "spacing", "manifest", "vector", "inventory"])
def test_verifier_rejects_lifecycle_and_authorization_adversaries(tmp_path: Path, mutation: str) -> None:
    root, _ = _tree(tmp_path)
    if mutation == "ordering":
        row = json.loads((root / "raw/windows/C11.json").read_text()); row["window_id"] = "C01"; (root / "raw/windows/C11.json").write_bytes(path.canonical_bytes(row))
    elif mutation == "duration":
        row = json.loads((root / "raw/windows/C01.json").read_text()); row["timing"]["actual_end_ns"] = row["timing"]["actual_start_ns"]; (root / "raw/windows/C01.json").write_bytes(path.canonical_bytes(row))
    elif mutation == "spacing":
        row = json.loads((root / "raw/windows/C11.json").read_text()); row["timing"]["actual_start_ns"] -= 5_000_000_000; (root / "raw/windows/C11.json").write_bytes(path.canonical_bytes(row))
    elif mutation == "manifest":
        row = json.loads((root / "state/threshold_freeze.json").read_text()); row["after_window_id"] = "C11"; (root / "state/threshold_freeze.json").write_bytes(path.canonical_bytes(row))
    elif mutation == "vector":
        row = json.loads((root / "state/authorization.json").read_text()); row["historical_authorization"]["measurement"] = True; row["authorization_sha256"] = path.sha256(path.canonical_bytes({key: value for key, value in row.items() if key != "authorization_sha256"})); (root / "state/authorization.json").write_bytes(path.canonical_bytes(row))
    else: (root / "unexpected.txt").write_text("x")
    with pytest.raises(verifier.X6R136VerificationError): verifier.verify_materialized_production_path(root, identity=IDENTITY, allow_source_test=True)


def test_recovery_prevalidation_precedes_cleanup_and_requires_distinct_process(tmp_path: Path) -> None:
    root, timing = _tree(tmp_path)
    terminal = json.loads((root / "terminal/terminal.json").read_text()); terminal["status"] = "INTERRUPTED"; (root / "terminal/terminal.json").write_bytes(path.canonical_bytes(terminal)); path.finalize_inventory(root)
    state = recovery.prevalidate_recovery(root, identity=IDENTITY, allow_source_test=True)
    with pytest.raises(recovery.X6R136RecoveryError, match="distinct"):
        recovery.recover_core(root, prevalidated=state, executor=_executor(timing))
    _recover_in_child(root, timing.value)
    result = verifier.verify_materialized_production_path(root, identity=IDENTITY, allow_source_test=True)
    assert result["terminal_status"] == verifier.TERMINAL and result["qualified"] is False


@pytest.mark.parametrize("mutation", ["ledger", "ownership", "inventory", "same_pid", "residual", "cleanup"])
def test_recovery_adversaries_fail_before_or_during_replay(tmp_path: Path, mutation: str) -> None:
    root, timing = _tree(tmp_path)
    terminal = json.loads((root / "terminal/terminal.json").read_text()); terminal["status"] = "INTERRUPTED"; (root / "terminal/terminal.json").write_bytes(path.canonical_bytes(terminal)); path.finalize_inventory(root)
    if mutation == "ledger": (root / "state/authorization_ledger.json").unlink()
    elif mutation == "ownership": (root / "state/ownership.json").write_text("{}")
    elif mutation == "inventory": (root / "state/artifact_inventory.json").write_text("{}")
    elif mutation == "same_pid":
        state = recovery.prevalidate_recovery(root, identity=IDENTITY, allow_source_test=True)
        with pytest.raises(recovery.X6R136RecoveryError): recovery.recover_core(root, prevalidated=state, executor=_executor(timing))
        return
    else:
        state = recovery.prevalidate_recovery(root, identity=IDENTITY, allow_source_test=True)
        def bad(argv: list[str]):
            row = _executor(timing)(argv)
            if mutation == "cleanup" and argv == path.COMMANDS["cleanup"]: row["return_code"] = 1
            if mutation == "residual" and argv == path.COMMANDS["processes"]: row["stdout"] = "clab-x6r1-r2"
            return row
        with pytest.raises(recovery.X6R136RecoveryError): recovery.recover_core(root, prevalidated=state, executor=bad)
        return
    with pytest.raises(recovery.X6R136RecoveryError): recovery.prevalidate_recovery(root, identity=IDENTITY, allow_source_test=True)


def test_production_cli_has_no_old_runner_or_injected_controls() -> None:
    source = Path(path.__file__).read_text(encoding="utf-8")
    assert "x6_r1_3_4_baseline_execution" not in source
    assert "parser.add_argument(\"--executor\"" not in source
    assert "parser.add_argument(\"--clock\"" not in source
    assert "parser.add_argument(\"--pid\"" not in source
    assert "shell=False" not in source  # subprocess abstraction owns this invariant.
