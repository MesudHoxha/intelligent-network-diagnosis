"""Authorized, accounting-only publication of accepted NOT_RUN outcomes."""
from __future__ import annotations

from pathlib import Path

from src.orchestration.x6_r1_5_1_contract import canonical,digest,load,require
from src.orchestration.x6_r1_5_1_durable import save
from src.orchestration.x6_r1_5_3_contract import CAMPAIGN_ID,CONTRACT_PROPOSAL_SHA256,INVENTORY_SHA256,NOT_RUN_REASONS,accepted_inventory,authorization_digest
from src.orchestration.x6_r1_5_3_historical_accounting import accounting_context as epoch_context, accounting_slot
from src.orchestration.x6_r1_5_3_durable import append_event,read_events,reject_not_run_artifacts,verify_action_ledger
from src.orchestration.x6_r1_5_3_reconstruction import invocation,validated


def _slot(slot_id):
    rows=[row for row in accepted_inventory()["slots"] if row["slot_id"]==slot_id]
    require(len(rows)==1,"unknown NOT_RUN target"); return rows[0]


def _epoch_document(path,campaign_root,*,observed_drift=False):
    from src.orchestration.x6_r1_5_3_historical_accounting import accounting_epoch
    return accounting_epoch(path,campaign_root,observed_drift=observed_drift)


@invocation
def derive_prerequisites(root,target_slot_ids,reason,supporting,*,historical_authorization=None):
    """Reconstruct the reason and target eligibility from canonical durable evidence."""
    root=Path(root); require(reason in NOT_RUN_REASONS,"NOT_RUN reason")
    slots=[_slot(slot_id) for slot_id in target_slot_ids]
    require(len(slots)==len(set(target_slot_ids)) and slots,"NOT_RUN bounded unique targets")
    heads={}
    for slot in slots:
        directory=root/"accounting/slot"/slot["slot_id"]
        if historical_authorization is None: require(not directory.exists(),"NOT_RUN target accounting directory exists")
        else:
            rows=read_events(root,"slot",slot["slot_id"])
            require(len(rows)==1 and rows[0]["state"]==reason and rows[0]["evidence"].get("authorization_sha256")==historical_authorization["authorization_sha256"],"historical NOT_RUN target was started or differently accounted")
        require(not (root/"slots"/slot["run_id"]).exists(),"NOT_RUN target has run artifacts")
        heads[slot["slot_id"]]="SCHEDULED"
    evidence={}
    if reason=="NOT_RUN_ENVIRONMENT_DRIFT":
        epoch_path=Path(supporting.get("expected_epoch_path",""))
    else:
        epoch_path=Path(supporting.get("epoch_path",""))
    applicable_epoch=_epoch_document(epoch_path,root)
    epoch_binding={"epoch_id":applicable_epoch["epoch_id"],"epoch_path":str(epoch_path.resolve()),"epoch_sha256":digest(epoch_path.read_bytes())}
    if reason=="NOT_RUN_OPERATIONAL_FAILURE":
        blocker_id=supporting.get("blocking_slot_id"); blocker=_slot(blocker_id)
        order={row["slot_id"]:index for index,row in enumerate(accepted_inventory()["slots"])}
        require(all(order[slot["slot_id"]]>order[blocker_id] for slot in slots),"operational blocker does not precede target")
        from src.expansion.x6_r1_5_3_materialized_verifier import verify_slot
        result=accounting_slot(root,blocker)
        boot_block=None
        if supporting.get("observed_epoch_path"):
            observed_path=Path(supporting["observed_epoch_path"]);observed=_epoch_document(observed_path,root)
            require(all(slot["block_id"]==blocker["block_id"] and slot["position"]=="S02" for slot in slots) and blocker["position"]=="S01","boot blocker is not preceding pair member")
            left=epoch_context(applicable_epoch);right=epoch_context(observed)
            old_boot=left.pop("boot_id");new_boot=right.pop("boot_id")
            from src.orchestration.x6_r1_5_3_epoch import difference
            require(difference({**left,"boot_id":old_boot},{**right,"boot_id":new_boot})=="NOT_RUN_OPERATIONAL_FAILURE","pair boot mismatch not independently observed")
            blocker_auth=read_events(root,"slot",blocker_id)[0]["evidence"]["authorization"]
            require(blocker_auth["epoch"]["epoch_id"]==applicable_epoch["epoch_id"] and result.get("cleanup_verified") is True,"pair boot blocker lacks original epoch/verified cleanup")
            boot_block={"observed_epoch_path":str(observed_path.resolve()),"observed_epoch_sha256":digest(observed_path.read_bytes()),"observed_epoch":observed}
        else:require(result.get("terminal") in {"SLOT_INTERRUPTED_UNRESOLVED","SLOT_CLEANUP_FAILED"},"operational/cleanup blocker not independently established")
        evidence={"epoch":applicable_epoch,"blocking_slot_id":blocker_id,"blocking_event_sha256":read_events(root,"slot",blocker_id)[-1]["event_sha256"],"blocking_terminal":result.get("terminal","SLOT_COMPLETE" if "row" in result else None),"scope":"PRECEDING_PAIR_MEMBER" if all(slot["block_id"]==blocker["block_id"] for slot in slots) else "CAMPAIGN_OPERATIONAL_BLOCK"}
        if boot_block is not None:evidence["pair_boot_change"]=boot_block
    elif reason=="NOT_RUN_ENVIRONMENT_DRIFT":
        expected_path=Path(supporting.get("expected_epoch_path","")); observed_path=Path(supporting.get("observed_epoch_path",""))
        expected=_epoch_document(expected_path,root); observed=_epoch_document(observed_path,root,observed_drift=True)
        require(expected["epoch_id"]!=observed["epoch_id"],"epoch mismatch identity absent")
        from src.orchestration.x6_r1_5_3_epoch import difference
        require(difference(epoch_context(expected),epoch_context(observed))=="NOT_RUN_ENVIRONMENT_DRIFT","environment drift absent")
        require(all(slot["stage"]==expected["stage"] for slot in slots),"drift target stage")
        remaining={slot["slot_id"] for slot in accepted_inventory()["slots"] if slot["stage"]==expected["stage"] and
                   (not (root/"accounting/slot"/slot["slot_id"]).exists() or historical_authorization is not None and slot["slot_id"] in target_slot_ids) and not (root/"slots"/slot["run_id"]).exists()}
        require(set(target_slot_ids)==remaining,"drift must account every remaining stage slot")
        evidence={"expected_epoch_path":str(expected_path.resolve()),"expected_epoch_sha256":digest(expected_path.read_bytes()),"observed_epoch_path":str(observed_path.resolve()),"observed_epoch_sha256":digest(observed_path.read_bytes()),"expected_epoch":expected,"observed_epoch":observed}
    elif reason=="NOT_RUN_DEVELOPMENT_INCONCLUSIVE":
        from src.orchestration.x6_r1_5_3_campaign import _stage_state
        state=_stage_state(root,"DEVELOPMENT"); evaluation={row["slot_id"] for row in accepted_inventory()["slots"] if row["stage"]=="EVALUATION"}
        require(set(target_slot_ids)==evaluation,"development inconclusive must account all evaluation slots")
        counts={name:sum(1 for row in state["eligible_rows"] if row["ground_truth"]["assignment"]==name) for name in ("N0","F1")}
        require(len(state["eligible_rows"])<48 or min(counts.values())<24,"development progression criteria satisfied")
        evidence={"epoch":applicable_epoch,"development_state_sha256":digest(canonical(state)),"eligible_count":len(state["eligible_rows"]),"class_counts":counts}
    else:
        evaluation={row["slot_id"] for row in accepted_inventory()["slots"] if row["stage"]=="EVALUATION"}
        require(set(target_slot_ids)==evaluation,"unusable model must account all evaluation slots")
        ledger=verify_action_ledger(root,"freeze-development",require_published=False)
        require(ledger["state"] in {"FAILED_SPENT","INTERRUPTED_SPENT","INTEGRITY_UNRESOLVED"},"model-freeze failure absent")
        require(not (root/"development-freeze-v1").exists(),"usable development freeze exists")
        freeze_authorization=ledger["authorization"]; authorization_digest(freeze_authorization)
        commitment=ledger.get("commitment_observation")
        require(isinstance(commitment,dict) and freeze_authorization["issued_ns"]<=commitment.get("monotonic_ns",-1)<=freeze_authorization["expires_ns"] and commitment.get("boot_id")==freeze_authorization["boot_id"],"failed freeze was not validly committed")
        from src.orchestration.x6_r1_5_3_campaign import _stage_state
        development=_stage_state(root,"DEVELOPMENT")
        counts={name:sum(row["ground_truth"]["assignment"]==name for row in development["eligible_rows"]) for name in ("N0","F1")}
        require(len(development["eligible_rows"])>=48 and min(counts.values())>=24,"unusable model lacks sufficient development inputs")
        freeze_prior={**development,"evaluation_unaccessed":True,"canonical_output_absent":True}
        require(freeze_authorization["input_inventory_sha256"]==digest(canonical(development["eligible_rows"])) and freeze_authorization["prior_state_sha256"]==digest(canonical(freeze_prior)),"failed freeze prerequisite binding")
        evidence={"epoch":applicable_epoch,"development_state_sha256":digest(canonical(development)),"freeze_authorization_sha256":ledger["authorization_sha256"],"freeze_ledger_sha256":ledger["ledger_sha256"],"freeze_state":ledger["state"]}
    return {"target_slots":slots,"expected_accounting_heads":heads,"reason":reason,"epoch":epoch_binding,"supporting_evidence":evidence}


def campaign_outcome(reason):
    return {"NOT_RUN_DEVELOPMENT_INCONCLUSIVE":"INCONCLUSIVE_INSUFFICIENT_DEVELOPMENT_DATA",
            "NOT_RUN_UNUSABLE_MODEL":"INCONCLUSIVE_UNUSABLE_MODEL",
            "NOT_RUN_ENVIRONMENT_DRIFT":"INCONCLUSIVE_ENVIRONMENT_DRIFT"}.get(reason)


def publish_events(root,authorization,prior,*,fail_after=None):
    root=Path(root); reason=authorization["reason"]
    for index,slot in enumerate(prior["target_slots"],1):
        evidence={"reason":reason,"authorization_id":authorization["authorization_id"],"authorization_sha256":authorization["authorization_sha256"],"source":authorization["source"],"epoch":authorization["epoch"],"supporting_evidence_sha256":authorization["supporting_evidence_sha256"],"prior_state_sha256":authorization["prior_state_sha256"]}
        append_event(root,"slot",slot["slot_id"],reason,evidence=evidence)
        if fail_after==index: raise RuntimeError("synthetic NOT_RUN publication interruption")
    return {"not-run.json":{"schema_version":1,"status":"NOT_RUN_ACCOUNTING_COMPLETE","campaign_outcome":campaign_outcome(reason),"authorization_id":authorization["authorization_id"],"authorization_sha256":authorization["authorization_sha256"],"reason":reason,"target_slot_ids":authorization["target_slot_ids"],"source":authorization["source"],"epoch":authorization["epoch"],"supporting_evidence":prior["supporting_evidence"],"supporting_evidence_sha256":authorization["supporting_evidence_sha256"],"prior_state_sha256":authorization["prior_state_sha256"]}}


def verify_not_run_action(root,authorization_id):
    return validated(root,"not-run-action",{"authorization_id":authorization_id},
                     lambda: _verify_not_run_action_once(root,authorization_id))


def _verify_not_run_action_once(root,authorization_id):
    # One read-only pass keeps validated stage results for both consumers.
    # Outer content/source checks and finally reset remain authoritative.
    from src.expansion.x6_r1_5_3_materialized_verifier import verification_pass
    with verification_pass(root):
        root=Path(root); ledger=verify_action_ledger(root,"record-not-run",authorization_id=authorization_id)
        authorization=ledger["authorization"]; output=root/"accounting-actions/not-run"/authorization_id
        authorization_digest(authorization)
        require(authorization["action"]=="record-not-run" and authorization["campaign_id"]==CAMPAIGN_ID and authorization["campaign_contract_sha256"]==CONTRACT_PROPOSAL_SHA256 and authorization["inventory_sha256"]==INVENTORY_SHA256,"NOT_RUN authorization contract binding")
        history=ledger["history"]; admitted=[row for row in history if row["state"]=="ADMITTED"]
        require(len(admitted)==1 and any(row["state"]=="CONSUMED" for row in history),"NOT_RUN commitment/consumption history")
        commitment=ledger.get("commitment_observation"); require(isinstance(commitment,dict) and authorization["issued_ns"]<=commitment.get("monotonic_ns",-1)<=authorization["expires_ns"] and commitment.get("boot_id")==authorization["boot_id"],"NOT_RUN authorization invalid at commitment")
        from src.expansion.x6_r1_5_3_materialized_verifier import _verify_publication
        manifest=_verify_publication(output)
        require(ledger.get("publication_manifest_sha256")==digest(canonical(manifest)),"NOT_RUN ledger/publication contradiction")
        value=load(output/"not-run.json")
        require(value.get("campaign_outcome")==campaign_outcome(authorization["reason"]),"NOT_RUN inconclusive outcome contradiction")
        supporting={"epoch":authorization["epoch"]}
        if authorization["reason"]=="NOT_RUN_OPERATIONAL_FAILURE": supporting["blocking_slot_id"]=value["supporting_evidence"]["blocking_slot_id"]
        elif authorization["reason"]=="NOT_RUN_ENVIRONMENT_DRIFT": supporting.update({k:value["supporting_evidence"][k] for k in ("expected_epoch_path","observed_epoch_path")})
        # Targets are terminal now, so reconstruct the prepublication evidence excluding target-head absence.
        require(value["authorization_sha256"]==authorization["authorization_sha256"] and value["target_slot_ids"]==authorization["target_slot_ids"],"NOT_RUN publication identity")
        require(value["supporting_evidence_sha256"]==digest(canonical(value["supporting_evidence"])),"NOT_RUN supporting evidence digest")
        require(value["supporting_evidence_sha256"]==authorization["supporting_evidence_sha256"],"NOT_RUN authorization evidence binding")
        epoch_path=Path(authorization["epoch"]["epoch_path"]); epoch_value=_epoch_document(epoch_path,root)
        require(epoch_value["epoch_id"]==authorization["epoch"]["epoch_id"] and digest(epoch_path.read_bytes())==authorization["epoch"]["epoch_sha256"],"NOT_RUN applicable epoch contradiction")
        if authorization["reason"]=="NOT_RUN_OPERATIONAL_FAILURE":
            blocker_id=value["supporting_evidence"]["blocking_slot_id"]
            from src.expansion.x6_r1_5_3_materialized_verifier import verify_slot
            blocker=accounting_slot(root,_slot(blocker_id))
            require(blocker.get("terminal","SLOT_COMPLETE" if "row" in blocker else None)==value["supporting_evidence"]["blocking_terminal"] and ("pair_boot_change" in value["supporting_evidence"] or blocker["terminal"] in {"SLOT_INTERRUPTED_UNRESOLVED","SLOT_CLEANUP_FAILED"}),"NOT_RUN operational evidence contradiction")
            require(read_events(root,"slot",blocker_id)[-1]["event_sha256"]==value["supporting_evidence"]["blocking_event_sha256"],"NOT_RUN blocking head changed")
        elif authorization["reason"]=="NOT_RUN_ENVIRONMENT_DRIFT":
            evidence=value["supporting_evidence"]
            expected_path=Path(evidence["expected_epoch_path"]); observed_path=Path(evidence["observed_epoch_path"])
            expected=_epoch_document(expected_path,root); observed=_epoch_document(observed_path,root,observed_drift=True)
            require(digest(expected_path.read_bytes())==evidence["expected_epoch_sha256"] and digest(observed_path.read_bytes())==evidence["observed_epoch_sha256"],"NOT_RUN epoch evidence changed")
            require(expected==evidence["expected_epoch"] and observed==evidence["observed_epoch"] and {k:v for k,v in epoch_context(expected).items() if k!="boot_id"}!={k:v for k,v in epoch_context(observed).items() if k!="boot_id"},"NOT_RUN epoch mismatch contradiction")
        elif authorization["reason"]=="NOT_RUN_DEVELOPMENT_INCONCLUSIVE":
            from src.orchestration.x6_r1_5_3_campaign import _stage_state
            state=_stage_state(root,"DEVELOPMENT"); counts={name:sum(1 for row in state["eligible_rows"] if row["ground_truth"]["assignment"]==name) for name in ("N0","F1")}
            require(digest(canonical(state))==value["supporting_evidence"]["development_state_sha256"] and len(state["eligible_rows"])==value["supporting_evidence"]["eligible_count"] and counts==value["supporting_evidence"]["class_counts"] and (len(state["eligible_rows"])<48 or min(counts.values())<24),"NOT_RUN development evidence contradiction")
        else:
            freeze=verify_action_ledger(root,"freeze-development",require_published=False)
            freeze_authorization=freeze["authorization"]; authorization_digest(freeze_authorization)
            from src.orchestration.x6_r1_5_3_campaign import _stage_state
            development=_stage_state(root,"DEVELOPMENT")
            counts={name:sum(row["ground_truth"]["assignment"]==name for row in development["eligible_rows"]) for name in ("N0","F1")}
            require(len(development["eligible_rows"])>=48 and min(counts.values())>=24,"unusable model lacks sufficient development inputs")
            freeze_prior={**development,"evaluation_unaccessed":True,"canonical_output_absent":True}
            require(freeze_authorization["input_inventory_sha256"]==digest(canonical(development["eligible_rows"])) and freeze_authorization["prior_state_sha256"]==digest(canonical(freeze_prior)),"NOT_RUN failed freeze prerequisite contradiction")
            require(digest(canonical(development))==value["supporting_evidence"]["development_state_sha256"] and freeze["ledger_sha256"]==value["supporting_evidence"]["freeze_ledger_sha256"] and freeze["state"]==value["supporting_evidence"]["freeze_state"],"NOT_RUN freeze failure contradiction")
        reconstruction_input={"epoch_path":authorization["epoch"]["epoch_path"]}
        if authorization["reason"]=="NOT_RUN_OPERATIONAL_FAILURE":
            reconstruction_input["blocking_slot_id"]=value["supporting_evidence"]["blocking_slot_id"]
            if "pair_boot_change" in value["supporting_evidence"]:reconstruction_input["observed_epoch_path"]=value["supporting_evidence"]["pair_boot_change"]["observed_epoch_path"]
        elif authorization["reason"]=="NOT_RUN_ENVIRONMENT_DRIFT": reconstruction_input={name:value["supporting_evidence"][name] for name in ("expected_epoch_path","observed_epoch_path")}
        reconstructed=derive_prerequisites(root,authorization["target_slot_ids"],authorization["reason"],reconstruction_input,historical_authorization=authorization)
        require(reconstructed["supporting_evidence"]==value["supporting_evidence"] and digest(canonical(reconstructed))==authorization["prior_state_sha256"] and
                digest(canonical(reconstructed["target_slots"]))==authorization["input_inventory_sha256"],"NOT_RUN canonical prerequisites contradiction")
        for slot_id in authorization["target_slot_ids"]:
            slot=_slot(slot_id); events=read_events(root,"slot",slot_id)
            require(len(events)==1 and events[0]["state"]==authorization["reason"],"NOT_RUN target event contradiction")
            evidence=events[0]["evidence"]
            require(evidence["authorization_sha256"]==authorization["authorization_sha256"] and evidence["supporting_evidence_sha256"]==authorization["supporting_evidence_sha256"],"NOT_RUN event authority contradiction")
            reject_not_run_artifacts(root,slot,events[0]["state"])
        return value
