"""Strict parser and actual successor boundaries; all observations are synthetic."""
import copy,json
import pytest
from src.orchestration.x6_r1_5_3_epoch import normalized_kernel,modinfo,modules,difference
from src.orchestration.x6_r1_5_1_contract import load,digest,canonical
from src.orchestration.x6_r1_5_3_contract import epoch_context,validate_epoch,accepted_inventory
from tests.unit.test_x6_r1_5_3_production_integration import isolated,worker

def observation():
    return {"kernel":"synthetic-kernel\n","kernel_config":"CONFIG_NET_SCH_NETEM=m\n",
            "module":"Module Size Used by\nsch_netem 20480 0\n",
            "module_provenance":"name: sch_netem\nfilename: /lib/modules/synthetic-kernel/kernel/net/sched/sch_netem.ko\nvermagic: synthetic-kernel SMP preempt\n"}

def test_information_not_invariant():
    original=observation(); changed=copy.deepcopy(original)
    changed["module"]="Module Size Used by\nxt_nat 12288 3\nsch_netem 32768 1 xt_nat\n"
    assert normalized_kernel(changed)==normalized_kernel(original)
    assert digest(canonical(changed))!=digest(canonical(original))

@pytest.mark.parametrize("text",[
"", "name: sch_netem\n", "name: \nfilename: /module\nvermagic: kernel\n",
"name: sch_netem\nname: sch_netem\nfilename: /module\nvermagic: kernel\n",
"name : sch_netem\nfilename: /module\nvermagic: kernel\n",
" name: sch_netem\nfilename: /module\nvermagic: kernel\n",
"name: sch_netem\n continuation\nfilename: /module\nvermagic: kernel\n",
"name: sch_netem\nfilename: /module\n continuation\nvermagic: kernel\n",
"name: sch_netem\nfilename: /module\nvermagic: kernel\n continuation\n",
"name: sch_netem\nfilename: /module\nvermagic: kernel\nunknown: value\nunknown: other\n",
"name: sch_netem\nfilename: /module\nvermagic: kernel\ndepends:\ndepends:\n",
"name: sch_netem\nfilename: /module\nvermagic: kernel\n\n",
"name: sch_netem\r\nfilename: /module\nvermagic: kernel\n",
"name: sch_netem\nfilename: /module\nvermagic: kernel\nx: a\n \n",
"name: sch_netem\nfilename: /module\nvermagic: kernel\nx: \x00\n",
"name: sch_netem\nfilename: /module\nvermagic: kernel\nnot-a-field"
])
def test_modinfo_rejects(text):
    with pytest.raises(ValueError):modinfo(text)

def test_delete_control_rejected():
    with pytest.raises(ValueError):modinfo("name: sch_netem\nfilename: /module\nvermagic: kernel\nx: \x7f\n")

def test_modinfo_optional_syntax():
    raw="name:\tsch_netem\nfilename: /module\nvermagic: kernel\ndepends: \t\nalias: first\nalias: second\nparm: one\nparm: two\nunknown: value\n  continued"
    parsed=modinfo(raw)
    assert parsed["depends"]==[""] and parsed["alias"]==["first","second"]
    assert parsed["parm"]==["one","two"] and parsed["unknown"]==["value continued"]

@pytest.mark.parametrize("text",["", "sch_netem 1 0", "Module Size Used by\nsch_netem 1 -1",
"Module Size Used by\nsch_netem 1 0\nsch_netem 1 0",
"Module Size Used by\nsch_netem NaN 0", "Module Size Used by\nsch_netem 1 0 bad,",
"Module Size Used by\n", "Module Size Used by\n\n"])
def test_lsmod_rejects(text):
    if text=="Module Size Used by\n":
        with pytest.raises(ValueError):normalized_kernel({**observation(),"module":text})
    else:
        with pytest.raises(ValueError):modules(text)

@pytest.mark.parametrize("key,value",[
("module","Module Size Used by\nother 1 0\n"),
("kernel_config","CONFIG_NET_SCH_NETEM=y\n"),
("kernel_config","CONFIG_NET_SCH_NETEM=m\nCONFIG_NET_SCH_NETEM=m\n"),
("kernel","other-kernel\n"),
("kernel","synthetic-kernel\nextra\n"),
("module_provenance","name: foreign\nfilename: /module\nvermagic: synthetic-kernel\n"),
("module_provenance","name: sch_netem\nfilename: /module\nvermagic: synthetic-kernel\n"),
("module_provenance","name: sch_netem\nfilename: /lib/modules/synthetic-kernel/kernel/net/sched/sch_netem.ko\nvermagic: wrong-kernel\n")
])
def test_required_drift_rejects(key,value):
    with pytest.raises(ValueError):normalized_kernel({**observation(),key:value})

def test_precedence_preserves_source_and_boot():
    context={"boot_id":"original","source":"same","kernel":normalized_kernel(observation())}
    assert difference(context,context) is None
    assert difference(context,{**context,"boot_id":"new"})=="NOT_RUN_OPERATIONAL_FAILURE"
    assert difference(context,{**context,"source":"new"})=="NOT_RUN_ENVIRONMENT_DRIFT"
    assert difference(context,{**context,"source":"new","boot_id":"new"})=="NOT_RUN_ENVIRONMENT_DRIFT"

def test_actual_admission_and_verifier_informational_difference(tmp_path):
    root=tmp_path/"synthetic-normalized-pair";env=isolated(root)
    result=worker(root,env,"epoch");assert result.returncode==0,result.stderr
    original=(root/"readiness/initial/epoch.json").read_bytes()
    for index in (0,1):
        state=json.loads((root/"stub-state.json").read_text())
        state["module_observation"]="Module Size Used by\nxt_nat 12288 3\nsch_netem 32768 1 xt_nat"
        (root/"stub-state.json").write_bytes(canonical(state))
        result=worker(root,env,"prepare",index);assert result.returncode==0,result.stderr
        result=worker(root,env,"run",index);assert result.returncode==0,result.stderr
        result=worker(root,env,"verify",index);assert result.returncode==0,result.stderr
    assert (root/"readiness/initial/epoch.json").read_bytes()==original
    slot=accepted_inventory()["slots"][1]
    assert load(root/"slots"/slot["run_id"]/"terminal/terminal.json")["status"]=="SLOT_COMPLETE"

def test_actual_admission_missing_module_spent_no_deployment(tmp_path):
    root=tmp_path/"synthetic-missing";env=isolated(root)
    result=worker(root,env,"epoch");assert result.returncode==0,result.stderr
    result=worker(root,env,"prepare",0);assert result.returncode==0,result.stderr
    state=json.loads((root/"stub-state.json").read_text());state["bad_module"]=True
    (root/"stub-state.json").write_bytes(canonical(state))
    result=worker(root,env,"run",0);assert result.returncode!=0
    slot=accepted_inventory()["slots"][0]
    assert not (root/"slots"/slot["run_id"]).exists()
    assert not any(call[0]=="containerlab" and call[1]=="deploy" for call in json.loads((root/"stub-state.json").read_text())["calls"])


def test_actual_epoch_projection_and_source_tamper(tmp_path):
    root=tmp_path/"synthetic-projection";env=isolated(root)
    result=worker(root,env,"epoch");assert result.returncode==0,result.stderr
    path=root/"readiness/initial/epoch.json";original=path.read_bytes();value=load(path)
    for key in ("projection","source"):
        bad=copy.deepcopy(value)
        if key=="projection":bad["normalization"]["invariants"]["required_module_loaded"]=False
        else:bad["source"]["git_commit"]="0"*40
        unsigned=dict(bad);unsigned.pop("epoch_id");bad["epoch_id"]=digest(canonical(unsigned))
        path.write_bytes(canonical(bad))
        with pytest.raises(ValueError):validate_epoch(path,root)
        path.write_bytes(original)
    assert path.read_bytes()==original
