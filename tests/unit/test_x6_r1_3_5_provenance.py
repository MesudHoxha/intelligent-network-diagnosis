"""Synthetic-only adversarial tests for the R1.3.5 prospective controls."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import pytest
from src.orchestration import x6_r1_3_5_baseline_provenance as p
from src.expansion import x6_r1_3_5_materialized_verifier as v
from src.orchestration import x6_r1_3_5_baseline_lifecycle as l

def executor(command: list[str]) -> dict[str, object]:
    if command == p.COMMANDS["qdisc"]: out='[{"kind":"noqueue","handle":"0:"}]'
    elif command == p.COMMANDS["filters"] or command == p.COMMANDS["processes"] or command == p.COMMANDS["namespaces"]: out="[]"
    elif command in (p.COMMANDS["r2_tx"],p.COMMANDS["r3_rx"]): out="1"
    elif command in (p.COMMANDS["r2_speed"],p.COMMANDS["r3_speed"]): out="1000"
    else: out="ok"
    return {"return_code": 0, "stdout": out, "stderr": ""}

def test_every_command_record_is_timestamped_ordered_and_hash_bound(tmp_path: Path) -> None:
    recorder = p.CommandRecorder(tmp_path, run_id="run", authorization_id="auth", source_test_only=True, clock=iter([1, 3, 4, 9]).__next__)
    recorder.capture(name="kernel", phase="provenance", action_id="a", executor=executor)
    recorder.capture(name="ping", phase="window", window_id="C01", action_id="w", executor=executor)
    rows = p.verify_command_inventory(tmp_path, run_id="run", authorization_id="auth")
    assert [row["order"] for row in rows] == [1, 2]
    assert rows[0]["elapsed_ns"] == 2 and rows[1]["shell"] is False

@pytest.mark.parametrize("mutation", ["timestamp", "elapsed", "argv", "shell", "rehash", "order"])
def test_command_record_adversaries_fail_closed(tmp_path: Path, mutation: str) -> None:
    recorder = p.CommandRecorder(tmp_path, run_id="run", authorization_id="auth", source_test_only=True, clock=iter([1, 2]).__next__)
    reference = recorder.capture(name="kernel", phase="provenance", action_id="a", executor=executor)
    path = tmp_path / reference["path"]; row = json.loads(path.read_text())
    if mutation == "timestamp": row.pop("started_at_utc")
    elif mutation == "elapsed": row["elapsed_ns"] = -1
    elif mutation == "argv": row["argv"] = []
    elif mutation == "shell": row["shell"] = True
    elif mutation == "rehash": row["stdout"] = "altered"; row["record_sha256"] = p.sha256(p.canonical_bytes({k:v for k,v in row.items() if k != "record_sha256"}))
    else:
        inv = json.loads((tmp_path/"state/command_inventory.json").read_text()); inv["records"][0]["order"] = 2; (tmp_path/"state/command_inventory.json").write_text(json.dumps(inv));
        with pytest.raises(p.X6R135Error): p.verify_command_inventory(tmp_path, run_id="run", authorization_id="auth")
        return
    path.write_text(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    with pytest.raises(p.X6R135Error): p.verify_command_inventory(tmp_path, run_id="run", authorization_id="auth")

def test_recovery_requires_distinct_process_and_successful_records(tmp_path: Path) -> None:
    recorder = p.CommandRecorder(tmp_path, run_id="run", authorization_id="auth", source_test_only=True, clock=iter([1,2,3,4]).__next__)
    recorder.capture(name="processes", phase="recovery", action_id="cleanup", executor=executor)
    recorder.capture(name="namespaces", phase="recovery", action_id="cleanup", executor=executor)
    assert p.verify_recovery(tmp_path, original_pid=10, recovery_pid=11, run_id="run", authorization_id="auth")["distinct_process"] is True
    with pytest.raises(p.X6R135Error): p.verify_recovery(tmp_path, original_pid=10, recovery_pid=10, run_id="run", authorization_id="auth")

def test_materialized_verifier_rejects_source_mismatch_and_synthetic_qualified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    identity = {"git_commit":"a"*40,"git_tree":"b"*40,"topology_path":"t","topology_sha256":"c"*64,"dockerfile_path":"d","dockerfile_sha256":"e"*64,"source_hashes":{}}
    monkeypatch.setattr(v, "derive_source_identity", lambda _: identity)
    auth = {"schema_version":1,"authorization_id":"auth","scope":"BASELINE_ONLY_QUALIFICATION","maximum_attempts":1,"source_identity":identity,"bindings":{},"mutation_prohibited":True,"runtime_enabled":True}
    auth["authorization_sha256"] = p.sha256(p.canonical_bytes(auth)); (tmp_path/"state").mkdir(); (tmp_path/"terminal").mkdir()
    (tmp_path/"state/authorization.json").write_text(json.dumps(auth)); (tmp_path/"state/authorization_ledger.json").write_text(json.dumps({"authorization_id":"auth","authorization_sha256":auth["authorization_sha256"],"state":"CONSUMED","consumed_monotonic_ns":0,"run_id":"run"})); (tmp_path/"state/action_journal.json").write_text(json.dumps({"authorization_id":"auth","state":"CONSUMED_BEFORE_STATEFUL_ACTION","run_id":"run"}))
    recorder = p.CommandRecorder(tmp_path, run_id="run", authorization_id="auth", source_test_only=True, clock=iter([1,2,3,4]).__next__); recorder.capture(name="processes", phase="recovery", action_id="a", executor=executor); recorder.capture(name="namespaces", phase="recovery", action_id="a", executor=executor)
    (tmp_path/"state/recovery.json").write_text(json.dumps({"original_pid":10,"recovery_pid":11})); (tmp_path/"terminal/verifier_terminal.json").write_text(json.dumps({"status":"QUALIFIED"}))
    artifacts=[]
    for path in [tmp_path/"state/authorization.json",tmp_path/"state/authorization_ledger.json",tmp_path/"state/action_journal.json",tmp_path/"state/recovery.json",tmp_path/"terminal/verifier_terminal.json"] + list((tmp_path/"raw/commands").glob("*.json")):
        artifacts.append({"path":str(path.relative_to(tmp_path)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    (tmp_path/"state/artifact_inventory.json").write_text(json.dumps({"artifacts":artifacts}))
    with pytest.raises(p.X6R135Error): v.verify_materialized_attempt(tmp_path, repository_root=tmp_path)
    auth["source_identity"] = {}; (tmp_path/"state/authorization.json").write_text(json.dumps(auth))
    with pytest.raises(p.X6R135Error, match="hash"): v.verify_materialized_attempt(tmp_path, repository_root=tmp_path)

def test_r1_3_5_never_accepts_a_qualified_terminal() -> None:
    assert "QUALIFIED" not in v.TERMINAL

def test_lifecycle_records_every_window_command_and_freezes_at_c10(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    values = {feature:{"availability":"observed","value":0 if feature != "throughput_mbps" else 100} for feature in l.NUMERIC_FEATURES}
    monkeypatch.setattr(l, "derive_window", lambda *args, **kwargs: values)
    auth={"authorization_id":"source-test-only","authorization_sha256":"a"*64,"source_identity":{},"runtime_enabled":True}
    recorder=l.initialize(tmp_path/"run",authorization=auth,ledger_root=tmp_path/"ledger",run_id="run",source_test_only=True)
    one=l.collect_window(recorder,window_id="C01",executor=executor,speed_mbps=1000)
    assert set(one["features"]) == set(l.NUMERIC_FEATURES)
    assert len(p.verify_command_inventory(tmp_path/"run",run_id="run",authorization_id="source-test-only")) == 14

def test_checkpoint_a_complete_thirty_windows_and_adversaries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    values = {feature:{"availability":"observed","value":0 if feature != "throughput_mbps" else 100} for feature in l.NUMERIC_FEATURES}
    monkeypatch.setattr(l, "derive_window", lambda *args, **kwargs: values)
    auth={"authorization_id":"source-test-only","authorization_sha256":"a"*64,"source_identity":{},"runtime_enabled":True}
    root=tmp_path/"run"; recorder=l.initialize(root,authorization=auth,ledger_root=tmp_path/"ledger",run_id="all",source_test_only=True)
    l.collect_thirty(recorder,executor=executor,speed_mbps=1000)
    assert v.verify_thirty_window_artifacts(root,run_id="all",authorization_id="source-test-only")["windows"] == 30
    row=json.loads((root/"raw/windows/C11.json").read_text()); row["window_id"]="C01"; (root/"raw/windows/C11.json").write_text(json.dumps(row))
    with pytest.raises(p.X6R135Error): v.verify_thirty_window_artifacts(root,run_id="all",authorization_id="source-test-only")

def test_checkpoint_a2_inventory_and_terminal_are_independently_derived(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    values={feature:{"availability":"observed","value":0 if feature != "throughput_mbps" else 100} for feature in l.NUMERIC_FEATURES}; monkeypatch.setattr(l,"derive_window",lambda *args,**kwargs: values)
    auth={"authorization_id":"source-test-only","authorization_sha256":"a"*64,"source_identity":{},"runtime_enabled":True}; root=tmp_path/"run"
    rec=l.initialize(root,authorization=auth,ledger_root=tmp_path/"ledger",run_id="a2",source_test_only=True); l.collect_thirty(rec,executor=executor,speed_mbps=1000); l.finalize_inventory(root)
    assert v.derive_checkpoint_a_terminal(root,run_id="a2",authorization_id="source-test-only")["terminal_status"] == "PROSPECTIVE_COMPLETE_CHECKPOINT_B_REQUIRED"
    (root/"unexpected.txt").write_text("x")
    assert v.derive_checkpoint_a_terminal(root,run_id="a2",authorization_id="source-test-only")["terminal_status"] == "VERIFICATION_FAILED"

def test_checkpoint_a3_raw_controls_are_derived_and_fail_closed() -> None:
    def row(name: str, out: str, start: int) -> dict[str, object]: return {"command_name":name,"stdout":out,"return_code":0,"timed_out":False,"interrupted":False,"started_monotonic_ns":start,"completed_monotonic_ns":start+1}
    records=[row("qdisc",'[{"kind":"noqueue","handle":"0:"}]',1),row("filters","[]",1),row("r2_tx","1",1),row("r2_tx","2",2),row("r3_rx","1",1),row("r3_rx","2",2),row("r2_speed","1000",1),row("r3_speed","1000",1),row("cleanup","",5),row("qdisc",'[{"kind":"noqueue","handle":"0:"}]',7),row("filters","[]",7),row("processes","[]",7),row("namespaces","",7)]
    assert v.derive_raw_controls(records)["cleanup_valid"] is True
    records[0]["stdout"]="not-json"
    with pytest.raises(p.X6R135Error): v.derive_raw_controls(records)
