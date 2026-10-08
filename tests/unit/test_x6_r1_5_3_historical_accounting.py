"""Historical validators and real accounting boundaries on isolated synthetic evidence."""
import copy
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from src.orchestration.x6_r1_5_1_contract import canonical, digest, load, current_boot_id
from src.orchestration.x6_r1_5_3_historical_accounting import (
    accounting_epoch, accounting_context, accounting_slot, validate_original_source,
    SUPPORTED_COMMIT,
)
from src.orchestration.x6_r1_5_3_contract import accepted_inventory

ROOT = Path(__file__).resolve().parents[2]


def command(argv, cwd, env, output, timeout=90):
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True,
                            shell=False, timeout=timeout)
    output.with_suffix(".stdout.log").write_text(result.stdout)
    output.with_suffix(".stderr.log").write_text(result.stderr)
    output.with_suffix(".json").write_text(json.dumps({"argv":argv,"cwd":str(cwd),
        "returncode":result.returncode,"source_test_only":True}) + "\n")
    assert result.returncode == 0, result.stderr
    return result


def make_history(directory):
    """Run the published predecessor unchanged, with its own Git/source identity."""
    directory.mkdir()
    source = directory / "published-source"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE":"1"}
    command(["/usr/bin/git","clone","--shared","--no-checkout",str(ROOT),str(source)],
            directory, env, directory/"clone")
    command(["/usr/bin/git","-C",str(source),"checkout","--detach",SUPPORTED_COMMIT],
            directory, env, directory/"snapshot")
    campaign = directory / "synthetic-campaign"
    campaign.mkdir()
    (campaign/"SOURCE_TEST_ONLY.json").write_bytes(canonical({"source_test_only":True,"root":str(campaign)}))
    tools = campaign/"bin"; tools.mkdir()
    for name in ("containerlab","docker","ip","tc","ps","uname","zgrep","lsmod","modinfo","python3","ethtool","git","cat"):
        (tools/name).symlink_to(source/"tests/fixtures/x6_r1_5_2_external_stub.py")
    state=campaign/"stub-state.json";state.write_text(json.dumps({"deployed":False,"qdisc":"baseline"}))
    # The original substitute predates the stricter raw-provenance syntax.
    # Substitute only external module-command responses, before collection;
    # leave the original schema, authorization, persistence and verifier intact.
    # These are labelled synthetic observations, not rewritten historical data.
    transport=directory/"synthetic-command-transport";transport.mkdir()
    (transport/"sitecustomize.py").write_text('''from pathlib import Path
import os, subprocess
original = subprocess.Popen
class SyntheticModuleProcess(original):
    def communicate(self, *args, **kwargs):
        stdout, stderr = super().communicate(*args, **kwargs)
        name = Path(self.args[0]).name
        state = os.environ.get("X6_STUB_STATE")
        if state and (Path(state).parent / "SOURCE_TEST_ONLY.json").is_file() and name in {"lsmod", "modinfo"} and self.returncode == 0:
            stdout = ("Module                  Size  Used by\\nsch_netem 32768 0\\n" if name == "lsmod" else "name: sch_netem\\nfilename: /lib/modules/synthetic-kernel/kernel/net/sched/sch_netem.ko\\nvermagic: synthetic-kernel\\n")
        return stdout, stderr
subprocess.Popen = SyntheticModuleProcess
''')
    env.update(PATH=str(tools),PYTHONPATH=str(transport)+os.pathsep+str(source),X6_STUB_STATE=str(state),
               X6_R1_5_1_CONTROLLED_CLOCK="1",X6_R1_5_2_RUNTIME_ENABLE="1")
    worker=source/"tests/fixtures/x6_r1_5_2_test_support.py"
    for mode in ("epoch","prepare","run","verify"):
        argv=[sys.executable,"-B",str(worker),str(campaign),mode]+([] if mode=="epoch" else ["0"])
        command(argv,source,env,directory/("original-"+mode))
    return campaign, env


@pytest.fixture(scope="module")
def historical(tmp_path_factory):
    return make_history(tmp_path_factory.mktemp("historical-parent")/"fixture")[0]


def fingerprint(root):
    return {str(p):digest(p.read_bytes()) for p in root.rglob("*") if p.is_file()}


def test_legitimate_original_epoch_slot_and_raw_preservation(historical):
    before=fingerprint(historical)
    path=historical/"readiness/initial/epoch.json"
    epoch=accounting_epoch(path,historical)
    assert epoch==load(path) and epoch["schema_version"]==1
    assert accounting_context(epoch)["kernel_and_module"]["required_module_loaded"] is True
    result=accounting_slot(historical,accepted_inventory()["slots"][0])
    assert result["cleanup_verified"] is True
    assert result["row"]["predictions"]["rule"] in {"ABSTAIN","F1_ABSENT"}
    assert before==fingerprint(historical)


@pytest.mark.parametrize("field,value",[("git_commit","0"*40),("git_tree","0"*40),
    ("clean",False),("executable_inventory_sha256","0"*64)])
def test_substituted_historical_source_rejected(historical,field,value):
    source=copy.deepcopy(load(historical/"readiness/initial/epoch.json")["source"])
    source[field]=value
    with pytest.raises(ValueError):validate_original_source(source)


@pytest.mark.parametrize("field,value",[("schema_version",3),("schema_version",True),
    ("campaign_id","OTHER_CAMPAIGN"),("stage","EVALUATION")])
def test_epoch_substitution_rejected(historical,tmp_path,field,value):
    epoch=load(historical/"readiness/initial/epoch.json")
    epoch[field]=value
    epoch.pop("epoch_id");epoch["epoch_id"]=digest(canonical(epoch))
    p=tmp_path/"altered-epoch.json";p.write_bytes(canonical(epoch))
    if field=="stage":
        # Slot reconstruction rejects stage substitution via the original bound
        # epoch hash; an isolated standalone epoch has no assigned slot stage.
        slot=copy.deepcopy(accepted_inventory()["slots"][0]);slot["stage"]="EVALUATION"
        with pytest.raises(ValueError):accounting_slot(historical,slot)
    else:
        with pytest.raises(ValueError):accounting_epoch(p,historical)


def test_tampered_raw_observation_rejected(historical,tmp_path):
    epoch=load(historical/"readiness/initial/epoch.json")
    copied=tmp_path/"readiness-copy";shutil.copytree(epoch["readiness_root"],copied)
    result_path=next((copied/"raw/commands").glob("*.result.json"))
    result=load(result_path);result["stdout"]="contradictory synthetic raw observation\n"
    result_path.write_bytes(canonical(result))
    epoch["readiness_root"]=str(copied);epoch.pop("epoch_id");epoch["epoch_id"]=digest(canonical(epoch))
    p=tmp_path/"epoch.json";p.write_bytes(canonical(epoch))
    with pytest.raises(ValueError):accounting_epoch(p,historical)


def test_inventory_and_validator_selection_are_not_caller_authority(historical,tmp_path):
    epoch=load(historical/"readiness/initial/epoch.json")
    source=copy.deepcopy(epoch["source"])
    source["executable_inventory"][0]["sha256"]="0"*64
    source["executable_inventory_sha256"]=digest(canonical(source["executable_inventory"]))
    with pytest.raises(ValueError):validate_original_source(source)
    bad_slot=copy.deepcopy(accepted_inventory()["slots"][0]);bad_slot["assignment"]="F1"
    with pytest.raises(ValueError):accounting_slot(historical,bad_slot)
    forged=copy.deepcopy(epoch);forged["validator_module"]="os"
    # Even an otherwise supported schema cannot select arbitrary code: the
    # unchanged original validator rejects fields outside its exact contract.
    forged.pop("epoch_id");forged["epoch_id"]=digest(canonical(forged))
    path=tmp_path/"forged-validator.json";path.write_bytes(canonical(forged))
    with pytest.raises(ValueError):accounting_epoch(path,historical)


def action_authorization(root,request,prior,source,suffix):
    from src.orchestration.x6_r1_5_3_contract import CAMPAIGN_ID,CONTRACT_PROPOSAL_SHA256,INVENTORY_SHA256,ACTIONS
    value={"schema_version":1,"record_kind":ACTIONS["record-not-run"],
        "authorization_id":"HISTORICAL_SYNTHETIC_"+suffix,"campaign_id":CAMPAIGN_ID,
        "campaign_contract_sha256":CONTRACT_PROPOSAL_SHA256,"inventory_sha256":INVENTORY_SHA256,
        "action":"record-not-run","stage":"ACCOUNTING","campaign_root":str(root),
        "canonical_output":str(root/"accounting-actions/not-run"/("HISTORICAL_SYNTHETIC_"+suffix)),
        "source":source,"input_inventory_sha256":digest(canonical(prior["target_slots"])),
        "prior_state_sha256":digest(canonical(prior)),"issued_ns":0,"expires_ns":2**63-1,
        "boot_id":current_boot_id(),"source_test_only":True,
        "target_slot_ids":request["target_slot_ids"],"expected_accounting_heads":prior["expected_accounting_heads"],
        "epoch":prior["epoch"],"reason":request["reason"],
        "supporting_evidence_sha256":digest(canonical(prior["supporting_evidence"]))}
    value["authorization_sha256"]=digest(canonical(value))
    return value


def test_actual_current_accounting_closure_and_replay(tmp_path,monkeypatch):
    root,env=make_history(tmp_path/"integration")
    old_epoch=root/"readiness/initial/epoch.json"
    old_bytes=old_epoch.read_bytes()
    run=root/"slots"/accepted_inventory()["slots"][0]["run_id"]
    original_run=fingerprint(run)
    for tool in (root/"bin").iterdir():
        tool.unlink();tool.symlink_to(ROOT/"tests/fixtures/x6_r1_5_3_external_stub.py")
    env.update(PYTHONPATH=str(ROOT),X6_R1_5_3_RUNTIME_ENABLE="1")
    for name,value in env.items():monkeypatch.setenv(name,value)
    from src.orchestration.x6_r1_5_3_campaign import source_identity,main,_stage_state
    from src.orchestration.x6_r1_5_3_contract import observe_epoch,validate_epoch
    from src.orchestration.x6_r1_5_3_not_run import derive_prerequisites,verify_not_run_action
    from src.orchestration.x6_r1_5_3_source_test import SyntheticContext
    from src.orchestration.x6_r1_5_3_slot import slot_prerequisites
    source=source_identity()
    new_epoch,_=observe_epoch(root,"DEVELOPMENT",source,root/"readiness/current",simulation=True)
    with pytest.raises(ValueError):validate_epoch(old_epoch,root)
    first_auth=load(root/(accepted_inventory()["slots"][0]["slot_id"]+"-authorization.json"))
    with pytest.raises(ValueError):slot_prerequisites(root,accepted_inventory()["slots"][1],first_auth,boot_id=current_boot_id())
    import src.orchestration.x6_r1_5_3_campaign as campaign_module
    import src.orchestration.x6_r1_5_3_not_run as not_run_module
    from src.expansion.x6_r1_5_3_materialized_verifier import _VERIFY_PASS
    from src.orchestration.x6_r1_5_3_reconstruction import _ACTIVE
    original_stage = campaign_module._reconstruct_stage_state
    rebuilt = []
    def observed_stage(*args, **kwargs):
        rebuilt.append(args[1] if len(args)>1 else kwargs.get("stage"))
        return original_stage(*args, **kwargs)
    # Count actual reconstructions while retaining all validation.
    monkeypatch.setattr(campaign_module, "_reconstruct_stage_state", observed_stage)
    milestones = []
    def milestone(name):
        milestones.append(name)
        with (tmp_path/"integration-milestones.jsonl").open("a") as stream:
            stream.write(json.dumps({"event":name,"monotonic_ns":time.monotonic_ns(),
                                     "reconstruction_count":len(rebuilt)})+"\n")
            stream.flush(); os.fsync(stream.fileno())
    inventory=accepted_inventory()["slots"]
    for ids,reason,support,suffix in [
        ([s["slot_id"] for s in inventory[1:60]],"NOT_RUN_ENVIRONMENT_DRIFT",
         {"expected_epoch_path":str(old_epoch),"observed_epoch_path":str(new_epoch)},"DRIFT"),
        ([s["slot_id"] for s in inventory[60:]],"NOT_RUN_DEVELOPMENT_INCONCLUSIVE",
         {"epoch_path":str(new_epoch)},"INCONCLUSIVE")]:
        request={"target_slot_ids":ids,"reason":reason,"supporting_evidence":support}
        prior=derive_prerequisites(root,ids,reason,support)
        authority=action_authorization(root,request,prior,source,suffix)
        if suffix=="DRIFT":
            for key,value in [("source",first_auth["source"]),("campaign_id","FORGED"),
                              ("prior_state_sha256","0"*64)]:
                bad=copy.deepcopy(authority);bad[key]=value;bad.pop("authorization_sha256")
                bad["authorization_sha256"]=digest(canonical(bad))
                path=root/("rejected-"+key+".json");path.write_bytes(canonical(bad))
                inp=root/"request.json";inp.write_bytes(canonical(request))
                with pytest.raises(ValueError):main(["record-not-run","--campaign-root",str(root),"--input",str(inp),"--authorization",str(path)],_synthetic_context=SyntheticContext())
        inp=root/(suffix+"-request.json");inp.write_bytes(canonical(request))
        auth=root/(suffix+"-authorization.json");auth.write_bytes(canonical(authority))
        argv=["record-not-run","--campaign-root",str(root),"--input",str(inp),"--authorization",str(auth)]
        assert main(argv,_synthetic_context=SyntheticContext())==0
        milestone(suffix+"_published")
        before = len(rebuilt)
        assert verify_not_run_action(root,authority["authorization_id"])["reason"]==reason
        milestone(suffix+"_postpublication_verified")
        assert _VERIFY_PASS.get() is None and _ACTIVE.get() is None
        if suffix=="INCONCLUSIVE":
            # Reason checking and canonical prerequisites share one actual pass.
            assert len(rebuilt)==before+1
            original_derive = not_run_module.derive_prerequisites
            target = root/"accounting/slot"/ids[0]/"000001.json"
            original_bytes = target.read_bytes()
            before = len(rebuilt)
            injected = []
            def mutate_between_consumers(*args, **kwargs):
                historical_authorization = kwargs.get("historical_authorization")
                # Nested DRIFT reconstruction is independently validated unchanged.
                if historical_authorization is not None and historical_authorization.get("authorization_id")==authority["authorization_id"]:
                    assert historical_authorization["authorization_id"]=="HISTORICAL_SYNTHETIC_INCONCLUSIVE"
                    assert _VERIFY_PASS.get()["stages"].get("DEVELOPMENT") is not None
                    injected.append(historical_authorization["authorization_id"])
                    target.write_bytes(original_bytes+b" ")
                return original_derive(*args, **kwargs)
            try:
                with monkeypatch.context() as patch:
                    patch.setattr(not_run_module,"derive_prerequisites",mutate_between_consumers)
                    with pytest.raises(ValueError,match="changed reconstruction inputs"):
                        verify_not_run_action(root,authority["authorization_id"])
            finally:
                target.write_bytes(original_bytes)
            assert injected==["HISTORICAL_SYNTHETIC_INCONCLUSIVE"]
            assert len(rebuilt)==before+1  # separate invocation independently rebuilds
            assert _VERIFY_PASS.get() is None and _ACTIVE.get() is None
            milestone("INCONCLUSIVE_fresh_invocation_mutation_rejected")
        with pytest.raises((ValueError,FileExistsError)):main(argv,_synthetic_context=SyntheticContext())
        milestone(suffix+"_replay_rejected")
        if suffix=="DRIFT":
            observed=[]; recording=[True]
            def audit(name,args):
                if recording[0] and name=="subprocess.Popen" and "--original-read-only" in args[1]:
                    observed.append(list(args[1]))
            sys.addaudithook(audit)
            try:
                stage=_stage_state(root,"DEVELOPMENT")
                assert 1<=len(observed)<=3
                first=len(observed)
                assert _stage_state(root,"DEVELOPMENT")==stage
                assert first<len(observed)<=first+3
                print("Independent historical workers in two fresh closure invocations:",first,len(observed)-first)
            finally:recording[0]=False
            assert len(stage["accounting_rows"])==60 and len(stage["eligible_rows"])==1
    assert old_epoch.read_bytes()==old_bytes and fingerprint(run)==original_run
    assert not any((root/"slots"/s["run_id"]).exists() for s in inventory[1:])
    milestone("final_historical_preservation_assertions_passed")
    assert {"INCONCLUSIVE_postpublication_verified",
            "INCONCLUSIVE_fresh_invocation_mutation_rejected",
            "INCONCLUSIVE_replay_rejected",
            "final_historical_preservation_assertions_passed"} <= set(milestones)


@pytest.mark.parametrize("target",["raw","head","ledger","publication","source"])
def test_invocation_reuse_rejects_content_mutation(tmp_path,target):
    from src.orchestration.x6_r1_5_3_reconstruction import reconstruction,validated
    root=tmp_path/"campaign";root.mkdir()
    external=tmp_path/"source";external.mkdir()
    path=(external if target=="source" else root)/(target+".json")
    path.write_text('{"value":1}')
    with pytest.raises(ValueError):
        with reconstruction(root):
            assert validated(root,"test-validation",{},lambda:{"ok":True},external_roots=[external])=={"ok":True}
            path.write_text('{"value":2}')
            validated(root,"test-validation",{},lambda:{"ok":False},external_roots=[external])


def test_invocation_reuse_is_fresh_sealed_and_cycle_safe(tmp_path):
    from src.orchestration.x6_r1_5_3_reconstruction import reconstruction,validated
    root=tmp_path/"campaign";root.mkdir()
    calls=[]
    def check():calls.append(1);return {"validated":True}
    with reconstruction(root) as context:
        for _ in range(3):assert validated(root,"same",{},check)=={"validated":True}
        assert len(calls)==1
        with pytest.raises(ValueError):
            validated(tmp_path/"other","same",{},check)
        with pytest.raises(ValueError):
            validated(root,"cycle",{},lambda:validated(root,"cycle",{},check))
        assert not context.pending
        def failure():raise ValueError("independent validation failed")
        for _ in range(2):
            with pytest.raises(ValueError):validated(root,"failed",{},failure)
        assert not context.pending
        key=next(iter(context.entries));data,seal=context.entries[key]
        context.entries[key]=(b'{"validated":false}',seal)
        with pytest.raises(ValueError):validated(root,"same",{},check)
        context.entries.clear()
    with reconstruction(root):validated(root,"same",{},check)
    assert len(calls)==2


def test_coalesced_lookup_retains_one_actual_guard(tmp_path, monkeypatch):
    from src.orchestration.x6_r1_5_3_reconstruction import reconstruction, validated, _Invocation
    root = tmp_path / "campaign"; root.mkdir()
    original = _Invocation.check
    calls = []
    def observed(context):
        calls.append(context)
        return original(context)
    # This observer delegates every check to the real source/content validator.
    monkeypatch.setattr(_Invocation, "check", observed)
    validations = []
    def independent():
        validations.append(1)
        return {"independently_validated": True}
    with reconstruction(root):
        assert validated(root, "same", {}, independent)["independently_validated"]
        assert len(calls) == 2  # before lookup and after independent work
        assert validated(root, "same", {}, independent)["independently_validated"]
        assert len(calls) == 3  # one full check before accepting reused bytes
        assert len(validations) == 1
        with reconstruction(root):
            assert len(calls) == 4  # ordinary nested callers retain their guard
    assert len(calls) == 5  # fresh outer-exit content validation


def test_coalesced_guard_rejects_mutation_during_registration(tmp_path):
    from src.orchestration.x6_r1_5_3_reconstruction import reconstruction, validated
    root = tmp_path / "campaign"; root.mkdir()
    raw = root / "raw.json"; raw.write_text('{"value":1}')
    external = tmp_path / "external"; external.mkdir()
    def registration():
        raw.write_text('{"value":2}')
        yield external
    with pytest.raises(ValueError, match="changed reconstruction inputs"):
        with reconstruction(root):
            validated(root, "same", {}, lambda: {"valid": True})
            validated(root, "same", {}, lambda: {"valid": False}, external_roots=registration())


def test_coalesced_guard_rejects_mutation_during_independent_validation(tmp_path):
    from src.orchestration.x6_r1_5_3_reconstruction import reconstruction, validated
    root = tmp_path / "campaign"; root.mkdir()
    raw = root / "raw.json"; raw.write_text('{"value":1}')
    def changed():
        raw.write_text('{"value":2}')
        return {"valid": True}
    with pytest.raises(ValueError, match="changed reconstruction inputs"):
        with reconstruction(root) as context:
            try:
                validated(root, "new", {}, changed)
            finally:
                assert not context.entries and not context.pending


def test_coalesced_guard_retains_outer_exit_and_fresh_boundary(tmp_path):
    from src.orchestration.x6_r1_5_3_reconstruction import reconstruction, validated
    root = tmp_path / "campaign"; root.mkdir()
    raw = root / "raw.json"; raw.write_text('{"value":1}')
    with pytest.raises(ValueError, match="changed reconstruction inputs"):
        with reconstruction(root):
            validated(root, "same", {}, lambda: {"value": 1})
            raw.write_text('{"value":2}')
    calls = []
    with reconstruction(root):
        value = validated(root, "same", {}, lambda: calls.append(1) or {"value": 2})
    assert value == {"value": 2} and calls == [1]


def test_not_run_verification_pass_resets_after_production_failure(tmp_path):
    from src.orchestration.x6_r1_5_3_not_run import verify_not_run_action
    from src.expansion.x6_r1_5_3_materialized_verifier import _VERIFY_PASS
    from src.orchestration.x6_r1_5_3_reconstruction import _ACTIVE
    root=tmp_path/"campaign"; root.mkdir()
    for _ in range(2):
        with pytest.raises((ValueError, FileNotFoundError)):
            verify_not_run_action(root,"MISSING_AUTHORITY")
        assert _VERIFY_PASS.get() is None and _ACTIVE.get() is None
