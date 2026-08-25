from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from src.expansion.x5_gate import verify_x5_gate
ROOT=Path(__file__).resolve().parents[2]; PLAN=Path("plans/expansion/X5_R1_OSPF_ADJACENCY_FAILURE_V1.json")
SIGNATURE={"ospf_adjacency_full":False,"ospf_route_advertised":False,"ospf_route_installed":False,"route_filter_allows_prefix":True}
def verify_x5_r1_gate(repository_root:Path=ROOT)->dict[str,object]:
 root=Path(repository_root); plan=json.loads((root/PLAN).read_text());
 if verify_x5_gate(root)["track"]["next_release"]!="X5_R1_OSPF_ADJACENCY_FAILURE": raise ValueError("X5-R0 parent drifted")
 if plan["source_boundary"]!={"parent_commit":"4b610bf057ee7f3f6017243b207e3fe9a73a2b35","extension_policy":"APPEND_ONLY","runtime_inherited":False}: raise ValueError("X5-R1 boundary drifted")
 if plan["slice"]["signature"]!=SIGNATURE or plan["slice"]["fault_type"]!="dynamic_routing_adjacency_failure": raise ValueError("X5-R1 C4 signature drifted")
 for row in plan["source_bindings"]:
  path=root/row["path"]
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]: raise ValueError("X5-R1 source binding drifted: "+row["path"])
 flags=plan["runtime_authorization"]
 if {k for k,v in flags.items() if v}!={"containerlab_execution","network_mutation","new_evidence_collection","method_prediction"}: raise ValueError("X5-R1 authorization drifted")
 return plan
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--repository-root",type=Path,default=ROOT); verify_x5_r1_gate(p.parse_args().repository_root);print("x5_r0_gate=VERIFIED\nx5_r1_gate=VERIFIED\nc4_signature=FALSE_FALSE_FALSE_TRUE_PASS\nsource_bindings=8/8_HASH_BOUND_PASS\nnext_release=X5_R2_ROUTE_FILTERING_OR_ADVERTISEMENT_PROBLEM");return 0
if __name__=="__main__":raise SystemExit(main())
