"""Frozen X6 F1 NetEm mutation and crash-safe recovery."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Callable, Mapping
from src.collection.x6_performance_collector import exact_fault_hierarchy, exact_noqueue
from src.fault_injection.phase6_common import utc_now, write_json_atomic

CommandExecutor=Callable[[list[str]],dict[str,object]]
ACTION_IDS=("INSTALL_NETEM_ROOT","INSTALL_PFIFO_CHILD")

def _read(path:Path)->dict[str,object]:
    value=json.loads(path.read_text());
    if not isinstance(value,dict): raise RuntimeError("X6-R1 durable state malformed")
    return value

def planned_journal(context:Mapping[str,object])->dict[str,object]:
    return {"schema_version":1,"release_id":"X6_R1_PACKET_LOSS","status":"PLANNED","events":[{"state":"PLANNED","at_utc":utc_now(),"detail":"durable_before_any_forward_command"}],"actions":[{"action_id":name,"status":"PLANNED"} for name in ACTION_IDS],"approved_forward_commands":context["qdisc"]["forward_commands"],"approved_recovery_command":context["qdisc"]["recovery_command"]}

def apply_mutation(root:Path, context:Mapping[str,object], executor:CommandExecutor)->list[dict[str,object]]:
    path=root/"mutation/action_journal.json"; journal=_read(path); records=[]
    for index,command in enumerate(context["qdisc"]["forward_commands"]):
        action=journal["actions"][index]; action["status"]="ATTEMPTED"; action["attempted_at_utc"]=utc_now(); journal["status"]="ATTEMPTED"; journal["events"].append({"state":"ATTEMPTED","action_id":action["action_id"],"at_utc":utc_now()}); write_json_atomic(path,journal)
        record=executor(command); records.append(record); action["command_record"]=record; action["status"]="COMMAND_ACCEPTED" if record.get("return_code")==0 else "FAILED"; journal["status"]=action["status"]; journal["events"].append({"state":action["status"],"action_id":action["action_id"],"at_utc":utc_now()}); write_json_atomic(path,journal)
        if record.get("return_code")!=0: raise RuntimeError("X6-R1 qdisc forward command rejected")
    write_json_atomic(root/"mutation/command_acceptance.json",{"schema_version":1,"status":"COMMAND_ACCEPTED","records":records,"physical_effectiveness":"NOT_INFERRED"}); return records

def recover(root:Path, context:Mapping[str,object], executor:CommandExecutor)->dict[str,object]:
    journal=_read(root/"mutation/action_journal.json"); qdisc=executor(context["qdisc"]["capture_command"]); filters=[executor(command) for command in context["qdisc"]["filter_commands"]]
    if exact_noqueue(qdisc,filters): status,command="ALREADY_RESTORED",None
    elif exact_fault_hierarchy(qdisc) or any(action.get("status") in {"ATTEMPTED","COMMAND_ACCEPTED","MUTATION_EFFECTIVE"} for action in journal["actions"]):
        command=executor(context["qdisc"]["recovery_command"]); status="RECOVERY_COMMAND_ACCEPTED" if command.get("return_code")==0 else "FAILED"
    else: raise RuntimeError("X6-R1 recovery refused unapproved qdisc state")
    final=executor(context["qdisc"]["capture_command"]); final_filters=[executor(command) for command in context["qdisc"]["filter_commands"]]
    restored=exact_noqueue(final,final_filters); journal["status"]="RESTORATION_CONFIRMED" if restored else "FAILED"; journal["events"].append({"state":journal["status"],"at_utc":utc_now()}); write_json_atomic(root/"mutation/action_journal.json",journal)
    return {"schema_version":1,"status":"RESTORATION_CONFIRMED" if restored else "RESTORATION_FAILED","operation":status,"command_record":command,"final_qdisc":final,"final_filters":final_filters,"completed_at_utc":utc_now()}
