"""CLI for one bounded exploratory campaign action. Imports authorize nothing."""
from __future__ import annotations

import argparse,copy,os
from pathlib import Path

from src.expansion.x6_r1_5_2_analysis import metrics, paired_bootstrap, evaluation_status
from src.expansion.x6_r1_5_2_materialized_verifier import verify_analysis,verify_campaign,verify_model,verify_slot
from src.expansion.x6_r1_5_2_model import fit, hybrid_output, ml_output, probabilities
from src.orchestration.x6_r1_5_1_contract import canonical,digest,load,require,current_boot_id
from src.orchestration.x6_r1_5_1_durable import stamp
from src.orchestration.x6_r1_5_2_contract import accepted_inventory,validate_action_authorization
from src.orchestration.x6_r1_5_2_durable import commit_action_authorization,publish_bundle,read_events
from src.orchestration.x6_r1_5_2_slot import CommandCollector,run_slot
from src.orchestration.x6_r1_5_2_recovery import recover,recover_action
from src.orchestration.x6_r1_5_2_not_run import derive_prerequisites,publish_events,verify_not_run_action
from src.runtime.subprocesses import run_capture


def source_identity():
    """Bind the actual implementation root, Git boundary, executable bytes and modes.

    The caller directory and environment are never identity inputs. Uncommitted
    source can be inspected but cannot authorize a production action.
    """
    root = Path(__file__).resolve().parents[2]
    def git(*args):
        result=run_capture(["git",*args],timeout_seconds=30,cwd=root)
        result.check_returncode()
        return result.stdout.strip()
    require(Path(git("rev-parse", "--show-toplevel")).resolve() == root, "implementation Git root")
    tracked=set(git("ls-files").splitlines())
    successor={path.relative_to(root).as_posix() for pattern in
               ("src/orchestration/x6_r1_5_2*.py","src/expansion/x6_r1_5_2*.py","plans/expansion/X6_R1_5_2*.json","tests/fixtures/x6_r1_5_2*.py")
               for path in root.glob(pattern)}
    inventory=[]
    for relative in sorted(tracked|successor):
        path=root/relative
        require(path.is_file() and not path.is_symlink(),"unsafe or missing implementation source")
        inventory.append({"path":relative,"sha256":digest(path.read_bytes()),
                          "mode":"100755" if path.stat().st_mode & 0o111 else "100644"})
    return {"git_commit":git("rev-parse","HEAD"),"git_tree":git("rev-parse","HEAD^{tree}"),
            "implementation_root":str(root),"executable_inventory":inventory,
            "executable_inventory_sha256":digest(canonical(inventory)),
            "clean":not bool(git("status", "--porcelain", "--untracked-files=all"))}


def require_production_source(source):
    require(source == source_identity() and source.get("clean") is True, "production source identity or clean boundary")


def _stage_state(root,stage):
    from src.expansion.x6_r1_5_2_materialized_verifier import verification_pass
    from copy import deepcopy
    with verification_pass(root) as state:
        if stage not in state["stages"]:state["stages"][stage]=_reconstruct_stage_state(root,stage)
        return deepcopy(state["stages"][stage])


def _reconstruct_stage_state(root, stage):
    """Reconstruct the canonical closed-stage input from durable slot evidence."""
    root=Path(root); inventory=accepted_inventory(); selected=[row for row in inventory["slots"] if row["stage"]==stage]
    slots=[]; accounting_rows=[]; heads=[]
    for slot in selected:
        events=read_events(root,"slot",slot["slot_id"])
        require(events and (events[-1]["state"] in {"TERMINAL","REJECTED_SPENT"} or events[-1]["state"].startswith("NOT_RUN_")),"stage slot is not final")
        verified=verify_slot(root,slot)
        heads.append({"slot_id":slot["slot_id"],"event_sha256":events[-1]["event_sha256"],"state":events[-1]["state"]})
        candidate=verified.get("row",verified.get("accounting_row"))
        if candidate is not None and candidate.get("eligible") is True and candidate.get("target_verified") is True:
            slots.append(candidate)
        from src.expansion.x6_r1_5_2_dataset import accounting_row
        accounting_rows.append(accounting_row(slot,events,verified))
    return {"stage":stage,"accepted_inventory_sha256":inventory["sha256"],"slot_heads":heads,"eligible_rows":slots,"accounting_rows":accounting_rows}


def _freeze_prerequisites(root):
    root=Path(root); state=_stage_state(root,"DEVELOPMENT")
    evaluation=[row for row in accepted_inventory()["slots"] if row["stage"]=="EVALUATION"]
    require(not any(read_events(root,"slot",row["slot_id"]) for row in evaluation),"evaluation access precedes development freeze")
    require(not any((root/"slots"/row["run_id"]).exists() for row in evaluation),"evaluation run artifact precedes development freeze")
    require(not (root/"action-ledger/X6_R1_5_2_FINAL_EVALUATION_ANALYSIS_AUTHORIZATION_V1").exists(),"evaluation authority precedes development freeze")
    require(not (root/"development-freeze-v1").exists() and not (root/"final-analysis-v1").exists(),"canonical output already exists")
    counts={label:sum(row["ground_truth"]["assignment"]==label for row in state["eligible_rows"]) for label in ("N0","F1")}
    require(len(state["eligible_rows"])>=48 and min(counts.values())>=24,"development freeze requires accepted sufficiency; use separately authorized NOT_RUN accounting for inconclusive closure")
    state["evaluation_unaccessed"]=True; state["canonical_output_absent"]=True
    return state


def _evaluation_prerequisites(root):
    root=Path(root); state=_stage_state(root,"EVALUATION")
    freeze=root/"development-freeze-v1"
    require(freeze.is_dir() and (freeze/"publication-manifest.json").is_file(),"verified development freeze absent")
    development=_stage_state(root,"DEVELOPMENT")["eligible_rows"]
    model=verify_model(freeze,development)
    require(not (root/"final-analysis-v1").exists(),"canonical analysis already exists")
    state.update({"development_freeze_sha256":digest((freeze/"publication-manifest.json").read_bytes()),
                  "model_sha256":model["model_sha256"],"canonical_output_absent":True})
    return state


def _action(campaign_root, action, authorization, requested_inputs, requested_prior, derive, operation, *, observe=stamp, source=None, boot_id=None):
    root=Path(campaign_root); actual_source=source_identity(); source=source or actual_source; boot_id=boot_id or current_boot_id()
    require(source==actual_source,"action source must be the executing implementation")
    canonical_prior, canonical_inputs=derive()
    require(canonical(requested_prior)==canonical(canonical_prior),"caller prior state contradicts canonical evidence")
    require(canonical(requested_inputs)==canonical(canonical_inputs),"caller input inventory contradicts canonical evidence")
    def validate(observed):
        fresh_prior,fresh_inputs=derive()
        require(canonical(fresh_prior)==canonical(canonical_prior) and canonical(fresh_inputs)==canonical(canonical_inputs),"canonical state changed before commitment")
        def validity(point):
            return validate_action_authorization(authorization,action=action,campaign_root=root,source=source,
                input_inventory_sha256=digest(canonical(fresh_inputs)),prior_state_sha256=digest(canonical(fresh_prior)),
                now_ns=point["monotonic_ns"],boot_id=point["boot_id"])
        return validity if observed is None else validity(observed)
    validate(observe())
    ledger,row,lock=commit_action_authorization(root,authorization,action=action,validate_at_commit=validate,observe=observe)
    try:
        from src.orchestration.x6_r1_5_2_durable import advance_action
        row=advance_action(ledger,row,"MATERIALIZING")
        output,files=operation(canonical_inputs,canonical_prior,source)
        staging=root/("."+output.name+".staging."+authorization["authorization_id"])
        from src.expansion.x6_r1_5_2_materialized_verifier import verify_candidate_bundle
        manifest=publish_bundle(staging,output,files,validate=lambda path: verify_candidate_bundle(path,action,root,canonical_inputs,canonical_prior,source))
        advance_action(ledger,row,"PUBLISHED",publication_manifest_sha256=digest(canonical(manifest)))
        return manifest
    except BaseException as error:
        from src.orchestration.x6_r1_5_2_durable import advance_action
        advance_action(ledger,row,"FAILED_SPENT",error_type=type(error).__name__,detail=str(error)); raise
    finally:
        os.close(lock)



def freeze_policies(source):
    from src.orchestration.x6_r1_5_2_contract import CONTRACT_PROPOSAL_SHA256,runtime_bindings
    from src.expansion.x6_r1_5_2_model import PARAMETERS
    from src.orchestration.x6_r1_5_1_contract import ROOT
    paths=("src/expansion/x6_r1_5_2_analysis.py","src/expansion/x6_r1_5_2_dataset.py","src/expansion/x6_r1_5_2_model.py",
           "src/expansion/x6_r1_5_2_materialized_verifier.py","src/orchestration/x6_r1_5_2_slot.py")
    return {"contract_sha256":CONTRACT_PROPOSAL_SHA256,"source":source,"runtime":runtime_bindings(),
            "historical_rule_source_sha256":digest((ROOT/"src/orchestration/x6_r1_5_1_production_path.py").read_bytes()),
            "implementation_hashes":{name:digest((ROOT/name).read_bytes()) for name in paths},
            "model_parameters":PARAMETERS,"hybrid_thresholds":{"lower":"0.20","upper":"0.80"},
            "test_vectors":{"ml":{"0.5":"F1_PRESENT"},"hybrid":{"0.20":"F1_ABSENT","0.80":"F1_PRESENT"}},
            "bootstrap":{"replicates":10000,"seed_uint64":3705850974925186758,"generator":"PCG64","quantiles":["0.025","0.975"],"method":"linear","minimum_estimable":9500}}

def freeze_development(root, authorization, rows, prior, **testing):
    def derive():
        state=_freeze_prerequisites(root); return state,state["eligible_rows"]
    def operation(canonical_rows, canonical_prior, committed_source):
        inventory_sha=digest(canonical(canonical_rows)); model=fit(canonical_rows,inventory_sha,committed_source)
        return Path(root)/"development-freeze-v1", {"development-rows.json":{"rows":canonical_rows},"model.json":model,
            "development_freeze.json":{"status":"IMMUTABLE_DEVELOPMENT_FREEZE","model_sha256":model["model_sha256"],"inventory_sha256":inventory_sha,
                           "prior_state_sha256":digest(canonical(canonical_prior)), "policies":freeze_policies(committed_source), "development_state":canonical_prior}}
    return _action(root,"freeze-development",authorization,rows,prior,derive,operation,**testing)


def evaluate(root, authorization, slots, prior, **testing):
    def derive():
        state=_evaluation_prerequisites(root); return state,state["accounting_rows"]
    def operation(canonical_slots, canonical_prior, committed_source):
        model=verify_model(Path(root)/"development-freeze-v1",_stage_state(root,"DEVELOPMENT")["eligible_rows"])
        evaluated=copy.deepcopy(canonical_slots)
        for row in evaluated:
            require(not row.get("predictions",{}).keys()-{"rule"},"preexisting learned prediction")
            if row.get("predictors") and row.get("eligible") is True:
                p=probabilities(model,[[float(row["predictors"][name]) for name in model["feature_order"]]])[0]
                row.setdefault("predictions",{})["ml"]=ml_output(p); row["predictions"]["hybrid"]=hybrid_output(row["predictions"].get("rule","ABSTAIN"),p)
        from src.expansion.x6_r1_5_2_analysis import analysis_document
        report=analysis_document(evaluated)
        return Path(root)/"final-analysis-v1", {"evaluation-slots.json":{"slots":evaluated},"analysis.json":report,
            "analysis-input.json":{"prior_state_sha256":digest(canonical(canonical_prior)),"model_sha256":model["model_sha256"]}}
    return _action(root,"evaluate",authorization,slots,prior,derive,operation,**testing)


def record_not_run(root,authorization,request,**testing):
    target_slot_ids=request["target_slot_ids"]; reason=request["reason"]; supporting=request["supporting_evidence"]
    def derive():
        state=derive_prerequisites(root,target_slot_ids,reason,supporting)
        return state,state["target_slots"]
    prior,inputs=derive()
    require(authorization["target_slot_ids"]==target_slot_ids and authorization["reason"]==reason,"NOT_RUN request authorization binding")
    require(authorization["expected_accounting_heads"]==prior["expected_accounting_heads"] and authorization["epoch"]==prior["epoch"],"NOT_RUN head/epoch binding")
    require(authorization["supporting_evidence_sha256"]==digest(canonical(prior["supporting_evidence"])),"NOT_RUN supporting evidence binding")
    fail_after=testing.pop("fail_after",None)
    def operation(canonical_slots,canonical_prior,committed_source):
        require(canonical_slots==canonical_prior["target_slots"] and committed_source==authorization["source"],"NOT_RUN committed inputs")
        files=publish_events(root,authorization,canonical_prior,fail_after=fail_after)
        output=Path(authorization["canonical_output"]); output.parent.mkdir(parents=True,exist_ok=True)
        return output,files
    return _action(root,"record-not-run",authorization,inputs,prior,derive,operation,**testing)


def main(argv=None, *, _synthetic_context=None):
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command",required=True)
    for name in ("inspect-launcher","verify-launcher","recover-action","validate-contract","verify-slot","verify-campaign","verify-model","verify-analysis","verify-not-run","recover-slot","freeze-development","evaluate","record-not-run","run-slot"):
        p=sub.add_parser(name); p.add_argument("--campaign-root",required=True); p.add_argument("--input"); p.add_argument("--authorization")
    args=parser.parse_args(argv); root=Path(args.campaign_root)
    if _synthetic_context is not None:
        from src.orchestration.x6_r1_5_2_source_test import SyntheticContext
        require(type(_synthetic_context) is SyntheticContext,"untrusted synthetic interface")
        SyntheticContext.validate(_synthetic_context,root)
    else:
        require(not (root/"SOURCE_TEST_ONLY.json").exists(),"synthetic fixture root forbidden at production entrypoint")
        require(os.environ.get("X6_R1_5_1_CONTROLLED_CLOCK") != "1" and not os.environ.get("X6_STUB_STATE"),"synthetic environment forbidden at production entrypoint")
    if args.command=="validate-contract": accepted_inventory(); return 0
    if args.command in {"run-slot","freeze-development","evaluate","record-not-run","recover-slot","recover-action"}:
        if _synthetic_context is None: require_production_source(source_identity())
        else: SyntheticContext.validate(_synthetic_context,root)
    if args.command in {"freeze-development","evaluate","record-not-run"}:
        require(load(args.authorization)["source_test_only"] is (_synthetic_context is not None),"production/synthetic action authorization separation")
    if args.command=="run-slot":
        value=load(args.input); auth=load(args.authorization)
        from src.orchestration.x6_r1_5_2_launcher import child_registration
        import sys
        child_registration(root,auth,list(argv) if argv is not None else sys.argv[1:],synthetic=_synthetic_context is not None)
        require(auth["source_test_only"] is (_synthetic_context is not None),"production/synthetic authorization separation")
        collector=CommandCollector(simulation=_synthetic_context is not None)
        run_slot(campaign_root=root,slot=value["slot"],authorization=auth,source=source_identity(),now_ns=stamp()["monotonic_ns"],boot_id=current_boot_id(),collector=collector); return 0
    if _synthetic_context is None and (args.command.startswith("verify") or args.command in {"inspect-launcher","recover-slot","recover-action"}):
        for ledger in (root/"action-ledger").glob("*/*.json"):
            require(load(ledger)["authorization"].get("source_test_only") is False,"production entrypoint rejects synthetic action evidence")
        for event in (root/"accounting/slot").glob("*/*.json"):
            authority=load(event).get("evidence",{}).get("authorization")
            if authority is not None:require(authority.get("source_test_only") is False,"production verifier rejects synthetic reservation")
        for path in (root/"slots").glob("*/state/authorization.json"):
            require(load(path).get("source_test_only") is False,"production verifier rejects synthetic authorization")
    if args.command in {"inspect-launcher","verify-launcher"}:
        from src.orchestration.x6_r1_5_2_launcher import verify_launcher
        auth=load(args.authorization)
        require(auth["source_test_only"] is (_synthetic_context is not None),"launcher production/synthetic inspection")
        from src.expansion.x6_r1_5_2_materialized_verifier import _verify_source_snapshot
        _verify_source_snapshot(auth["source"])
        print(canonical(verify_launcher(root,auth,require_known=args.command=="verify-launcher")).decode())
        return 0
    value=load(args.input) if args.input else {}
    if args.command=="freeze-development": freeze_development(root,load(args.authorization),value["rows"],value["prior_state"]); return 0
    if args.command=="evaluate": evaluate(root,load(args.authorization),value["slots"],value["prior_state"]); return 0
    if args.command=="record-not-run": record_not_run(root,load(args.authorization),value); return 0
    if args.command=="verify-not-run": verify_not_run_action(root,value["authorization_id"]); return 0
    if args.command=="recover-action": recover_action(root,value["action"],value["authorization_id"]); return 0
    if args.command=="recover-slot": recover(root,value["slot_id"],source=source_identity(),simulation=_synthetic_context is not None); return 0
    if args.command=="verify-slot": verify_slot(root,value["slot"]); return 0
    if args.command=="verify-campaign": verify_campaign(root,accepted_inventory()); return 0
    if args.command=="verify-model": verify_model(root/"development-freeze-v1",_stage_state(root,"DEVELOPMENT")["eligible_rows"]); return 0
    if args.command=="verify-analysis":
        model=verify_model(root/"development-freeze-v1",_stage_state(root,"DEVELOPMENT")["eligible_rows"])
        verify_analysis(root/"final-analysis-v1",root,accepted_inventory(),model); return 0
    raise AssertionError(args.command)


if __name__=="__main__": raise SystemExit(main())
