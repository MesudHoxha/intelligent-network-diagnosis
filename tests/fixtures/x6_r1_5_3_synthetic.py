"""Raw-observation fixtures produced through the controlled production CLI.

Copies are explicitly synthetic development/test material, never campaign data.
"""
import json,shutil
from pathlib import Path
from src.orchestration.x6_r1_5_1_contract import canonical,digest,load
from src.orchestration.x6_r1_5_1_durable import records
from src.orchestration.x6_r1_5_3_contract import accepted_inventory,campaign_catalog
from tests.unit.test_x6_r1_5_3_production_integration import isolated,worker


def save(path,value,*,exclusive=False):
 """Construct or alter synthetic input fixtures, not a persistence substitute.

 Production CLI, reservations, events, publication, and crash-boundary tests
 continue to use the real durable writer. These copies are fully prepared
 before independent verification and are never a durability claim.
 """
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 with path.open("xb" if exclusive else "wb") as stream:stream.write(canonical(value))


def raw_pair(root):
 env=isolated(root)
 result=worker(root,env,"epoch");assert result.returncode==0,result.stderr
 for index in (0,1):
  if index==1:
   state=json.loads((root/"stub-state.json").read_text());state["diagnostic_abstention"]=True
   (root/"stub-state.json").write_text(json.dumps(state))
  result=worker(root,env,"prepare",index);assert result.returncode==0,result.stderr
  result=worker(root,env,"run",index);assert result.returncode==0,result.stderr
  result=worker(root,env,"verify",index);assert result.returncode==0,result.stderr
 # Retain one actual nonzero launcher observation as a labelled fixture seed.
 result=worker(root,env,"prepare",2);assert result.returncode==0,result.stderr
 state=json.loads((root/"stub-state.json").read_text());state["fail_iperf"]=True
 (root/"stub-state.json").write_text(json.dumps(state))
 result=worker(root,env,"run",2);assert result.returncode!=0
 return root


def _rewrite(value,old,new,offset=0):
 if isinstance(value,str):return value.replace(str(old),str(new))
 if isinstance(value,list):return [_rewrite(v,old,new,offset) for v in value]
 if isinstance(value,dict):
  return {k:(v+offset if k in {"monotonic_ns","start_ns","end_ns"} and type(v) is int else _rewrite(v,old,new,offset)) for k,v in value.items()}
 return value


def copy_launcher(original,root,template,auth):
    """Construct labelled synthetic snapshots from observed prototype receipts.

    These are unit-test data, not assertions that copied slots were executed.
    The actual N0/F1 integration tests execute the outer process for each slot.
    """
    from src.orchestration.x6_r1_5_3_launcher import sealed,evidence_inventory
    source=original/"launcher-receipts"/template["run_id"]
    destination=root/"launcher-receipts"/auth["run_id"]
    start=_rewrite(load(source/"started.json"),original,root)
    start["run_id"]=auth["run_id"];start["output_root"]=auth["output_root"]
    start["authorization_sha256"]=auth["authorization_sha256"]
    start["authorization_file_sha256"]=digest(canonical(auth))
    start["input"]={"slot":auth["slot"],"slot_id":auth["slot"]["slot_id"]}
    start["input_bytes"]=canonical(start["input"]).decode()
    start["input_sha256"]=digest(canonical(start["input"]))
    start["child_arguments"]=["run-slot","--campaign-root",str(root),"--input",str(root/(auth["slot"]["slot_id"]+"-input.json")),"--authorization",str(root/(auth["slot"]["slot_id"]+"-authorization.json"))]
    start["argv"]=start["argv"][:3]+start["child_arguments"]
    start["synthetic_fixture_prototype_sha256"]=digest((source/"started.json").read_bytes())
    start.pop("receipt_sha256");save(destination/"started.json",sealed(start))
    child=load(source/"child.json");child["started_sha256"]=digest((destination/"started.json").read_bytes());child["child_arguments"]=start["child_arguments"]
    child.pop("receipt_sha256");save(destination/"child.json",sealed(child))
    terminal=load(source/"terminal.json");terminal["started_sha256"]=digest((destination/"started.json").read_bytes());terminal["child_sha256"]=digest((destination/"child.json").read_bytes())
    terminal["run_evidence"]=evidence_inventory(auth["output_root"])
    terminal.pop("receipt_sha256");save(destination/"terminal.json",sealed(terminal))


def copy_epoch(source_path,root,destination,*,stage=None,offset=0):
 old=load(source_path);source_directory=Path(old["readiness_root"])
 shutil.copytree(source_directory,destination)
 for path in destination.rglob("*.json"):
  value=_rewrite(load(path),old["campaign_root"],root,offset)
  value=_rewrite(value,source_directory,destination)
  save(path,value)
 for path in sorted((destination/"raw/commands").glob("*.result.json")):
  value=load(path);intent=load(path.with_name(path.name.replace(".result.json",".intent.json")))
  value["intent_sha256"]=digest(canonical(intent));save(path,value)
 epoch_path=destination/"epoch.json";epoch=load(epoch_path)
 epoch["readiness_root"]=str(destination)
 if stage is not None:epoch["stage"]=stage
 epoch["readiness_observation_hashes"]=[digest(canonical(row)) for row in records(destination,campaign_catalog())]
 epoch.pop("epoch_id");epoch["epoch_id"]=digest(canonical(epoch));save(epoch_path,epoch)
 return epoch_path,epoch


def copy_readiness(original,root):
 return copy_epoch(original/"readiness/initial/epoch.json",root,root/"readiness/initial")


def copy_slot(original,root,slot,*,offset=0,epoch_path=None,freeze_sha=None):
 inventory=accepted_inventory()["slots"]
 template=next(s for s in inventory[:2] if s["assignment"]==slot["assignment"])
 oldrun=original/"slots"/template["run_id"];run=root/"slots"/slot["run_id"]
 shutil.copytree(oldrun,run)
 for path in run.rglob("*.json"):
  value=_rewrite(load(path),oldrun,run,offset)
  value=_rewrite(value,template["run_id"],slot["run_id"])
  save(path,value)
 # Rebind each intent/result hash after controlled clock offsets.
 for path in sorted((run/"raw/commands").glob("*.result.json")):
  intent_path=path.with_name(path.name.replace(".result.json",".intent.json"))
  value=load(path);value["intent_sha256"]=digest(canonical(load(intent_path)));save(path,value)
 raw=records(run,campaign_catalog())
 auth=load(oldrun/"state/authorization.json");auth["slot"]=slot;auth["run_id"]=slot["run_id"];auth["output_root"]=str(run)
 epoch_path=epoch_path or root/"readiness/initial/epoch.json";epoch=load(epoch_path)
 auth["development_freeze_sha256"]=freeze_sha
 auth["epoch"]={"path":str(epoch_path),"sha256":digest(epoch_path.read_bytes()),"epoch_id":epoch["epoch_id"]}
 auth["authorization_id"]=slot["slot_id"]+"_SYNTHETIC";auth.pop("authorization_sha256");auth["authorization_sha256"]=digest(canonical(auth));save(run/"state/authorization.json",auth)
 for name in ("restoration-action","recovery"):
  path=run/"state"/(name+".json")
  if path.exists():
   value=load(path);value["records_sha256"]=digest(canonical([row for row in raw if row["order"] in value["command_orders"]]));save(path,value)
 cohort_path=run/"state/target-cohort.json";cohort=load(cohort_path)
 cohort["windows"]=[{"window_id":wid,"sha256":digest((run/"raw/windows"/(wid+".json")).read_bytes())} for wid in ("F01","F02","F03")];save(cohort_path,cohort)
 terminal_path=run/"terminal/terminal.json";terminal=load(terminal_path);terminal["target_cohort_sha256"]=digest(cohort_path.read_bytes());save(terminal_path,terminal)
 row=load(run/"parsed/campaign-row.json");row["slot_identity"]={k:slot[k] for k in ("slot_id","block_id","stage","position")};row["block_id"]=slot["block_id"];save(run/"parsed/campaign-row.json",row)
 # Seed a legal hash chain from the actual production attempt, preserving timings.
 events=[load(path) for path in sorted((original/"accounting/slot"/template["slot_id"]).glob("*.json"))]
 old_admitted=next(value for value in events if value["state"]=="ADMITTED")
 old_admission=Path(old_admitted["evidence"]["prerequisites"]["admission"]["path"])
 admission_path,admission_epoch=copy_epoch(old_admission,root,root/"readiness"/(slot["slot_id"]+"-admission"),stage=slot["stage"],offset=offset)
 admission={"path":str(admission_path),"sha256":digest(admission_path.read_bytes()),"epoch_id":admission_epoch["epoch_id"]}
 prior=[{"slot_id":p["slot_id"],"head":load(sorted((root/"accounting/slot"/p["slot_id"]).glob("*.json"))[-1])["event_sha256"]} for p in inventory[:inventory.index(slot)]]
 for index,value in enumerate(events,1):
  value=_rewrite(value,oldrun,run,offset);value["identity"]=slot["slot_id"]
  if index==1:value["evidence"]={"authorization":auth,"authorization_sha256":auth["authorization_sha256"]}
  if value["state"]=="ADMITTED":value["evidence"]={"decision":"AUTHORIZED_SLOT_ENTRY","authorization_sha256":auth["authorization_sha256"],"commitment_observation":value["evidence"]["commitment_observation"],"prerequisites":{"prior_heads":prior,"epoch_sha256":auth["epoch"]["sha256"],"development_freeze_sha256":freeze_sha,"admission":admission}}
  value["previous_sha256"]=None if index==1 else previous
  value.pop("event_sha256");value["event_sha256"]=digest(canonical(value));previous=value["event_sha256"]
  save(root/"accounting/slot"/slot["slot_id"]/f"{index:06d}.json",value,exclusive=True)
 copy_launcher(original,root,template,auth)
 return run


def campaign_copy(original,root,count=2):
 root.mkdir(exist_ok=True);copy_readiness(original,root)
 for index,slot in enumerate(accepted_inventory()["slots"][:count]):copy_slot(original,root,slot,offset=index*2000_000_000_000)
 return root


def live_action_auth(root,action,inputs,prior,source):
    from src.orchestration.x6_r1_5_3_contract import ACTIONS,CAMPAIGN_ID,CONTRACT_PROPOSAL_SHA256,INVENTORY_SHA256
    from src.orchestration.x6_r1_5_1_contract import current_boot_id
    value={"schema_version":1,"record_kind":ACTIONS[action],"authorization_id":action.upper().replace("-","_")+"_SYNTHETIC",
           "campaign_id":CAMPAIGN_ID,"campaign_contract_sha256":CONTRACT_PROPOSAL_SHA256,"inventory_sha256":INVENTORY_SHA256,
           "action":action,"stage":"DEVELOPMENT" if action=="freeze-development" else "EVALUATION",
           "campaign_root":str(root),"canonical_output":str(root/("development-freeze-v1" if action=="freeze-development" else "final-analysis-v1")),
           "source":source,"input_inventory_sha256":digest(canonical(inputs)),"prior_state_sha256":digest(canonical(prior)),
           "issued_ns":0,"expires_ns":2**63-1,"boot_id":current_boot_id(),"source_test_only":True}
    value["authorization_sha256"]=digest(canonical(value));return value


def rejected_development(original,root):
    from src.orchestration.x6_r1_5_3_durable import append_event
    root.mkdir(exist_ok=True);copy_readiness(original,root)
    template=load(original/"slots"/accepted_inventory()["slots"][0]["run_id"]/"state/authorization.json")
    for slot in accepted_inventory()["slots"][:60]:
        auth={**template,"slot":slot,"run_id":slot["run_id"],"output_root":str(root/"slots"/slot["run_id"]),"authorization_id":slot["slot_id"]+"_SYNTHETIC","scope":"N0_CONTROL" if slot["assignment"]=="N0" else "F1_PACKET_LOSS_SINGLE_FAULT"}
        ep=root/"readiness/initial/epoch.json";auth["epoch"]={"path":str(ep),"sha256":digest(ep.read_bytes()),"epoch_id":load(ep)["epoch_id"]}
        auth.pop("authorization_sha256");auth["authorization_sha256"]=digest(canonical(auth))
        append_event(root,"slot",slot["slot_id"],"RESERVED_UNDECIDED",evidence={"authorization":auth,"authorization_sha256":auth["authorization_sha256"]})
        append_event(root,"slot",slot["slot_id"],"REJECTED_SPENT",evidence={"detail":"synthetic interrupted undecided reservation"})
        copy_launcher(original,root,accepted_inventory()["slots"][2],auth)
    return root


def observed_drift(root,expected_path):
    import copy
    from src.orchestration.x6_r1_5_3_contract import campaign_catalog
    expected=load(expected_path);source_root=Path(expected["readiness_root"]);observed_root=root/"readiness/drift"
    shutil.copytree(source_root,observed_root)
    for path in (observed_root/"raw/commands").glob("*.result.json"):
        value=load(path)
        if value["name"] in {"kernel","module_provenance"}:
            value["stdout"]=value["stdout"].replace("synthetic-kernel","synthetic-changed-kernel")
            value["stdout_sha256"]=digest(value["stdout"].encode());save(path,value)
    raw=records(observed_root,campaign_catalog());by_name={row["name"]:row for row in raw}
    value=copy.deepcopy(expected);value["readiness_root"]=str(observed_root)
    value["kernel_and_module"]={name:by_name[name]["stdout"] for name in value["kernel_and_module"]}
    value["readiness_observation_hashes"]=[digest(canonical(row)) for row in raw]
    value.pop("epoch_id");value["epoch_id"]=digest(canonical(value));path=observed_root/"epoch.json";save(path,value)
    return path


def rebind_synthetic_launcher_snapshot(root,slot,*,failure_prototype=None):
    """Rebind constructed unit-test snapshots only; never an execution receipt."""
    from src.orchestration.x6_r1_5_3_launcher import sealed,evidence_inventory
    run=Path(root)/"slots"/slot["run_id"]
    auth=load(run/"state/authorization.json")
    assert auth["source_test_only"] is True
    directory=Path(root)/"launcher-receipts"/slot["run_id"]
    start=load(directory/"started.json")
    assert start["synthetic"] is True and start.get("synthetic_fixture_prototype_sha256")
    terminal=load(directory/"terminal.json")
    if failure_prototype is not None:
        prototype=Path(failure_prototype)/"launcher-receipts"/accepted_inventory()["slots"][2]["run_id"]/"terminal.json"
        observed=load(prototype)
        assert observed["status"]["child_return_code"]==1
        terminal["status"]=observed["status"]
        terminal["synthetic_failure_prototype_sha256"]=digest(prototype.read_bytes())
    terminal["run_evidence"]=evidence_inventory(run)
    terminal.pop("receipt_sha256");save(directory/"terminal.json",sealed(terminal))
