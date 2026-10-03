"""Actual campaign production boundaries exercised only with synthetic external tools."""
import json,os,subprocess,sys,copy
from pathlib import Path
import pytest
from src.orchestration.x6_r1_5_1_contract import canonical,digest,load
from src.orchestration.x6_r1_5_2_contract import accepted_inventory
ROOT=Path(__file__).resolve().parents[2]
STUB=ROOT/"tests/fixtures/x6_r1_5_2_external_stub.py"
WORKER=ROOT/"tests/fixtures/x6_r1_5_2_test_support.py"


def worker(root,env,mode,index=None):
 argv=[sys.executable,str(WORKER),str(root),mode]+([] if index is None else [str(index)])
 result=subprocess.run(argv,cwd=ROOT,env=env,text=True,capture_output=True,shell=False,timeout=90)
 attempt=len(list(root.glob("invocation-*.json")))+1
 prefix=root/f"invocation-{attempt:04d}"
 prefix.with_suffix(".stdout.log").write_text(result.stdout)
 prefix.with_suffix(".stderr.log").write_text(result.stderr)
 prefix.with_suffix(".json").write_text(json.dumps({"argv":argv,"return_code":result.returncode,"mode":mode,"index":index})+"\n")
 return result


def isolated(root):
 root.mkdir();(root/"SOURCE_TEST_ONLY.json").write_bytes(canonical({"source_test_only":True,"root":str(root)}))
 bin=root/"bin";bin.mkdir()
 for name in ("containerlab","docker","ip","tc","ps","uname","zgrep","lsmod","modinfo","python3","ethtool","git","cat"):(bin/name).symlink_to(STUB)
 state=root/"stub-state.json";state.write_text(json.dumps({"deployed":False,"qdisc":"baseline"}))
 return {**os.environ,"PATH":str(bin),"PYTHONPATH":str(ROOT),"X6_STUB_STATE":str(state),"X6_R1_5_1_CONTROLLED_CLOCK":"1","X6_R1_5_2_RUNTIME_ENABLE":"1"}


def test_real_schema_preflight_lifecycle_and_independent_replay_n0_f1(tmp_path):
 root=tmp_path/"synthetic-campaign";env=isolated(root)
 result=worker(root,env,"epoch");assert result.returncode==0,result.stderr
 for index in (0,1):
  if index==1:
   state=json.loads((root/"stub-state.json").read_text());state["diagnostic_abstention"]=True
   (root/"stub-state.json").write_text(json.dumps(state))
  prepared=worker(root,env,"prepare",index);assert prepared.returncode==0,prepared.stderr
  result=worker(root,env,"run",index);assert result.returncode==0,result.stderr
  result=worker(root,env,"verify",index);assert result.returncode==0,result.stderr
  slot=accepted_inventory()["slots"][index];run=root/"slots"/slot["run_id"]
  assert load(run/"terminal/terminal.json")["status"]=="SLOT_COMPLETE"
  assert len(list((run/"raw/windows").glob("*.json")))==16
  assert load(run/"parsed/campaign-row.json")["eligible"] is True
  if index==1:
   assert load(run/"terminal/terminal.json")["diagnosis"]=="ABSTAIN"
   assert all((run/"raw/windows"/(wid+".json")).is_file() for wid in ("R01","R02","R03"))
  replay=worker(root,env,"run",index);assert replay.returncode!=0
 calls=json.loads((root/"stub-state.json").read_text())["calls"]
 assert sum(name=="containerlab" and args[0]=="deploy" for name,*args in calls)==2



def test_compressed_external_client_cannot_finish_before_ping_admission(tmp_path):
    import time
    root=tmp_path/"synthetic-overlap";env=isolated(root)
    state=json.loads((root/"stub-state.json").read_text());state["deployed"]=True;state["window_generation"]=1
    (root/"stub-state.json").write_text(json.dumps(state))
    client=subprocess.Popen(["docker","exec","clab-x6r1-hosta","/usr/bin/iperf3","-c","10.61.3.2","-J"],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,shell=False)
    try:
        import fcntl
        def observed_generation():
            with (root/"stub-state.json").open() as stream:
                fcntl.flock(stream.fileno(),fcntl.LOCK_SH)
                return json.load(stream).get("client_generation",0)
        deadline=time.monotonic()+5
        while observed_generation()<1:
            assert time.monotonic()<deadline;time.sleep(.001)
        assert client.poll() is None
        ping=subprocess.run(["docker","exec","clab-x6r1-hosta","/usr/bin/ping","10.61.3.2"],env=env,capture_output=True,text=True,shell=False,timeout=5)
        assert ping.returncode==0
        out,err=client.communicate(timeout=5);assert client.returncode==0,err
        assert json.loads(out)["end"]["sum_received"]["bits_per_second"]==7750000000
    finally:
        if client.poll() is None:client.kill();client.communicate()


def test_partial_fault_failure_keeps_mutation_restoration_denominator(tmp_path):
 root=tmp_path/"synthetic-partial-fault";env=isolated(root)
 assert worker(root,env,"epoch").returncode==0
 assert worker(root,env,"prepare",0).returncode==0
 result=worker(root,env,"run",0);assert result.returncode==0,result.stderr
 state=json.loads((root/"stub-state.json").read_text());state["fail_fault_iperf"]=True
 (root/"stub-state.json").write_text(json.dumps(state))
 assert worker(root,env,"prepare",1).returncode==0
 result=worker(root,env,"run",1);assert result.returncode!=0
 result=worker(root,env,"verify",1);assert result.returncode==0,result.stderr
 from src.expansion.x6_r1_5_2_materialized_verifier import verify_slot
 from src.expansion.x6_r1_5_2_dataset import accounting_row
 from src.expansion.x6_r1_5_2_analysis import metrics
 from src.orchestration.x6_r1_5_2_durable import read_events
 slot=accepted_inventory()["slots"][1];run=root/"slots"/slot["run_id"]
 verified=verify_slot(root,slot);row=accounting_row(slot,read_events(root,"slot",slot["slot_id"]),verified)
 assert row["entered_mutation"] is True and row["restoration_confirmed"] is False
 assert row["predictions"]=={} and "predictors" not in row and row["target_verified"] is False
 assert not list((run/"raw/windows").glob("R*.json"))
 rows=[{"block_id":f"EVAL_B{i:02d}","assignment":label,"accounting_status":"NOT_RUN_OPERATIONAL_FAILURE","predictions":{}} for i in range(1,21) for label in ("N0","F1")]
 rows[1].update({key:row[key] for key in ("entered_mutation","restoration_confirmed","target_verified","lifecycle_verified","eligible")})
 assert metrics(rows,"rule")["restoration_rate"]==0


def test_orphan_terminal_is_preserved_and_recovery_issues_no_commands(tmp_path):
 root=tmp_path/"synthetic-orphan-terminal";env=isolated(root)
 assert worker(root,env,"epoch").returncode==0
 assert worker(root,env,"prepare",0).returncode==0
 result=worker(root,env,"run-terminal-event-crash",0);assert result.returncode!=0
 slot=accepted_inventory()["slots"][0];run=root/"slots"/slot["run_id"];path=run/"terminal/terminal.json";before=path.read_bytes()
 assert load(path)["status"]=="SLOT_COMPLETE"
 from src.orchestration.x6_r1_5_2_durable import read_events
 from src.orchestration.x6_r1_5_1_contract import digest
 assert read_events(root,"slot",slot["slot_id"])[-1]["state"]=="RUNNING"
 assert load(root/"injected-terminal-publication-failure.json")["terminal_sha256"]==digest(before)
 result=worker(root,env,"verify",0);assert result.returncode!=0 and "slot not final" in result.stderr
 calls=json.loads((root/"stub-state.json").read_text())["calls"]
 result=worker(root,env,"recover",0);assert result.returncode!=0 and "orphan terminal publication" in result.stderr
 assert json.loads((root/"stub-state.json").read_text())["calls"]==calls
 assert path.read_bytes()==before and not (run/"state/recovery.json").exists()
 result=worker(root,env,"run",0);assert result.returncode!=0
 assert path.read_bytes()==before


def test_actual_cli_holds_campaign_lock_through_running(tmp_path):
 import time,pytest
 from src.orchestration.x6_r1_5_2_durable import lock_campaign
 root=tmp_path/"synthetic-running-lock";env=isolated(root)
 assert worker(root,env,"epoch").returncode==0
 assert worker(root,env,"prepare",0).returncode==0
 argv=[sys.executable,str(WORKER),str(root),"run-pause-running","0"]
 process=subprocess.Popen(argv,cwd=ROOT,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False)
 try:
  deadline=time.monotonic()+20
  while not (root/"synthetic-running-pause.json").exists():
   assert process.poll() is None,"worker exited before RUNNING pause"
   assert time.monotonic()<deadline,"worker did not reach RUNNING pause"
   time.sleep(.01)
  with pytest.raises(BlockingIOError):lock_campaign(root)
 finally:
  (root/"synthetic-running-release").write_text("release isolated source-test pause\n")
  stdout,stderr=process.communicate(timeout=90)
  (root/"running-worker.stdout.log").write_text(stdout);(root/"running-worker.stderr.log").write_text(stderr)
  (root/"running-worker-return-code.json").write_text(json.dumps({"argv":argv,"return_code":process.returncode})+"\n")
 assert process.returncode==0,stderr
 result=worker(root,env,"verify",0);assert result.returncode==0,result.stderr
 fd=lock_campaign(root);os.close(fd)
