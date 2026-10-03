from __future__ import annotations

import copy, json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from tests.fixtures.x6_r1_5_2_synthetic import rebind_synthetic_launcher_snapshot,raw_pair,campaign_copy,copy_readiness,copy_slot,copy_epoch,live_action_auth,rejected_development,observed_drift
from tests.unit.test_x6_r1_5_2_production_integration import isolated
from src.orchestration.x6_r1_5_2_slot import CommandCollector
from src.orchestration.x6_r1_5_2_contract import observe_epoch,campaign_catalog
from src.orchestration.x6_r1_5_1_durable import stamp


from src.expansion.x6_r1_5_2_analysis import metrics, paired_bootstrap, evaluation_status
from src.expansion.x6_r1_5_2_dataset import aggregate_target, build_row, model_matrix
from src.expansion.x6_r1_5_2_model import fit, hybrid_output, ml_output, probabilities
from src.expansion.x6_r1_5_2_materialized_verifier import verify_analysis, verify_campaign, verify_model, verify_slot
from src.orchestration.x6_r1_5_1_contract import canonical, current_boot_id, digest, load
from src.orchestration.x6_r1_5_2_contract import CONTRACT_PROPOSAL_SHA256, INVENTORY_SHA256, accepted_inventory, validate_action_authorization, validate_slot_authorization, validate_transition, runtime_bindings
from src.orchestration.x6_r1_5_2_durable import append_event, advance_action, publish_bundle, read_events, reject_not_run_artifacts, reserve_action
from src.orchestration.x6_r1_5_2_not_run import derive_prerequisites, verify_not_run_action
from src.orchestration.x6_r1_5_2_slot import run_slot, slot_run_id
from src.orchestration.x6_r1_5_2_recovery import recover
from src.orchestration.x6_r1_5_1_durable import save
from src.orchestration import x6_r1_5_2_campaign as campaign
from src.orchestration import x6_r1_5_2_slot as slot_module

SOURCE={"git_commit":"c"*40,"git_tree":"d"*40}
POINT=lambda: {"monotonic_ns":100,"utc":"2026-09-28T00:00:00Z","boot_id":"boot"}

def signed(value):
    value=dict(value); value["authorization_sha256"]=digest(canonical(value)); return value

def slot(stage="DEVELOPMENT",block="DEV_B01",position="S01",assignment="N0"):
    sid=f"X6_F1_EXP_V1_{'DEV' if stage=='DEVELOPMENT' else 'EVAL'}_B{block[-2:]}_{position}_{assignment}"
    return {"slot_id":sid,"block_id":block,"stage":stage,"position":position,"assignment":assignment,"run_id":sid.lower().replace("_","-")}

def slot_auth(root,row,boot="boot",now=100):
    return signed({"schema_version":1,"record_kind":"X6_R1_5_2_CAMPAIGN_SLOT_AUTHORIZATION_V1","authorization_id":row["slot_id"]+"_A01","campaign_id":"X6_F1_EXPLORATORY_BINARY_V1","campaign_contract_sha256":CONTRACT_PROPOSAL_SHA256,"inventory_sha256":INVENTORY_SHA256,"slot":row,"run_id":row["run_id"],"output_root":str(root/"slots"/row["run_id"]),"source":SOURCE,"issued_ns":0,"expires_ns":200,"boot_id":boot,"scope":"N0_CONTROL" if row["assignment"]=="N0" else "F1_PACKET_LOSS_SINGLE_FAULT","artifact_inventory":["raw","parsed","state","terminal"],"source_test_only":False,"runtime_image":runtime_bindings()["image"],"runtime_bindings":runtime_bindings(),"epoch":{"path":str(root/"epoch.json"),"sha256":"a"*64,"epoch_id":"b"*64},"development_freeze_sha256":None})

def action_auth(root,action,inputs,prior,boot="boot"):
    kind="X6_R1_5_2_DEVELOPMENT_FREEZE_MODEL_FIT_AUTHORIZATION_V1" if action=="freeze-development" else "X6_R1_5_2_FINAL_EVALUATION_ANALYSIS_AUTHORIZATION_V1"
    output=root/("development-freeze-v1" if action=="freeze-development" else "final-analysis-v1")
    return signed({"schema_version":1,"record_kind":kind,"authorization_id":action.upper().replace("-","_")+"_A01","campaign_id":"X6_F1_EXPLORATORY_BINARY_V1","campaign_contract_sha256":CONTRACT_PROPOSAL_SHA256,"inventory_sha256":INVENTORY_SHA256,"action":action,"stage":"DEVELOPMENT" if action=="freeze-development" else "EVALUATION","campaign_root":str(root),"canonical_output":str(output),"source":SOURCE,"input_inventory_sha256":digest(canonical(inputs)),"prior_state_sha256":digest(canonical(prior)),"issued_ns":0,"expires_ns":200,"boot_id":boot,"source_test_only":True})

def not_run_auth(root,request,prior,*,expires=200,suffix="A01",boot="boot"):
    authorization_id="NOT_RUN_"+request["reason"]+"_"+suffix
    slots=prior["target_slots"]
    return signed({"schema_version":1,"record_kind":"X6_R1_5_2_NOT_RUN_ACCOUNTING_AUTHORIZATION_V1","authorization_id":authorization_id,"campaign_id":"X6_F1_EXPLORATORY_BINARY_V1","campaign_contract_sha256":CONTRACT_PROPOSAL_SHA256,"inventory_sha256":INVENTORY_SHA256,"action":"record-not-run","stage":"ACCOUNTING","campaign_root":str(root),"canonical_output":str(root/"accounting-actions/not-run"/authorization_id),"source":SOURCE,"input_inventory_sha256":digest(canonical(slots)),"prior_state_sha256":digest(canonical(prior)),"issued_ns":0,"expires_ns":expires,"boot_id":boot,"source_test_only":True,"target_slot_ids":request["target_slot_ids"],"expected_accounting_heads":prior["expected_accounting_heads"],"epoch":prior["epoch"],"reason":request["reason"],"supporting_evidence_sha256":digest(canonical(prior["supporting_evidence"]))})

@pytest.fixture
def observation():
    return {"window":{"measurements":{"packet_loss_ratio":"0.100000","round_trip_latency_ms_p95":"1.000000","throughput_mbps":"90.000000","interface_utilization_ratio":"0.700000","queue_drop_count":0,"rate_limit_detected":False}},"target_replies":["1.000000"]*30,"controls":{"queue_drop_count":0,"rate_limit_detected":False},"diagnosis":"ABSTAIN","fixture_sha256":"e"*64}

def test_exact_aggregation_and_half_even():
    windows=[{"packet_loss_ratio":x,"round_trip_latency_ms_p95":"9.0","throughput_mbps":t,"interface_utilization_ratio":u} for x,t,u in [("0.100000","1.000000","0.600000"),("0.200000","3.000000","0.700000"),("0.300001","2.000000","0.800000")]]
    value=aggregate_target(windows,[str(x) for x in range(1,21)])
    assert value=={"packet_loss_ratio":"0.200000","round_trip_latency_ms_p95":"19.000000","throughput_mbps":"2.000000","interface_utilization_ratio":"0.700000"}

@pytest.mark.parametrize("bad",["NaN","Infinity","-Infinity"])
def test_nonfinite_rejected(bad):
    windows=[{"packet_loss_ratio":bad,"round_trip_latency_ms_p95":"1","throughput_mbps":"2","interface_utilization_ratio":".5"}]*3
    with pytest.raises(Exception): aggregate_target(windows,["1"])

def test_slot_authorization_wrong_path_slot_and_replay(tmp_path):
    row=slot(); auth=slot_auth(tmp_path,row)
    validate_slot_authorization(auth,campaign_root=tmp_path,slot=row,source=SOURCE,now_ns=100,boot_id="boot")
    for mutation in (lambda x:x.update(output_root=str(tmp_path/"other")),lambda x:x.update(slot=slot(block="DEV_B02"))):
        bad=copy.deepcopy(auth); mutation(bad)
        with pytest.raises(Exception): validate_slot_authorization(bad,campaign_root=tmp_path,slot=row,source=SOURCE,now_ns=100,boot_id="boot")

def test_expiry_after_reservation_is_spent_without_lifecycle_entry(tmp_path,raw_fixture,monkeypatch):
    root=tmp_path/"fresh";row,auth=fresh(root,raw_fixture,monkeypatch)
    auth["expires_ns"]=10**15;auth.pop("authorization_sha256");auth["authorization_sha256"]=digest(canonical(auth))
    expired=lambda:{**stamp(),"monotonic_ns":auth["expires_ns"]+1}
    with pytest.raises(ValueError,match="validity"):
        run_slot(campaign_root=root,slot=row,authorization=auth,source=auth["source"],now_ns=0,boot_id=auth["boot_id"],collector=CommandCollector(simulation=True),observe=expired)
    assert [e["state"] for e in read_events(root,"slot",row["slot_id"])]==["RESERVED_UNDECIDED","REJECTED_SPENT"]
    assert not Path(auth["output_root"]).exists()


def test_admitted_consumption_persistence_failure_is_classified_spent(tmp_path):
    from tests.unit.test_x6_r1_5_2_production_integration import isolated,worker
    from src.orchestration.x6_r1_5_2_launcher import verify_launcher
    root=tmp_path/"fresh";env=isolated(root)
    assert worker(root,env,"epoch").returncode==0
    assert worker(root,env,"prepare",0).returncode==0
    row=accepted_inventory()["slots"][0]
    auth=load(root/(row["slot_id"]+"-authorization.json"))
    result=worker(root,env,"run-authorization-crash",0)
    assert result.returncode==1
    status=verify_launcher(root,auth)
    assert status["child_return_code"]==1 and "synthetic fsync boundary" in status["stderr"]
    assert [e["state"] for e in read_events(root,"slot",row["slot_id"])]==["RESERVED_UNDECIDED","ADMITTED","TERMINAL"]
    assert verify_slot(root,row)["terminal"]=="SLOT_FAILED_INTEGRITY"


def test_action_rejects_state_change_at_commit_and_remains_spent(tmp_path):
    stable_inputs=[{"x":1}]; stable_prior={"closed":True}; auth=action_auth(tmp_path,"freeze-development",stable_inputs,stable_prior)
    source=campaign.source_identity();auth["source"]=source;auth.pop("authorization_sha256");auth["authorization_sha256"]=digest(canonical(auth))
    calls=0
    def derive():
        nonlocal calls; calls+=1
        return (stable_prior,stable_inputs) if calls<3 else ({"closed":False},stable_inputs)
    with pytest.raises(Exception):
        campaign._action(tmp_path,"freeze-development",auth,stable_inputs,stable_prior,derive,lambda *_:None,observe=POINT,source=source,boot_id="boot")
    ledgers=list((tmp_path/"action-ledger").rglob("*.json")); assert len(ledgers)==1
    assert json.loads(ledgers[0].read_text())["state"]=="REJECTED_SPENT"

def test_n0_and_f1_lifecycle_collection_independent_of_abstention(raw_fixture):
    for row in accepted_inventory()["slots"][:2]:
        result=verify_slot(raw_fixture,row)
        assert result["row"]["target_verified"] and result["cleanup_verified"]
        run=raw_fixture/"slots"/row["run_id"]
        assert len(list((run/"raw/windows").glob("*.json")))==16
        if row["assignment"]=="F1":assert load(run/"terminal/terminal.json")["diagnosis"]=="ABSTAIN"


def test_consumed_slot_cannot_replay(tmp_path,raw_fixture):
    root=raw_copy(tmp_path,raw_fixture);row=accepted_inventory()["slots"][0];auth=load(root/"slots"/row["run_id"]/"state/authorization.json")
    with pytest.raises(ValueError):run_slot(campaign_root=root,slot=row,authorization=auth,source=auth["source"],now_ns=100,boot_id=auth["boot_id"],collector=CommandCollector(simulation=True))


def test_independent_slot_reconstruction_rejects_tampering(tmp_path,raw_fixture):
    root=raw_copy(tmp_path,raw_fixture);row=accepted_inventory()["slots"][0]
    assert verify_slot(root,row)["state"]=="TERMINAL"
    path=root/"slots"/row["run_id"]/"parsed/campaign-row.json";value=load(path);value["predictors"]["throughput_mbps"]="1.000000";save(path,value)
    rebind_synthetic_launcher_snapshot(root,row)
    with pytest.raises(ValueError,match="predictor"):verify_slot(root,row)


def test_verifier_reconstructs_complete_fault_evidence_on_failed_terminal(tmp_path,raw_fixture):
    root=raw_copy(tmp_path,raw_fixture,count=1);row=accepted_inventory()["slots"][0];run=terminal_failure(root,row,raw_fixture=raw_fixture)
    result=verify_slot(root,row);assert result["terminal"]=="SLOT_FAILED_OPERATIONAL" and result["accounting_row"]["target_verified"]
    path=run/"parsed/target-replies.json";save(path,{"replies":["99.0"]})
    rebind_synthetic_launcher_snapshot(root,row)
    with pytest.raises(ValueError,match="raw ping"):verify_slot(root,row)


def test_failed_partial_path_rejects_fabricated_completed_artifacts(tmp_path,raw_fixture):
    root=raw_copy(tmp_path,raw_fixture,count=1);row=accepted_inventory()["slots"][0];run=terminal_failure(root,row,raw_fixture=raw_fixture)
    path=run/"parsed/campaign-row.json";save(path,{"fabricated":True},exclusive=True)
    with pytest.raises((ValueError,KeyError)):verify_slot(root,row)


def test_verifier_rejects_restoration_and_cleanup_assertion_tampering(tmp_path,raw_fixture):
    root=raw_copy(tmp_path,raw_fixture,count=1);row=accepted_inventory()["slots"][0];run=root/"slots"/row["run_id"]
    path=run/"state/cleanup.json";value=load(path);value["cycles"][0]["owned_before"]=[];save(path,value)
    with pytest.raises(ValueError):verify_slot(root,row)


def test_not_run_forbids_fabricated_artifacts(tmp_path):
    row=slot(); append_event(tmp_path,"slot",row["slot_id"],"NOT_RUN_OPERATIONAL_FAILURE",evidence={"reason":"blocked"}); reject_not_run_artifacts(tmp_path,row,"NOT_RUN_OPERATIONAL_FAILURE")
    (tmp_path/"slots"/row["run_id"]).mkdir(parents=True)
    with pytest.raises(Exception): reject_not_run_artifacts(tmp_path,row,"NOT_RUN_OPERATIONAL_FAILURE")

def test_transition_table_rejects_skips_reverse_and_terminal():
    for pair in [("SCHEDULED","RUNNING"),("RUNNING","ADMITTED"),("TERMINAL","RUNNING")]:
        with pytest.raises(Exception): validate_transition(*pair)

def test_event_chain_rejects_contradiction(tmp_path):
    row=slot(); append_event(tmp_path,"slot",row["slot_id"],"RESERVED_UNDECIDED"); path=tmp_path/"accounting/slot"/row["slot_id"]/"000001.json"; value=json.loads(path.read_text()); value["state"]="RUNNING"; path.write_text(json.dumps(value))
    with pytest.raises(Exception): read_events(tmp_path,"slot",row["slot_id"])

def test_action_authorization_binding_and_reservation(tmp_path):
    inputs=[{"x":1}]; prior={"closed":True}; auth=action_auth(tmp_path,"freeze-development",inputs,prior)
    validate_action_authorization(auth,action="freeze-development",campaign_root=tmp_path,source=SOURCE,input_inventory_sha256=digest(canonical(inputs)),prior_state_sha256=digest(canonical(prior)),now_ns=100,boot_id="boot")
    reserve_action(tmp_path,auth,action="freeze-development")
    with pytest.raises(Exception): reserve_action(tmp_path,auth,action="freeze-development")

def test_commit_last_bundle_and_partial_publication(tmp_path):
    output=tmp_path/"final"
    def validate(staging):assert load(staging/"a.json")=={"a":1}
    publish_bundle(tmp_path/"stage",output,{"a.json":{"a":1}},validate=validate)
    assert (output/"publication-manifest.json").exists()
    with pytest.raises(ValueError):publish_bundle(tmp_path/"other",output,{"b.json":{"b":2}},validate=validate)


def rows_for_model():
    rows=[]
    for i in range(24):
        for assignment,base in (("N0",0.01),("F1",0.10)):
            row=slot(block=f"DEV_B{(i%30)+1:02d}",assignment=assignment); predictors={"packet_loss_ratio":f"{base+i/10000:.6f}","round_trip_latency_ms_p95":f"{1+i/100:.6f}","throughput_mbps":f"{95-base*10-i/100:.6f}","interface_utilization_ratio":f"{.7+i/10000:.6f}"}
            rows.append(build_row(slot=row,predictors=predictors,controls={"queue_drop_count":0,"rate_limit_detected":False},effectiveness="EFFECTIVE",provenance={}))
    return rows

def test_development_only_model_freeze_and_roundtrip():
    rows=rows_for_model(); model=fit(rows,digest(canonical(rows)),SOURCE); matrix,_=model_matrix(rows); p=probabilities(model,matrix)
    assert len(p)==48 and all(0<=x<=1 for x in p) and ml_output(.5)=="F1_PRESENT"

def test_synthetic_non_slot_authorizations_are_consumed_and_published(tmp_path,raw_fixture,monkeypatch):
    root=tmp_path/"complete";env=isolated(root)
    campaign_copy(raw_fixture,root,count=60)
    for key,value in env.items():monkeypatch.setenv(key,value)
    _set_clock_after(root,monkeypatch)
    source=load(root/"readiness/initial/epoch.json")["source"]
    prior=campaign._freeze_prerequisites(root);rows=prior["eligible_rows"]
    auth=live_action_auth(root,"freeze-development",rows,prior,source)
    from src.orchestration.x6_r1_5_2_source_test import SyntheticContext
    authorization=tmp_path/"freeze-authorization.json";request=tmp_path/"freeze-request.json"
    save(authorization,auth);save(request,{"rows":rows,"prior_state":prior})
    assert campaign.main(["freeze-development","--campaign-root",str(root),"--authorization",str(authorization),"--input",str(request)],_synthetic_context=SyntheticContext())==0
    model=verify_model(root/"development-freeze-v1",rows)
    freeze_sha=digest((root/"development-freeze-v1/publication-manifest.json").read_bytes())
    ep,_=copy_epoch(raw_fixture/"readiness/initial/epoch.json",root,root/"readiness/evaluation",stage="EVALUATION")
    for index,slot in enumerate(accepted_inventory()["slots"][60:],60):copy_slot(raw_fixture,root,slot,offset=index*2000_000_000_000,epoch_path=ep,freeze_sha=freeze_sha)
    _set_clock_after(root,monkeypatch)
    prior=campaign._evaluation_prerequisites(root);slots=prior["accounting_rows"]
    auth=live_action_auth(root,"evaluate",slots,prior,source)
    authorization=tmp_path/"evaluation-authorization.json";request=tmp_path/"evaluation-request.json"
    save(authorization,auth);save(request,{"slots":slots,"prior_state":prior})
    assert campaign.main(["evaluate","--campaign-root",str(root),"--authorization",str(authorization),"--input",str(request)],_synthetic_context=SyntheticContext())==0
    verify_analysis(root/"final-analysis-v1",root,accepted_inventory(),model)
    path=root/"final-analysis-v1/evaluation-slots.json";value=load(path);value["slots"][0]["predictions"]["ml"]="ABSTAIN";save(path,value)
    with pytest.raises(ValueError):verify_analysis(root/"final-analysis-v1",root,accepted_inventory(),model)
    with pytest.raises(ValueError):campaign.evaluate(root,auth,slots,prior,source=source)


def test_predictor_leakage_rejected():
    rows=rows_for_model(); rows[0]["predictors"]["assignment"]="F1"
    with pytest.raises(Exception): model_matrix(rows)

@pytest.mark.parametrize("p,expected",[(.8,"F1_PRESENT"),(.2,"F1_ABSENT"),(.5,"ABSTAIN")])
def test_hybrid_boundaries(p,expected): assert hybrid_output("ABSTAIN",p)==expected

def evaluation_slots():
    result=[]
    for i in range(20):
        for assignment in ("N0","F1"):
            result.append({"block_id":f"EVAL_B{i+1:02d}","assignment":assignment,"predictions":{"rule":"F1_ABSENT" if assignment=="N0" else "F1_PRESENT","ml":"F1_ABSENT" if assignment=="N0" else "F1_PRESENT","hybrid":"F1_ABSENT" if assignment=="N0" else "F1_PRESENT"},"effectiveness":"EFFECTIVE" if assignment=="F1" else "CLEAN_CONTROL","clean_control":assignment=="N0","target_verified":True,"entered_mutation":assignment=="F1","restoration_confirmed":True,"intervention_valid":True,"lifecycle_verified":True})
    return result

def test_metrics_full_denominator_and_paired_bootstrap():
    slots=evaluation_slots(); assert metrics(slots,"ml")["assignment_accuracy"]==1
    result=paired_bootstrap(slots,["rule","ml","hybrid"],replicates=10000); assert result["replicates"]==10000

def test_operational_missing_has_no_prediction():
    slots=evaluation_slots(); slots[0]["predictions"].pop("ml"); slots[0]["accounting_status"]="NO_PREDICTION_OPERATIONAL"
    value=metrics(slots,"ml"); assert value["assignment_accuracy"]==39/40 and value["unavailable_rate"]==1/40

def test_external_stub_is_bounded_and_shell_false():
    path=Path("tests/fixtures/x6_r1_5_2_external_stub.py")
    proc=subprocess.run([str(path),"ok","arg with spaces"],shell=False,text=True,capture_output=True,check=True,timeout=5)
    assert json.loads(proc.stdout)["source_test_only"] is True

def test_source_identity_uses_bounded_wrapper_and_preserves_output(monkeypatch,tmp_path):
    calls=[];original=campaign.run_capture
    def bounded(command,*,timeout_seconds,cwd):
        calls.append((command,timeout_seconds,cwd));return original(command,timeout_seconds=timeout_seconds,cwd=cwd)
    monkeypatch.setattr(campaign,"run_capture",bounded)
    monkeypatch.setenv("X6_R1_5_2_SOURCE_COMMIT","f"*40);monkeypatch.chdir(tmp_path)
    source=campaign.source_identity()
    assert source["git_commit"]!="f"*40 and source["executable_inventory_sha256"]==digest(canonical(source["executable_inventory"]))
    assert calls and all(timeout==30 and cwd==Path(__file__).resolve().parents[2] for _,timeout,cwd in calls)


def test_campaign_inventory_hash_is_recomputed(tmp_path):
    inventory=accepted_inventory(); altered=copy.deepcopy(inventory); altered["schedule"]["blocks"][0]["within_block_order"].reverse()
    with pytest.raises(Exception): verify_campaign(tmp_path,altered)

def test_standalone_recovery_never_resumes_and_terminalizes_owned_cleanup(tmp_path):
    from tests.unit.test_x6_r1_5_2_production_integration import isolated,worker
    root=tmp_path/"synthetic-recovery";env=isolated(root)
    assert worker(root,env,"epoch").returncode==0
    assert worker(root,env,"prepare",0).returncode==0
    state=json.loads((root/"stub-state.json").read_text());state["interrupt_after_deploy"]=True
    save(root/"stub-state.json",state)
    interrupted=worker(root,env,"run",0);assert interrupted.returncode==247
    from src.orchestration.x6_r1_5_2_launcher import verify_launcher
    row=accepted_inventory()["slots"][0]
    auth=load(root/(row["slot_id"]+"-authorization.json"))
    assert verify_launcher(root,auth)["child_return_code"]==-9
    calls_before=list(json.loads((root/"stub-state.json").read_text())["calls"])
    result=worker(root,env,"recover",0);assert result.returncode==0,result.stderr
    verified=worker(root,env,"verify",0);assert verified.returncode==0,verified.stderr
    after=json.loads((root/"stub-state.json").read_text())["calls"][len(calls_before):]
    assert not any("-c" in call or "ping" in call for call in after)
    row=accepted_inventory()["slots"][0];run=root/"slots"/row["run_id"]
    assert load(run/"terminal/terminal.json")["status"]=="SLOT_INTERRUPTED_RECOVERED"
    assert not list((run/"raw/windows").glob("*.json"))
    assert worker(root,env,"run",0).returncode!=0

@pytest.mark.parametrize("return_code",[1,124])
def test_source_identity_preserves_failure_and_timeout(monkeypatch,tmp_path,return_code):
    def bounded(command,*,timeout_seconds,cwd):
        return subprocess.CompletedProcess(command,return_code,"","git failed" if return_code==1 else "Command timed out after 30 seconds.")
    monkeypatch.delenv("X6_R1_5_2_SOURCE_COMMIT",raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(campaign,"run_capture",bounded)
    with pytest.raises(subprocess.CalledProcessError) as error:
        campaign.source_identity()
    assert error.value.returncode==return_code

def epoch(root,boot,path):
    value={"schema_version":1,"campaign_id":"X6_F1_EXPLORATORY_BINARY_V1","campaign_root":str(root.resolve()),"epoch_id":"epoch-01","boot_id":boot,"source":SOURCE,"topology":"bound","image":"bound"}
    save(path,value,exclusive=True); return value

def request_and_prior(root,targets,reason,supporting):
    request={"target_slot_ids":[row["slot_id"] for row in targets],"reason":reason,"supporting_evidence":supporting}
    return request,derive_prerequisites(root,request["target_slot_ids"],reason,supporting)

def test_not_run_environment_drift_cli_path_and_independent_verifier(tmp_path,raw_fixture):
    root,request,prior,source=drift_setup(tmp_path,raw_fixture);auth=live_not_run(root,request,prior,source)
    campaign.record_not_run(root,auth,request,source=source)
    assert verify_not_run_action(root,auth["authorization_id"])["reason"]=="NOT_RUN_ENVIRONMENT_DRIFT"
    assert verify_slot(root,accepted_inventory()["slots"][0])["prediction"] is None
    with pytest.raises(ValueError):campaign.record_not_run(root,auth,request,source=source)


def test_not_run_production_command_and_concurrent_calls(tmp_path,raw_fixture):
    root,request,prior,source=drift_setup(tmp_path,raw_fixture)
    auth1=live_not_run(root,request,prior,source,suffix="A01");auth2=live_not_run(root,request,prior,source,suffix="A02")
    def execute(auth):
        try:campaign.record_not_run(root,auth,request,source=source);return "published"
        except (ValueError,BlockingIOError):return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(execute,[auth1,auth2]))
    assert sorted(outcomes)==["published","rejected"]
    for slot in accepted_inventory()["slots"][:60]:assert len(read_events(root,"slot",slot["slot_id"]))==1
    published=auth1 if Path(auth1["canonical_output"]).exists() else auth2
    verify_not_run_action(root,published["authorization_id"])


def _capture_not_run(root,auth,request):
    try:
        campaign.record_not_run(root,auth,request,observe=POINT,source=SOURCE,boot_id="boot")
        return "published"
    except Exception:
        return "rejected"

def test_not_run_expiry_at_commit_is_spent_without_slot_events(tmp_path,raw_fixture):
    root,request,prior,source=drift_setup(tmp_path,raw_fixture);auth=live_not_run(root,request,prior,source,expires=1000)
    points=iter(({"monotonic_ns":100,"boot_id":current_boot_id(),"utc":"2026-10-01T00:00:00Z"},{"monotonic_ns":1001,"boot_id":current_boot_id(),"utc":"2026-10-01T00:00:01Z"}))
    with pytest.raises(ValueError,match="validity"):campaign.record_not_run(root,auth,request,source=source,observe=lambda:next(points))
    assert not any((root/"accounting/slot").glob("*/*.json"))
    ledger=next((root/"action-ledger").glob("*/*.json"));assert load(ledger)["state"]=="REJECTED_SPENT"


def test_not_run_commit_last_crash_is_spent_and_partial_not_fabricated(tmp_path,raw_fixture):
    root,request,prior,source=drift_setup(tmp_path,raw_fixture);auth=live_not_run(root,request,prior,source)
    with pytest.raises(RuntimeError):campaign.record_not_run(root,auth,request,source=source,fail_after=1)
    assert not Path(auth["canonical_output"]).exists()
    assert len(list((root/"accounting/slot").glob("*/*.json")))==1
    with pytest.raises(ValueError):verify_not_run_action(root,auth["authorization_id"])
    with pytest.raises(ValueError):campaign.record_not_run(root,auth,request,source=source)


def test_not_run_rejects_started_slot_and_forged_epoch_evidence(tmp_path,raw_fixture):
    root,request,prior,source=drift_setup(tmp_path,raw_fixture);slot_id=request["target_slot_ids"][0]
    (root/"accounting/slot"/slot_id).mkdir(parents=True)
    with pytest.raises(ValueError,match="directory"):derive_prerequisites(root,request["target_slot_ids"],request["reason"],request["supporting_evidence"])
    # An empty target directory is not equivalent to a never-started target.
    (root/"accounting/slot"/slot_id).rmdir()
    path=Path(request["supporting_evidence"]["observed_epoch_path"]);save(path,{"schema_version":1,"campaign_id":"forged"})
    with pytest.raises(ValueError):derive_prerequisites(root,request["target_slot_ids"],request["reason"],request["supporting_evidence"])


def test_not_run_development_inconclusive_and_unusable_model_reasons(tmp_path,raw_fixture,monkeypatch):
    root=rejected_development(raw_fixture,tmp_path/"insufficient")
    targets=accepted_inventory()["slots"][60:];supporting={"epoch_path":str(root/"readiness/initial/epoch.json")}
    request,prior=request_and_prior(root,targets,"NOT_RUN_DEVELOPMENT_INCONCLUSIVE",supporting)
    source=load(root/"readiness/initial/epoch.json")["source"];auth=live_not_run(root,request,prior,source)
    campaign.record_not_run(root,auth,request,source=source);verify_not_run_action(root,auth["authorization_id"])
    other=campaign_copy(raw_fixture,tmp_path/"unusable",count=60);_set_clock_after(other,monkeypatch)
    prior=campaign._freeze_prerequisites(other);rows=prior["eligible_rows"];assert len(rows)==60
    auth=live_action_auth(other,"freeze-development",rows,prior,source)
    from src.orchestration.x6_r1_5_2_durable import commit_action_authorization
    def prepare(_):return lambda point:validate_action_authorization(auth,action="freeze-development",campaign_root=other,source=source,input_inventory_sha256=digest(canonical(rows)),prior_state_sha256=digest(canonical(prior)),now_ns=point["monotonic_ns"],boot_id=point["boot_id"])
    ledger,value,lock=commit_action_authorization(other,auth,action="freeze-development",validate_at_commit=prepare)
    try:advance_action(ledger,value,"FAILED_SPENT",error_type="OSError",detail="synthetic interrupted model-freeze publication")
    finally:os.close(lock)
    request,prior=request_and_prior(other,targets,"NOT_RUN_UNUSABLE_MODEL",{"epoch_path":str(other/"readiness/initial/epoch.json")})
    auth=live_not_run(other,request,prior,source);campaign.record_not_run(other,auth,request,source=source);verify_not_run_action(other,auth["authorization_id"])


def test_not_run_operational_cleanup_failure_blocks_only_unstarted_pair_member(tmp_path,monkeypatch):
    from tests.unit.test_x6_r1_5_2_production_integration import isolated,worker
    root=tmp_path/"synthetic-cleanup-failure";env=isolated(root)
    assert worker(root,env,"epoch").returncode==0
    assert worker(root,env,"prepare",0).returncode==0
    state=json.loads((root/"stub-state.json").read_text());state["fail_cleanup"]=True
    (root/"stub-state.json").write_text(json.dumps(state))
    attempt=worker(root,env,"run",0);assert attempt.returncode!=0
    checked=worker(root,env,"verify",0);assert checked.returncode==0,checked.stderr
    blocker,target=accepted_inventory()["slots"][:2]
    assert load(root/"slots"/blocker["run_id"]/"terminal/terminal.json")["status"]=="SLOT_CLEANUP_FAILED"
    request,prior=request_and_prior(root,[target],"NOT_RUN_OPERATIONAL_FAILURE",{"epoch_path":str(root/"readiness/initial/epoch.json"),"blocking_slot_id":blocker["slot_id"]})
    source=load(root/"readiness/initial/epoch.json")["source"];auth=live_not_run(root,request,prior,source)
    _set_clock_after(root,monkeypatch)
    campaign.record_not_run(root,auth,request,source=source);verify_not_run_action(root,auth["authorization_id"])
    assert not (root/"slots"/target["run_id"]).exists()


@pytest.fixture(scope="module")
def raw_fixture(tmp_path_factory):
    return raw_pair(tmp_path_factory.mktemp("raw-command-fixtures")/"synthetic-campaign")

def raw_copy(tmp_path,raw_fixture,count=2):
    return campaign_copy(raw_fixture,tmp_path/"campaign",count=count)

def fresh(root,raw_fixture,monkeypatch):
    env=isolated(root)
    for key,value in env.items(): monkeypatch.setenv(key,value)
    copy_readiness(raw_fixture,root)
    row=accepted_inventory()["slots"][0]
    auth=load(raw_fixture/"slots"/row["run_id"]/"state/authorization.json")
    auth["output_root"]=str(root/"slots"/row["run_id"])
    ep=root/"readiness/initial/epoch.json";auth["epoch"]={"path":str(ep),"sha256":digest(ep.read_bytes()),"epoch_id":load(ep)["epoch_id"]}
    auth.pop("authorization_sha256");auth["authorization_sha256"]=digest(canonical(auth))
    return row,auth

def terminal_failure(root,row,status="SLOT_FAILED_OPERATIONAL",*,raw_fixture):
    run=root/"slots"/row["run_id"];path=run/"terminal/terminal.json";value=load(path);value["status"]=status;save(path,value)
    ep=sorted((root/"accounting/slot"/row["slot_id"]).glob("*.json"))[-1];event=load(ep);event["evidence"]["classification"]=status
    event.pop("event_sha256");event["event_sha256"]=digest(canonical(event));save(ep,event)
    (run/"parsed/campaign-row.json").unlink()
    rebind_synthetic_launcher_snapshot(root,row,failure_prototype=raw_fixture)
    return run


def live_not_run(root,request,prior,source,*,suffix="SYNTHETIC",expires=2**63-1):
    auth=not_run_auth(root,request,prior,expires=expires,suffix=suffix,boot=current_boot_id())
    auth["source"]=source;auth.pop("authorization_sha256");auth["authorization_sha256"]=digest(canonical(auth));return auth

def drift_setup(tmp_path,raw_fixture):
    root=tmp_path/"drift";root.mkdir();expected,_=copy_readiness(raw_fixture,root)
    observed=observed_drift(root,expected)
    targets=accepted_inventory()["slots"][:60]
    request,prior=request_and_prior(root,targets,"NOT_RUN_ENVIRONMENT_DRIFT",{"expected_epoch_path":str(expected),"observed_epoch_path":str(observed)})
    return root,request,prior,load(expected)["source"]

def _set_clock_after(root,monkeypatch):
    from src.orchestration import x6_r1_5_1_durable as clock
    monkeypatch.setenv("X6_R1_5_1_CONTROLLED_CLOCK","1")
    times=[load(path)["at"]["monotonic_ns"] for path in (root/"accounting/slot").glob("*/*.json")]
    clock._CLOCK_NS=max(times,default=0)+1000_000_000


def test_read_only_verification_pass_rejects_midpass_evidence_mutation(tmp_path):
    from src.expansion.x6_r1_5_2_materialized_verifier import verification_pass
    path=tmp_path/"evidence.json";save(path,{"source_test_only":True,"value":1})
    with pytest.raises(ValueError,match="changed during"):
        with verification_pass(tmp_path):save(path,{"source_test_only":True,"value":2})


def test_fresh_readiness_only_is_not_environment_drift(tmp_path,raw_fixture):
    root=tmp_path/"same-context";root.mkdir()
    ep,_=copy_epoch(raw_fixture/"readiness/initial/epoch.json",root,root/"readiness/expected")
    observed,_=copy_epoch(ep,root,root/"readiness/fresh",offset=1000)
    targets=accepted_inventory()["slots"][:60]
    with pytest.raises(ValueError,match="environment drift absent"):
        request_and_prior(root,targets,"NOT_RUN_ENVIRONMENT_DRIFT",{"expected_epoch_path":str(ep),"observed_epoch_path":str(observed)})


@pytest.mark.parametrize("boundary",["RESERVED_UNDECIDED","ADMITTED"])
def test_durable_slot_boundary_abruption_is_spent_and_reconstructable(tmp_path,boundary):
    from tests.unit.test_x6_r1_5_2_production_integration import isolated,worker
    from src.orchestration.x6_r1_5_2_launcher import verify_launcher
    root=tmp_path/"synthetic-boundary";env=isolated(root)
    assert worker(root,env,"epoch").returncode==0
    assert worker(root,env,"prepare",0).returncode==0
    row=accepted_inventory()["slots"][0];auth=load(root/(row["slot_id"]+"-authorization.json"))
    mode="run-reservation-crash" if boundary=="RESERVED_UNDECIDED" else "run-admission-crash"
    assert worker(root,env,mode,0).returncode==1
    assert verify_launcher(root,auth)["child_return_code"]==1
    result=worker(root,env,"recover",0);assert result.returncode==0,result.stderr
    checked=verify_slot(root,row)
    assert checked["state"]==("REJECTED_SPENT" if boundary=="RESERVED_UNDECIDED" else "TERMINAL")
    assert not (root/"slots"/row["run_id"]/"raw").exists()
    assert worker(root,env,"run",0).returncode!=0


def test_operational_failure_retains_observed_diagnosis_but_not_primary_success():
    rows=evaluation_slots();rows[0]["lifecycle_verified"]=False
    result=metrics(rows,"ml")
    assert rows[0]["predictions"]["ml"]=="F1_ABSENT"
    assert result["assignment_accuracy"]==39/40 and result["end_to_end_success"]==39/40
    assert result["secondary_clean_control_specificity"]==1
    assert evaluation_status(rows)=="INCONCLUSIVE_INCOMPLETE_EVALUATION"
    # Missing eligibility is not proof of common-gate passing rows.
    for row in rows: row["eligible"]=True
    assert evaluation_status(rows)=="EXPLORATORY_COMPLETE"


@pytest.mark.parametrize("field",["runtime_bindings","source"])
def test_observed_drift_cannot_invent_topology_or_source_bindings(tmp_path,raw_fixture,field):
    from src.orchestration.x6_r1_5_2_contract import validate_epoch
    root=tmp_path/"drift-forgery";root.mkdir();expected,_=copy_readiness(raw_fixture,root)
    path=observed_drift(root,expected);value=load(path)
    if field=="runtime_bindings":value[field]["topology"]["sha256"]="f"*64
    else:value[field]["executable_inventory_sha256"]="f"*64
    value.pop("epoch_id");value["epoch_id"]=digest(canonical(value));save(path,value)
    with pytest.raises(ValueError):validate_epoch(path,root,allow_observed_drift=True)



def test_internally_rebound_target_artifacts_cannot_replace_raw_ping(tmp_path,raw_fixture):
    from src.expansion.x6_r1_5_2_dataset import aggregate_target,historical_rule
    from src.orchestration.x6_r1_5_1_contract import accepted_manifest
    root=raw_copy(tmp_path,raw_fixture);slot=accepted_inventory()["slots"][1];run=root/"slots"/slot["run_id"]
    reply_path=run/"parsed/target-replies.json";reply=load(reply_path);reply["replies"]=["123.000000"]*len(reply["replies"]);save(reply_path,reply)
    cohort_path=run/"state/target-cohort.json";cohort=load(cohort_path)
    windows=[load(run/"raw/windows"/(f"F{i:02d}.json"))["measurements"] for i in range(1,4)]
    cohort["target_replies_sha256"]=digest(reply_path.read_bytes());cohort["predictors"]=aggregate_target(windows,reply["replies"]);save(cohort_path,cohort)
    row_path=run/"parsed/campaign-row.json";row=load(row_path);row["predictors"]=cohort["predictors"]
    rule=historical_rule(row["predictors"],row["controls"],accepted_manifest());row["predictions"]["rule"]=rule["output"];save(row_path,row);save(run/"state/historical-rule.json",rule)
    terminal_path=run/"terminal/terminal.json";terminal=load(terminal_path);terminal["target_cohort_sha256"]=digest(cohort_path.read_bytes());terminal["diagnosis"]=rule["output"];save(terminal_path,terminal)
    rebind_synthetic_launcher_snapshot(root,slot)
    with pytest.raises(ValueError,match="raw ping"):verify_slot(root,slot)


@pytest.mark.parametrize("change",["decision","commitment_boot","consumption_time"])
def test_rehashed_authorization_event_contradictions_rejected(tmp_path,raw_fixture,change):
    root=raw_copy(tmp_path,raw_fixture,count=1);slot=accepted_inventory()["slots"][0]
    paths=sorted((root/"accounting/slot"/slot["slot_id"]).glob("*.json"));previous=None
    for path in paths:
        event=load(path)
        if event["state"]=="ADMITTED":
            if change=="decision":event["evidence"]["decision"]="DENIED"
            elif change=="commitment_boot":event["evidence"]["commitment_observation"]["boot_id"]="different-original-boot"
        if event["state"]=="CONSUMED" and change=="consumption_time":event["at"]["monotonic_ns"]=0
        event["previous_sha256"]=previous;event.pop("event_sha256");event["event_sha256"]=digest(canonical(event));previous=event["event_sha256"];save(path,event)
    with pytest.raises(ValueError):verify_slot(root,slot)



def test_pair_boot_change_is_accounted_without_resuming_member(tmp_path,raw_fixture,monkeypatch):
    import shutil
    from src.orchestration.x6_r1_5_1_durable import records
    from tests.fixtures.x6_r1_5_2_synthetic import _rewrite
    root=raw_copy(tmp_path,raw_fixture,count=1);expected=root/"readiness/initial/epoch.json";value=load(expected)
    old=Path(value["readiness_root"]);new=root/"readiness/new-boot";shutil.copytree(old,new)
    for path in new.glob("raw/commands/*.json"):
        observation=_rewrite(load(path),value["boot_id"],"synthetic-subsequent-boot");save(path,observation)
    for path in new.glob("raw/commands/*.result.json"):
        observation=load(path);intent=path.with_name(path.name.replace(".result.json",".intent.json"));observation["intent_sha256"]=digest(canonical(load(intent)));save(path,observation)
    value["readiness_root"]=str(new);value["boot_id"]="synthetic-subsequent-boot";value["readiness_observation_hashes"]=[digest(canonical(row)) for row in records(new,campaign_catalog())]
    value.pop("epoch_id");value["epoch_id"]=digest(canonical(value));observed=new/"epoch.json";save(observed,value)
    blocker,target=accepted_inventory()["slots"][:2]
    with pytest.raises(ValueError,match="environment drift absent"):
        request_and_prior(root,accepted_inventory()["slots"][1:60],"NOT_RUN_ENVIRONMENT_DRIFT",{"expected_epoch_path":str(expected),"observed_epoch_path":str(observed)})
    request,prior=request_and_prior(root,[target],"NOT_RUN_OPERATIONAL_FAILURE",{"epoch_path":str(expected),"blocking_slot_id":blocker["slot_id"],"observed_epoch_path":str(observed)})
    source=load(expected)["source"];auth=live_not_run(root,request,prior,source);_set_clock_after(root,monkeypatch)
    campaign.record_not_run(root,auth,request,source=source);verify_not_run_action(root,auth["authorization_id"])
    assert not (root/"slots"/target["run_id"]).exists()



def test_recovery_cannot_claim_prior_cleanup_as_final_absence(tmp_path,raw_fixture):
    from src.orchestration.x6_r1_5_1_durable import records
    from src.expansion.x6_r1_5_2_materialized_verifier import _verify_bound_operation
    from tests.fixtures.x6_r1_5_2_synthetic import _rewrite
    root=raw_copy(tmp_path,raw_fixture,count=1);slot=accepted_inventory()["slots"][0];run=root/"slots"/slot["run_id"]
    original=records(run,campaign_catalog());cycle=[row for row in original if row["phase"] in {"cleanup_before","cleanup"}]
    offset=original[-1]["completed"]["monotonic_ns"]-cycle[0]["intent_at"]["monotonic_ns"]+100_000_000
    for index,template in enumerate(cycle,len(original)+1):
        row=_rewrite(template,"unused","unused",offset);row["order"]=index
        intent={key:row[key] for key in ("order","name","phase","window","argv","timeout_seconds","shell","source_test_only","intent_at")}
        row["intent_sha256"]=digest(canonical(intent))
        if row["name"]=="cleanup":row.update(return_code=1,stderr="synthetic cleanup failure",stderr_sha256=digest(b"synthetic cleanup failure"))
        save(run/"raw/commands"/(f"{index:05d}.intent.json"),intent);save(run/"raw/commands"/(f"{index:05d}.result.json"),row)
    selected=[row for row in original if row["phase"] in {"n0_restoration_controls","cleanup_before","cleanup","cleanup_after"}]
    save(run/"state/recovery.json",{"status":"RECOVERED_NO_RESUME","command_orders":[row["order"] for row in selected],"records_sha256":digest(canonical(selected)),"source_test_only":True})
    raw=records(run,campaign_catalog(),permit_incomplete=True)
    with pytest.raises(ValueError,match="final absence"):_verify_bound_operation(run,"recovery",raw,required=True)



@pytest.mark.parametrize("action",["freeze-development","evaluate"])
def test_canonical_action_partial_reservation_blocks_different_authority(tmp_path,action):
    from src.orchestration.x6_r1_5_2_durable import lock_campaign
    from src.orchestration.x6_r1_5_2_contract import validate_action_authorization
    root=tmp_path/"synthetic-single-action";source=campaign.source_identity()
    first=live_action_auth(root,action,[],{},source)
    second=copy.deepcopy(first);second["authorization_id"]+="_SECOND";second.pop("authorization_sha256");second["authorization_sha256"]=digest(canonical(second))
    validate_action_authorization(first,action=action,campaign_root=root,source=source,input_inventory_sha256=digest(canonical([])),prior_state_sha256=digest(canonical({})),now_ns=stamp()["monotonic_ns"],boot_id=current_boot_id())
    lock=lock_campaign(root)
    try:
        path,row=reserve_action(root,first,action=action)
        with pytest.raises(ValueError,match="canonical single action already reserved"):reserve_action(root,second,action=action)
        assert load(path)["state"]=="RESERVED_UNDECIDED"
        assert len(list(path.parent.glob("*.reservation.json")))==1
    finally:os.close(lock)
