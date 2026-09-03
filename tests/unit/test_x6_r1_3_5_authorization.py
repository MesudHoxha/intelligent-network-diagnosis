import pytest
from pathlib import Path
from src.orchestration import x6_r1_3_5_authorization as a
from src.orchestration.x6_r1_3_5_baseline_provenance import canonical_bytes, sha256, X6R135Error
from src.orchestration import x6_r1_3_5_baseline_lifecycle as l
from src.orchestration import x6_r1_3_5_baseline_provenance as p
from src.expansion import x6_r1_3_5_materialized_verifier as v
IDENTITY={"git_commit":"a"*40,"git_tree":"b"*40,"topology_sha256":"c"*64,"image_id":"d"}
def auth():
    row={"schema_version":1,"authorization_id":"source-test-only","scope":a.SCOPE,"source_identity":IDENTITY,"output_root":"run","issued_ns":1,"expires_ns":9,"source_test_only":True,"prohibitions":{k:True for k in a.FALSE_VECTOR}}
    row["authorization_sha256"]=sha256(canonical_bytes(row)); return row
def test_b1_validates_then_consumes_once(tmp_path:Path):
    value=a.validate(auth(),identity=IDENTITY,output_root="run",now_ns=2); ledger=a.consume(tmp_path,authorization=value,run_id="r",output_root="run",identity=IDENTITY,validated_ns=2,consumed_ns=3); a.verify_ledger(ledger,authorization=value,run_id="r",output_root="run",identity=IDENTITY)
    with pytest.raises(X6R135Error): a.consume(tmp_path,authorization=value,run_id="r2",output_root="run",identity=IDENTITY,validated_ns=2,consumed_ns=3)
@pytest.mark.parametrize("field,value",[("scope","F1"),("output_root","other"),("expires_ns",0),("authorization_sha256","0"*64)])
def test_b1_authorization_adversaries_fail_closed(field,value):
    value_row=auth(); value_row[field]=value
    with pytest.raises(X6R135Error): a.validate(value_row,identity=IDENTITY,output_root="run",now_ns=2)
def test_b11_durable_transition_ordering(tmp_path:Path):
    value=a.validate(auth(),identity=IDENTITY,output_root="run",now_ns=2)
    states=[("ABSENT","LOADED"),("LOADED","VALIDATED"),("VALIDATED","CONSUMPTION_PLANNED"),("CONSUMPTION_PLANNED","CONSUMED_DURABLE"),("CONSUMED_DURABLE","STATEFUL_ACTION_PERMITTED")]
    rows=[a.transition(tmp_path,run_id="r",authorization=value,previous=x,current=y,order=i,monotonic=i) for i,(x,y) in enumerate(states,1)]
    a.verify_transitions(rows,run_id="r",authorization=value,first_action_ns=6)
    rows[-1]["monotonic_ns"]=0
    with pytest.raises(X6R135Error): a.verify_transitions(rows,run_id="r",authorization=value,first_action_ns=6)
def test_b1_lifecycle_inventory_and_terminal(tmp_path:Path, monkeypatch):
    value=auth(); path=tmp_path/"authorization.json"; path.write_bytes(canonical_bytes(value)); root=tmp_path/"run"
    recorder=l.initialize_b1(root,authorization_path=path,ledger_root=tmp_path/"ledger",run_id="r",output_root="run",identity=IDENTITY,now_ns=2)
    values={f:{"availability":"observed","value":0 if f != "throughput_mbps" else 100} for f in l.NUMERIC_FEATURES}; monkeypatch.setattr(l,"derive_window",lambda *args,**kwargs: values)
    def executor(command):
        if command==p.COMMANDS["qdisc"]: out='[{"kind":"noqueue","handle":"0:"}]'
        elif command==p.COMMANDS["filters"]: out="[]"
        elif command[-1].endswith("tx_bytes") or command[-1].endswith("rx_bytes"): out="1"
        elif command[-1]=="speed": out="1000"
        else: out="[]"
        return {"return_code":0,"stdout":out,"stderr":""}
    l.collect_thirty(recorder,executor=executor,speed_mbps=1000)
    l.finalize_inventory(root)
    result=v.derive_b1_terminal(root,run_id="r",output_root="run",identity=IDENTITY); assert result["terminal_status"] == "PROSPECTIVE_COMPLETE_RECOVERY_REPLAY_REQUIRED", result
    (root/"state/authorization_ledger.json").unlink()
    assert v.derive_b1_terminal(root,run_id="r",output_root="run",identity=IDENTITY)["terminal_status"] == "VERIFICATION_FAILED"
