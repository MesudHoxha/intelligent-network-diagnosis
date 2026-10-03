"""Observed outer-process receipts; all external tools are controlled substitutes."""
import copy,json
from pathlib import Path
import pytest
from src.orchestration.x6_r1_5_1_contract import canonical,digest,load
from src.orchestration.x6_r1_5_2_contract import accepted_inventory
from src.orchestration.x6_r1_5_2_launcher import verify_launcher,receipt_directory,sealed
from tests.unit.test_x6_r1_5_2_production_integration import isolated,worker


def prepared(tmp_path):
    root=tmp_path/"synthetic-launcher";env=isolated(root)
    assert worker(root,env,"epoch").returncode==0
    assert worker(root,env,"prepare",0).returncode==0
    slot=accepted_inventory()["slots"][0]
    auth=load(root/(slot["slot_id"]+"-authorization.json"))
    return root,env,slot,auth


@pytest.fixture
def successful(tmp_path):
    root,env,slot,auth=prepared(tmp_path)
    result=worker(root,env,"run",0)
    assert result.returncode==0,result.stderr
    assert worker(root,env,"verify",0).returncode==0
    return root,env,slot,auth


def test_actual_successful_launcher_and_replay_rejection(successful):
    root,env,slot,auth=successful
    assert verify_launcher(root,auth)["child_return_code"]==0
    directory=receipt_directory(root,slot["run_id"])
    before=(directory/"terminal.json").read_bytes()
    assert worker(root,env,"run",0).returncode!=0
    assert (directory/"terminal.json").read_bytes()==before


def test_actual_failed_cli_exit_is_observed(tmp_path):
    root,env,slot,auth=prepared(tmp_path)
    state=json.loads((root/"stub-state.json").read_text());state["fail_iperf"]=True
    (root/"stub-state.json").write_text(json.dumps(state))
    result=worker(root,env,"run",0)
    assert result.returncode!=0
    status=verify_launcher(root,auth)
    assert status["kind"]=="NORMAL_EXIT" and status["child_return_code"]==1
    assert worker(root,env,"verify",0).returncode==0


def test_actual_signal_termination_is_not_inferred(tmp_path):
    root,env,slot,auth=prepared(tmp_path)
    assert worker(root,env,"signal-child",0).returncode!=0
    status=verify_launcher(root,auth)
    assert status["kind"]=="OBSERVED_SIGNAL" and status["child_return_code"]==-15
    assert not (root/"slots"/slot["run_id"]).exists()


@pytest.mark.parametrize("field",["status","argv","source","run","evidence","process","symlink","missing-binding","clock","timeout-type","streams","terminal-schema","parent-boot","parent-pid","argv-path","argv-type","start-schema","capture-type"])
def test_rebound_receipt_contradictions_rejected(successful,field):
    root,env,slot,auth=successful;directory=receipt_directory(root,slot["run_id"])
    start=load(directory/"started.json");terminal=load(directory/"terminal.json")
    if field=="timeout-type":start["timeout_seconds"]=True
    elif field=="streams":terminal["status"]["stdout"]=None;terminal["status"]["stderr"]=None
    elif field=="terminal-schema":terminal["schema_version"]=2
    elif field=="start-schema":start["schema_version"]=True
    elif field=="capture-type":terminal["status"]["wrapper_return_code"]=False
    elif field=="parent-boot":start["launcher_process"]["boot_id"]="foreign-boot"
    elif field=="parent-pid":start["launcher_process"]["pid"]=0
    elif field in {"argv-path","argv-type"}:
        start["child_arguments"][4]="relative-input.json" if field=="argv-path" else 7
        start["argv"]=start["argv"][:3]+start["child_arguments"]
    elif field=="missing-binding":terminal["run_evidence"].pop()
    elif field=="clock":terminal["observed"]["monotonic_ns"]=float(terminal["observed"]["monotonic_ns"])
    elif field=="process":
        child=load(directory/"child.json");child["process"]["pid"]+=100
        child.pop("receipt_sha256");(directory/"child.json").write_bytes(canonical(sealed(child)))
        terminal["child_sha256"]=digest((directory/"child.json").read_bytes())
    elif field=="symlink":
        moved=directory.with_name(directory.name+"-substituted");directory.rename(moved);directory.symlink_to(moved)
        with pytest.raises(ValueError,match="unsafe"):verify_launcher(root,auth)
        return
    elif field=="status":terminal["status"]["child_return_code"]=1;terminal["status"]["wrapper_return_code"]=1
    elif field=="argv":start["argv"][2]="foreign.module"
    elif field=="source":start["source"]["git_commit"]="f"*40
    elif field=="run":start["run_id"]="foreign-run"
    elif field=="evidence":terminal["run_evidence"][0]["sha256"]="f"*64
    if field in {"argv","source","run","timeout-type","parent-boot","parent-pid","argv-path","argv-type","start-schema"}:
        start.pop("receipt_sha256");(directory/"started.json").write_bytes(canonical(sealed(start)))
        terminal["started_sha256"]=digest((directory/"started.json").read_bytes())
        child=load(directory/"child.json")
        child["started_sha256"]=terminal["started_sha256"];child["child_arguments"]=start["child_arguments"]
        child["parent_pid"]=start["launcher_process"]["pid"]
        child.pop("receipt_sha256");(directory/"child.json").write_bytes(canonical(sealed(child)))
        terminal["child_sha256"]=digest((directory/"child.json").read_bytes())
    terminal.pop("receipt_sha256");(directory/"terminal.json").write_bytes(canonical(sealed(terminal)))
    with pytest.raises(ValueError):verify_launcher(root,auth)


@pytest.mark.parametrize("kind",["missing","unknown","interrupted"])
def test_unavailable_status_never_satisfies_known_exit(successful,kind):
    root,env,slot,auth=successful;directory=receipt_directory(root,slot["run_id"])
    if kind=="missing":(directory/"terminal.json").unlink()
    else:
        row=load(directory/"terminal.json")
        row["status"]={"kind":"LAUNCHER_INTERRUPTED" if kind=="interrupted" else "UNAVAILABLE_CHILD_STATUS",
                       "child_return_code":None,"wrapper_return_code":None}
        row.pop("receipt_sha256");(directory/"terminal.json").write_bytes(canonical(sealed(row)))
    with pytest.raises(ValueError,match="status"):verify_launcher(root,auth)
    assert verify_launcher(root,auth,require_known=False)["child_return_code"] is None


def test_actual_terminal_receipt_persistence_interruption(tmp_path,monkeypatch):
    root,env,slot,auth=prepared(tmp_path)
    from src.orchestration import x6_r1_5_2_launcher as launcher
    for key,value in env.items():monkeypatch.setenv(key,value)
    real=launcher.save
    def fail_terminal(path,value,**kwargs):
        if Path(path).name=="terminal.json":
            raise OSError("synthetic failure before outer terminal publication")
        return real(path,value,**kwargs)
    monkeypatch.setattr(launcher,"save",fail_terminal)
    with pytest.raises(OSError,match="outer terminal"):
        launcher.launch(root,root/(slot["slot_id"]+"-input.json"),
                        root/(slot["slot_id"]+"-authorization.json"),
                        timeout_seconds=90,synthetic=True)
    assert load(root/"slots"/slot["run_id"]/"terminal/terminal.json")["status"]=="SLOT_COMPLETE"
    with pytest.raises(ValueError,match="unavailable"):verify_launcher(root,auth)
    assert verify_launcher(root,auth,require_known=False)["child_return_code"] is None


def test_actual_launcher_interrupt_records_unknown_and_never_resumes(tmp_path):
    import os,signal,subprocess,sys,time
    from tests.unit.test_x6_r1_5_2_production_integration import WORKER,ROOT
    from src.orchestration.x6_r1_5_1_durable import alive
    root,env,slot,auth=prepared(tmp_path)
    process=subprocess.Popen([sys.executable,str(WORKER),str(root),"run-pause-window","0"],
                             cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,shell=False)
    try:
        deadline=time.monotonic()+20
        while not (root/"synthetic-window-pause.json").exists():
            assert process.poll() is None
            assert time.monotonic()<deadline
            time.sleep(.01)
        os.kill(process.pid,signal.SIGINT)
        stdout,stderr=process.communicate(timeout=10)
        assert process.returncode!=0
        directory=receipt_directory(root,slot["run_id"])
        status=verify_launcher(root,auth,require_known=False)
        assert status["kind"]=="LAUNCHER_INTERRUPTED" and status["child_return_code"] is None
        child=load(directory/"child.json")["process"]
        deadline=time.monotonic()+5
        while alive(child):
            assert time.monotonic()<deadline
            time.sleep(.01)
        run=root/"slots"/slot["run_id"]
        assert not list((run/"raw/windows").glob("*.json"))
        before=(directory/"terminal.json").read_bytes()
        result=worker(root,env,"recover",0);assert result.returncode==0,result.stderr
        assert (directory/"terminal.json").read_bytes()==before
        assert not list((run/"raw/windows").glob("*.json"))
        with pytest.raises(ValueError,match="known"):verify_launcher(root,auth)
    finally:
        if process.poll() is None:
            process.kill();process.communicate(timeout=10)


def test_live_foreign_command_is_never_signalled(tmp_path):
    import os,subprocess,sys
    from src.orchestration.x6_r1_5_1_durable import process_identity,save
    from src.orchestration.x6_r1_5_1_contract import current_boot_id
    from src.orchestration.x6_r1_5_2_launcher import stop_registered_child
    directory=tmp_path/"isolated-receipt"
    child=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],shell=False)
    try:
        process={"pid":child.pid,"start_ticks":Path("/proc/"+str(child.pid)+"/stat").read_text().rsplit(")",1)[1].split()[19],
                 "boot_id":current_boot_id()}
        save(directory/"started.json",sealed({"launcher_process":process_identity(),
                                             "argv":[sys.executable,"-m","foreign.module"]}),exclusive=True)
        save(directory/"child.json",sealed({"started_sha256":digest((directory/"started.json").read_bytes()),
                                           "parent_pid":os.getpid(),"process":process}),exclusive=True)
        with pytest.raises(ValueError,match="live child ownership"):
            stop_registered_child(directory,{})
        assert child.poll() is None
    finally:
        child.terminate();child.wait(timeout=5)


def test_consumed_preentry_interruption_preserves_original_status(tmp_path):
    root,env,slot,auth=prepared(tmp_path)
    assert worker(root,env,"run-consumed-crash",0).returncode==247
    directory=receipt_directory(root,slot["run_id"])
    before=(directory/"terminal.json").read_bytes()
    assert verify_launcher(root,auth)["child_return_code"]==-9
    result=worker(root,env,"recover",0);assert result.returncode==0,result.stderr
    assert worker(root,env,"verify",0).returncode==0
    assert (directory/"terminal.json").read_bytes()==before
    assert verify_launcher(root,auth)["child_return_code"]==-9
    run=root/"slots"/slot["run_id"]
    assert not (run/"raw").exists()
    assert load(run/"terminal/terminal.json")["lifecycle_entered"] is False


def test_actual_bounded_timeout_retains_unknown_original_status(tmp_path,monkeypatch):
    root,env,slot,auth=prepared(tmp_path)
    from src.orchestration.x6_r1_5_2_launcher import launch
    for key,value in env.items():monkeypatch.setenv(key,value)
    monkeypatch.setenv("X6_R1_5_2_SOURCE_TEST_MODE","run-pause-window")
    assert launch(root,root/(slot["slot_id"]+"-input.json"),
                  root/(slot["slot_id"]+"-authorization.json"),timeout_seconds=5,synthetic=True)==124
    status=verify_launcher(root,auth,require_known=False)
    assert status["kind"]=="UNAVAILABLE_CHILD_STATUS"
    assert status["child_return_code"] is None and status["wrapper_return_code"]==124
    assert "timed out" in status["stderr"]
    with pytest.raises(ValueError):verify_launcher(root,auth)
