"""Standalone ownership-safe slot recovery; never resumes collection."""
from __future__ import annotations
import os
from pathlib import Path

from src.orchestration.x6_r1_5_1_contract import canonical,digest,load,require
from src.orchestration.x6_r1_5_1_durable import Recorder,acquire_topology_lock,alive,process_identity,records,save
from src.orchestration.x6_r1_5_1_observations import catalog,reconstruct_cleanup_cycles,validate_owned_cleanup_state,host_state
from src.orchestration.x6_r1_5_1_contract import RELEASE as R1_5_1_RELEASE
from src.orchestration.x6_r1_5_1_production_path import cleanup,restore
from src.orchestration.x6_r1_5_2_contract import accepted_inventory
from src.orchestration.x6_r1_5_2_durable import append_event,lock_campaign,read_events

from src.orchestration.x6_r1_5_2_contract import campaign_catalog as catalog


def classify(campaign_root,slot_id):
    rows=read_events(campaign_root,"slot",slot_id); require(rows,"slot accounting absent")
    return {"slot_id":slot_id,"state":rows[-1]["state"],"resume_permitted":False,"authorization_reusable":False}


class ProductionRecovery:
    def __init__(self,root,slot,*,simulation=False): self.root=Path(root); self.slot=slot; self.simulation=simulation
    def execute(self):
        require((self.root/"state/authorization.json").is_file(),"recovery authorization absent")
        require((self.root/"state/source.json").is_file(),"recovery source absent")
        require((self.root/"state/host_before.json").is_file(),"ownership baseline absent")
        raw=records(self.root,catalog(),permit_incomplete=True)
        before=host_state([row for row in raw if row["phase"]=="host_before"])
        require(load(self.root/"state/host_before.json")==before,"recovery ownership baseline contradicts raw")
        deployment=load(self.root/"state/deployment.json") if (self.root/"state/deployment.json").exists() else None
        deployed=[row for row in raw if row["phase"]=="deployment_after"]
        if deployment is not None: require(deployment==host_state(deployed),"recovery deployment snapshot contradicts raw")
        require(not before["containers"] and not before["namespaces"],"preexisting lifecycle resources")
        validate_owned_cleanup_state(before,deployment,require_complete=False)
        if (self.root/"state/deployment_intent.json").exists():
            require(any(row["name"]=="deploy" for row in raw),"recovery deployment intent lacks bound command")
        topology=acquire_topology_lock(); recorder=Recorder(self.root,catalog(),simulation=self.simulation)
        first=len(records(self.root,catalog(),permit_incomplete=True))+1
        try:
            if self.slot["assignment"]=="F1" and (self.root/"state/mutation.json").exists(): restore(recorder)
            if (self.root/"state/deployment_intent.json").exists(): cleanup(recorder,before,require_complete=False)
            rows=records(self.root,catalog(),permit_incomplete=True); selected=[row for row in rows if row["order"]>=first]
            require(selected,"recovery produced no ownership observations")
            journal=load(self.root/"state/cleanup.json")
            from src.expansion.x6_r1_5_2_materialized_verifier import _cleanup_observations
            require(_cleanup_observations(self.root,rows,successful=False,required=True),"recovery final absence not independently established")
            return {"status":"RECOVERED_NO_RESUME","command_orders":[r["order"] for r in selected],"records_sha256":digest(canonical(selected)),"source_test_only":self.simulation}
        finally: os.close(topology)


def recover(campaign_root,slot_id,*,source,adapter=None,simulation=False):
    root=Path(campaign_root); inventory=accepted_inventory(); matches=[row for row in inventory["slots"] if row["slot_id"]==slot_id]
    require(len(matches)==1,"unknown recovery slot"); slot=matches[0]; run=root/"slots"/slot["run_id"]
    lock=lock_campaign(root)
    try:
        rows=read_events(root,"slot",slot_id); require(rows,"slot accounting absent")
        states=[row["state"] for row in rows]
        auth=rows[0]["evidence"].get("authorization")
        from src.orchestration.x6_r1_5_2_contract import authorization_digest,validate_slot_authorization
        require(auth and authorization_digest(auth)==rows[0]["evidence"].get("authorization_sha256") and auth["source"]==source,"recovery historical authorization/source")
        from src.expansion.x6_r1_5_2_materialized_verifier import _verify_source_snapshot
        _verify_source_snapshot(auth["source"])
        validate_slot_authorization(auth,campaign_root=root,slot=slot,source=auth["source"],now_ns=auth["issued_ns"],boot_id=auth["boot_id"])
        if "CONSUMED" not in states:
            require(rows[-1]["state"] in {"RESERVED_UNDECIDED","ADMITTED"},"partial reservation already classified")
            allowed=run/"state/authorization.json"
            if run.exists():
                require(all(path==allowed for path in run.rglob("*") if path.is_file()),"partial reservation contradictory artifacts")
                if allowed.exists(): require(load(allowed)==auth,"partial authorization contradiction")
            if "ADMITTED" in states:
                from src.expansion.x6_r1_5_2_materialized_verifier import _verify_event_authority
                _verify_event_authority(rows,run,slot,allow_partial=True)
                append_event(root,"slot",slot_id,"TERMINAL",evidence={"classification":"SLOT_FAILED_INTEGRITY","authorization_committed":True,"consumption_complete":False,"detail":"interrupted before consumption completion"})
            else:
                append_event(root,"slot",slot_id,"REJECTED_SPENT",evidence={"authorization_sha256":auth["authorization_sha256"],"detail":"interrupted reservation without positive commitment"})
            return {**classify(root,slot_id),"cleanup":"NOT_REQUIRED_NO_LIFECYCLE_AUTHORITY"}
        from src.expansion.x6_r1_5_2_materialized_verifier import _verify_event_authority
        _verify_event_authority(rows,run,slot)
        require(run.is_dir() and (run/"state/authorization.json").is_file() and load(run/"state/authorization.json")==auth,"consumed run-root/authorization contradiction")
        consumed=rows[states.index("CONSUMED")]["evidence"]; process=consumed.get("process")
        require(isinstance(process,dict) and process!=process_identity() and not alive(process),"original slot process is active or unbound")
        require(not (run/"state/recovery.json").exists(),"recovery already attempted")
        if rows[-1]["state"]=="CONSUMED":
            require(not (run/"raw/commands").exists(),"pre-entry consumption contains runtime evidence")
            terminal={"status":"SLOT_INTERRUPTED_RECOVERED","qualified":False,"scientific_acceptance":False,"lifecycle_entered":False}
            save(run/"terminal/terminal.json",terminal,exclusive=True)
            append_event(root,"slot",slot_id,"TERMINAL",evidence={"classification":terminal["status"]})
            return {**classify(root,slot_id),"cleanup":"NOT_REQUIRED_NO_LIFECYCLE_ENTRY"}
        require((run/"state/source.json").is_file() and load(run/"state/source.json")==source,"recovery source binding")
        if rows[-1]["state"]=="RUNNING":
            require(not (run/"terminal/terminal.json").exists(),"orphan terminal publication contradicts running recovery; preserve without commands")
        before_recovery=len(records(run,catalog(),permit_incomplete=True))
        try:
            result=(adapter or ProductionRecovery(run,slot,simulation=simulation)).execute()
        except BaseException as error:
            raw=records(run,catalog(),permit_incomplete=True)
            selected=raw[before_recovery:]
            failure={"status":"RECOVERY_UNRESOLVED_NO_RESUME","first_command_order":before_recovery+1,
                     "command_orders":[row["order"] for row in selected],"records_sha256":digest(canonical(selected)),
                     "source_test_only":simulation,"error_type":type(error).__name__,"detail":str(error)}
            save(run/"state/recovery-failed.json",failure,exclusive=True)
            if rows[-1]["state"]=="RUNNING":
                from src.orchestration.x6_r1_5_1_observations import failed_command_orders
                cleanup_failed=any(row["name"]=="cleanup" and failed_command_orders([row]) for row in selected)
                terminal={"status":"SLOT_CLEANUP_FAILED" if cleanup_failed else "SLOT_INTERRUPTED_UNRESOLVED", "qualified":False,"scientific_acceptance":False}
                if (run/"state/target-cohort.json").exists():terminal["target_cohort_sha256"]=digest((run/"state/target-cohort.json").read_bytes())
                save(run/"terminal/terminal.json",terminal,exclusive=True)
                append_event(root,"slot",slot_id,"TERMINAL",evidence={"classification":terminal["status"]})
            raise

        require(result["status"]=="RECOVERED_NO_RESUME","recovery did not establish clean state")
        save(run/"state/recovery.json",result,exclusive=True)
        if rows[-1]["state"]=="RUNNING":
            terminal={"status":"SLOT_INTERRUPTED_RECOVERED","qualified":False,"scientific_acceptance":False}
            terminal_path=run/"terminal/terminal.json"
            require(not terminal_path.exists(),"existing terminal contradicts running recovery")
            if (run/"state/target-cohort.json").exists(): terminal["target_cohort_sha256"]=digest((run/"state/target-cohort.json").read_bytes())
            save(terminal_path,terminal,exclusive=True)
            append_event(root,"slot",slot_id,"TERMINAL",evidence={"classification":terminal["status"]})
        else:
            require(rows[-1]["state"]=="TERMINAL","recovery state is not interrupted/final")
        return {**classify(root,slot_id),"cleanup":"OWNED_CLEANUP_COMPLETE"}
    finally: os.close(lock)


def recover_action(root,action,authorization_id):
    """Classify abandoned publication; never refit, analyze, publish, or resume."""
    from src.orchestration.x6_r1_5_2_contract import ACTIONS,ACTION_FINAL
    from src.orchestration.x6_r1_5_2_durable import verify_action_ledger,advance_action
    root=Path(root); lock=lock_campaign(root)
    try:
        row=verify_action_ledger(root,action,require_published=False,authorization_id=authorization_id)
        require(row["state"] not in ACTION_FINAL,"action already terminal; no recovery mutation permitted")
        process=row.get("process")
        require(isinstance(process,dict) and process!=process_identity() and not alive(process),"action process active or unbound")
        output=Path(row["authorization"]["canonical_output"])
        staging=root/("."+output.name+".staging."+authorization_id)
        inventory=[]
        for directory in (staging,output):
            if directory.exists():
                for path in sorted(directory.rglob("*")):
                    if path.is_file():inventory.append({"path":str(path),"sha256":digest(path.read_bytes())})
        state="REJECTED_SPENT" if row["state"]=="RESERVED_UNDECIDED" else "INTERRUPTED_SPENT"
        if row["state"]!="RESERVED_UNDECIDED" and (output.exists() or row["state"]=="ADMITTED" and staging.exists()):state="INTEGRITY_UNRESOLVED"
        ledger=root/"action-ledger"/ACTIONS[action]/(authorization_id+".reservation.json")
        classified=advance_action(ledger,row,state,recovery={"no_resume":True,"preserved_inventory":inventory,"original_state":row["state"],"unexpected_unadmitted_publication":row["state"]=="RESERVED_UNDECIDED" and (staging.exists() or output.exists())})
        return {"state":classified["state"],"authorization_reusable":False,"resume_permitted":False,"preserved_inventory":inventory}
    finally:os.close(lock)
