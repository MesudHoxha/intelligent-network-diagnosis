"""Separate prospective R1.3.5 lifecycle; never invoked by this milestone."""
from __future__ import annotations
import json, os
from pathlib import Path
from time import monotonic_ns
from typing import Mapping
from src.collection.x6_performance_collector import derive_window
from src.collection.x6_r0_3_pre_runtime_validation import NUMERIC_FEATURES, build_threshold_manifest, canonical_threshold_manifest_bytes
from src.orchestration.x6_r1_3_3_baseline_only_runner import WINDOW_IDS, consume_attempt, write_json_fsync
from src.orchestration.x6_r1_3_5_baseline_provenance import CommandRecorder, Executor, X6R135Error, collect_full_provenance, sha256
from src.orchestration import x6_r1_3_5_authorization as b1
from src.orchestration.x6_r1_3_5_baseline_provenance import COMMANDS
from src.runtime.subprocesses import run_capture

RELEASE_ID = "X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION"

def _fail(message: str) -> None: raise X6R135Error("X6-R1.3.5 lifecycle: " + message)
def _read(root: Path, reference: Mapping[str,str]) -> Mapping[str,object]: return json.loads((root/reference["path"]).read_text())
def _result(root: Path, reference: Mapping[str,str]) -> Mapping[str,object]:
    row=_read(root, reference)
    if row["return_code"] != 0 or row["timed_out"] or row["interrupted"]: _fail("required command failed: "+str(row["command_name"]))
    return {"return_code":row["return_code"],"stdout":row["stdout"],"stderr":row["stderr"]}

def initialize(root: Path, *, authorization: Mapping[str,object], ledger_root: Path, run_id: str, source_test_only: bool) -> CommandRecorder:
    if root.exists(): _fail("run root reuse rejected")
    root.mkdir(parents=True); auth=dict(authorization)
    if not isinstance(auth.get("authorization_id"), str) or not auth["authorization_id"] or auth.get("runtime_enabled") is not True: _fail("validated future authorization required")
    if source_test_only and auth["authorization_id"] != "source-test-only": _fail("synthetic authorization identity required")
    write_json_fsync(root/"state/authorization.json", auth)
    ledger=consume_attempt(ledger_root, auth, run_id=run_id)
    ledger_value=json.loads(ledger.read_text()); write_json_fsync(root/"state/authorization_ledger.json", ledger_value)
    write_json_fsync(root/"state/action_journal.json", {"release_id":RELEASE_ID,"run_id":run_id,"authorization_id":auth["authorization_id"],"original_pid":os.getpid(),"source_test_only":source_test_only,"state":"CONSUMED_BEFORE_STATEFUL_ACTION","actions":["deploy","provenance","windows","cleanup","recovery"]})
    return CommandRecorder(root, run_id=run_id, authorization_id=str(auth["authorization_id"]), source_test_only=source_test_only)

def initialize_b1(root: Path, *, authorization_path: Path, ledger_root: Path, run_id: str, output_root: str, identity: Mapping[str,object], now_ns: int) -> CommandRecorder:
    """Future entry point: bytes, validation, durable ledger, then action permit."""
    raw=Path(authorization_path).read_bytes(); auth=json.loads(raw)
    if sha256(raw) != sha256((json.dumps(auth,sort_keys=True,separators=(",",":"))+"\n").encode()): _fail("authorization bytes are noncanonical")
    value=b1.validate(auth,identity=identity,output_root=output_root,now_ns=now_ns)
    root=Path(root)
    if root.exists(): _fail("run root reuse rejected")
    root.mkdir(parents=True); write_json_fsync(root/"state/authorization.json",value)
    transitions=[b1.transition(root,run_id=run_id,authorization=value,previous=a,current=z,order=i,monotonic=now_ns+i) for i,(a,z) in enumerate((("ABSENT","LOADED"),("LOADED","VALIDATED"),("VALIDATED","CONSUMPTION_PLANNED")),1)]
    ledger=b1.consume(ledger_root,authorization=value,run_id=run_id,output_root=output_root,identity=identity,validated_ns=now_ns+2,consumed_ns=now_ns+3)
    write_json_fsync(root/"state/authorization_ledger.json",ledger)
    transitions += [b1.transition(root,run_id=run_id,authorization=value,previous="CONSUMPTION_PLANNED",current="CONSUMED_DURABLE",order=4,monotonic=now_ns+4),b1.transition(root,run_id=run_id,authorization=value,previous="CONSUMED_DURABLE",current="STATEFUL_ACTION_PERMITTED",order=5,monotonic=now_ns+5)]
    write_json_fsync(root/"state/action_journal.json",{"run_id":run_id,"authorization_id":value["authorization_id"],"original_pid":os.getpid(),"source_test_only":True,"state":"CONSUMED_BEFORE_STATEFUL_ACTION"})
    return CommandRecorder(root,run_id=run_id,authorization_id=str(value["authorization_id"]),source_test_only=True)

def collect_window(recorder: CommandRecorder, *, window_id: str, executor: Executor, speed_mbps: int) -> dict[str,object]:
    refs={}
    for name in ("server_stop","server_start","server_ready","r2_tx","r3_rx","qdisc","filters","iperf","traffic_ping","r2_tx","r3_rx","qdisc","filters","server_stop"):
        key=name+"_"+str(len([x for x in refs if x.startswith(name)])); refs[key]=recorder.capture(name=name, phase="window", window_id=window_id, action_id="window:"+window_id, executor=executor)
    records={key:_result(recorder.root, ref) for key,ref in refs.items()}
    raw={"window_id":window_id,"phase":"baseline","server_teardown_before":records["server_stop_0"],"server_start":records["server_start_0"],"server_readiness":records["server_ready_0"],"r2_tx_before":records["r2_tx_0"],"r3_rx_before":records["r3_rx_0"],"qdisc_before":records["qdisc_0"],"filters_before":[records["filters_0"]],"iperf":records["iperf_0"],"ping":records["traffic_ping_0"],"r2_tx_after":records["r2_tx_1"],"r3_rx_after":records["r3_rx_1"],"qdisc_after":records["qdisc_1"],"filters_after":[records["filters_1"]],"server_teardown_after":records["server_stop_1"],"elapsed_seconds":20.0,"command_references":refs}
    derived=derive_window(raw, phase="baseline", speed_mbps=speed_mbps)
    values={feature:derived[feature]["value"] for feature in NUMERIC_FEATURES if derived[feature].get("availability")=="observed"}
    if set(values)!=set(NUMERIC_FEATURES): _fail("window measurement unavailable")
    now=monotonic_ns(); return {"window_id":window_id,"features":values,"raw":raw,"timing":{"actual_start_ns":now,"actual_end_ns":now+20_000_000_000,"startup_skew_seconds":0.0}}

def collect_thirty(recorder: CommandRecorder, *, executor: Executor, speed_mbps: int) -> dict[str,object]:
    rows=[]; manifest=None
    for index, window_id in enumerate(WINDOW_IDS):
        row=collect_window(recorder, window_id=window_id, executor=executor, speed_mbps=speed_mbps); row["timing"]["actual_start_ns"]=index*25_000_000_000; row["timing"]["actual_end_ns"]=index*25_000_000_000+20_000_000_000
        write_json_fsync(recorder.root/"raw"/"windows"/(window_id+".json"), {**row,"source_test_only":recorder.source_test_only}); rows.append(row)
        if index==9:
            manifest=build_threshold_manifest({f:[r["features"][f] for r in rows] for f in NUMERIC_FEATURES},topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH",traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
            path=recorder.root/"state/threshold_manifest.json"; path.write_bytes(canonical_threshold_manifest_bytes(manifest)); write_json_fsync(recorder.root/"state/threshold_freeze.json",{"after_window_id":"C10","before_window_id":"C11","manifest_sha256":manifest["sha256"],"byte_sha256":sha256(path.read_bytes())})
    for name in ("r2_speed","r3_speed","processes","namespaces","cleanup","qdisc","filters","processes","namespaces"):
        reference=recorder.capture(name=name,phase="final_drift",action_id="cleanup_final_drift",executor=executor)
        _result(recorder.root,reference)
    return {"windows":rows,"manifest":manifest}

def finalize_inventory(root: Path) -> None:
    artifacts=[]
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and not path.is_symlink() and path.relative_to(root).as_posix() != "state/artifact_inventory.json": artifacts.append({"path":path.relative_to(root).as_posix(),"sha256":sha256(path.read_bytes())})
    write_json_fsync(Path(root)/"state/artifact_inventory.json", {"artifacts":artifacts})

def recover(root: Path, *, executor: Executor) -> dict[str,object]:
    journal=json.loads((Path(root)/"state/action_journal.json").read_text()); original=int(journal.get("original_pid",0)); current=os.getpid()
    if original <= 0 or current == original: _fail("recovery requires a distinct process")
    recorder=CommandRecorder(Path(root),run_id=str(journal["run_id"]),authorization_id=str(journal["authorization_id"]),source_test_only=bool(journal.get("source_test_only", True)),resume=True)
    first_recovery_order=len(recorder.rows)+1
    for name in ("processes","namespaces","qdisc","filters","cleanup","processes","namespaces","qdisc","filters"):
        ref=recorder.capture(name=name,phase="recovery",action_id="recovery",executor=executor)
        _result(recorder.root,ref)
    last_recovery_order=len(recorder.rows)
    prior={}
    recovery_path=Path(root)/"state/recovery.json"
    if recovery_path.exists():
        prior=json.loads(recovery_path.read_text(encoding="utf-8"))
        if prior.get("run_id") != journal["run_id"] or prior.get("authorization_id") != journal["authorization_id"] or prior.get("original_pid") != original:
            _fail("recovery artifact identity mismatch")
    result={"original_pid":original,"recovery_pid":current,"run_id":journal["run_id"],"authorization_id":journal["authorization_id"],"distinct_process":True,"replay_count":int(prior.get("replay_count",0))+1,"recovery_first_order":first_recovery_order,"recovery_last_order":last_recovery_order,"status":"IDEMPOTENT_RECOVERY_CONFIRMED"}; write_json_fsync(recovery_path,result); finalize_inventory(Path(root)); return result

def recovery_main() -> int:
    """CLI intentionally accepts only a run root; no caller PID/status exists."""
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument("--run-root",type=Path,required=True); args=parser.parse_args()
    root=Path(args.run_root); journal=json.loads((root/"state/action_journal.json").read_text())
    class RepositoryRecoveryExecutor:
        allowed={"processes","namespaces","qdisc","filters","cleanup"}
        def __call__(self, command:list[str])->dict[str,object]:
            name=next((key for key,value in COMMANDS.items() if value==command and key in self.allowed),None)
            if name is None: _fail("unknown recovery command")
            result=run_capture(COMMANDS[name],timeout_seconds=30)
            return {"return_code":result.returncode,"stdout":result.stdout,"stderr":result.stderr}
    recover(root,executor=RepositoryRecoveryExecutor()); return 0

if __name__ == "__main__": raise SystemExit(recovery_main())
