from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

from src.collection.ospf_state_collector_x5_r4 import capture, collect_x5_r4_evidence, build_x5_r4_feature_vector, target_state
from src.fault_injection.phase6_common import utc_now, write_json_atomic
from src.rules.ospf_rule_engine_x5_r4 import diagnose_targeted_ospf_adjacency_failure_v2

ROOT=Path(__file__).resolve().parents[2]

def _ok(result:dict[str,object], label:str)->None:
    if result["return_code"]!=0: raise RuntimeError(label+": "+str(result["stderr"]))

def _state_until_effective(timeout_seconds:float=45.0)->dict[str,object]:
    attempts=[]; deadline=monotonic()+timeout_seconds
    while True:
        r2=capture(["docker","exec","clab-x5r1-r2","vtysh","-c","show ip ospf neighbor json"]); route=capture(["docker","exec","clab-x5r1-r1","vtysh","-c","show ip route 10.51.3.0/24 json"]); database=capture(["docker","exec","clab-x5r1-r1","vtysh","-c","show ip ospf database json"]); policy=capture(["docker","exec","clab-x5r1-r2","vtysh","-c","show running-config"])
        targeted=target_state(r2); state={"target_r2_r3_non_full":not bool(targeted["r2_r3_full"]),"control_r1_r2_full":bool(targeted["r1_r2_full"]),"passive_eth2_present":"ip ospf passive" in str(policy["stdout"]),"route_absent":"ospf" not in str(route["stdout"]).lower(),"target_lsa_absent":"3.3.3.3" not in str(database["stdout"]),"targeted_neighbor":targeted,"r2_neighbor":r2,"route":route,"database":database,"policy":policy};attempts.append(state)
        if all(bool(state[key]) for key in ("target_r2_r3_non_full","control_r1_r2_full","passive_eth2_present","route_absent","target_lsa_absent")): return {"status":"MUTATION_EFFECTIVE","attempts":attempts}
        if monotonic()>=deadline: return {"status":"MUTATION_NOT_EFFECTIVE","attempts":attempts}
        sleep(1)

def run_x5_r4_experiment(output_root:Path, baseline:Path, *, experiment_id:str|None=None)->dict[str,object]:
    experiment_id=experiment_id or "x5-r4-targeted-c4-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"-"+uuid4().hex; root=Path(output_root)/experiment_id; root.mkdir(parents=True,exist_ok=False); mutation=root/"mutation";mutation.mkdir()
    before=capture(["bash",str(baseline)]);write_json_atomic(root/"validation/baseline_before.json",before);_ok(before,"X5-R4 baseline before failed")
    intent={"schema_version":1,"scenario_id":"X5_R4_OSPF_CORRECTION_AND_REVALIDATION","fault_type":"dynamic_routing_adjacency_failure","target":"r2:eth2_to_r3:eth1","status":"RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED","created_at_utc":utc_now()};write_json_atomic(mutation/"recovery_intent.json",intent);primary=None
    try:
        command=capture(["docker","exec","clab-x5r1-r2","vtysh","-c","configure terminal","-c","router ospf","-c","passive-interface eth2"]);write_json_atomic(mutation/"injection_record.json",{**intent,"mutation_command":command,"status":"COMMAND_ACCEPTED" if command["return_code"]==0 else "COMMAND_REJECTED"});_ok(command,"X5-R4 passive-interface command failed")
        effectiveness=_state_until_effective();write_json_atomic(mutation/"mutation_effectiveness.json",effectiveness)
        if effectiveness["status"]!="MUTATION_EFFECTIVE": raise RuntimeError("X5-R4 targeted C4 postcondition did not converge")
        evidence=collect_x5_r4_evidence(root,repository_root=ROOT);vector=build_x5_r4_feature_vector(root,evidence,repository_root=ROOT);diagnosis=diagnose_targeted_ospf_adjacency_failure_v2(vector,repository_root=ROOT);write_json_atomic(root/"diagnosis/diagnosis_result_v2.json",diagnosis)
        if diagnosis["status"]!="diagnosed": raise RuntimeError("X5-R4 exact targeted C4 rule did not diagnose")
    except BaseException as error: primary=error
    restore=capture(["docker","exec","clab-x5r1-r2","vtysh","-c","configure terminal","-c","router ospf","-c","no passive-interface eth2"]);write_json_atomic(mutation/"restoration_record.json",{**intent,"restoration_command":restore,"status":"RESTORATION_CONFIRMED" if restore["return_code"]==0 else "RESTORATION_FAILED","completed_at_utc":utc_now()});_ok(restore,"X5-R4 restoration failed")
    after=capture(["bash",str(baseline)]);write_json_atomic(root/"validation/baseline_after.json",after);_ok(after,"X5-R4 baseline after failed")
    if primary: raise primary
    write_json_atomic(root/"manifest.json",{"schema_version":1,"release_id":"X5_R4_OSPF_CORRECTION_AND_REVALIDATION","experiment_id":experiment_id,"status":"COMPLETED","completed_at_utc":utc_now()});return {"status":"COMPLETED","experiment_directory":str(root),"restoration_confirmed":True,"baseline_valid_after":True}
