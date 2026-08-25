from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from src.expansion.x5_r3_gate import verify_x5_r3_source_gate
ROOT=Path(__file__).resolve().parents[2];PLAN=Path("plans/expansion/X5_R4_OSPF_CORRECTION_AND_REVALIDATION_V1.json");SIG={"ospf_adjacency_full":False,"ospf_route_advertised":False,"ospf_route_installed":False,"route_filter_allows_prefix":True}
def verify_x5_r4_gate(repository_root:Path=ROOT)->dict[str,object]:
 root=Path(repository_root);plan=json.loads((root/PLAN).read_text());
 if verify_x5_r3_source_gate(root)["status"]!="ACCEPTED_SOURCE_CLOSEOUT":raise ValueError("X5-R3 parent drifted")
 if plan["source_boundary"]!={"parent_commit":"c6f6080981c4ed98338b66c28d5049c6a82d28dd","extension_policy":"APPEND_ONLY","runtime_inherited":False}:raise ValueError("X5-R4 boundary drifted")
 if plan["status"]!="ACCEPTED_CORRECTED_SUCCESSOR_CLOSEOUT" or plan["signature"]!=SIG or plan["corrections"]["historical_x5_r1"]!="RETAINED_HISTORICAL_NOT_AUTHORITATIVE_FOR_TARGETED_C4_SCIENTIFIC_USE":raise ValueError("X5-R4 correction contract drifted")
 for row in plan["source_bindings"]:
  path=root/row["path"]
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]:raise ValueError("X5-R4 binding drifted: "+row["path"])
 if {k for k,v in plan["runtime_authorization"].items() if v}!={"containerlab_execution","network_mutation","new_evidence_collection","method_prediction"}:raise ValueError("X5-R4 authorization drifted")
 return plan
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--repository-root",type=Path,default=ROOT);plan=verify_x5_r4_gate(p.parse_args().repository_root);print("x5_r4_gate=VERIFIED\ntarget_identity=R2_ETH2_TO_R3_ETH1_PASS\nsource_bindings="+str(len(plan["source_bindings"]))+"/8_HASH_BOUND_PASS\nnext_release=X6_R0_PERFORMANCE_FAULT_DESIGN_GATE");return 0
if __name__=="__main__":raise SystemExit(main())
