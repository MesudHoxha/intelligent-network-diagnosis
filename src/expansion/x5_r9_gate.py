from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from src.expansion.x5_r8_gate import verify_x5_r8_runtime_safety_gate
ROOT=Path(__file__).resolve().parents[2];PLAN=Path("plans/expansion/X5_R9_C5_RUNTIME_SAFETY_REVALIDATION_V1.json");SIGNATURE={"ospf_adjacency_full":True,"ospf_route_advertised":False,"ospf_route_installed":False,"route_filter_allows_prefix":False}
def verify_x5_r9_gate(repository_root:Path=ROOT)->dict[str,object]:
 root=Path(repository_root);parent=verify_x5_r8_runtime_safety_gate(root)
 if parent["track"]["next_release"]!="X5_R9_C5_RUNTIME_SAFETY_REVALIDATION":raise ValueError("X5-R8 parent sequence drifted")
 plan=json.loads((root/PLAN).read_text())
 if plan.get("source_boundary")!={"parent_commit":"1b3b5ddd9dba42048d44567b351aea9669ebbcec","extension_policy":"APPEND_ONLY","runtime_inherited":False} or plan.get("slice",{}).get("signature")!=SIGNATURE or plan["slice"].get("rule_id")!="R_X5_OSPF_002":raise ValueError("X5-R9 boundary drifted")
 if plan["mutation"].get("planned_journal_before_attempt_required") is not True or plan["mutation"].get("forbidden_action")!="remove network 10.51.3.0/24 area 0":raise ValueError("X5-R9 safety drifted")
 if not all(plan["acceptance"].get(name) is True for name in ("actual_raw_hashes_required","partial_mutation_recovery_required","standalone_replay_required","expected_digest_equality_required_when_recorded")):raise ValueError("X5-R9 acceptance drifted")
 if plan["track"]!={"next_release":"X5_R10_C5_CRASH_SAFE_AUTHORITATIVE_CLOSEOUT","x6_status":"PAUSED_PENDING_X5_R10","p9_r2_status":"PAUSED_BY_USER"}:raise ValueError("X5-R9 track drifted")
 if len(plan["source_bindings"])!=7:raise ValueError("X5-R9 requires seven source bindings")
 for row in plan["source_bindings"]:
  path=root/row["path"]
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]:raise ValueError("X5-R9 source binding drifted: "+row["path"])
 return plan
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--repository-root",type=Path,default=ROOT);plan=verify_x5_r9_gate(p.parse_args().repository_root);print("x5_r9_gate=VERIFIED\nc5_signature=TRUE_FALSE_FALSE_FALSE_PASS\nsource_bindings="+str(len(plan["source_bindings"]))+"/7_HASH_BOUND_PASS\nnext_release=X5_R10_C5_CRASH_SAFE_AUTHORITATIVE_CLOSEOUT");return 0
if __name__=="__main__":raise SystemExit(main())
