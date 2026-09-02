"""Synthetic-only tests for prospective X6-R1.3.3 preparation."""
from __future__ import annotations
import copy, hashlib, json, os
from pathlib import Path
import pytest
from src.orchestration import x6_r1_3_3_baseline_only_runner as runner
from src.expansion import x6_r1_3_3_baseline_control_verifier as verifier

SOURCE = {"git_commit": "a" * 40, "git_tree": "b" * 40, "topology_sha256": "c" * 64, "image_id": "sha256:" + "d" * 64, "traffic_sha256": "e" * 64}
BINDINGS = {"plan": "f" * 64, "contract": "1" * 64, "verifier": "2" * 64, "tests": "3" * 64}

def auth(*, enabled: bool = True) -> dict[str, object]:
    row: dict[str, object] = {"schema_version": 1, "authorization_id": "synthetic-x6-r1-4-only", "scope": runner.SCOPE, "maximum_attempts": 1, "source_identity": SOURCE, "bindings": BINDINGS, "mutation_prohibited": True, "runtime_enabled": enabled}
    row["authorization_sha256"] = hashlib.sha256((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest(); return row

def ref(root: Path, path: str, payload: object) -> dict[str, str]:
    target = root / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    return {"path": path, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

def controls(root: Path) -> dict[str, object]:
    q = {"interface": "clab-x6r1-r2:eth2", "qdisc": {"kind": "noqueue", "handle": "0:", "children": []}}
    f = {"interface": "clab-x6r1-r2:eth2", "filters": []}
    return {"qdisc_before": ref(root, "raw/q-before.json", q), "qdisc_after": ref(root, "raw/q-after.json", q), "filters_before": ref(root, "raw/f-before.json", f), "filters_after": ref(root, "raw/f-after.json", f), "counters": ref(root, "raw/counters.json", [{"interface": "clab-x6r1-r2:eth2", "monotonic_ns": 1, "rx_packets": 1, "tx_packets": 1}, {"interface": "clab-x6r1-r2:eth2", "monotonic_ns": 2, "rx_packets": 2, "tx_packets": 2}]), "cleanup": ref(root, "raw/cleanup.json", {"owned_processes": [], "containers": [], "namespaces": [], "temporary_resources": []}), "replay": ref(root, "raw/replay.json", {"new_process": True, "status": "IDEMPOTENT_RECOVERY_CONFIRMED"}), "authorization_ledger": ref(root, "raw/ledger.json", {"state": "CONSUMED", "authorization_id": "synthetic", "authorization_sha256": "a" * 64})}

def test_future_authorization_and_atomic_consumption(tmp_path: Path) -> None:
    value = runner.validate_authorization(auth(), expected_source=SOURCE, expected_bindings=BINDINGS)
    first = runner.consume_attempt(tmp_path / "ledger", value, run_id="run-1", pid=7)
    assert json.loads(first.read_text())["state"] == "CONSUMED"
    with pytest.raises(runner.X6R133HarnessError, match="already reserved"):
        runner.consume_attempt(tmp_path / "ledger", value, run_id="run-2")

@pytest.mark.parametrize("mutation", ["missing", "scope", "source", "binding", "rehash", "disabled"])
def test_authorization_adversaries_fail_closed(mutation: str) -> None:
    value = auth()
    if mutation == "missing": value = {}  # type: ignore[assignment]
    elif mutation == "scope": value["scope"] = "F1"
    elif mutation == "source": value["source_identity"] = {}
    elif mutation == "binding": value["bindings"] = {}
    elif mutation == "rehash": value["authorization_sha256"] = "0" * 64
    else: value["runtime_enabled"] = False
    with pytest.raises(runner.X6R133HarnessError): runner.validate_authorization(value, expected_source=SOURCE, expected_bindings=BINDINGS)

@pytest.mark.parametrize("command", [["bash", "-lc", "sudo modprobe sch_netem"], ["docker", "exec", "x", "tc", "qdisc", "replace"], ["ip", "route", "add", "x"], ["echo", "x"]])
def test_wrappers_mutations_and_unbounded_commands_are_rejected(command: list[str]) -> None:
    with pytest.raises(runner.X6R133HarnessError): runner.validate_command(command)

def test_frozen_schedule_and_copy_recovery_fail_closed(tmp_path: Path) -> None:
    schedule = runner.frozen_schedule(); assert len(schedule["windows"]) == 30 and schedule["mutation"] == "FORBIDDEN"
    value = runner.validate_authorization(auth(), expected_source=SOURCE, expected_bindings=BINDINGS)
    runner.initialize_attempt(tmp_path / "run", authorization=value, ledger_root=tmp_path / "ledger", run_id="r")
    with pytest.raises(runner.X6R133HarnessError): runner.initialize_attempt(tmp_path / "run", authorization=value, ledger_root=tmp_path / "ledger2", run_id="copy")
    with pytest.raises(runner.X6R133HarnessError): runner.recover_attempt(tmp_path / "missing")

@pytest.mark.parametrize("mutation", ["qdisc", "counter", "cleanup", "replay", "ledger", "hash"])
def test_raw_control_adversaries_fail_closed(tmp_path: Path, mutation: str) -> None:
    value = controls(tmp_path)
    if mutation == "qdisc": (tmp_path / "raw/q-after.json").write_text("{}")
    elif mutation == "counter": (tmp_path / "raw/counters.json").write_text(json.dumps([{ "interface": "clab-x6r1-r2:eth2", "monotonic_ns": 2, "rx_packets": 2, "tx_packets": 2}, {"interface": "clab-x6r1-r2:eth2", "monotonic_ns": 1, "rx_packets": 1, "tx_packets": 1}]))
    elif mutation == "cleanup": (tmp_path / "raw/cleanup.json").write_text(json.dumps({"owned_processes": [1], "containers": [], "namespaces": [], "temporary_resources": []}))
    elif mutation == "replay": (tmp_path / "raw/replay.json").write_text(json.dumps({"new_process": False, "status": "IDEMPOTENT_RECOVERY_CONFIRMED"}))
    elif mutation == "ledger": (tmp_path / "raw/ledger.json").write_text(json.dumps({"state": "PLANNED"}))
    else: value["qdisc_before"]["sha256"] = "0" * 64
    with pytest.raises(verifier.X6R133VerifierError): verifier.verify_raw_controls(value, run_root=tmp_path)

def test_raw_controls_are_independently_derived(tmp_path: Path) -> None:
    result = verifier.verify_raw_controls(controls(tmp_path), run_root=tmp_path)
    assert result == {"qdisc_filter_state_valid": True, "counter_continuity_valid": True, "cleanup_valid": True, "replay_valid": True, "authorization_consumed": True}
