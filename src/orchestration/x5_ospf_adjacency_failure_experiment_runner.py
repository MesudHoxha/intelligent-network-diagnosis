from __future__ import annotations
import json
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from src.collection.ospf_state_collector_v1 import build_ospf_feature_vector_v2, collect_ospf_adjacency_evidence_v4
from src.fault_injection.phase6_common import utc_now, write_json_atomic
from src.rules.ospf_rule_engine_x5_r1 import diagnose_ospf_adjacency_failure_v2
from src.runtime.subprocesses import run_capture

ROOT=Path(__file__).resolve().parents[2]
def _run(command:list[str])->dict[str,object]:
 r=run_capture(command,timeout_seconds=90.0); return {"command":command,"return_code":r.returncode,"stdout":r.stdout,"stderr":r.stderr}
def _ok(result:dict[str,object], message:str)->None:
 if result["return_code"]!=0: raise RuntimeError(message+": "+str(result["stderr"]))
def run_x5_r1_experiment(output_root:Path, baseline:Path, *, experiment_id:str|None=None)->dict[str,object]:
 experiment_id=experiment_id or "x5-r1-ospf-adjacency-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"-"+uuid4().hex
 root=Path(output_root)/experiment_id; root.mkdir(parents=True,exist_ok=False); mutation=root/"mutation"; mutation.mkdir(); before=_run(["bash",str(baseline)]); write_json_atomic(root/"validation/baseline_before.json",before); _ok(before,"X5-R1 baseline before failed")
 intent={"schema_version":1,"scenario_id":"X5_R1_OSPF_ADJACENCY_FAILURE","fault_type":"dynamic_routing_adjacency_failure","target":"r2:eth2","status":"RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED","created_at_utc":utc_now()}; write_json_atomic(mutation/"recovery_intent.json",intent)
 primary=None
 try:
  injected=_run(["docker","exec","clab-x5r1-r2","vtysh","-c","configure terminal","-c","router ospf","-c","passive-interface eth2"]); write_json_atomic(mutation/"injection_record.json",{**intent,"mutation_command":injected,"status":"FAULT_CONFIRMED" if injected["return_code"]==0 else "FAULT_NOT_CONFIRMED"}); _ok(injected,"X5-R1 mutation failed")
  evidence=collect_ospf_adjacency_evidence_v4(root,repository_root=ROOT); vector=build_ospf_feature_vector_v2(root,evidence,repository_root=ROOT); diagnosis=diagnose_ospf_adjacency_failure_v2(vector,repository_root=ROOT); write_json_atomic(root/"diagnosis/diagnosis_result_v2.json",diagnosis)
  if diagnosis["status"]!="diagnosed": raise RuntimeError("X5-R1 exact C4 rule did not diagnose")
 except BaseException as error: primary=error
 restore=_run(["docker","exec","clab-x5r1-r2","vtysh","-c","configure terminal","-c","router ospf","-c","no passive-interface eth2"]); write_json_atomic(mutation/"restoration_record.json",{**intent,"restoration_command":restore,"status":"RESTORATION_CONFIRMED" if restore["return_code"]==0 else "RESTORATION_FAILED","completed_at_utc":utc_now()}); _ok(restore,"X5-R1 restoration failed")
 after=_run(["bash",str(baseline)]); write_json_atomic(root/"validation/baseline_after.json",after); _ok(after,"X5-R1 baseline after failed")
 if primary: raise primary
 write_json_atomic(root/"manifest.json",{"schema_version":1,"release_id":"X5_R1_OSPF_ADJACENCY_FAILURE","experiment_id":experiment_id,"status":"COMPLETED","completed_at_utc":utc_now()})
 return {"status":"COMPLETED","experiment_directory":str(root),"restoration_confirmed":True,"baseline_valid_after":True}
