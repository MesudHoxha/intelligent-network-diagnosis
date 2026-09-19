"""Focused source-only checks for R1.4.1 timing and cross-boot recovery."""
from __future__ import annotations
import copy
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

from src.orchestration.x6_r1_4_1_contract import (
    AUTHORIZATION_RELEASE, PREDECESSOR, RELEASE, ROOT, TRUST_MODEL, Invalid,
    canonical, digest, frozen_contract, identity, validate_committed_attempt,
    validate_new_attempt, validate_partial_attempt,
)
from src.orchestration.x6_r1_4_1_durable import load, reservation_path, reserve, save


def point(ns, boot):
    return {"monotonic_ns": ns, "utc": "2026-09-18T00:00:00Z", "boot_id": boot}


def authorization(root, source, *, boot="boot-original", issued=100, expires=200, production=False):
    value = {
        "schema_version": 4, "record_kind": "CONCRETE_AUTHORIZATION", "release_id": AUTHORIZATION_RELEASE,
        "trust_model": TRUST_MODEL, "authorization_id": "synthetic-r1-4-1", "scope": "BASELINE_ONLY_QUALIFICATION",
        "source_identity": source, "predecessor": PREDECESSOR, "output_root": str(root), "run_id": "synthetic-run",
        "issued_ns": issued, "expires_ns": expires, "boot_id": boot, "source_test_only": not production,
        "contract": frozen_contract(), "runtime_image": {"Id": "sha256:" + "1" * 64, "RepoDigests": []},
    }
    value["authorization_sha256"] = digest(canonical(value))
    return value


def clock(monkeypatch, values, boot="boot-original"):
    import src.orchestration.x6_r1_4_1_contract as contract
    import src.orchestration.x6_r1_4_1_durable as durable
    sequence = iter(point(value, boot) for value in values)
    monkeypatch.setattr(contract, "current_boot_id", lambda: boot)
    monkeypatch.setattr(durable, "current_boot_id", lambda: boot)
    monkeypatch.setattr(durable, "stamp", lambda: next(sequence))
    return durable


def test_exclusive_persistence_publishes_complete_bytes_and_preserves_first_writer(tmp_path):
    path = tmp_path / "record.json"
    first = {"state": "RESERVED_UNDECIDED", "value": "first"}
    save(path, first, exclusive=True)
    assert path.read_bytes() == canonical(first)
    with pytest.raises(FileExistsError):
        save(path, {"state": "REPLACEMENT"}, exclusive=True)
    assert path.read_bytes() == canonical(first)


def test_expiry_during_clean_check_and_reservation_is_spent_without_lifecycle(tmp_path, monkeypatch):
    import src.orchestration.x6_r1_4_1_production_path as production
    source = identity(); root = tmp_path / "run"; auth = authorization(root, source, production=True)
    auth_path = tmp_path / "auth.json"; auth_path.write_bytes(canonical(auth))
    durable = clock(monkeypatch, [190, 201, 202])
    monkeypatch.setattr(production, "stamp", lambda: point(150, "boot-original"))
    monkeypatch.setattr(production, "identity", lambda: source)
    monkeypatch.setattr(production, "run_capture", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(production, "acquire_topology_lock", lambda: os.open("/dev/null", os.O_RDONLY))
    entered = []
    monkeypatch.setattr(production, "lifecycle", lambda *a: entered.append(True))
    with pytest.raises(Invalid, match="validity"):
        production.execute(auth_path, root, "synthetic-run", simulation=False)
    ledger = load(reservation_path(root, auth))
    assert ledger["state"] == "REJECTED" and ledger["admission"]["decision"] == "REJECTED_BEFORE_LIFECYCLE"
    assert not root.exists() and entered == []
    with pytest.raises((FileExistsError, Invalid)):
        reserve(root, auth, admission_validator=lambda observation: None)


def test_valid_post_reservation_commit_survives_later_consumption_and_expiry(tmp_path, monkeypatch):
    source = identity(); root = tmp_path / "run"; auth = authorization(root, source)
    clock(monkeypatch, [150, 180, 250, 260])
    row = reserve(root, auth, admission_validator=lambda observation: validate_new_attempt(
        auth, root=root, run_id="synthetic-run", source_identity=source, observation=observation, simulation=True))
    assert row["admission"]["observed_after_reservation"]["monotonic_ns"] == 180
    assert row["consumed"]["monotonic_ns"] == 250 > auth["expires_ns"]
    assert validate_committed_attempt(auth, row, root=root, run_id="synthetic-run", source_identity=source, simulation=True) == auth


def test_partial_reservation_is_spent_and_durably_classified(tmp_path, monkeypatch):
    import src.orchestration.x6_r1_4_1_durable as durable
    import src.orchestration.x6_r1_4_1_recovery as recovery
    source = identity(); root = tmp_path / "run"; auth = authorization(root, source)
    clock(monkeypatch, [150])
    original_save = durable.save
    def interrupted_save(path, value, **kwargs):
        original_save(path, value, **kwargs)
        if kwargs.get("exclusive") and Path(path) == reservation_path(root, auth):
            raise KeyboardInterrupt("after exclusive reservation")
    monkeypatch.setattr(durable, "save", interrupted_save)
    with pytest.raises(KeyboardInterrupt):
        durable.reserve(root, auth, admission_validator=lambda observation: None)
    monkeypatch.setattr(durable, "save", original_save)
    with pytest.raises(FileExistsError):
        durable.reserve(root, auth, admission_validator=lambda observation: None)
    monkeypatch.setattr(recovery, "assert_external_simulation", lambda: None)
    monkeypatch.setattr(recovery, "identity", lambda: source)
    monkeypatch.setattr(recovery, "alive", lambda process: False)
    monkeypatch.setattr(recovery, "process_identity", lambda: {"pid": 999999, "start_ticks": "0", "boot_id": "boot-original"})
    monkeypatch.setattr(recovery, "stamp", lambda: point(300, "boot-recovery"))
    result = recovery.recover(root, simulation=True)
    assert result["status"] == "INTERRUPTED_BEFORE_AUTHORIZATION_COMMIT"
    assert reservation_path(root, auth).exists() and reservation_path(root, auth).with_suffix(".interrupted.json").exists()


@pytest.mark.parametrize("recovery_boot", ["boot-original", "boot-recovery"])
def test_rejected_decision_is_spent_and_shared_verifiers_agree(tmp_path, monkeypatch, recovery_boot):
    import src.orchestration.x6_r1_4_1_durable as durable
    import src.orchestration.x6_r1_4_1_recovery as recovery
    from src.expansion.x6_r1_4_1_materialized_verifier import verify
    source = identity(); root = tmp_path / "run"; auth = authorization(root, source)
    clock(monkeypatch, [150, 201, 202])
    with pytest.raises(Invalid, match="validity"):
        reserve(root, auth, admission_validator=lambda observation: validate_new_attempt(
            auth, root=root, run_id="synthetic-run", source_identity=source, observation=observation, simulation=True))
    monkeypatch.setattr(recovery, "assert_external_simulation", lambda: None)
    monkeypatch.setattr(recovery, "identity", lambda: source)
    monkeypatch.setattr(recovery, "alive", lambda process: False)
    monkeypatch.setattr(recovery, "process_identity", lambda: {"pid": 999999, "start_ticks": "0", "boot_id": recovery_boot})
    monkeypatch.setattr(recovery, "stamp", lambda: point(10 if recovery_boot != "boot-original" else 203, recovery_boot))
    monkeypatch.setattr(durable, "current_boot_id", lambda: recovery_boot)
    result = recovery.recover(root, simulation=True)
    assert result["status"] == "RESERVATION_REJECTED" and result["authorization_committed"] is False
    replay = verify(root, source_identity=source, simulation=True, permit_interrupted=True)
    assert replay["terminal"] == "RESERVATION_REJECTED" and replay["authorization_committed"] is False
    assert not root.exists()


def interrupted_at(tmp_path, monkeypatch, boundary):
    import src.orchestration.x6_r1_4_1_durable as durable
    source = identity(); root = tmp_path / "run"; auth = authorization(root, source)
    clock(monkeypatch, [150, 180, 190, 195])
    original_save = durable.save
    ledger_path = reservation_path(root, auth)
    auth_path = root / "state/authorization.json"
    consumption_path = root / "state/consumption.json"
    def failpoint(path, value, **kwargs):
        path = Path(path)
        before = (
            (boundary == "after_root_create" and path == ledger_path and value.get("state") == "ADMITTED" and "root_identity" in value)
        )
        if before:
            raise KeyboardInterrupt(boundary)
        result = original_save(path, value, **kwargs)
        after = (
            (boundary == "after_admitted" and path == ledger_path and value.get("state") == "ADMITTED" and "root_identity" not in value) or
            (boundary == "after_root_identity" and path == ledger_path and value.get("state") == "ADMITTED" and "root_identity" in value) or
            (boundary == "after_authorization_copy" and path == auth_path) or
            (boundary == "after_consumed_ledger" and path == ledger_path and value.get("state") == "CONSUMED") or
            (boundary == "after_consumption_copy" and path == consumption_path)
        )
        if after:
            raise KeyboardInterrupt(boundary)
        return result
    monkeypatch.setattr(durable, "save", failpoint)
    with pytest.raises(KeyboardInterrupt, match=boundary):
        durable.reserve(root, auth, admission_validator=lambda observation: validate_new_attempt(
            auth, root=root, run_id="synthetic-run", source_identity=source, observation=observation, simulation=True))
    monkeypatch.setattr(durable, "save", original_save)
    return source, root, auth, load(ledger_path)


@pytest.mark.parametrize("boundary,expected", [
    ("after_admitted", "AUTHORIZATION_COMMITTED_CONSUMPTION_INCOMPLETE"),
    ("after_root_create", "AUTHORIZATION_COMMITTED_CONSUMPTION_INCOMPLETE"),
    ("after_root_identity", "AUTHORIZATION_COMMITTED_CONSUMPTION_INCOMPLETE"),
    ("after_authorization_copy", "AUTHORIZATION_COMMITTED_CONSUMPTION_INCOMPLETE"),
    ("after_consumed_ledger", "AUTHORIZATION_CONSUMED_RECORD_INCOMPLETE"),
])
@pytest.mark.parametrize("recovery_boot", ["boot-original", "boot-recovery"])
def test_persistence_failpoints_are_spent_and_consistently_classified(tmp_path, monkeypatch, boundary, expected, recovery_boot):
    import src.orchestration.x6_r1_4_1_durable as durable
    import src.orchestration.x6_r1_4_1_recovery as recovery
    from src.expansion.x6_r1_4_1_materialized_verifier import verify
    source, root, auth, ledger = interrupted_at(tmp_path, monkeypatch, boundary)
    monkeypatch.setattr(recovery, "assert_external_simulation", lambda: None)
    monkeypatch.setattr(recovery, "identity", lambda: source)
    monkeypatch.setattr(recovery, "alive", lambda process: False)
    monkeypatch.setattr(recovery, "process_identity", lambda: {"pid": 999999, "start_ticks": "0", "boot_id": recovery_boot})
    monkeypatch.setattr(recovery, "stamp", lambda: point(10 if recovery_boot != "boot-original" else 199, recovery_boot))
    monkeypatch.setattr(durable, "current_boot_id", lambda: recovery_boot)
    result = recovery.recover(root, simulation=True)
    assert result["status"] == expected and result["authorization_committed"] is True
    with pytest.raises(Invalid, match="persistence is incomplete"):
        verify(root, source_identity=source, simulation=True)
    replay = verify(root, source_identity=source, simulation=True, permit_interrupted=True)
    assert replay["terminal"] == expected and replay["authorization_committed"] is True and replay["consumption_complete"] is False
    assert not root.exists() or not list((root / "raw").glob("**/*"))
    with pytest.raises((FileExistsError, Invalid)):
        reserve(root, auth, admission_validator=lambda observation: None)
    assert recovery.recover(root, simulation=True) == result


def test_complete_consumption_copy_allows_interruption_recovery_without_resuming_work(tmp_path, monkeypatch):
    import src.orchestration.x6_r1_4_1_durable as durable
    import src.orchestration.x6_r1_4_1_recovery as recovery
    from src.expansion.x6_r1_4_1_materialized_verifier import verify
    source, root, auth, ledger = interrupted_at(tmp_path, monkeypatch, "after_consumption_copy")
    monkeypatch.setattr(recovery, "assert_external_simulation", lambda: None)
    monkeypatch.setattr(recovery, "identity", lambda: source)
    monkeypatch.setattr(recovery, "alive", lambda process: False)
    monkeypatch.setattr(recovery, "process_identity", lambda: {"pid": 999999, "start_ticks": "0", "boot_id": "boot-recovery"})
    monkeypatch.setattr(recovery, "stamp", lambda: point(10, "boot-recovery"))
    monkeypatch.setattr(durable, "current_boot_id", lambda: "boot-recovery")
    monkeypatch.setattr(recovery, "acquire_topology_lock", lambda: os.open("/dev/null", os.O_RDONLY))
    assert recovery.recover(root, simulation=True)["status"] == "INTERRUPTED"
    assert verify(root, source_identity=source, simulation=True, permit_interrupted=True)["terminal"] == "INTERRUPTED"


@pytest.mark.parametrize("mutation", ["decision", "consumed_key", "consumption_copy", "root_identity", "foreign_artifact"])
def test_admitted_partial_rejects_inconsistent_or_tampered_state(tmp_path, monkeypatch, mutation):
    import src.orchestration.x6_r1_4_1_durable as durable
    import src.orchestration.x6_r1_4_1_recovery as recovery
    source, root, auth, ledger = interrupted_at(tmp_path, monkeypatch, "after_root_identity")
    if mutation == "decision": ledger["admission"]["decision"] = "REJECTED_BEFORE_LIFECYCLE"
    elif mutation == "consumed_key": ledger["consumed"] = point(190, "boot-original")
    elif mutation == "consumption_copy": save(root / "state/consumption.json", ledger)
    elif mutation == "root_identity": ledger["root_identity"]["inode"] += 1
    else: save(root / "state/lifecycle.json", {"fabricated": True})
    if mutation in {"decision", "consumed_key", "root_identity"}:
        save(reservation_path(root, auth), ledger)
    monkeypatch.setattr(recovery, "assert_external_simulation", lambda: None)
    monkeypatch.setattr(recovery, "identity", lambda: source)
    monkeypatch.setattr(recovery, "alive", lambda process: False)
    with pytest.raises(Invalid):
        recovery.recover(root, simulation=True)
    assert not reservation_path(root, auth).with_suffix(".interrupted.json").exists()


def test_new_execution_rejects_authorization_from_previous_boot(tmp_path):
    source = identity(); root = tmp_path / "run"; auth = authorization(root, source)
    with pytest.raises(Invalid, match="live clock epoch"):
        validate_new_attempt(auth, root=root, run_id="synthetic-run", source_identity=source,
                             observation=point(150, "boot-new"), simulation=True)


def test_real_successor_cli_rejects_previous_boot_before_reservation(tmp_path, monkeypatch):
    import subprocess
    source = identity(); root = tmp_path / "run"
    auth = authorization(root, source, boot="definitely-not-the-current-boot", issued=0, expires=10**30)
    auth_path = tmp_path / "authorization.json"; auth_path.write_bytes(canonical(auth))
    env_state = environment(tmp_path, monkeypatch)
    result = subprocess.run(
        [sys.executable, "-m", "src.orchestration.x6_r1_4_1_production_path", "--authorization", str(auth_path),
         "--run-root", str(root), "--run-id", "synthetic-run", "--execute", "--source-test"],
        cwd=ROOT, env=os.environ.copy(), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    )
    assert result.returncode != 0 and "live clock epoch" in result.stderr
    assert not root.exists() and not reservation_path(root, auth).exists()


@pytest.mark.parametrize("mutation", ["reservation_boot", "decision_time", "decision_boot", "consumption_boot", "state", "authorization"])
def test_historical_validation_rejects_altered_boot_timestamp_and_consumption(tmp_path, monkeypatch, mutation):
    source = identity(); root = tmp_path / "run"; auth = authorization(root, source)
    clock(monkeypatch, [150, 180, 250, 260])
    row = reserve(root, auth, admission_validator=lambda observation: validate_new_attempt(
        auth, root=root, run_id="synthetic-run", source_identity=source, observation=observation, simulation=True))
    altered = copy.deepcopy(row)
    if mutation == "reservation_boot": altered["reservation"]["started"]["boot_id"] = "other"
    elif mutation == "decision_time": altered["admission"]["observed_after_reservation"]["monotonic_ns"] = 201
    elif mutation == "decision_boot": altered["admission"]["observed_after_reservation"]["boot_id"] = "other"
    elif mutation == "consumption_boot": altered["consumed"]["boot_id"] = "other"
    elif mutation == "state": altered["state"] = "ADMITTED"
    else: altered["authorization"]["expires_ns"] += 1
    with pytest.raises(Invalid):
        validate_committed_attempt(auth, altered, root=root, run_id="synthetic-run", source_identity=source, simulation=True)


def environment(tmp_path, monkeypatch, **state_values):
    tool_dir = tmp_path / "tools"; tool_dir.mkdir()
    stub = ROOT / "tests/fixtures/x6_r1_4_1_external_stub.py"
    for name in ("containerlab", "docker", "ip", "tc", "ps", "uname", "zgrep", "lsmod", "modinfo", "python3", "ethtool", "git"):
        (tool_dir / name).symlink_to(stub)
    state = tmp_path / "external-state.json"; state.write_text(json.dumps({"deployed": False, **state_values}))
    monkeypatch.setenv("PATH", str(tool_dir)); monkeypatch.setenv("X6_STUB_STATE", str(state))
    return state


def consumed_attempt(tmp_path, monkeypatch, *, deployed=False, replacement=False):
    import src.orchestration.x6_r1_4_1_durable as durable
    source = identity(); root = tmp_path / "run"; auth = authorization(root, source)
    clock(monkeypatch, [150, 180, 190, 195])
    ledger = reserve(root, auth, admission_validator=lambda observation: validate_new_attempt(
        auth, root=root, run_id="synthetic-run", source_identity=source, observation=observation, simulation=True))
    save(root / "terminal/terminal.json", {"release_id": RELEASE, "status": "INTERRUPTED", "qualified": False, "detail": "synthetic interruption", "at": point(196, "boot-original")})
    if deployed:
        initial = {"containers": [], "namespaces": [], "links": [], "qdisc": []}
        containers = [{"Names": "clab-x6r1-" + node, "ID": node, "Image": "ind-linux:0.1", "Labels": "containerlab=x6r1"} for node in ("hosta", "r1", "r2", "r3", "hostb")]
        save(root / "state/host_before.json", initial)
        save(root / "state/deployment_intent.json", {"at": point(197, "boot-original"), "host_before_sha256": digest(canonical(initial))})
        save(root / "state/deployment.json", {"containers": containers, "namespaces": [], "links": [], "qdisc": []})
    monkeypatch.setattr(durable, "current_boot_id", lambda: "boot-recovery")
    monkeypatch.setattr(durable, "stamp", lambda: point(10, "boot-recovery"))
    return source, root, auth, ledger


def test_recovery_and_read_only_replay_accept_committed_attempt_after_boot_change(tmp_path, monkeypatch):
    import src.orchestration.x6_r1_4_1_recovery as recovery
    from src.expansion.x6_r1_4_1_materialized_verifier import verify
    source, root, auth, ledger = consumed_attempt(tmp_path, monkeypatch)
    monkeypatch.setattr(recovery, "assert_external_simulation", lambda: None)
    monkeypatch.setattr(recovery, "identity", lambda: source)
    result = recovery.recover(root, simulation=True)
    assert result["status"] == "INTERRUPTED"
    journal = load(root / "state/recovery.json")
    assert journal["sessions"][0]["boot_id"] == "boot-recovery"
    assert verify(root, source_identity=source, simulation=True, permit_interrupted=True)["terminal"] == "INTERRUPTED"


def test_recovery_rejects_tampered_consumed_lifecycle_boundary(tmp_path, monkeypatch):
    import src.orchestration.x6_r1_4_1_recovery as recovery
    source, root, auth, ledger = consumed_attempt(tmp_path, monkeypatch)
    lifecycle = load(root / "state/lifecycle.json")
    lifecycle["at"]["boot_id"] = "other-boot"
    save(root / "state/lifecycle.json", lifecycle)
    monkeypatch.setattr(recovery, "assert_external_simulation", lambda: None)
    monkeypatch.setattr(recovery, "identity", lambda: source)
    with pytest.raises(Invalid, match="lifecycle timing/boot"):
        recovery.recover(root, simulation=True)


def test_abrupt_recovery_session_is_classified_before_a_new_cleanup_session(tmp_path, monkeypatch):
    import src.orchestration.x6_r1_4_1_recovery as recovery
    source, root, auth, ledger = consumed_attempt(tmp_path, monkeypatch)
    save(root / "state/recovery.json", {
        "release_id": RELEASE, "run_id": "synthetic-run", "output_root": str(root),
        "original_process": ledger["process"], "source_test_only": True,
        "sessions": [{"index": 1, "process": {"pid": 999998, "start_ticks": "0", "boot_id": "boot-recovery"},
                      "boot_id": "boot-recovery", "started": point(5, "boot-recovery"),
                      "first_order": 1, "last_order": 0, "status": "STARTED"}],
    })
    monkeypatch.setattr(recovery, "assert_external_simulation", lambda: None)
    monkeypatch.setattr(recovery, "identity", lambda: source)
    assert recovery.recover(root, simulation=True)["status"] == "INTERRUPTED"
    sessions = load(root / "state/recovery.json")["sessions"]
    assert [row["status"] for row in sessions] == ["INTERRUPTED", "CLEANUP_COMPLETE"]


@pytest.mark.parametrize("foreign", [False, True])
def test_cross_boot_recovery_only_cleans_independently_owned_resources_and_never_resumes_traffic(tmp_path, monkeypatch, foreign):
    import src.orchestration.x6_r1_4_1_recovery as recovery
    state_path = environment(tmp_path, monkeypatch, deployed=True, replacement_id={"hosta": "foreign"} if foreign else {})
    source, root, auth, ledger = consumed_attempt(tmp_path, monkeypatch, deployed=True)
    monkeypatch.setattr(recovery, "identity", lambda: source)
    if foreign:
        with pytest.raises(Invalid, match="identity mismatch"):
            recovery.recover(root, simulation=True)
        assert load(root / "terminal/terminal.json")["status"] == "CLEANUP_FAILED"
    else:
        assert recovery.recover(root, simulation=True)["status"] == "INTERRUPTED"
    state = json.loads(state_path.read_text())
    calls = state.get("calls", [])
    assert not any("iperf" in " ".join(row) or "ping" in " ".join(row) for row in calls)
    destroys = [row for row in calls if row[:2] == ["containerlab", "destroy"]]
    assert len(destroys) == (0 if foreign else 1)
    assert state["deployed"] is foreign


def test_successor_gate_binds_append_only_correction():
    from src.expansion.x6_r1_4_1_gate import verify_source
    assert verify_source(historical=False)["authorization"] == "0/10_FALSE"
