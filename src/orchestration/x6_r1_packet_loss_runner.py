"""One-shot, crash-safe X6-R1 controlled packet-loss pilot."""
from __future__ import annotations
from datetime import datetime,timezone
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
import hashlib,json,math,sys
from pathlib import Path
from time import monotonic,sleep
from typing import Callable
from uuid import uuid4
from src.collection.x6_performance_collector import FEATURES,aggregate_windows,collect_window,derive_window,exact_fault_hierarchy,exact_noqueue,materialize_evidence,qdisc_dropped,validate_speed_pair
from src.collection.x6_r0_2_measurement_semantics import _REPLY
from src.collection.x6_r0_3_pre_runtime_validation import build_threshold_manifest,canonical_threshold_manifest_bytes,validate_threshold_manifest
from src.expansion.x6_r1_runtime_context import load_x6_r1_runtime_context,x6_r1_context_identity
from src.collection.x6_r0_5_route_bootstrap import validate_management_default,validate_route_get
from src.fault_injection.phase6_common import utc_now,write_json_atomic
from src.fault_injection.x6_packet_loss import apply_mutation,planned_journal,recover
from src.expansion.x6_r1_performance_rule import diagnose_x6_r1,predicates_from_vector
from src.runtime.subprocesses import run_capture
from src.expansion.x6_r1_failure_terminalization import terminalize_x6_r1_failure

ROOT=Path(__file__).resolve().parents[2]
CommandExecutor=Callable[[list[str]],dict[str,object]]
def capture(command:list[str])->dict[str,object]:
    timeout=25 if "/usr/bin/iperf3" in command and "-c" in command else 16 if "/usr/bin/ping" in command and "-c" in command and "50" in command else 10 if "/usr/sbin/tc" in command else 10
    result=run_capture(command,timeout_seconds=timeout); return {"command":command,"timeout_seconds":timeout,"return_code":result.returncode,"stdout":result.stdout,"stderr":result.stderr,"started_at_utc":utc_now(),"completed_at_utc":utc_now()}
def _ok(record:dict[str,object],label:str)->None:
    if record.get("return_code")!=0: raise RuntimeError(label+": "+str(record.get("stderr","")))
def verify_x6_r0_7_host_netem_prerequisite(executor:CommandExecutor)->dict[str,object]:
    """Verify only; the scientific runner must never load a host module."""
    records={"kernel":executor(["uname","-r"]),"kernel_config":executor(["bash","-lc","zgrep CONFIG_NET_SCH_NETEM /proc/config.gz"]),"module":executor(["modinfo","sch_netem"]),"loaded_modules":executor(["lsmod"])}
    if any(record.get("return_code")!=0 for record in records.values()): raise RuntimeError("X6-R1 MODULE_UNAVAILABLE: X6-R0.7 host NetEm prerequisite command failed")
    kernel=str(records["kernel"].get("stdout","")).strip(); config=str(records["kernel_config"].get("stdout","")).strip(); module=str(records["module"].get("stdout","")).strip(); loaded=str(records["loaded_modules"].get("stdout","")).strip()
    if not kernel or "CONFIG_NET_SCH_NETEM=m" not in config and "CONFIG_NET_SCH_NETEM=y" not in config or "name:           sch_netem" not in module or kernel not in module or not any(line.startswith("sch_netem ") for line in loaded.splitlines()): raise RuntimeError("X6-R1 MODULE_UNAVAILABLE: run sudo modprobe sch_netem before deployment")
    return {"status":"X6_R0_7_HOST_NETEM_PREREQUISITE_VERIFIED","policy":"VERIFY_ONLY_NEVER_PRIVILEGED_MODULE_LOAD","records":records}
def wait_for_baseline_health(executor:CommandExecutor,*,timeout_seconds:float=15.0,poll_seconds:float=.1)->dict[str,object]:
    """Wait only for the declared healthy path; never use a fixed sleep."""
    deadline=monotonic()+timeout_seconds; attempts=[]
    while True:
        attempt={"at_utc":utc_now(),"ping":executor(["docker","exec","clab-x6r1-hosta","ping","-c","1","-W","2","10.61.3.2"]),"forwarding":[executor(["docker","exec","clab-x6r1-"+node,"sysctl","-n","net.ipv4.ip_forward"]) for node in ("r1","r2","r3")],"routes":[executor(["docker","exec","clab-x6r1-"+node,"ip","route","get",destination]) for node,destination in (("hosta","10.61.3.2"),("r1","10.61.3.2"),("r2","10.61.3.2"),("r3","10.61.1.2"))]}
        healthy=attempt["ping"].get("return_code")==0 and all(row.get("return_code")==0 and str(row.get("stdout","")).strip()=="1" for row in attempt["forwarding"]) and all(row.get("return_code")==0 for row in attempt["routes"])
        attempts.append(attempt)
        if healthy:return {"status":"BASELINE_HEALTHY","attempts":attempts}
        if monotonic()>=deadline:return {"status":"BASELINE_HEALTH_TIMEOUT","attempts":attempts}
        sleep(poll_seconds)
def _raw(root:Path,phase:str,index:int,value:dict[str,object])->Path:
    path=root/"raw/v4/performance_collector"/(phase+"_window_"+f"{index:02d}"+".json"); write_json_atomic(path,value); return path
def _speed(executor:CommandExecutor)->tuple[int,dict[str,object]]:
    commands={"r2_speed": ["docker","exec","clab-x6r1-r2","cat","/sys/class/net/eth2/speed"],"r3_speed":["docker","exec","clab-x6r1-r3","cat","/sys/class/net/eth1/speed"],"r2_ethtool":["docker","exec","clab-x6r1-r2","ethtool","eth2"],"r3_ethtool":["docker","exec","clab-x6r1-r3","ethtool","eth1"]}; records={name:executor(command) for name,command in commands.items()}; return validate_speed_pair(records["r2_speed"],records["r3_speed"],records["r2_ethtool"],records["r3_ethtool"]),records
def _topology_preflight(executor:CommandExecutor,context:dict[str,object])->dict[str,object]:
    defaults={node:executor(["docker","exec","clab-x6r1-"+node,"ip","-j","route","show","default"]) for node in ("hosta","hostb")}
    for record in defaults.values(): validate_management_default(record)
    expected={
        "hosta_forward":("hosta","10.61.3.2","10.61.1.1","eth1","10.61.1.2"),
        "hostb_reverse":("hostb","10.61.1.2","10.61.3.1","eth1","10.61.3.2"),
        "r1_forward":("r1","10.61.3.2","10.61.12.2","eth2","10.61.12.1"),
        "r2_forward":("r2","10.61.3.2","10.61.23.2","eth2","10.61.23.1"),
        "r2_reverse":("r2","10.61.1.2","10.61.12.1","eth1","10.61.12.2"),
        "r3_reverse":("r3","10.61.1.2","10.61.23.1","eth1","10.61.23.2"),
    }
    routes={name:executor(["docker","exec","clab-x6r1-"+node,"ip","-j","route","get",destination]) for name,(node,destination,_,_,_) in expected.items()}
    for name,(node,destination,via,dev,src) in expected.items(): validate_route_get(routes[name],destination=destination,via=via,dev=dev,src=src)
    interfaces={name:executor(command) for name,command in {
        "r2_eth2":["docker","exec","clab-x6r1-r2","ip","-j","link","show","eth2"],
        "r3_eth1":["docker","exec","clab-x6r1-r3","ip","-j","link","show","eth1"],
    }.items()}
    for name,record in interfaces.items():
        try: rows=json.loads(str(record["stdout"])); healthy=record["return_code"]==0 and isinstance(rows,list) and len(rows)==1 and "UP" in rows[0].get("flags",[])
        except (KeyError,json.JSONDecodeError,TypeError): healthy=False
        if not healthy: raise RuntimeError("X6-R1 interface preflight failed: "+name)
    tools={"kernel":executor(["docker","exec","clab-x6r1-r2","/usr/bin/uname","-r"])}
    for index,command in enumerate(context["traffic"]["version_commands"]): tools["frozen_tool_"+str(index)]=executor(command)
    if any(record.get("return_code")!=0 for record in tools.values()): raise RuntimeError("X6-R1 tool-version preflight failed")
    return {"management_defaults":defaults,"experiment_routes":routes,"interfaces":interfaces,"tool_versions":tools}
def _standalone(root:Path)->dict[str,object]:
    command=[sys.executable,"-m","src.orchestration.x6_r1_packet_loss_runner","--recover",str(root)]; result=run_capture(command,timeout_seconds=20,cwd=ROOT); record={"command":command,"return_code":result.returncode,"stdout":result.stdout,"stderr":result.stderr,"status":"FAILED"}
    if result.returncode==0:
        try: replay=json.loads(result.stdout)
        except json.JSONDecodeError: replay=None
        if isinstance(replay,dict) and replay.get("status")=="RESTORATION_CONFIRMED": record.update({"status":"STANDALONE_REPLAY_CONFIRMED","replay":replay})
    write_json_atomic(root/"mutation/standalone_replay.json",record); return record
def _within_restored_baseline(windows:list[dict[str,object]],threshold:dict[str,object])->bool:
    if len(windows)!=3 or any(any(item["availability"]!="observed" for item in row.values()) for row in windows): return False
    bounds={row["feature_id"]:row for row in threshold["features"]}
    for row in windows:
        if float(row["packet_loss_ratio"]["value"])>float(bounds["packet_loss_ratio"]["upper_threshold"]): return False
        if float(row["round_trip_latency_ms_p95"]["value"])>float(bounds["round_trip_latency_ms_p95"]["upper_threshold"]): return False
        if float(row["throughput_mbps"]["value"])<float(bounds["throughput_mbps"]["lower_threshold"]): return False
        if float(row["interface_utilization_ratio"]["value"])>float(bounds["interface_utilization_ratio"]["upper_threshold"]): return False
        if int(row["queue_drop_count"]["value"])>int(float(bounds["queue_drop_count"]["upper_threshold"])) or row["rate_limit_detected"]["value"] is not False: return False
    return True

def canonical_threshold_baselines(numeric:dict[str,list[object]])->dict[str,list[str]]:
    """Serialize the manifest's bound baseline inputs before deriving fields.

    Raw collector records retain native precision.  The threshold manifest
    declares six-decimal half-even canonical baseline values, so all derived
    fields must be calculated from exactly those durable bound values.
    """
    quantum=Decimal("0.000001"); result:dict[str,list[str]]={}
    for feature_id,values in numeric.items():
        canonical=[]
        for value in values:
            if isinstance(value,bool): raise RuntimeError("X6-R1 baseline numeric observation is malformed")
            try: decimal=Decimal(str(value))
            except (InvalidOperation,ValueError) as error: raise RuntimeError("X6-R1 baseline numeric observation is malformed") from error
            if not decimal.is_finite(): raise RuntimeError("X6-R1 baseline numeric observation is malformed")
            canonical.append(format(decimal.quantize(quantum,rounding=ROUND_HALF_EVEN),"f"))
        result[feature_id]=canonical
    return result

def _terminalize_without_masking(root:Path,*,terminal_phase:str,last_successful_phase:str,error:BaseException,cleanup_status:str)->None:
    """Persist incomplete-lifecycle state, retaining the originating error."""
    try:
        terminalize_x6_r1_failure(root,terminal_phase=terminal_phase,last_successful_phase=last_successful_phase,error=error,cleanup_status=cleanup_status)
    except Exception:
        # A terminal-record write failure must never replace the causal failure.
        pass

def run_x6_r1(output_root:Path,*,experiment_id:str|None=None,executor:CommandExecutor=capture,predeployment_image_identity:dict[str,object]|None=None,predeployment_netem_prerequisite:dict[str,object]|None=None)->dict[str,object]:
    context=load_x6_r1_runtime_context(ROOT); experiment_id=experiment_id or "x6-r1-packet-loss-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"-"+uuid4().hex; root=Path(output_root)/experiment_id; root.mkdir(parents=True,exist_ok=False); (root/"raw/v4/performance_collector").mkdir(parents=True); (root/"mutation").mkdir(); (root/"validation").mkdir(); (root/"parsed").mkdir(); (root/"diagnosis").mkdir()
    try:
        source={"topology_sha256":hashlib.sha256((ROOT/context["topology"]["file"]).read_bytes()).hexdigest(),"dockerfile_sha256":hashlib.sha256((ROOT/context["image"]["dockerfile"]).read_bytes()).hexdigest(),**x6_r1_context_identity(ROOT)}; write_json_atomic(root/"validation/source_identity.json",source)
        prerequisite=predeployment_netem_prerequisite or verify_x6_r0_7_host_netem_prerequisite(executor)
        if prerequisite.get("status")!="X6_R0_7_HOST_NETEM_PREREQUISITE_VERIFIED": raise RuntimeError("X6-R1 MODULE_UNAVAILABLE: invalid X6-R0.7 prerequisite record")
        write_json_atomic(root/"validation/netem_prerequisite.json",prerequisite)
        image=predeployment_image_identity or executor(context["image"]["identity_command"]); _ok(image,"X6-R1 image identity unavailable"); entries=json.loads(str(image["stdout"])); write_json_atomic(root/"validation/runtime_image_identity.json",{"record":image,"captured_before_deployment":predeployment_image_identity is not None,"image_id":entries[0].get("Id"),"repo_digests":entries[0].get("RepoDigests",[])})
        health=wait_for_baseline_health(executor); write_json_atomic(root/"validation/baseline_health.json",health)
        if health["status"]!="BASELINE_HEALTHY": raise RuntimeError("X6-R1 bounded baseline health did not converge")
        topology_preflight=_topology_preflight(executor,context)
        q0=executor(context["qdisc"]["capture_command"]); f0=[executor(command) for command in context["qdisc"]["filter_commands"]]
        if not exact_noqueue(q0,f0): raise RuntimeError("X6-R1 unsupported qdisc pre-state")
        speed,speed_records=_speed(executor); write_json_atomic(root/"validation/baseline_before.json",{"status":"BASELINE_VALID","health":health,"topology_preflight":topology_preflight,"qdisc":q0,"filters":f0,"speed_mbps":speed,"speed_records":speed_records})
        sleep(5); readiness=executor(["docker","exec","clab-x6r1-hosta","ping","-c","1","-W","2","10.61.3.2"]); _ok(readiness,"X6-R1 readiness failed"); write_json_atomic(root/"validation/readiness.json",readiness)
        raw_files=[]; baseline=[]
        for index in range(1,11):
            raw=collect_window(f"baseline-{index:02d}","baseline",context,executor); path=_raw(root,"baseline",index,raw); raw_files.append(path); baseline.append(derive_window(raw,phase="baseline",speed_mbps=speed))
        numeric={name:[row[name]["value"] for row in baseline] for name in FEATURES[:5]}
        if any(value is None for values in numeric.values() for value in values): raise RuntimeError("X6-R1 baseline observation unavailable")
        threshold_inputs=canonical_threshold_baselines(numeric)
        threshold=build_threshold_manifest(threshold_inputs,topology_context_id=context["topology"]["context_id"],traffic_context_id="X6_TRAFFIC_01_FROZEN_TCP_AND_PING"); validate_threshold_manifest(threshold,repository_root=ROOT); threshold_path=root/"validation/threshold_manifest_v1.json"; threshold_path.write_bytes(canonical_threshold_manifest_bytes(threshold)); frozen_hash=hashlib.sha256(threshold_path.read_bytes()).hexdigest(); write_json_atomic(root/"validation/threshold_freeze_record.json",{"status":"FROZEN_BEFORE_MUTATION","sha256":frozen_hash,"fault_inputs":"FORBIDDEN","baseline_input_representation":"six_decimal_round_half_even_canonical_values","frozen_at_utc":utc_now()})
        intent={"schema_version":1,"release_id":"X6_R1_PACKET_LOSS","status":"RECOVERY_REQUIRED_IF_PLANNED","runtime_context_identity":source,"target":"clab-x6r1-r2:eth2","created_at_utc":utc_now()}; write_json_atomic(root/"mutation/recovery_intent.json",intent); write_json_atomic(root/"mutation/action_journal.json",planned_journal(context))
    except BaseException as error:
        _terminalize_without_masking(root,terminal_phase="pre_mutation",last_successful_phase="evidence_root_created",error=error,cleanup_status="NO_MUTATION_PLANNED_OR_ACCEPTED")
        raise
    primary=None
    try:
        apply_mutation(root,context,executor); q_effect=executor(context["qdisc"]["capture_command"])
        if not exact_fault_hierarchy(q_effect): raise RuntimeError("X6-R1 qdisc hierarchy not physically effective")
        fault=[]
        for index in range(1,4):
            current_speed,_=_speed(executor)
            if current_speed!=speed: raise RuntimeError("X6-R1 interface speed changed")
            raw=collect_window(f"fault-{index:02d}","fault",context,executor); path=_raw(root,"fault",index,raw); raw_files.append(path); fault.append(derive_window(raw,phase="fault",speed_mbps=speed))
        values=aggregate_windows(fault); pooled=sorted(float(rtt) for path in raw_files[-3:] for _,rtt in _REPLY.findall(str(json.loads(path.read_text())["ping"].get("stdout",""))))
        if pooled: values["round_trip_latency_ms_p95"]={"availability":"observed","value":pooled[math.ceil(.95*len(pooled))-1]}
        else: values["round_trip_latency_ms_p95"]={"availability":"collection_unavailable","value":None,"reason":"no_pooled_rtt_samples"}
        lost=round(float(values["packet_loss_ratio"]["value"])*150) if values["packet_loss_ratio"]["availability"]=="observed" else -1; netem=sum((qdisc_dropped(json.loads(path.read_text())["qdisc_after"],kind="netem",handle="10:") or 0)-(qdisc_dropped(json.loads(path.read_text())["qdisc_before"],kind="netem",handle="10:") or 0) for path in raw_files[-3:]); pfifo=int(values["queue_drop_count"]["value"]) if values["queue_drop_count"]["availability"]=="observed" else -1
        effective=exact_fault_hierarchy(q_effect) and 6<=lost<=25 and netem>=0 and pfifo==0; effectiveness={"schema_version":1,"status":"MUTATION_EFFECTIVE" if effective else "DIAGNOSTIC_NON_AUTHORITATIVE","lost_packet_count":lost,"netem_drop_delta":netem,"pfifo_drop_delta":pfifo,"accepted_range":[6,25],"hierarchy_exact":exact_fault_hierarchy(q_effect),"diagnosis_not_used":True}; write_json_atomic(root/"mutation/mutation_effectiveness.json",effectiveness)
        if not effective: raise RuntimeError("X6-R1 independent effectiveness/separation failed")
        aggregate_path=root/"raw/v4/performance_collector/fault_aggregate_provenance.json"; write_json_atomic(aggregate_path,{"schema_version":1,"window_ids":["fault-01","fault-02","fault-03"],"input_sha256":{str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in raw_files[-3:]},"derived_values":values,"derivation":"frozen_x6_r0_4_feature_semantics"}); raw_files.append(aggregate_path)
        evidence,vector=materialize_evidence(root,values,[aggregate_path,*raw_files[:-1]],repository_root=ROOT); predicates=predicates_from_vector(vector,threshold,repository_root=ROOT); write_json_atomic(root/"diagnosis/conditional_predicates.json",{"rule_id":"R_X6_PERFORMANCE_001","predicates":predicates}); diagnosis=diagnose_x6_r1(vector,threshold,repository_root=ROOT); write_json_atomic(root/"diagnosis/diagnosis_result_v2.json",diagnosis)
        if diagnosis["status"]!="diagnosed": raise RuntimeError("X6-R1 conditional signature did not separate")
    except BaseException as error: primary=error
    try:
        restoration=recover(root,context,executor); write_json_atomic(root/"mutation/restoration_record.json",restoration)
        replay=_standalone(root)
    except BaseException as error:
        _terminalize_without_masking(root,terminal_phase="recovery_or_replay",last_successful_phase="fault_or_diagnosis",error=error,cleanup_status="RECOVERY_OR_REPLAY_FAILED")
        raise
    restored=[]
    if restoration["status"]=="RESTORATION_CONFIRMED" and replay["status"]=="STANDALONE_REPLAY_CONFIRMED":
        speed_after,_=_speed(executor)
        for index in range(1,4):
            raw=collect_window(f"restored-{index:02d}","restored",context,executor); path=_raw(root,"restored",index,raw); raw_files.append(path); restored.append(derive_window(raw,phase="restored",speed_mbps=speed_after))
    else:
        error=RuntimeError("X6-R1 restoration/replay failed")
        _terminalize_without_masking(root,terminal_phase="recovery_or_replay",last_successful_phase="fault_or_diagnosis",error=error,cleanup_status="RECOVERY_OR_REPLAY_FAILED")
        raise error
    baseline_after={"status":"BASELINE_VALID_AFTER" if _within_restored_baseline(restored,threshold) else "BASELINE_INVALID_AFTER","windows":restored,"threshold_sha256":frozen_hash}; write_json_atomic(root/"validation/baseline_after.json",baseline_after)
    if baseline_after["status"]!="BASELINE_VALID_AFTER":
        error=RuntimeError("X6-R1 baseline-after did not return within frozen thresholds")
        _terminalize_without_masking(root,terminal_phase="baseline_after_validation",last_successful_phase="restoration_and_standalone_replay",error=error,cleanup_status="RESTORATION_AND_REPLAY_COMPLETED")
        raise error
    hashes={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in raw_files}; write_json_atomic(root/"validation/raw_hashes.json",{"status":"VERIFIED","artifacts":hashes});
    if primary:
        _terminalize_without_masking(root,terminal_phase="fault_or_diagnosis",last_successful_phase="restoration_and_standalone_replay",error=primary,cleanup_status="RESTORATION_AND_REPLAY_COMPLETED")
        raise primary
    write_json_atomic(root/"manifest.json",{"schema_version":1,"release_id":"X6_R1_PACKET_LOSS","status":"AUTHORITATIVE","experiment_id":experiment_id,"threshold_sha256":frozen_hash,"completed_at_utc":utc_now()}); return {"status":"AUTHORITATIVE","experiment_directory":str(root),"threshold_sha256":frozen_hash,"speed_mbps":speed}

def main()->int:
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument("--recover",type=Path); args=parser.parse_args()
    if args.recover is None: parser.error("--recover required")
    context=load_x6_r1_runtime_context(ROOT); print(json.dumps(recover(args.recover,context,capture),sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
