"""Independent campaign reconstruction; persisted summaries are comparison targets."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from src.expansion.x6_r1_5_3_analysis import metrics, paired_bootstrap, evaluation_status
from src.expansion.x6_r1_5_3_dataset import aggregate_target,reconstruct_effectiveness,historical_rule
from src.expansion.x6_r1_5_3_model import fit,hybrid_output,ml_output,probabilities
from src.orchestration.x6_r1_5_1_contract import accepted_manifest,canonical,digest,load,require
from src.orchestration.x6_r1_5_1_durable import records
from src.orchestration.x6_r1_5_1_observations import catalog,failed_command_orders,reconstruct_window
from src.orchestration.x6_r1_5_1_observations import reconstruct_cleanup_cycles
from src.orchestration.x6_r1_5_1_contract import RELEASE as R1_5_1_RELEASE
from src.collection.x6_performance_collector import validate_speed_pair
from src.orchestration.x6_r1_5_1_production_path import inclusive
from src.orchestration.x6_r1_5_3_contract import FEATURES,INVENTORY_SHA256,accepted_inventory,require_accepted_slot
from src.orchestration.x6_r1_5_3_durable import read_events,reject_not_run_artifacts,verify_action_ledger

from src.orchestration.x6_r1_5_3_contract import campaign_catalog as catalog



# A read-only verification pass reconstructs each raw stream once, then checks
# the entire evidence inventory again before returning. Nothing is reused across
# passes, processes, source versions, or evidence mutations.
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
_VERIFY_PASS = ContextVar("x6_r1_5_3_verification_pass", default=None)


def _evidence_fingerprint(root):
    return tuple((str(path.relative_to(root)),digest(path.read_bytes()),path.stat().st_mode & 0o777)
                 for path in sorted(Path(root).rglob("*")) if path.is_file() and not path.is_symlink())


@contextmanager
def verification_pass(root):
    from src.orchestration.x6_r1_5_3_reconstruction import reconstruction
    with reconstruction(root):
        with _verification_pass_once(root) as state:
            yield state


@contextmanager
def _verification_pass_once(root):
    root=Path(root).resolve(); current=_VERIFY_PASS.get()
    if current is not None:
        require(current["root"]==root,"cross-campaign verification cache")
        yield current; return
    state={"root":root,"fingerprint":_evidence_fingerprint(root),"raw":{},"slots":{},"cleanup":{},"events":{},"stages":{},"models":{},"source":None}
    token=_VERIFY_PASS.set(state)
    try:
        yield state
        require(state["fingerprint"]==_evidence_fingerprint(root),"evidence changed during independent verification")
        if state["source"] is not None:
            from src.orchestration.x6_r1_5_3_campaign import source_identity
            require(state["source"]==source_identity(),"source changed during independent verification")
    finally: _VERIFY_PASS.reset(token)


def _pass_boundary(root_argument):
    import functools
    def decorate(function):
        @functools.wraps(function)
        def checked(*args,**kwargs):
            root=root_argument(*args,**kwargs)
            with verification_pass(root): return function(*args,**kwargs)
        return checked
    return decorate


def _verify_source_snapshot(source):
    from src.orchestration.x6_r1_5_3_campaign import source_identity
    state=_VERIFY_PASS.get()
    observed=state["source"] if state is not None and state["source"] is not None else source_identity()
    require(source==observed,"historical source does not match executing implementation root/bytes/modes")
    if state is not None: state["source"]=observed


def _verify_admission_prerequisites(root,slot,events,auth,commitment):
    from src.orchestration.x6_r1_5_3_contract import validate_epoch,SLOT_FINAL
    binding=auth["epoch"]; path=Path(binding["path"])
    require(digest(path.read_bytes())==binding["sha256"],"historical epoch hash")
    epoch=validate_epoch(path,root)
    require(epoch["epoch_id"]==binding["epoch_id"] and epoch["source"]==auth["source"] and
            epoch["stage"]==slot["stage"] and epoch["boot_id"]==commitment["boot_id"],"historical epoch context")
    accepted=accepted_inventory()["slots"];position=accepted.index(slot);prior=[]
    for preceding in accepted[:position]:
        rows=read_events(root,"slot",preceding["slot_id"])
        require(rows and rows[-1]["state"] in SLOT_FINAL,"historical preceding slot state")
        if "CONSUMED" in [row["state"] for row in rows]:
            run=root/"slots"/preceding["run_id"]
            state=_VERIFY_PASS.get(); key=str(run.resolve())
            raw=[] if state is not None and key in state["cleanup"] else _raw_records(run,True)
            if state is None:
                clean=_verify_bound_operation(run,"cleanup",raw,required=True,successful=load(run/"terminal/terminal.json")["status"]=="SLOT_COMPLETE")
            else:
                if key not in state["cleanup"]: state["cleanup"][key]=_verify_bound_operation(run,"cleanup",raw,required=True,successful=load(run/"terminal/terminal.json")["status"]=="SLOT_COMPLETE")
                clean=state["cleanup"][key]
            require(clean,"historical prior cleanup")
        if rows[-1]["at"]["boot_id"]==commitment["boot_id"]:
            require(rows[-1]["at"]["monotonic_ns"]<=commitment["monotonic_ns"],"commitment predates prior slot closure")
        prior.append({"slot_id":preceding["slot_id"],"head":rows[-1]["event_sha256"]})
    if position and accepted[position-1]["stage"]==slot["stage"]:
        prior_auth=read_events(root,"slot",accepted[position-1]["slot_id"])[0]["evidence"].get("authorization")
        if prior_auth is not None:
            from src.orchestration.x6_r1_5_3_contract import epoch_context
            prior_epoch=validate_epoch(prior_auth["epoch"]["path"],root)
            left=epoch_context(prior_epoch);right=epoch_context(epoch)
            left.pop("boot_id");right.pop("boot_id")
            require(left==right,"historical non-boot drift continuation")
    if slot["position"]=="S02":
        first=read_events(root,"slot",accepted[position-1]["slot_id"])[0]["evidence"]["authorization"]
        require(first["epoch"]["epoch_id"]==binding["epoch_id"],"historical pair epoch")
    freeze=None
    if slot["stage"]=="EVALUATION":
        from src.orchestration.x6_r1_5_3_campaign import _stage_state
        bundle=root/"development-freeze-v1";verify_model(bundle,_stage_state(root,"DEVELOPMENT")["eligible_rows"])
        freeze=digest((bundle/"publication-manifest.json").read_bytes())
        require(freeze==auth["development_freeze_sha256"],"historical evaluation freeze")
    admitted=next(row for row in events if row["state"]=="ADMITTED")
    prerequisites=admitted["evidence"].get("prerequisites",{})
    admission=prerequisites.get("admission")
    require(isinstance(admission,dict) and set(admission)=={"path","sha256","epoch_id"},"fresh admission evidence absent")
    require(digest(Path(admission["path"]).read_bytes())==admission["sha256"],"fresh admission evidence hash")
    fresh=validate_epoch(admission["path"],root)
    from src.orchestration.x6_r1_5_3_contract import epoch_context
    require(fresh["epoch_id"]==admission["epoch_id"] and epoch_context(fresh)==epoch_context(epoch),"fresh admission context contradiction")
    fresh_raw=records(Path(fresh["readiness_root"]),catalog())
    require(max(row["completed"]["monotonic_ns"] for row in fresh_raw)<=commitment["monotonic_ns"],"positive commitment predates readiness completion")
    require(prerequisites=={"prior_heads":prior,"epoch_sha256":binding["sha256"],"development_freeze_sha256":freeze,"admission":admission},"historical admission prerequisites contradiction")
    return True

def _verify_event_authority(events,run,slot,*,allow_partial=False):
    states=[row["state"] for row in events]
    require(states[0]=="RESERVED_UNDECIDED","slot reservation absent")
    if "ADMITTED" not in states:
        require(states[-1]=="REJECTED_SPENT","unadmitted reservation is not rejected")
        return None
    admitted=events[states.index("ADMITTED")]; commitment=admitted["evidence"].get("commitment_observation")
    require(admitted["evidence"].get("decision")=="AUTHORIZED_SLOT_ENTRY","positive slot authorization decision absent")
    require(isinstance(commitment,dict) and type(commitment.get("monotonic_ns")) is int and commitment.get("boot_id"),"durable commitment observation")
    reserved=events[0]["evidence"]; auth=reserved.get("authorization")
    require(isinstance(auth,dict) and reserved.get("authorization_sha256")==auth.get("authorization_sha256"),"reservation authorization binding")
    _verify_source_snapshot(auth["source"])
    if (run/"state/authorization.json").exists(): require(load(run/"state/authorization.json")==auth,"run authorization contradiction")
    require(admitted["evidence"].get("authorization_sha256")==auth["authorization_sha256"],"admission authorization binding")
    from src.orchestration.x6_r1_5_3_contract import validate_slot_authorization
    validate_slot_authorization(auth,campaign_root=run.parent.parent,slot=slot,source=auth["source"],
                                now_ns=commitment["monotonic_ns"],boot_id=commitment["boot_id"])
    require(events[0]["at"]["boot_id"]==commitment["boot_id"] and
            commitment["monotonic_ns"]>=events[0]["at"]["monotonic_ns"],"commitment precedes reservation")
    _verify_admission_prerequisites(run.parent.parent,slot,events,auth,commitment)
    if allow_partial:
        require("CONSUMED" not in states,"partial authority unexpectedly consumed"); return auth
    require("CONSUMED" in states and states.index("CONSUMED")>states.index("ADMITTED"),"consumption absent or reordered")
    consumed=events[states.index("CONSUMED")]["evidence"]
    require(consumed.get("root")==str(run),"consumption run-root binding")
    process=consumed.get("process")
    require(isinstance(process,dict) and set(process)=={"pid","start_ticks","boot_id"} and
            type(process["pid"]) is int and process["pid"]>0 and str(process["start_ticks"]).isdigit() and process["boot_id"]==commitment["boot_id"],"consumption process identity")
    require(isinstance(consumed.get("process"),dict) and consumed.get("consumed",{}).get("boot_id")==commitment["boot_id"] and
            consumed["consumed"]["monotonic_ns"]>=commitment["monotonic_ns"],"consumption process/timing binding")
    return auth


def _window_inventory(run,raw,slot):
    rows=[]
    for path in sorted((run/"raw/windows").glob("*.json")) if (run/"raw/windows").exists() else []:
        row=load(path); require(path.stem==row["window_id"],"window identity"); rows.append(row)
    expected=[*(f"B{i:02d}" for i in range(1,11)),*(f"F{i:02d}" for i in range(1,4)),*(f"R{i:02d}" for i in range(1,4))]
    require([row["window_id"] for row in rows]==expected[:len(rows)],"window order/cardinality")
    begun=[wid for wid in expected if any(item.get("window")==wid for item in raw)]
    persisted={row["window_id"] for row in rows}
    require(set(begun[:-1])<=persisted,"later raw window proves missing required predecessor window")
    if raw and rows:
        speed_rows=[row for row in raw if row.get("phase")=="speed"]
        speed=validate_speed_pair(*speed_rows)
        for row in rows:
            selected=[item for item in raw if item.get("window")==row["window_id"]]
            require(selected and all(not item.get("incomplete") for item in selected),"window raw evidence incomplete")
            phase = "fault" if row["window_id"].startswith("F") and slot["assignment"]=="F1" else "restored" if row["window_id"].startswith("R") else "baseline"
            require(row["phase"]==phase,"window phase contradicts accepted slot assignment")
            reconstructed=reconstruct_window(selected,speed,phase=phase)
            expected_row={**reconstructed,"window_id":row["window_id"],"phase":row["phase"],"command_orders":[item["order"] for item in selected],"source_test_only":load(run/"state/authorization.json")["source_test_only"]}
            require(canonical(row)==canonical(expected_row),"window summary contradicts raw observations")
    return rows


def _raw_records(run,failed):
    if not (run/"raw/commands").exists(): return []
    state=_VERIFY_PASS.get(); key=(str(run.resolve()),failed)
    if state is None: return records(run,catalog(),permit_incomplete=failed)
    if key not in state["raw"]: state["raw"][key]=records(run,catalog(),permit_incomplete=failed)
    return deepcopy(state["raw"][key])



def _cleanup_observations(run,rows,*,successful,required):
    """Reconstruct complete cycles and retain incomplete failed cleanup attempts."""
    from src.orchestration.x6_r1_5_1_observations import host_state,validate_owned_cleanup_state,cleanup_cycle,HOST_NAMES
    relevant=[row for row in rows if row["phase"] in {"cleanup_before","cleanup","cleanup_after"}]
    if not relevant:
        require(not required,"required cleanup raw observations absent")
        require(not (run/"state/cleanup.json").exists(),"cleanup journal without observations")
        return False
    initial_rows=[row for row in rows if row["phase"]=="host_before"]
    initial=host_state(initial_rows)
    require(load(run/"state/host_before.json")==initial,"cleanup initial snapshot contradicts raw")
    deployment_path=run/"state/deployment.json";deployment=None
    if deployment_path.exists():
        deployment=host_state([row for row in rows if row["phase"]=="deployment_after"])
        require(load(deployment_path)==deployment,"cleanup deployment snapshot contradicts raw")
    cycles=[];offset=0;incomplete=[]
    while offset<len(relevant):
        before=relevant[offset:offset+5]
        if len(before)<5 or any(row.get("incomplete") for row in before):
            require(not successful and not (run/"state/cleanup.json").exists() and
                    [row["name"] for row in before]==HOST_NAMES[:len(before)] and
                    all(row["phase"]=="cleanup_before" for row in before) and offset+len(before)==len(relevant),
                    "contradictory incomplete cleanup group")
            return False
        require([row["name"] for row in before]==HOST_NAMES and all(row["phase"]=="cleanup_before" for row in before),"cleanup before group")
        require(all(right["order"]==left["order"]+1 for left,right in zip(before,before[1:])),"cleanup before ordering")
        state=validate_owned_cleanup_state(host_state(before),deployment,require_complete=successful and not cycles)
        offset+=5;action=None
        if offset<len(relevant) and relevant[offset]["phase"]=="cleanup":action=relevant[offset];offset+=1
        require((action is not None)==bool(state["containers"]),"cleanup action/ownership contradiction")
        after=relevant[offset:offset+5]
        if len(after)==5 and all(row["phase"]=="cleanup_after" for row in after) and (action is None or not failed_command_orders([action])):
            cycles.append(cleanup_cycle(before,action,after,initial=initial,deployment=deployment,
                require_complete=successful and not cycles,run_id=load(run/"state/authorization.json")["run_id"],output_root=str(run),index=len(cycles)+1))
            offset+=5
        else:
            require(not successful,"successful cleanup has incomplete/failed observations")
            # The earlier command error or interrupted observation remains in raw
            # evidence. It supplies no absence proof and is never a successful cycle.
            incomplete.extend(before+([action] if action else []))
            while offset<len(relevant) and relevant[offset]["phase"]=="cleanup_after":incomplete.append(relevant[offset]);offset+=1
    journal_path=run/"state/cleanup.json"
    if cycles:
        require(journal_path.exists(),"completed cleanup cycle lacks journal")
        expected={"release_id":R1_5_1_RELEASE,"run_id":load(run/"state/authorization.json")["run_id"],"output_root":str(run),"cycles":cycles}
        require(load(journal_path)==expected,"cleanup journal contradicts reconstructed cycles")
        # No later unfinished cycle can be called final clean state.
        clean=not incomplete or relevant[-1]["order"]==cycles[-1]["after_orders"][-1]
        if successful:require(clean and not incomplete,"successful cleanup retains incomplete attempts")
        return clean
    require(not journal_path.exists(),"cleanup journal fabricates completed cycle")
    return False

def _verify_bound_operation(run,name,rows,*,required,successful=False):
    path=run/"state"/(name+".json")
    if not path.exists():
        require(not required,"required "+name+" evidence absent"); return False
    value=load(path)
    require(value.get("source_test_only",load(run/"state/authorization.json")["source_test_only"]) is load(run/"state/authorization.json")["source_test_only"], name+" production/synthetic evidence mismatch")
    orders=value.get("command_orders")
    if name=="cleanup" and orders is None and isinstance(value.get("cycles"),list):
        orders=[]
        for cycle in value["cycles"]:
            orders.extend(cycle.get("before_orders",[]))
            if cycle.get("action_order") is not None: orders.append(cycle["action_order"])
            orders.extend(cycle.get("after_orders",[]))
    require(isinstance(orders,list) and orders,name+" raw binding absent")
    selected=[row for row in rows if row["order"] in orders]
    require([row["order"] for row in selected]==orders,name+" command ordering")
    if name=="cleanup":
        return _cleanup_observations(run,rows,successful=successful,required=required)
    if name in {"restoration-action","recovery"}:
        from src.orchestration.x6_r1_5_1_observations import controls, success
        from src.collection.x6_performance_collector import exact_noqueue
        import json
        probes=[row for row in selected if row["phase"]=="restoration_probe"]
        final=[row for row in selected if row["phase"] in {"restoration_controls","n0_restoration_controls"}]
        actions=[row for row in selected if row["name"]=="mutation_restore"]
        if probes:
            require(len(probes)==5 and [row["name"] for row in probes]==["r2_counter","r3_counter","qdisc","filters_root","filters_ingress"] and
                    all(b["order"]==a["order"]+1 for a,b in zip(probes,probes[1:])),"restoration probe cardinality/identity/order")
            for row in probes: success(row)
            absent=exact_noqueue(probes[2],probes[3:])
            if not absent:
                qdisc=json.loads(probes[2]["stdout"])
                require([json.loads(row["stdout"]) for row in probes[3:]]==[[],[]] and
                        len(qdisc) in {1,2} and qdisc[0].get("kind")=="netem" and qdisc[0].get("handle")=="10:" and
                        (len(qdisc)==1 or qdisc[1].get("kind")=="pfifo" and qdisc[1].get("handle")=="20:" and qdisc[1].get("parent")=="10:1"),"foreign restoration ownership")
            require(len(actions)==int(not absent),"restoration action/observed state contradiction")
            if actions: require(probes[-1]["order"]<actions[0]["order"]<final[0]["order"],"restoration action ordering")
        else:
            require(not actions,"restoration action lacks ownership probe")
        if name=="restoration-action" or probes:
            require(len(final)==5,"restoration final control cardinality")
            require(all(b["order"]==a["order"]+1 for a,b in zip(final,final[1:])),"restoration final control ordering")
            controls(final,phase="restored")
        if name=="recovery":
            require((run/"state/cleanup.json").is_file(),"recovery cleanup journal absent")
            require(_verify_bound_operation(run,"cleanup",rows,required=True,successful=False),"recovery journal does not establish final absence")
    if value.get("records_sha256") is not None:
        require(value["records_sha256"]==digest(canonical(selected)),name+" raw observation contradiction")
    require(all(not row.get("incomplete") and not row.get("timed_out") and not row.get("interrupted") for row in selected) and not failed_command_orders(selected),name+" command failure")
    return True


@_pass_boundary(lambda campaign_root,slot:campaign_root)
def verify_slot(campaign_root,slot):
    state=_VERIFY_PASS.get(); key=digest(canonical(slot))
    if key not in state["slots"]: state["slots"][key]=_verify_slot_once(campaign_root,slot)
    return deepcopy(state["slots"][key])


def _verify_slot_once(campaign_root,slot):
    require_accepted_slot(slot)
    root=Path(campaign_root); events=read_events(root,"slot",slot["slot_id"]); require(events,"slot events absent")
    state=events[-1]["state"]
    if state.startswith("NOT_RUN_"):
        reject_not_run_artifacts(root,slot,state)
        require(len(events)==1,"NOT_RUN slot has non-accounting history")
        evidence=events[0].get("evidence",{})
        require(evidence.get("reason")==state and evidence.get("authorization_id") and evidence.get("authorization_sha256") and evidence.get("supporting_evidence_sha256"),"NOT_RUN authority evidence")
        forbidden={"measurements","predictors","predictions","method_outputs"}
        require(not forbidden.intersection(evidence),"NOT_RUN fabricated observation/output")
        from src.orchestration.x6_r1_5_3_not_run import verify_not_run_action
        verify_not_run_action(root,evidence["authorization_id"])
        return {"slot_id":slot["slot_id"],"state":state,"prediction":None,"not_run_authorization_id":evidence["authorization_id"]}
    require(state in {"TERMINAL","REJECTED_SPENT"},"slot not final")
    from src.orchestration.x6_r1_5_3_launcher import verify_launcher
    verify_launcher(root,events[0]["evidence"]["authorization"])
    if state=="REJECTED_SPENT":
        from src.orchestration.x6_r1_5_3_contract import authorization_digest
        reserved=events[0]["evidence"]
        require(authorization_digest(reserved["authorization"])==reserved["authorization_sha256"],"rejected reservation authority integrity")
        auth=reserved["authorization"];_verify_source_snapshot(auth["source"])
        from src.orchestration.x6_r1_5_3_contract import validate_slot_authorization
        validate_slot_authorization(auth,campaign_root=root,slot=slot,source=auth["source"],now_ns=auth["issued_ns"],boot_id=auth["boot_id"])
        require(not (root/"slots"/slot["run_id"]).exists() or not any(path.is_file() and path.name!="authorization.json" for path in (root/"slots"/slot["run_id"]).rglob("*")),"rejected reservation fabricated observations")
        require([row["state"] for row in events]==["RESERVED_UNDECIDED","REJECTED_SPENT"],"rejected reservation transition")
        return {"slot_id":slot["slot_id"],"state":state,"prediction":None}
    run=root/"slots"/slot["run_id"]
    states=[row["state"] for row in events]
    if "ADMITTED" in states and "CONSUMED" not in states:
        _verify_event_authority(events,run,slot,allow_partial=True)
        require(events[-1]["evidence"].get("classification")=="SLOT_FAILED_INTEGRITY" and events[-1]["evidence"].get("authorization_committed") is True and events[-1]["evidence"].get("consumption_complete") is False,"admitted partial classification")
        if run.exists(): require(not any(p.is_file() for p in run.rglob("*") if p.name!="authorization.json"),"admitted partial fabricated evidence")
        return {"slot_id":slot["slot_id"],"state":state,"terminal":"SLOT_FAILED_INTEGRITY","prediction":None}
    require(run.is_dir(),"terminal slot root absent")
    _verify_event_authority(events,run,slot)
    terminal=load(run/"terminal/terminal.json"); require(events[-1]["evidence"].get("classification")==terminal["status"],"terminal/event contradiction")
    failed=terminal["status"]!="SLOT_COMPLETE"; raw=_raw_records(run,failed);
    require(raw or not (run/"state/deployment_intent.json").exists(),"deployment lacks bound raw evidence"); windows=_window_inventory(run,raw,slot)
    fault=[row for row in windows if row["window_id"].startswith("F")]
    if slot["assignment"]=="N0":
        require(not any(row.get("name","").startswith("mutation_") for row in raw),"N0 forbidden mutation command regardless of asserted phase")
    elif fault:
        mutations=[row for row in raw if row.get("name") in {"mutation_root","mutation_child"}]
        require([row["name"] for row in mutations]==["mutation_root","mutation_child"] and not failed_command_orders(mutations),"fault windows lack successful bound mutation commands")
        require(mutations[-1]["order"]<min(row["order"] for row in raw if row.get("window")=="F01"),"fault mutation ordering")
    reconstructed_row=None
    persisted_path=run/"parsed/campaign-row.json"
    if len(fault)<3:
        require(not persisted_path.exists(),"partial target has fabricated campaign row")
    else:
        replies_path=run/"parsed/target-replies.json"
        from src.collection.x6_r0_2_measurement_semantics import _REPLY
        require(raw, "completed target lacks bound raw command evidence")
        replies = [rtt for item in raw if item.get("window") in {"F01","F02","F03"}
                   and item["name"] == "traffic_ping" and not item.get("incomplete")
                   for _,rtt in _REPLY.findall(item["stdout"])]
        if replies_path.exists(): require(load(replies_path)=={"replies":replies},"target replies contradict raw ping evidence")
        reconstructed=aggregate_target([row["measurements"] for row in fault],replies)
        cohort_path=run/"state/target-cohort.json"
        publication_required = (not failed or persisted_path.exists() or terminal.get("target_cohort_sha256") is not None
                                or any(item.get("window","").startswith("R") for item in raw)
                                or any((run/"state"/name).exists() for name in ("historical-rule.json","restoration-action.json")))
        require(not publication_required or cohort_path.is_file(),"completed target cohort commitment absent")
        if cohort_path.exists():
            require(replies_path.is_file(),"committed target lacks required reply artifact")
            cohort=load(cohort_path)
            expected_cohort={"windows":[{"window_id":row["window_id"],"sha256":digest((run/"raw/windows"/(row["window_id"]+".json")).read_bytes())} for row in fault],
                             "target_replies_sha256":digest(replies_path.read_bytes()),"predictors":reconstructed}
            require(cohort==expected_cohort,"target cohort commitment contradiction")
            require(terminal.get("target_cohort_sha256")==digest(cohort_path.read_bytes()),"terminal target cohort binding contradiction")
        else:
            require(not terminal.get("target_cohort_sha256"),"absent target cohort falsely committed")
    if len(fault)==3 and persisted_path.exists():
        persisted=load(persisted_path); require(persisted["predictors"]==reconstructed,"persisted predictor contradiction")
        controls={"queue_drop_count":sum(int(row["measurements"]["queue_drop_count"]) for row in fault),"rate_limit_detected":any(row["measurements"]["rate_limit_detected"] for row in fault)}
        require(persisted["controls"]==controls,"persisted controls contradiction")
        require(persisted["ground_truth"]=={"assignment":slot["assignment"]} and persisted["slot_identity"]=={k:slot[k] for k in ("slot_id","block_id","stage","position")},"slot row identity")
        rule=historical_rule(reconstructed,controls,accepted_manifest())
        require(load(run/"state/historical-rule.json")==rule,"historical predicates contradict reconstructed inputs")
        require(persisted.get("predictions",{}).get("rule")==rule["output"] and (failed and "diagnosis" not in terminal or terminal.get("diagnosis")==rule["output"]),"rule/terminal contradiction")
        if raw: require(persisted["effectiveness"]==reconstruct_effectiveness(slot,fault,raw) and (failed and "effectiveness" not in terminal or terminal.get("effectiveness")==persisted["effectiveness"]),"effectiveness contradiction")
    elif len(fault)==3:
        require(failed,"complete successful target lacks campaign row")
    restored=len(windows)==16
    manifest=accepted_manifest()
    def accepted_windows(prefix):
        selected=[item for item in windows if item["window_id"].startswith(prefix)]
        try:
            for row in selected: inclusive(row,manifest)
        except ValueError:
            return False
        return len(selected)==(10 if prefix=="B" else 3)
    baseline_valid=accepted_windows("B"); restoration_valid=accepted_windows("R")
    require(not fault or baseline_valid,"target collection after baseline gate failure")
    if not failed: require(baseline_valid and restoration_valid,"successful slot numeric gate failure")
    _verify_bound_operation(run,"restoration-action",raw,required=not failed or restored)
    cleanup_verified=_cleanup_observations(run,raw,required=not failed or (run/"state/recovery.json").exists(),successful=not failed)
    if len(fault)==3:
        from src.expansion.x6_r1_5_3_dataset import build_row
        controls={"queue_drop_count":sum(int(row["measurements"]["queue_drop_count"]) for row in fault),"rate_limit_detected":any(row["measurements"]["rate_limit_detected"] for row in fault)}
        effect=reconstruct_effectiveness(slot,fault,raw)
        rule=historical_rule(reconstructed,controls,accepted_manifest())
        if (run/"state/historical-rule.json").exists():
            require(load(run/"state/historical-rule.json")==rule,"completed historical rule contradiction")
        eligible=controls=={"queue_drop_count":0,"rate_limit_detected":False}
        reconstructed_row={"schema_version":1,"slot_identity":{k:slot[k] for k in ("slot_id","block_id","stage","position")},
                           "predictors":reconstructed,"controls":controls,"effectiveness":effect,
                           "provenance":{"source_test_only":load(run/"state/authorization.json")["source_test_only"],"command_records":len(raw)},
                           "ground_truth":{"assignment":slot["assignment"]},"assignment":slot["assignment"],"block_id":slot["block_id"],
                           "target_verified":True,"entered_mutation":any(row["name"]=="mutation_root" for row in raw),
                           "clean_control":slot["assignment"]=="N0" and effect=="CLEAN_CONTROL",
                           "intervention_valid":effect in {"EFFECTIVE","CLEAN_CONTROL"},
                           "restoration_confirmed":restoration_valid and _verify_bound_operation(run,"restoration-action",raw,required=restoration_valid),
                           "lifecycle_verified":not failed and cleanup_verified,"eligible":eligible,
                           "predictions":{"rule":rule["output"]} if eligible else {}}
        if persisted_path.exists():
            proposed=deepcopy(reconstructed_row)
            if failed and restored and restoration_valid and cleanup_verified:
                proposed["lifecycle_verified"]=True  # proposal persisted before commit-last terminal; never promoted into accounting
            require(load(persisted_path)==proposed,"persisted outcome flags/provenance contradict reconstruction")
    if terminal["status"]=="SLOT_CLEANUP_FAILED":
        require(any(row["name"]=="cleanup" and failed_command_orders([row]) for row in raw),"cleanup-failure classification lacks raw failed action")
    if failed:
        recovery_failure=run/"state/recovery-failed.json"
        if recovery_failure.exists():
            failure=load(recovery_failure);first=failure.get("first_command_order")
            require(type(first) is int and 1<=first<=len(raw)+1,"recovery failure boundary")
            selected=[row for row in raw if row["order"]>=first]
            require(failure.get("status")=="RECOVERY_UNRESOLVED_NO_RESUME" and failure.get("command_orders")==[row["order"] for row in selected] and
                    failure.get("records_sha256")==digest(canonical(selected)) and failure.get("source_test_only") is load(run/"state/authorization.json")["source_test_only"],"recovery failure raw binding")
            require(not cleanup_verified,"unresolved recovery falsely asserts final clean state")
        recovery=run/"state/recovery.json"
        if recovery.exists(): _verify_bound_operation(run,"recovery",raw,required=True)
        result={"slot_id":slot["slot_id"],"state":state,"prediction":None,"terminal":terminal["status"],"completed_windows":[r["window_id"] for r in windows],"cleanup_verified":cleanup_verified,
                "outcomes":{"target_verified":False,"entered_mutation":any(row["name"]=="mutation_root" for row in raw),
                            "restoration_confirmed":restoration_valid and _verify_bound_operation(run,"restoration-action",raw,required=restoration_valid),
                            "lifecycle_verified":False,"eligible":False}}
        if len(fault)==3:
            result["reconstructed_predictors"]=reconstructed; result["accounting_row"]=reconstructed_row
        return result
    require(len(windows)==16 and persisted_path.exists(),"successful slot evidence incomplete")
    row=load(persisted_path); require(set(row["predictors"])==set(FEATURES),"predictor boundary")
    return {"slot_id":slot["slot_id"],"state":state,"row_sha256":digest(persisted_path.read_bytes()),"row":reconstructed_row,"accounting_row":reconstructed_row,"cleanup_verified":cleanup_verified}


def _verify_publication(bundle):
    bundle=Path(bundle); manifest=load(bundle/"publication-manifest.json"); inventory=[]
    require(len(manifest["inventory"])==len({item["path"] for item in manifest["inventory"]}),"duplicated publication path")
    for item in manifest["inventory"]:
        relative=Path(item["path"])
        require(not relative.is_absolute() and ".." not in relative.parts and relative.parts and relative.as_posix()==item["path"],"unsafe publication path")
        path=bundle/relative;require(not path.is_symlink() and path.resolve().is_relative_to(bundle.resolve()),"publication escapes bundle"); require(path.is_file() and digest(path.read_bytes())==item["sha256"],"publication file binding"); inventory.append(item)
    require(manifest["inventory_sha256"]==digest(canonical(sorted(inventory,key=lambda x:x["path"]))),"publication inventory")
    require({p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()}=={x["path"] for x in inventory}|{"publication-manifest.json"},"publication artifact inventory")
    return manifest


@_pass_boundary(lambda bundle,development_rows:Path(bundle).parent)
def verify_model(bundle,development_rows):
    pass_state=_VERIFY_PASS.get();key=str(Path(bundle).resolve())
    if pass_state is not None and key in pass_state["models"]:
        cached=pass_state["models"][key]
        require(cached["inventory"]==digest(canonical(development_rows)),"cached model input contradiction")
        return deepcopy(cached["model"])
    ledger=verify_action_ledger(Path(bundle).parent,"freeze-development")
    manifest=_verify_publication(bundle); require(ledger.get("publication_manifest_sha256")==digest(canonical(manifest)),"freeze ledger/publication contradiction")
    model=load(Path(bundle)/"model.json")
    inventory=digest(canonical(development_rows)); require(model["development_inventory_sha256"]==inventory,"development inventory")
    require(model["model_sha256"]==digest(canonical({k:v for k,v in model.items() if k not in {"model_sha256","development_probability_hex"}})),"model identity")
    require(fit(development_rows,inventory,model["source_identity"])==model,"independent model reconstruction")
    from src.orchestration.x6_r1_5_3_campaign import freeze_policies,_stage_state
    freeze=load(Path(bundle)/"development_freeze.json")
    state=_stage_state(Path(bundle).parent,"DEVELOPMENT")
    expected_state={**state,"evaluation_unaccessed":True,"canonical_output_absent":True}
    require(freeze=={"status":"IMMUTABLE_DEVELOPMENT_FREEZE","model_sha256":model["model_sha256"],"inventory_sha256":inventory,
                     "prior_state_sha256":digest(canonical(expected_state)),"policies":freeze_policies(ledger["authorization"]["source"]),"development_state":expected_state},"freeze policy/provenance contradiction")
    require(model["source_identity"]==ledger["authorization"]["source"],"freeze model/source authority contradiction")
    if pass_state is not None:pass_state["models"][key]={"inventory":inventory,"model":deepcopy(model)}
    return model


@_pass_boundary(lambda bundle,campaign_root,inventory,model:campaign_root)
def verify_analysis(bundle,campaign_root,inventory,model):
    from src.orchestration.x6_r1_5_3_campaign import _stage_state
    independently_verified=verify_model(Path(campaign_root)/"development-freeze-v1",_stage_state(campaign_root,"DEVELOPMENT")["eligible_rows"])
    require(model==independently_verified,"caller model contradicts independently reconstructed freeze")
    model=independently_verified
    ledger=verify_action_ledger(Path(bundle).parent,"evaluate")
    manifest=_verify_publication(bundle); require(ledger.get("publication_manifest_sha256")==digest(canonical(manifest)),"analysis ledger/publication contradiction")
    require(digest(canonical(inventory["schedule"]))==INVENTORY_SHA256,"accepted inventory hash")
    reconstructed=[]
    for slot in inventory["slots"]:
        if slot["stage"]!="EVALUATION": continue
        result=verify_slot(campaign_root,slot)
        from src.expansion.x6_r1_5_3_dataset import accounting_row
        reconstructed.append(accounting_row(slot,read_events(campaign_root,"slot",slot["slot_id"]),result))
    persisted=load(Path(bundle)/"evaluation-slots.json")["slots"]
    require(len(persisted)==40,"evaluation output inventory")
    expected=[]
    for row in reconstructed:
        value=dict(row)
        if value.get("predictors") and value.get("eligible") is True:
            p=probabilities(model,[[float(value["predictors"][name]) for name in model["feature_order"]]])[0]
            value.setdefault("predictions",{})["ml"]=ml_output(p); value["predictions"]["hybrid"]=hybrid_output(value["predictions"].get("rule","ABSTAIN"),p)
        else: require(not value.get("predictions"),"unmeasured slot has prediction")
        expected.append(value)
    require(canonical(persisted)==canonical(expected),"persisted predictions contradict reconstructed evidence/model")
    report=load(Path(bundle)/"analysis.json"); calculated={m:metrics(expected,m) for m in ("rule","ml","hybrid")}
    require(report["metrics"]==calculated,"reported metrics contradiction")
    require(report["bootstrap"]==paired_bootstrap(expected,["rule","ml","hybrid"]),"reported bootstrap contradiction")
    from src.expansion.x6_r1_5_3_analysis import outcome_accounting,progression
    require(report.get("outcome_accounting")==outcome_accounting(expected,["rule","ml","hybrid"]) and report.get("progression")==progression(expected,["rule","ml","hybrid"]),"class/reason/progression reporting contradiction")
    require(report.get("scientific_acceptance") is False and report.get("status")==evaluation_status(expected),"scientific claim/inconclusive outcome")
    return report


@_pass_boundary(lambda campaign_root,inventory:campaign_root)
def verify_campaign(campaign_root,inventory):
    accepted=accepted_inventory()
    require(digest(canonical(inventory["schedule"]))==INVENTORY_SHA256 and canonical(inventory)==canonical(accepted),"campaign inventory")
    accounting=Path(campaign_root)/"accounting/slot"
    if accounting.exists(): require({p.name for p in accounting.iterdir()}=={row["slot_id"] for row in inventory["slots"]},"extra or missing slot accounting")
    from src.orchestration.x6_r1_5_3_historical_accounting import accounting_slot
    results=[accounting_slot(campaign_root,slot) for slot in inventory["slots"]]
    authorization_ids=sorted({row["not_run_authorization_id"] for row in results if "not_run_authorization_id" in row})
    if authorization_ids:
        from src.orchestration.x6_r1_5_3_not_run import verify_not_run_action
        for authorization_id in authorization_ids: verify_not_run_action(campaign_root,authorization_id)
    return results


def verify_candidate_bundle(bundle,action,campaign_root,inputs,prior,source):
    """Reconstruct staged contents before publication; no fitting or analysis is published here."""
    import copy
    from src.orchestration.x6_r1_5_3_campaign import freeze_policies
    _verify_publication(bundle)
    bundle=Path(bundle)
    if action=="freeze-development":
        from src.orchestration.x6_r1_5_3_campaign import _freeze_prerequisites
        fresh=_freeze_prerequisites(campaign_root)
        require(fresh==prior and fresh["eligible_rows"]==inputs,"development inputs changed before publication")
    elif action=="evaluate":
        from src.orchestration.x6_r1_5_3_campaign import _evaluation_prerequisites
        fresh=_evaluation_prerequisites(campaign_root)
        require(fresh==prior and fresh["accounting_rows"]==inputs,"evaluation inputs changed before publication")
    else:
        from src.orchestration.x6_r1_5_3_not_run import derive_prerequisites
        ledger=verify_action_ledger(campaign_root,"record-not-run",require_published=False,authorization_id=load(bundle/"not-run.json")["authorization_id"])
        auth=ledger["authorization"];support={"epoch_path":auth["epoch"]["epoch_path"]}
        if prior["reason"]=="NOT_RUN_OPERATIONAL_FAILURE":
            support["blocking_slot_id"]=prior["supporting_evidence"]["blocking_slot_id"]
            if "pair_boot_change" in prior["supporting_evidence"]:support["observed_epoch_path"]=prior["supporting_evidence"]["pair_boot_change"]["observed_epoch_path"]
        elif prior["reason"]=="NOT_RUN_ENVIRONMENT_DRIFT":support={name:prior["supporting_evidence"][name] for name in ("expected_epoch_path","observed_epoch_path")}
        fresh=derive_prerequisites(campaign_root,auth["target_slot_ids"],prior["reason"],support,historical_authorization=auth)
        require(fresh==prior and fresh["target_slots"]==inputs,"NOT_RUN prerequisites changed before publication")
    if action=="freeze-development":
        require(load(bundle/"development-rows.json")=={"rows":inputs},"staged development inputs")
        model=fit(inputs,digest(canonical(inputs)),source)
        require(load(bundle/"model.json")==model,"staged model reconstruction")
        require(load(bundle/"development_freeze.json")=={"status":"IMMUTABLE_DEVELOPMENT_FREEZE","model_sha256":model["model_sha256"],
                "inventory_sha256":digest(canonical(inputs)),"prior_state_sha256":digest(canonical(prior)),
                "policies":freeze_policies(source),"development_state":prior},"staged freeze policies")
    elif action=="evaluate":
        from src.orchestration.x6_r1_5_3_campaign import _stage_state
        model=verify_model(Path(campaign_root)/"development-freeze-v1",_stage_state(campaign_root,"DEVELOPMENT")["eligible_rows"])
        expected=copy.deepcopy(inputs)
        for row in expected:
            if row.get("predictors") and row.get("eligible") is True:
                p=probabilities(model,[[float(row["predictors"][name]) for name in model["feature_order"]]])[0]
                row.setdefault("predictions",{})["ml"]=ml_output(p)
                row["predictions"]["hybrid"]=hybrid_output(row["predictions"].get("rule","ABSTAIN"),p)
        require(load(bundle/"evaluation-slots.json")=={"slots":expected},"staged predictions")
        from src.expansion.x6_r1_5_3_analysis import analysis_document
        require(load(bundle/"analysis.json")==analysis_document(expected),"staged analysis reconstruction")
        require(load(bundle/"analysis-input.json")=={"prior_state_sha256":digest(canonical(prior)),"model_sha256":model["model_sha256"]},"staged analysis bindings")
    else:
        require(action=="record-not-run","unknown publication action")
        row=load(bundle/"not-run.json")
        from src.orchestration.x6_r1_5_3_not_run import campaign_outcome
        require(row.get("campaign_outcome")==campaign_outcome(prior["reason"]),"staged inconclusive outcome contradiction")
        require(row["supporting_evidence"]==prior["supporting_evidence"] and row["prior_state_sha256"]==digest(canonical(prior)),"staged NOT_RUN prerequisites")
        for slot in inputs:
            events=read_events(campaign_root,"slot",slot["slot_id"])
            require(len(events)==1 and events[0]["state"]==prior["reason"],"staged NOT_RUN transition")
            reject_not_run_artifacts(campaign_root,slot,prior["reason"])
    return True
