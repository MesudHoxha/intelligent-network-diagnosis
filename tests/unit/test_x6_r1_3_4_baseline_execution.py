"""Synthetic-only R1.3.4 lifecycle and materialized-verifier tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.expansion import x6_r1_3_4_materialized_verifier as verifier
from src.orchestration import x6_r1_3_4_baseline_execution as runner

SOURCE = {"git_commit": "a" * 40, "git_tree": "b" * 40, "topology_sha256": "c" * 64, "image_id": "sha256:" + "d" * 64, "traffic_sha256": "e" * 64}
BINDINGS = {"plan": "f" * 64, "runner": "1" * 64, "verifier": "2" * 64, "tests": "3" * 64}


def _authorization() -> dict[str, object]:
    value: dict[str, object] = {"schema_version": 1, "authorization_id": "temporary-source-test-only", "scope": "BASELINE_ONLY_QUALIFICATION", "maximum_attempts": 1, "source_identity": SOURCE, "bindings": BINDINGS, "mutation_prohibited": True, "runtime_enabled": True}
    value["authorization_sha256"] = hashlib.sha256((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()
    return value


def _write_authorization(path: Path) -> None:
    path.write_text(json.dumps(_authorization(), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _executor(command: list[str]) -> dict[str, object]:
    if command == runner.COMMANDS["qdisc"]:
        out = '[{"kind":"noqueue","handle":"0:"}]'
    elif command in (runner.COMMANDS["filters_root"], runner.COMMANDS["filters_ingress"]):
        out = "[]"
    elif command in (runner.COMMANDS["r2_speed"], runner.COMMANDS["r3_speed"]):
        out = "1000\n"
    else:
        out = ""
    return {"return_code": 0, "stdout": out, "stderr": ""}


def _collector(seen: list[str]):
    def collect(window_id: str) -> dict[str, object]:
        seen.append(window_id)
        values = {"packet_loss_ratio": 0.0, "round_trip_latency_ms_p95": 1.0, "throughput_mbps": 100.0, "interface_utilization_ratio": 0.1, "queue_drop_count": 0.0}
        index = len(seen) - 1; start = 20_000_000_000 + index * 25_000_000_000
        return {"measurements": values, "observations": dict(values), "raw": {"synthetic": True, "window_id": window_id}, "timing": {"actual_start_ns": start, "actual_end_ns": start + 20_000_000_000, "startup_skew_seconds": 0.0}}
    return collect


def _clock() -> callable:
    state = {"value": 0}
    def now() -> int:
        state["value"] += 1_000_000_000
        return state["value"]
    return now


def test_temporary_authorization_runs_exact_lifecycle_and_never_qualifies(tmp_path: Path) -> None:
    authorization = tmp_path / "authorization.json"; _write_authorization(authorization)
    seen: list[str] = []
    terminal = runner.execute(authorization_path=authorization, run_root=tmp_path / "run", ledger_root=tmp_path / "ledger", run_id="synthetic", expected_source=SOURCE, expected_bindings=BINDINGS, executor=_executor, collector=_collector(seen), source_test_only=True, clock=_clock(), sleeper=lambda _: None)
    assert terminal["status"] == "INCONCLUSIVE"
    assert seen == list(runner.WINDOW_IDS)
    root = tmp_path / "run"
    freeze = json.loads((root / "state" / "threshold_freeze.json").read_text())
    assert freeze["after_window_id"] == "C10" and (root / "raw" / "windows" / "H10.json").is_file()
    result = verifier.verify_materialized_run(root, repository_root=Path(__file__).resolve().parents[2])
    assert result["all_windows_complete"] is True and result["qualified"] is False and result["source_test_only"] is True


@pytest.mark.parametrize("mutation", ["different_observation", "missing_feature"])
def test_window_contract_rejects_ambiguous_or_incomplete_values(tmp_path: Path, mutation: str) -> None:
    def bad(window_id: str) -> dict[str, object]:
        values = {"packet_loss_ratio": 0.0, "round_trip_latency_ms_p95": 1.0, "throughput_mbps": 100.0, "interface_utilization_ratio": 0.1, "queue_drop_count": 0.0}
        observations = dict(values)
        if mutation == "different_observation": observations["throughput_mbps"] = 99.0
        else: values.pop("queue_drop_count")
        return {"measurements": values, "observations": observations, "raw": {}, "timing": {"actual_start_ns": 20_000_000_000, "actual_end_ns": 40_000_000_000, "startup_skew_seconds": 0.0}}
    with pytest.raises(runner.X6R134Error):
        runner.collect_thirty_windows(tmp_path, bad, source_test_only=True, clock=_clock(), sleeper=lambda _: None)


def test_single_attempt_is_consumed_before_the_first_executor_call(tmp_path: Path) -> None:
    authorization = tmp_path / "authorization.json"; _write_authorization(authorization)
    observed: list[bool] = []
    def checking_executor(command: list[str]) -> dict[str, object]:
        observed.append((tmp_path / "ledger" / "temporary-source-test-only.json").is_file())
        return _executor(command)
    runner.execute(authorization_path=authorization, run_root=tmp_path / "run", ledger_root=tmp_path / "ledger", run_id="one", expected_source=SOURCE, expected_bindings=BINDINGS, executor=checking_executor, collector=_collector([]), source_test_only=True, clock=_clock(), sleeper=lambda _: None)
    assert observed and all(observed)


def test_materialized_verifier_rejects_changed_raw_control(tmp_path: Path) -> None:
    authorization = tmp_path / "authorization.json"; _write_authorization(authorization)
    root = tmp_path / "run"
    runner.execute(authorization_path=authorization, run_root=root, ledger_root=tmp_path / "ledger", run_id="verify", expected_source=SOURCE, expected_bindings=BINDINGS, executor=_executor, collector=_collector([]), source_test_only=True, clock=_clock(), sleeper=lambda _: None)
    (root / "raw" / "qdisc.json").write_text("{}\n")
    with pytest.raises(verifier.X6R134VerificationError):
        verifier.verify_materialized_run(root, repository_root=Path(__file__).resolve().parents[2])


def test_timing_and_later_cohort_manipulation_fail_closed(tmp_path: Path) -> None:
    def overlapping(window_id: str) -> dict[str, object]:
        values = {"packet_loss_ratio": 0.0, "round_trip_latency_ms_p95": 1.0, "throughput_mbps": 100.0, "interface_utilization_ratio": 0.1, "queue_drop_count": 0.0}
        return {"measurements": values, "observations": dict(values), "raw": {}, "timing": {"actual_start_ns": 20_000_000_000, "actual_end_ns": 40_000_000_000, "startup_skew_seconds": 0.0}}
    with pytest.raises(runner.X6R134Error, match="spacing"):
        runner.collect_thirty_windows(tmp_path / "overlap", overlapping, source_test_only=True, clock=_clock(), sleeper=lambda _: None)
    authorization = tmp_path / "authorization.json"; _write_authorization(authorization)
    root = tmp_path / "run"
    runner.execute(authorization_path=authorization, run_root=root, ledger_root=tmp_path / "ledger", run_id="later", expected_source=SOURCE, expected_bindings=BINDINGS, executor=_executor, collector=_collector([]), source_test_only=True, clock=_clock(), sleeper=lambda _: None)
    h01 = root / "raw" / "windows" / "H01.json"; row = json.loads(h01.read_text()); row["canonical_features"]["throughput_mbps"] = 999999.0; h01.write_text(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(verifier.X6R134VerificationError):
        verifier.verify_materialized_run(root, repository_root=Path(__file__).resolve().parents[2])


def test_recovery_is_new_process_and_retains_raw_records(tmp_path: Path) -> None:
    authorization = tmp_path / "authorization.json"; _write_authorization(authorization)
    root = tmp_path / "run"
    runner.execute(authorization_path=authorization, run_root=root, ledger_root=tmp_path / "ledger", run_id="recover", expected_source=SOURCE, expected_bindings=BINDINGS, executor=_executor, collector=_collector([]), source_test_only=True, clock=_clock(), sleeper=lambda _: None)
    replay = runner.recover_attempt(root, executor=_executor, replay_pid=1, source_test_only=True)
    assert replay["new_process"] is True and (root / "state" / "recovery.json").is_file()
