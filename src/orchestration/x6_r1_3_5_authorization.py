"""Future-authorization and durable one-attempt ledger primitives (source-only)."""
from __future__ import annotations
import hashlib, json, os
from pathlib import Path
from time import monotonic_ns
from typing import Mapping
from src.orchestration.x6_r1_3_3_baseline_only_runner import write_json_fsync
from src.orchestration.x6_r1_3_5_baseline_provenance import X6R135Error, canonical_bytes, sha256

SCOPE="BASELINE_ONLY_QUALIFICATION"
FALSE_VECTOR={"containerlab":False,"measurement":False,"f1_revalidation":False,"f2":False,"f3":False,"f4":False,"dataset":False,"ml_hybrid":False,"api":False,"p9_r2":False}
def fail(message:str)->None: raise X6R135Error("X6-R1.3.5 authorization: "+message)
def validate(record: Mapping[str,object], *, identity: Mapping[str,object], output_root: str, now_ns: int) -> dict[str,object]:
    required={"schema_version","authorization_id","scope","source_identity","output_root","issued_ns","expires_ns","source_test_only","prohibitions","authorization_sha256"}
    if set(record)!=required or record.get("schema_version")!=1 or not isinstance(record.get("authorization_id"),str) or not record["authorization_id"] or record.get("scope")!=SCOPE or record.get("source_identity")!=dict(identity) or record.get("output_root")!=output_root or record.get("source_test_only") is not True: fail("authorization schema/binding drift")
    if not isinstance(record.get("issued_ns"),int) or not isinstance(record.get("expires_ns"),int) or record["issued_ns"]>now_ns or record["expires_ns"]<now_ns: fail("authorization validity window drift")
    if set(record.get("prohibitions",{}))!=set(FALSE_VECTOR) or any(record["prohibitions"].get(k) is not True for k in FALSE_VECTOR): fail("authorization prohibition drift")
    unsigned=dict(record); digest=unsigned.pop("authorization_sha256")
    if not isinstance(digest,str) or digest!=sha256(canonical_bytes(unsigned)): fail("authorization hash drift")
    return dict(record)
def consume(root: Path, *, authorization: Mapping[str,object], run_id:str, output_root:str, identity:Mapping[str,object], validated_ns:int, consumed_ns:int)->dict[str,object]:
    if not run_id or consumed_ns<validated_ns: fail("ledger ordering drift")
    path=Path(root)/(str(authorization["authorization_id"])+".json")
    if path.exists(): fail("authorization already consumed")
    row={"schema_version":1,"authorization_id":authorization["authorization_id"],"authorization_sha256":authorization["authorization_sha256"],"run_id":run_id,"output_root":output_root,"source_identity":dict(identity),"validated_monotonic_ns":validated_ns,"consumed_monotonic_ns":consumed_ns,"pid":os.getpid(),"previous_state":"VALIDATED","state":"CONSUMED"}
    row["ledger_sha256"]=sha256(canonical_bytes(row)); write_json_fsync(path,row); return row
def verify_ledger(row:Mapping[str,object], *, authorization:Mapping[str,object], run_id:str, output_root:str, identity:Mapping[str,object])->None:
    unsigned=dict(row); digest=unsigned.pop("ledger_sha256",None)
    if digest!=sha256(canonical_bytes(unsigned)) or row.get("authorization_id")!=authorization.get("authorization_id") or row.get("authorization_sha256")!=authorization.get("authorization_sha256") or row.get("run_id")!=run_id or row.get("output_root")!=output_root or row.get("source_identity")!=dict(identity) or row.get("previous_state")!="VALIDATED" or row.get("state")!="CONSUMED" or not isinstance(row.get("validated_monotonic_ns"),int) or not isinstance(row.get("consumed_monotonic_ns"),int) or row["consumed_monotonic_ns"]<row["validated_monotonic_ns"]: fail("ledger semantic drift")

def transition(root:Path, *, run_id:str, authorization:Mapping[str,object], previous:str, current:str, order:int, monotonic:int)->dict[str,object]:
    if order <= 0 or monotonic < 0 or not previous or not current: fail("journal transition malformed")
    row={"schema_version":1,"run_id":run_id,"authorization_id":authorization["authorization_id"],"authorization_sha256":authorization["authorization_sha256"],"order":order,"previous_state":previous,"state":current,"monotonic_ns":monotonic,"source_test_only":True}
    row["transition_sha256"]=sha256(canonical_bytes(row)); write_json_fsync(Path(root)/"state"/("transition-%03d.json"%order),row); return row
def verify_transitions(rows:list[Mapping[str,object]], *, run_id:str, authorization:Mapping[str,object], first_action_ns:int)->None:
    required=[("ABSENT","LOADED"),("LOADED","VALIDATED"),("VALIDATED","CONSUMPTION_PLANNED"),("CONSUMPTION_PLANNED","CONSUMED_DURABLE"),("CONSUMED_DURABLE","STATEFUL_ACTION_PERMITTED")]
    if len(rows)!=len(required): fail("journal transition count drift")
    previous=-1
    for index,(row,pair) in enumerate(zip(rows,required),1):
        unsigned=dict(row); digest=unsigned.pop("transition_sha256",None)
        if row.get("order")!=index or (row.get("previous_state"),row.get("state"))!=pair or row.get("run_id")!=run_id or row.get("authorization_id")!=authorization.get("authorization_id") or row.get("authorization_sha256")!=authorization.get("authorization_sha256") or digest!=sha256(canonical_bytes(unsigned)) or not isinstance(row.get("monotonic_ns"),int) or row["monotonic_ns"]<previous: fail("journal transition ordering drift")
        previous=row["monotonic_ns"]
    if previous>first_action_ns: fail("stateful action preceded durable consumption")
