"""One authorized N0 or F1 campaign-slot lifecycle."""
from __future__ import annotations

import os
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from src.expansion.x6_r1_5_2_dataset import aggregate_target, build_row, reconstruct_effectiveness
from src.orchestration.x6_r1_5_1_contract import PHASE_BY_WINDOW, accepted_manifest, canonical, digest, load, require
from src.orchestration.x6_r1_5_1_durable import Recorder, acquire_topology_lock, process_identity, records, save, stamp
from src.orchestration.x6_r1_5_1_observations import BOOTSTRAP_NAMES, bootstrap, catalog, controls, host_state
from src.orchestration.x6_r1_5_1_production_path import CONTROLS, HOST, capture_group, cleanup, inclusive, mutate, persist_manifest, phase_wait, preflight, restore, window
from src.collection.x6_performance_collector import validate_speed_pair
from src.collection.x6_r0_2_measurement_semantics import _REPLY
from src.orchestration.x6_r1_5_2_contract import validate_slot_authorization
from src.orchestration.x6_r1_5_2_durable import append_event, lock_campaign, reject_not_run_artifacts

from src.orchestration.x6_r1_5_2_contract import campaign_catalog as catalog


def slot_run_id(slot):
    return slot["slot_id"].lower().replace("_", "-")



def slot_prerequisites(campaign_root,slot,authorization,*,boot_id):
    """Canonical admission prerequisites, called only while campaign lock is held."""
    from src.orchestration.x6_r1_5_2_contract import accepted_inventory,validate_epoch,SLOT_FINAL
    from src.orchestration.x6_r1_5_2_durable import read_events
    from src.expansion.x6_r1_5_2_materialized_verifier import verify_slot,verify_model
    root=Path(campaign_root)
    binding=authorization["epoch"]; path=Path(binding["path"])
    require(path.is_file() and digest(path.read_bytes())==binding["sha256"],"slot epoch evidence hash")
    epoch=validate_epoch(path,root)
    require(epoch["epoch_id"]==binding["epoch_id"] and epoch["boot_id"]==boot_id and
            epoch["stage"]==slot["stage"] and epoch["source"]==authorization["source"],"slot epoch identity")
    slots=accepted_inventory()["slots"]; position=slots.index(slot); prior=[]
    for previous in slots[:position]:
        events=read_events(root,"slot",previous["slot_id"])
        require(events and events[-1]["state"] in SLOT_FINAL,"preceding slot not finalized")
        result=verify_slot(root,previous)
        if "CONSUMED" in [row["state"] for row in events]:
            require(result.get("cleanup_verified") is True,"preceding slot cleanup not independently verified")
        prior.append({"slot_id":previous["slot_id"],"head":events[-1]["event_sha256"]})
    if position and slots[position-1]["stage"]==slot["stage"]:
        prior_auth=read_events(root,"slot",slots[position-1]["slot_id"])[0]["evidence"].get("authorization")
        if prior_auth is not None:
            from src.orchestration.x6_r1_5_2_contract import epoch_context
            prior_epoch=validate_epoch(prior_auth["epoch"]["path"],root)
            left=epoch_context(prior_epoch);right=epoch_context(epoch)
            left.pop("boot_id");right.pop("boot_id")
            require(left==right,"non-boot environment drift prohibits stage continuation")
    if slot["position"]=="S02":
        first=slots[position-1]; auth=read_events(root,"slot",first["slot_id"])[0]["evidence"].get("authorization")
        require(auth and auth["epoch"]["epoch_id"]==binding["epoch_id"],"pair epoch mismatch")
    freeze=None
    if slot["stage"]=="EVALUATION":
        from src.orchestration.x6_r1_5_2_campaign import _stage_state
        bundle=root/"development-freeze-v1"
        verify_model(bundle,_stage_state(root,"DEVELOPMENT")["eligible_rows"])
        freeze=digest((bundle/"publication-manifest.json").read_bytes())
        require(freeze==authorization["development_freeze_sha256"],"evaluation freeze binding")
    return {"prior_heads":prior,"epoch_sha256":binding["sha256"],"development_freeze_sha256":freeze}

def run_slot(*, campaign_root, slot, authorization, source, now_ns, boot_id, collector, observe=stamp):
    """Run one slot through a collector implementing the real lifecycle boundary.

    Production uses CommandCollector; source tests use a controlled substitute
    with identical persistence and reconstruction interfaces.
    """
    campaign_root = Path(campaign_root)
    validate_slot_authorization(authorization, campaign_root=campaign_root, slot=slot, source=source, now_ns=now_ns, boot_id=boot_id)
    require(authorization["run_id"] == slot_run_id(slot), "slot run identity")
    root = campaign_root / "slots" / authorization["run_id"]
    lock = lock_campaign(campaign_root)
    try:
        prerequisites=slot_prerequisites(campaign_root,slot,authorization,boot_id=boot_id)
        append_event(campaign_root, "slot", slot["slot_id"], "RESERVED_UNDECIDED", evidence={"authorization_sha256": authorization["authorization_sha256"],"authorization":authorization})
        committed = None
        try:
            admission=collector.prepare_admission(campaign_root,slot,authorization,source)
            require(slot_prerequisites(campaign_root,slot,authorization,boot_id=boot_id)==prerequisites,"slot prerequisites changed before commitment")
            committed = observe()
            validate_slot_authorization(authorization, campaign_root=campaign_root, slot=slot, source=source,
                                        now_ns=committed["monotonic_ns"], boot_id=committed["boot_id"])
            require(not root.exists(), "slot root exists")

        except BaseException as error:
            append_event(campaign_root, "slot", slot["slot_id"], "REJECTED_SPENT",
                         evidence={"authorization_sha256": authorization["authorization_sha256"],
                                   "commitment_observation": committed, "error_type": type(error).__name__, "detail": str(error)})
            raise
        append_event(campaign_root, "slot", slot["slot_id"], "ADMITTED",
                     evidence={"decision":"AUTHORIZED_SLOT_ENTRY","authorization_sha256": authorization["authorization_sha256"], "commitment_observation": committed, "prerequisites":{**prerequisites,"admission":admission}})
        try:
            root.mkdir(parents=True); save(root / "state/authorization.json", authorization, exclusive=True)
            consumed = observe()
            append_event(campaign_root, "slot", slot["slot_id"], "CONSUMED", evidence={"root": str(root), "consumed": consumed, "process": process_identity()})
        except BaseException as error:
            append_event(campaign_root,"slot",slot["slot_id"],"TERMINAL",evidence={"classification":"SLOT_FAILED_INTEGRITY","authorization_committed":True,"consumption_complete":False,"error_type":type(error).__name__,"detail":str(error)})
            raise
        append_event(campaign_root, "slot", slot["slot_id"], "RUNNING", evidence={"root": str(root)})
        try:
            collector.begin(root, slot, source)
            baseline = []
            for i in range(1, 11):
                if i > 1: collector.separate(root, f"B{i:02d}")
                baseline.append(collector.window(root, f"B{i:02d}", "baseline"))
            collector.validate_baseline(baseline)
            if slot["assignment"] == "F1": collector.mutate(root)
            else: collector.assert_no_mutation(root)
            target = []
            for i in range(1, 4):
                if i > 1: collector.separate(root, f"F{i:02d}")
                target.append(collector.window(root, f"F{i:02d}", "fault" if slot["assignment"] == "F1" else "baseline"))
            replies = collector.target_replies(root, target)
            save(root / "parsed/target-replies.json", {"replies": replies}, exclusive=True)
            cohort={"windows":[{"window_id":row["window_id"],"sha256":digest((root/"raw/windows"/(row["window_id"]+".json")).read_bytes())} for row in target],
                    "target_replies_sha256":digest((root/"parsed/target-replies.json").read_bytes()),
                    "predictors":aggregate_target([row["measurements"] for row in target],replies)}
            save(root/"state/target-cohort.json",cohort,exclusive=True)
            effect = collector.effectiveness(root, slot, target)
            diagnosis = collector.historical_diagnosis(root, target)
            # Neither effect nor diagnosis controls restoration collection.
            collector.restore(root, slot)
            collector.cooldown(root)
            restored = []
            for i in range(1, 4):
                if i > 1: collector.separate(root, f"R{i:02d}")
                restored.append(collector.window(root, f"R{i:02d}", "restored"))
            collector.validate_restoration(restored)
            try: collector.cleanup(root)
            except BaseException:
                save(root/"state/cleanup-failed.json", {"status":"SLOT_CLEANUP_FAILED"},exclusive=True)
                raise
            predictors = aggregate_target([row["measurements"] for row in target], replies)
            row = build_row(slot=slot, predictors=predictors, controls=collector.common_controls(root, target), effectiveness=effect, provenance=collector.provenance(root))
            row["predictions"] = {"rule": diagnosis}
            save(root / "parsed/campaign-row.json", row, exclusive=True)
            terminal = {"status": "SLOT_COMPLETE", "assignment": slot["assignment"], "effectiveness": effect, "diagnosis": diagnosis, "windows": {"baseline":10,"target":3,"restored":3}, "qualified": False, "scientific_acceptance": False,
                        "target_cohort_sha256":digest((root/"state/target-cohort.json").read_bytes())}
            save(root / "terminal/terminal.json", terminal, exclusive=True)
            append_event(campaign_root, "slot", slot["slot_id"], "TERMINAL", evidence={"classification":"SLOT_COMPLETE", "terminal":str(root / "terminal/terminal.json")})
            return terminal
        except BaseException as error:
            # Preserve durable orphan terminal evidence after final-event failure.
            if (root/"terminal/terminal.json").exists():
                raise
            classification = "SLOT_CLEANUP_FAILED" if (root/"state/cleanup-failed.json").exists() else "SLOT_FAILED_OPERATIONAL"
            try: collector.recover(root, slot)
            except BaseException:
                if classification!="SLOT_CLEANUP_FAILED": classification = "SLOT_INTERRUPTED_UNRESOLVED"
            terminal={"status":classification,"error_type":type(error).__name__,"detail":str(error),"qualified":False,"scientific_acceptance":False}
            if (root/"state/target-cohort.json").exists(): terminal["target_cohort_sha256"]=digest((root/"state/target-cohort.json").read_bytes())
            save(root / "terminal/terminal.json",terminal,exclusive=True)
            append_event(campaign_root, "slot", slot["slot_id"], "TERMINAL", evidence={"classification":classification})
            raise

    finally:
        os.close(lock)


class CommandCollector:
    """Production collector reusing accepted bounded raw-command primitives."""
    def __init__(self, *, simulation=False): self.simulation=simulation; self.recorder = self.before = self.manifest = self.speed = self.lock = None
    def prepare_admission(self,campaign_root,slot,authorization,source):
        require(os.environ.get("X6_R1_5_2_RUNTIME_ENABLE")=="1","runtime campaign execution is not enabled")
        from src.orchestration.x6_r1_5_2_contract import observe_epoch,validate_epoch,epoch_context
        accepted=validate_epoch(authorization["epoch"]["path"],campaign_root)
        path,value=observe_epoch(campaign_root,slot["stage"],source,Path(campaign_root)/"readiness"/(slot["slot_id"]+"-admission"),simulation=self.simulation)
        require(epoch_context(value)==epoch_context(accepted),"admission environment differs from bound epoch")
        return {"path":str(path),"sha256":digest(path.read_bytes()),"epoch_id":value["epoch_id"]}
    def begin(self, root, slot, source):
        require(os.environ.get("X6_R1_5_2_RUNTIME_ENABLE") == "1", "runtime campaign execution is not enabled by source acceptance")
        self.lock = acquire_topology_lock()
        self.recorder = Recorder(root, catalog(), simulation=self.simulation)
        save(root / "state/source.json", source, exclusive=True); self.before = preflight(self.recorder, source); self.manifest,_ = persist_manifest(root)
        save(root / "state/deployment_intent.json", {"status":"PLANNED"}, exclusive=True)
        from src.orchestration.x6_r1_5_1_observations import success
        success(self.recorder.capture("deploy","deployment")); deployed=host_state(capture_group(self.recorder,HOST,"deployment_after")); require(len(deployed["containers"])==5,"incomplete topology"); save(root / "state/deployment.json",deployed,exclusive=True)
        for i in range(4): success(self.recorder.capture("container_tool_"+str(i),"container_provenance"))
        bootstrap(capture_group(self.recorder,BOOTSTRAP_NAMES,"bootstrap")); controls(capture_group(self.recorder,CONTROLS,"initial_controls"),phase="baseline")
        phase_wait(root,"readiness",5); phase_wait(root,"warmup",5)
        self.speed=validate_speed_pair(*capture_group(self.recorder,("r2_speed","r3_speed","r2_ethtool","r3_ethtool"),"speed"))
    def window(self,root,window_id,phase):
        old=PHASE_BY_WINDOW[window_id]; PHASE_BY_WINDOW[window_id]=phase
        try: return window(self.recorder,window_id,self.speed)
        finally: PHASE_BY_WINDOW[window_id]=old
    def validate_baseline(self,rows):
        for row in rows: inclusive(row,self.manifest)
    def separate(self,root,window_id): phase_wait(root,"separation-"+window_id,5)
    def mutate(self,root): mutate(self.recorder)
    def assert_no_mutation(self,root): controls(capture_group(self.recorder,CONTROLS,"n0_target_controls"),phase="baseline")
    def effectiveness(self,root,slot,rows):
        return reconstruct_effectiveness(slot,rows,records(root,catalog()))
    def historical_diagnosis(self,root,rows):
        from src.expansion.x6_r1_5_2_dataset import historical_rule
        replies=self.target_replies(root,rows)
        values=aggregate_target([row["measurements"] for row in rows],replies)
        result=historical_rule(values,self.common_controls(root,rows),self.manifest)
        save(root / "state/historical-rule.json",result,exclusive=True)
        return result["output"]
    def restore(self,root,slot):
        first=len(records(root,catalog()))+1
        if slot["assignment"]=="F1": restore(self.recorder)
        else: controls(capture_group(self.recorder,CONTROLS,"n0_restoration_controls"),phase="baseline")
        selected=[row for row in records(root,catalog()) if row["order"]>=first]
        save(root/"state/restoration-action.json",{"assignment":slot["assignment"],"status":"CONFIRMED","command_orders":[r["order"] for r in selected],"records_sha256":digest(canonical(selected)),"source_test_only":self.simulation},exclusive=True)
    def cooldown(self,root): phase_wait(root,"cooldown",5)
    def validate_restoration(self,rows):
        for row in rows: inclusive(row,self.manifest)
    def cleanup(self,root):
        cleanup(self.recorder,self.before,require_complete=True)
        if self.lock is not None: os.close(self.lock); self.lock=None
    def recover(self,root,slot):
        first=len(records(root,catalog(),permit_incomplete=True))+1 if self.recorder is not None else 1
        try:
            if self.before is None and (Path(root)/"state/host_before.json").exists(): self.before=load(Path(root)/"state/host_before.json")
            require(self.recorder is not None and self.before is not None,"recovery ownership observations unavailable")
            if slot["assignment"]=="F1" and (Path(root)/"state/mutation.json").exists(): restore(self.recorder)
            cleanup(self.recorder,self.before,require_complete=False)
            selected=[row for row in records(root,catalog(),permit_incomplete=True) if row["order"]>=first]
            save(root/"state/recovery.json",{"status":"RECOVERED_NO_RESUME","command_orders":[r["order"] for r in selected],"records_sha256":digest(canonical(selected)),"source_test_only":self.simulation},exclusive=True)
        finally:
            if self.lock is not None: os.close(self.lock); self.lock=None
    def target_replies(self,root,rows):
        return [rtt for row in records(root,catalog()) if row.get("window") in {"F01","F02","F03"} and row["name"]=="traffic_ping" for _,rtt in _REPLY.findall(row["stdout"])]
    def common_controls(self,root,rows): return {"queue_drop_count":sum(int(row["measurements"]["queue_drop_count"]) for row in rows),"rate_limit_detected":any(row["measurements"]["rate_limit_detected"] for row in rows)}
    def provenance(self,root): return {"source_test_only":self.simulation,"command_records":len(records(root,catalog()))}
