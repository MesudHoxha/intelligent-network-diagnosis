"""Focused source-only checks for the future-F1 production successor."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from src.orchestration.x6_r1_5_contract import ACCEPTED_IMAGE, AUTHORIZATION_RELEASE, PREDECESSOR, TRUST_MODEL, Invalid, accepted_manifest, canonical, current_boot_id, digest, frozen_contract, identity
from src.orchestration.x6_r1_5_durable import load, reservation_path, reserve, stamp
from src.orchestration.x6_r1_5_observations import controls

ROOT = Path(__file__).resolve().parents[2]
STUB = ROOT / "tests/fixtures/x6_r1_5_external_stub.py"


def authorization(root, source, *, authorization_id="synthetic-future-f1"):
    value = {
        "schema_version": 1, "record_kind": "CONCRETE_AUTHORIZATION", "release_id": AUTHORIZATION_RELEASE,
        "trust_model": TRUST_MODEL, "authorization_id": authorization_id, "scope": "F1_PACKET_LOSS_SINGLE_FAULT",
        "source_identity": source, "predecessor": PREDECESSOR, "output_root": str(root), "run_id": "synthetic-f1-run",
        "issued_ns": 0, "expires_ns": 2**63 - 1, "boot_id": current_boot_id(), "source_test_only": True,
        "contract": frozen_contract(), "runtime_image": dict(ACCEPTED_IMAGE),
    }
    value["authorization_sha256"] = digest(canonical(value))
    return value


def isolated_environment(tmp_path, state=None):
    bindir = tmp_path / "bin"; bindir.mkdir()
    for name in {"containerlab", "docker", "ip", "tc", "ps", "uname", "zgrep", "lsmod", "modinfo", "python3", "ethtool", "git"}:
        (bindir / name).symlink_to(STUB)
    state_path = tmp_path / "stub-state.json"
    state_path.write_text(json.dumps(state or {"deployed": False, "qdisc": "baseline"}))
    env = dict(os.environ, PATH=str(bindir), X6_STUB_STATE=str(state_path), X6_R1_5_CONTROLLED_CLOCK="1")
    return env, state_path


def run_cli(tmp_path, *, state=None, authorization_id="synthetic-future-f1"):
    env, state_path = isolated_environment(tmp_path, state)
    run_root = tmp_path / "run"
    source = identity(); auth = authorization(run_root, source, authorization_id=authorization_id)
    auth_path = tmp_path / "authorization.json"; auth_path.write_bytes(canonical(auth))
    command = [sys.executable, "-m", "src.orchestration.x6_r1_5_production_path", "--authorization", str(auth_path), "--run-root", str(run_root), "--run-id", "synthetic-f1-run", "--execute", "--source-test"]
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=60, check=False)
    return result, run_root, auth, source, env, state_path


def test_accepted_manifest_is_exact_and_runtime_has_no_builder():
    manifest = accepted_manifest()
    assert manifest["sha256"] == "0db20fccbb22f7bcde7bc5d7be0d3fd8923e32d663d59297c178dd300ce7c301"
    assert manifest["traffic_context_id"] == "X6_R1_BASELINE_ONLY_QUALIFICATION"
    production = (ROOT / "src/orchestration/x6_r1_5_production_path.py").read_text()
    verifier = (ROOT / "src/expansion/x6_r1_5_materialized_verifier.py").read_text()
    assert "build_threshold_manifest" not in production + verifier


def test_freeze_record_tampering_and_authorization_context_drift_fail_closed(tmp_path):
    target = tmp_path / "plans/expansion"; target.mkdir(parents=True)
    record = json.loads((ROOT / "plans/expansion/X6_PROSPECTIVE_SUCCESSOR_PARAMETER_THRESHOLD_FREEZE_V1.json").read_text())
    record["frozen_threshold_manifest"]["traffic_context_id"] = "X6_TRAFFIC_01_FROZEN_TCP_AND_PING"
    (target / "X6_PROSPECTIVE_SUCCESSOR_PARAMETER_THRESHOLD_FREEZE_V1.json").write_text(json.dumps(record))
    with pytest.raises(Invalid, match="freeze record drift"):
        accepted_manifest(tmp_path)
    source = identity(); root = tmp_path / "run"; auth = authorization(root, source)
    auth["contract"] = copy.deepcopy(auth["contract"]); auth["contract"]["threshold"]["embedded_sha256"] = "0" * 64
    unsigned = dict(auth); unsigned.pop("authorization_sha256"); auth["authorization_sha256"] = digest(canonical(unsigned))
    from src.orchestration.x6_r1_5_contract import validate_authorization_integrity
    with pytest.raises(Invalid, match="authorization contract"):
        validate_authorization_integrity(auth, root=root, run_id="synthetic-f1-run", source_identity=source, simulation=True)


def row(name, stdout, *, rc=0):
    return {"name": name, "stdout": stdout, "stderr": "", "return_code": rc, "incomplete": False, "interrupted": False, "timed_out": False}


def test_phase_controls_are_distinct_and_reject_mismatch():
    counters = [row("r2_counter", "1"), row("r3_counter", "1")]
    noqueue = [*counters, row("qdisc", '[{"kind":"noqueue","handle":"0:"}]'), row("filters_root", "[]"), row("filters_ingress", "[]")]
    fault = [*counters, row("qdisc", '[{"kind":"netem","handle":"10:","root":true},{"kind":"pfifo","handle":"20:","parent":"10:1"}]'), row("filters_root", "[]"), row("filters_ingress", "[]")]
    assert controls(noqueue, phase="baseline") == [1, 1]
    assert controls(fault, phase="fault") == [1, 1]
    with pytest.raises(Invalid, match="fault qdisc"):
        controls(noqueue, phase="fault")
    with pytest.raises(Invalid, match="healthy qdisc"):
        controls(fault, phase="restored")


def test_production_cli_success_replay_and_authorization_reuse(tmp_path):
    result, run_root, auth, source, env, _ = run_cli(tmp_path)
    assert result.returncode == 0, result.stderr
    terminal = load(run_root / "terminal/terminal.json")
    assert terminal["status"] == "F1_SOURCE_CONTRACT_COMPLETE_REPLAY_REQUIRED" and terminal["qualified"] is False
    replay = subprocess.run([sys.executable, "-m", "src.orchestration.x6_r1_5_recovery", "--run-root", str(run_root), "--source-test"], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60, check=False)
    assert replay.returncode == 0, replay.stderr
    terminal = load(run_root / "terminal/terminal.json")
    assert terminal["status"] == "F1_SOURCE_CONTRACT_COMPLETE_REPLAY_VERIFIED" and terminal["scientific_acceptance"] is False
    from src.expansion.x6_r1_5_materialized_verifier import verify
    verified = verify(run_root, source_identity=source, simulation=True)
    assert verified["windows"] == 16 and verified["fault_effectiveness"] == "MUTATION_EFFECTIVE" and verified["diagnosis"] == "diagnosed" and verified["restoration"] == "RESTORATION_CONFIRMED"
    assert load(run_root / "state/threshold_manifest.json") == accepted_manifest()
    with pytest.raises((FileExistsError, Invalid)):
        reserve(run_root, auth, admission_validator=lambda observation: auth)


def test_altered_observation_is_rejected_by_independent_reconstruction(tmp_path):
    result, run_root, auth, source, env, _ = run_cli(tmp_path, authorization_id="synthetic-altered")
    assert result.returncode == 0, result.stderr
    path = run_root / "raw/windows/B01.json"; value = load(path); value["measurements"]["throughput_mbps"] += 1
    path.write_bytes(canonical(value))
    from src.expansion.x6_r1_5_materialized_verifier import verify
    with pytest.raises(Invalid, match="window summary contradiction"):
        verify(run_root, source_identity=source, simulation=True)


@pytest.mark.parametrize("artifact", ["evidence", "vector", "effectiveness", "diagnosis", "identity", "consistent_chain"])
def test_fault_artifacts_are_independently_bound_to_raw_observations(tmp_path, artifact):
    result, run_root, auth, source, env, _ = run_cli(tmp_path, authorization_id="synthetic-fault-" + artifact)
    assert result.returncode == 0, result.stderr
    evidence_path = run_root / "parsed/evidence_v4.json"
    vector_path = run_root / "parsed/feature_vector_v2.json"
    effect_path = run_root / "state/fault_effectiveness.json"
    diagnosis_path = run_root / "state/diagnosis.json"
    if artifact in {"evidence", "consistent_chain"}:
        evidence = load(evidence_path)
        evidence["observations"]["throughput_mbps"]["value"] += 1
        evidence_path.write_bytes(canonical(evidence))
    if artifact in {"vector", "consistent_chain"}:
        vector = load(vector_path)
        vector["values"]["throughput_mbps"]["value"] += 1
        if artifact == "consistent_chain":
            vector["provenance"]["evidence_sha256"] = digest(evidence_path.read_bytes())
        vector_path.write_bytes(canonical(vector))
    if artifact == "effectiveness":
        effect = load(effect_path); effect["lost_packet_count"] -= 1
        effect_path.write_bytes(canonical(effect))
    if artifact in {"diagnosis", "consistent_chain"}:
        diagnosis = load(diagnosis_path)
        if artifact == "consistent_chain":
            from src.expansion.x6_r1_performance_rule import diagnose_x6_r1, predicates_from_vector
            vector = load(vector_path); manifest = accepted_manifest()
            diagnosis["predicates"] = predicates_from_vector(vector, manifest, repository_root=ROOT)
            diagnosis["result"] = diagnose_x6_r1(vector, manifest, repository_root=ROOT)
        else:
            diagnosis["result"]["status"] = "insufficient_evidence"
        diagnosis_path.write_bytes(canonical(diagnosis))
    if artifact == "identity":
        evidence = load(evidence_path); evidence["evidence_id"] = "foreign:evidence:v4"
        evidence_path.write_bytes(canonical(evidence))
    from src.expansion.x6_r1_5_materialized_verifier import verify
    with pytest.raises(Invalid):
        verify(run_root, source_identity=source, simulation=True)


def test_command_failure_terminalizes_and_spends_without_retry(tmp_path):
    result, run_root, auth, source, env, _ = run_cli(tmp_path, state={"deployed": False, "qdisc": "baseline", "fail_iperf": True}, authorization_id="synthetic-failure")
    assert result.returncode != 0
    terminal = load(run_root / "terminal/terminal.json")
    assert terminal["status"] in {"F1_ATTEMPT_FAILED", "CLEANUP_FAILED"} and terminal["qualified"] is False
    ledger = load(reservation_path(run_root, auth)); assert ledger["state"] == "CONSUMED"
    with pytest.raises((FileExistsError, Invalid)):
        reserve(run_root, auth, admission_validator=lambda observation: auth)


def interrupted_recovered_run(tmp_path):
    env, state_path = isolated_environment(
        tmp_path,
        {"deployed": False, "qdisc": "baseline", "pause_mutation_child": 2},
    )
    run_root = tmp_path / "run"
    source = identity()
    auth = authorization(run_root, source, authorization_id="synthetic-interrupted")
    auth_path = tmp_path / "authorization.json"
    auth_path.write_bytes(canonical(auth))
    command = [
        sys.executable, "-m", "src.orchestration.x6_r1_5_production_path",
        "--authorization", str(auth_path), "--run-root", str(run_root),
        "--run-id", "synthetic-f1-run", "--execute", "--source-test",
    ]
    process = subprocess.Popen(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text())
            except json.JSONDecodeError:
                state = {}
            if state.get("qdisc") == "fault":
                break
        time.sleep(.02)
    else:
        process.kill(); process.wait(timeout=10)
        pytest.fail("mutation failpoint was not reached")
    process.kill()
    process.wait(timeout=10)
    time.sleep(2.1)  # let the isolated substitute release its state-file lock
    replay = subprocess.run(
        [sys.executable, "-m", "src.orchestration.x6_r1_5_recovery", "--run-root", str(run_root), "--source-test"],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=60, check=False,
    )
    assert replay.returncode == 0, replay.stderr
    return run_root, auth, source, env, state_path


def test_abrupt_interruption_uses_recovery_without_resuming_traffic(tmp_path):
    run_root, auth, source, env, state_path = interrupted_recovered_run(tmp_path)
    terminal = load(run_root / "terminal/terminal.json")
    assert terminal["status"] == "INTERRUPTED" and terminal["qualified"] is False
    recovered_state = json.loads(state_path.read_text())
    assert recovered_state["qdisc"] == "baseline" and recovered_state["deployed"] is False
    calls = recovered_state["calls"]
    mutation_index = next(i for i, row in enumerate(calls) if row[0] == "docker" and "parent" in row)
    assert not any(row[0] == "docker" and "-c" in row and "-J" in row for row in calls[mutation_index + 1:])
    ledger = load(reservation_path(run_root, auth))
    assert ledger["state"] == "CONSUMED"
    with pytest.raises((FileExistsError, Invalid)):
        reserve(run_root, auth, admission_validator=lambda observation: auth)
    from src.expansion.x6_r1_5_materialized_verifier import verify
    result = verify(run_root, source_identity=source, simulation=True, permit_interrupted=True)
    assert result["terminal"] == "INTERRUPTED" and result["qualified"] is False and result["cleanup"] == "CLEANUP_RECONSTRUCTED"


@pytest.mark.parametrize("mutation", ["missing", "reordered", "contradictory", "foreign"])
def test_interrupted_cleanup_evidence_is_independently_reconstructed(tmp_path, mutation):
    run_root, auth, source, env, state_path = interrupted_recovered_run(tmp_path)
    cleanup_path = run_root / "state/cleanup.json"
    cleanup = load(cleanup_path)
    cycle = cleanup["cycles"][-1]
    if mutation == "missing":
        order = cycle["after_orders"][-1]
        (run_root / f"raw/commands/{order:05d}.result.json").unlink()
    elif mutation == "reordered":
        cycle["before_orders"] = list(reversed(cycle["before_orders"]))
        cleanup_path.write_bytes(canonical(cleanup))
    elif mutation == "contradictory":
        cycle["action_order"] = None
        cleanup_path.write_bytes(canonical(cleanup))
    else:
        order = cycle["before_orders"][0]
        path = run_root / f"raw/commands/{order:05d}.result.json"
        row = load(path)
        foreign = {"Names": "clab-x6r1-foreign", "ID": "foreign", "Image": "ind-linux:0.1", "Labels": "containerlab=x6r1"}
        row["stdout"] += json.dumps(foreign) + "\n"
        row["stdout_sha256"] = digest(row["stdout"].encode())
        path.write_bytes(canonical(row))
    from src.expansion.x6_r1_5_materialized_verifier import verify
    with pytest.raises(Invalid):
        verify(run_root, source_identity=source, simulation=True, permit_interrupted=True)


def test_partial_deployment_failure_has_valid_owned_cleanup_without_success_claim(tmp_path):
    result, run_root, auth, source, env, _ = run_cli(
        tmp_path,
        state={"deployed": False, "qdisc": "baseline", "partial_deploy": True},
        authorization_id="synthetic-partial-deployment",
    )
    assert result.returncode != 0
    terminal = load(run_root / "terminal/terminal.json")
    assert terminal["status"] == "F1_ATTEMPT_FAILED"
    from src.expansion.x6_r1_5_materialized_verifier import verify
    verified = verify(run_root, source_identity=source, simulation=True, permit_interrupted=True)
    assert verified["cleanup"] == "CLEANUP_RECONSTRUCTED" and verified["qualified"] is False


def test_environment_ineligible_before_deployment_requires_no_cleanup_claim(tmp_path):
    result, run_root, auth, source, env, _ = run_cli(
        tmp_path,
        state={"deployed": False, "qdisc": "baseline", "bad_module": True},
        authorization_id="synthetic-ineligible",
    )
    assert result.returncode != 0
    assert load(run_root / "terminal/terminal.json")["status"] == "ENVIRONMENT_INELIGIBLE"
    from src.expansion.x6_r1_5_materialized_verifier import verify
    verified = verify(run_root, source_identity=source, simulation=True, permit_interrupted=True)
    assert verified["cleanup"] == "NOT_REQUIRED_BEFORE_DEPLOYMENT_INTENT"


def test_cleanup_failure_is_preserved_without_false_success_claim(tmp_path):
    result, run_root, auth, source, env, _ = run_cli(
        tmp_path,
        state={"deployed": False, "qdisc": "baseline", "fail_iperf": True, "fail_cleanup": True},
        authorization_id="synthetic-cleanup-failure",
    )
    assert result.returncode != 0
    assert load(run_root / "terminal/terminal.json")["status"] == "CLEANUP_FAILED"
    from src.expansion.x6_r1_5_materialized_verifier import verify
    verified = verify(run_root, source_identity=source, simulation=True, permit_interrupted=True)
    assert verified["cleanup"] == "CLEANUP_FAILED_NO_SUCCESS_CLAIM" and verified["qualified"] is False


def test_completed_attempt_replays_after_boot_change_without_new_attempt_validation(tmp_path, monkeypatch):
    result, run_root, auth, source, env, _ = run_cli(tmp_path, authorization_id="synthetic-cross-boot")
    assert result.returncode == 0, result.stderr
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    import src.orchestration.x6_r1_5_durable as durable
    import src.orchestration.x6_r1_5_recovery as recovery
    recovery_boot = "synthetic-recovery-boot"
    monkeypatch.setattr(durable, "current_boot_id", lambda: recovery_boot)
    monkeypatch.setattr(recovery, "process_identity", lambda: {"pid": 999999, "start_ticks": "0", "boot_id": recovery_boot})
    recovered = recovery.recover(run_root, simulation=True)
    assert recovered["status"] == "F1_SOURCE_CONTRACT_COMPLETE_REPLAY_VERIFIED"
    journal = load(run_root / "state/recovery.json")
    assert journal["sessions"][-1]["boot_id"] == recovery_boot
    from src.expansion.x6_r1_5_materialized_verifier import verify
    verified = verify(run_root, source_identity=source, simulation=True)
    assert verified["status"] == "F1_SOURCE_CONTRACT_COMPLETE_FOR_REVIEW"
    with pytest.raises(Invalid, match="live clock epoch"):
        from src.orchestration.x6_r1_5_contract import validate_new_attempt
        validate_new_attempt(auth, root=run_root, run_id=auth["run_id"], source_identity=source, observation=durable.stamp(), simulation=True)
