"""Isolated source-only regressions for the eight compliance corrections."""
import copy
from pathlib import Path

import pytest

from src.orchestration.x6_r1_5_1_contract import canonical,digest,accepted_manifest
from src.orchestration.x6_r1_5_1_durable import save
from src.orchestration.x6_r1_5_2_contract import runtime_bindings,validate_slot_authorization,validate_epoch
from src.orchestration.x6_r1_5_2_durable import append_event,read_events,publish_bundle
from src.orchestration.x6_r1_5_2_campaign import source_identity
from src.expansion.x6_r1_5_2_dataset import historical_rule,model_matrix
from src.expansion.x6_r1_5_2_materialized_verifier import _verify_bound_operation
from src.expansion.x6_r1_5_2_analysis import metrics,evaluation_status
from tests.unit.test_x6_r1_5_2_campaign import slot,slot_auth,SOURCE


def signed(value):
    value=copy.deepcopy(value); value.pop("authorization_sha256",None)
    value["authorization_sha256"]=digest(canonical(value)); return value


def authorization(root):
    value=slot_auth(root,slot())
    value.update(runtime_image=runtime_bindings()["image"],runtime_bindings=runtime_bindings(),
                 epoch={"path":str(root/"epoch.json"),"sha256":"a"*64,"epoch_id":"b"*64},development_freeze_sha256=None)
    return signed(value)


def test_slot_schema_carries_image_required_by_actual_preflight(tmp_path):
    value=authorization(tmp_path)
    validate_slot_authorization(value,campaign_root=tmp_path,slot=slot(),source=SOURCE,now_ns=100,boot_id="boot")
    assert value["runtime_image"]==value["runtime_bindings"]["image"]


@pytest.mark.parametrize("field",["runtime_image","runtime_bindings","development_freeze_sha256"])
def test_runtime_binding_tampering_rejected(tmp_path,field):
    value=authorization(tmp_path); value[field]={"altered":True}; value=signed(value)
    with pytest.raises(ValueError): validate_slot_authorization(value,campaign_root=tmp_path,slot=slot(),source=SOURCE,now_ns=100,boot_id="boot")


def test_caller_directory_and_environment_cannot_replace_source(tmp_path,monkeypatch):
    expected=source_identity()
    monkeypatch.chdir(tmp_path); monkeypatch.setenv("X6_SOURCE_COMMIT","0"*40)
    assert source_identity()==expected
    assert expected["implementation_root"]==str(Path(__file__).resolve().parents[2])
    assert expected["executable_inventory_sha256"]==digest(canonical(expected["executable_inventory"]))


def test_rehashed_illegal_event_transition_rejected(tmp_path):
    event=append_event(tmp_path,"slot","synthetic-slot","RESERVED_UNDECIDED")
    event["state"]="RUNNING"; event.pop("event_sha256"); event["event_sha256"]=digest(canonical(event))
    save(tmp_path/"accounting/slot/synthetic-slot/000001.json",event)
    with pytest.raises(ValueError,match="illegal transition"): read_events(tmp_path,"slot","synthetic-slot")


@pytest.mark.parametrize("name",["cleanup","recovery","restoration-action"])
def test_production_verifier_rejects_synthetic_status_assertion(tmp_path,name):
    save(tmp_path/"state/authorization.json",{"source_test_only":False})
    save(tmp_path/"state"/(name+".json"),{"source_test_only":True,"status":"CLEAN"})
    with pytest.raises(ValueError,match="production/synthetic"): _verify_bound_operation(tmp_path,name,[],required=True)


def test_bundle_not_published_without_independent_validation(tmp_path):
    staging=tmp_path/"staging"; output=tmp_path/"output"
    with pytest.raises(ValueError,match="prepublication"): publish_bundle(staging,output,{"a.json":{"synthetic":True}})
    assert staging.exists() and not output.exists()


def test_contradictory_epoch_document_rejected(tmp_path):
    path=tmp_path/"epoch.json"; save(path,{"schema_version":1,"campaign_id":"X6_F1_EXPLORATORY_BINARY_V1","epoch_id":"forged"})
    with pytest.raises(ValueError,match="epoch schema"): validate_epoch(path,tmp_path)


def test_historical_rule_has_exact_six_unchanged_predicates():
    manifest=accepted_manifest(); bounds={row["feature_id"]:row for row in manifest["features"]}
    predictors={"packet_loss_ratio":bounds["packet_loss_ratio"]["upper_threshold"],
                "round_trip_latency_ms_p95":bounds["round_trip_latency_ms_p95"]["upper_threshold"],
                "throughput_mbps":bounds["throughput_mbps"]["lower_threshold"],
                "interface_utilization_ratio":bounds["interface_utilization_ratio"]["upper_threshold"]}
    result=historical_rule(predictors,{"queue_drop_count":0,"rate_limit_detected":False},manifest)
    assert result=={"output":"ABSTAIN","predicates":[False,True,True,True,True,True]}


def test_evaluation_rows_rejected_before_fitting():
    row={"slot_identity":{"stage":"EVALUATION","block_id":"EVAL_B01"}}
    with pytest.raises(ValueError,match="evaluation row"): model_matrix([row])


def test_empty_conditional_denominators_and_incomplete_evaluation():
    slots=[{"block_id":f"EVAL_B{i:02d}","assignment":label,"accounting_status":"NO_PREDICTION_OPERATIONAL","predictions":{}}
           for i in range(1,21) for label in ("N0","F1")]
    result=metrics(slots,"rule")
    assert result["assignment_accuracy"]==0 and result["unavailable_rate"]==1
    assert result["secondary_effectiveness_qualified_sensitivity"]=="NOT_ESTIMABLE"
    assert result["secondary_clean_control_specificity"]=="NOT_ESTIMABLE"
    assert evaluation_status(slots)=="INCONCLUSIVE_INCOMPLETE_EVALUATION"


@pytest.mark.parametrize("relative",["../escape.json","/tmp/escape.json","publication-manifest.json"])
def test_publication_rejects_unsafe_inventory_paths(tmp_path,relative):
    with pytest.raises(ValueError,match="artifact path"):
        publish_bundle(tmp_path/"staging",tmp_path/"published",{relative:{"synthetic":True}},validate=lambda p:True)
    assert not (tmp_path/"published").exists()


def test_verified_event_cache_is_pass_local_and_read_only(tmp_path):
    from src.expansion.x6_r1_5_2_materialized_verifier import verification_pass
    append_event(tmp_path,"slot","synthetic-slot","RESERVED_UNDECIDED")
    with verification_pass(tmp_path):
        first=read_events(tmp_path,"slot","synthetic-slot");first[0]["state"]="FORGED"
        assert read_events(tmp_path,"slot","synthetic-slot")[0]["state"]=="RESERVED_UNDECIDED"
        with pytest.raises(ValueError,match="read-only verification"):
            append_event(tmp_path,"slot","synthetic-slot","REJECTED_SPENT")
    append_event(tmp_path,"slot","synthetic-slot","REJECTED_SPENT")
    assert read_events(tmp_path,"slot","synthetic-slot")[-1]["state"]=="REJECTED_SPENT"


def test_class_reason_accounting_and_progression_are_not_predictors():
    from src.expansion.x6_r1_5_2_analysis import outcome_accounting,progression
    slots=[{"block_id":f"EVAL_B{i:02d}","assignment":label,"accounting_state":"NOT_RUN_DEVELOPMENT_INCONCLUSIVE","accounting_status":"NO_PREDICTION_OPERATIONAL","predictions":{}}
           for i in range(1,21) for label in ("N0","F1")]
    result=outcome_accounting(slots,["ml"])["ml"]
    assert result["F1"]=={"denominator":20,"abstention_count":0,"unavailable_count":20,"unavailable_by_reason":{"NOT_RUN_DEVELOPMENT_INCONCLUSIVE":20}}
    assert result["restoration"]["not_reached"]==20
    assert progression(slots,["ml"])["ml"]["eligible_for_separately_reviewed_confirmatory_proposal"] is False


def test_fake_synthetic_context_cannot_bypass_production_boundary(tmp_path):
    from src.orchestration.x6_r1_5_2_campaign import main
    class Fake:
        def validate(self,root): pass
    with pytest.raises(ValueError,match="untrusted synthetic interface"):
        main(["validate-contract","--campaign-root",str(tmp_path)],_synthetic_context=Fake())
