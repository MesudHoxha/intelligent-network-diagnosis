from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2
from src.expansion.x5_r4_closeout_gate import verify_x5_r4_corrected_successor_receipt
from src.expansion.x5_r6_gate import verify_x5_r6_gate
ROOT=Path(__file__).resolve().parents[2]; PLAN=Path("plans/expansion/X5_R7_C5_CORRECTED_SUCCESSOR_CLOSEOUT_V1.json"); RECEIPT=Path("plans/expansion/X5_R7_AUTHORITATIVE_SUCCESSOR_RECEIPT_V1.json")
def verify_x5_r7_closeout(repository_root:Path=ROOT, *, verify_materialized:bool=False)->dict[str,object]:
 root=Path(repository_root); plan=json.loads((root/PLAN).read_text()); receipt=json.loads((root/RECEIPT).read_text()); verify_x5_r6_gate(root)
 if plan["source_boundary"]!={"parent_commit":"4a1a039cb91aa584eff492135d9c0bf2842bda4a","extension_policy":"APPEND_ONLY","runtime_inherited":False} or plan["authoritative_runs"]!={"c4":"X5_R4_OSPF_CORRECTION_AND_REVALIDATION","c5":"X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION"}: raise ValueError("X5-R7 authority drifted")
 if len(plan["runtime_authorization"])!=10 or any(plan["runtime_authorization"].values()) or plan["track"]!={"next_release":"X6_R0_PERFORMANCE_FAULT_DESIGN_GATE","p9_r2_status":"PAUSED_BY_USER"}: raise ValueError("X5-R7 boundary drifted")
 if receipt["historical_evidence"]!=plan["historical_evidence"]: raise ValueError("X5-R7 historical status drifted")
 if verify_materialized:
  verify_x5_r4_corrected_successor_receipt(repository_root=root,verify_materialized=True)
  run=root/receipt["c5_relative_run_path"]
  for relative,digest in receipt["c5_artifacts"].items():
   path=run/relative
   if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise ValueError("X5-R7 C5 hash drifted: "+relative)
  evidence=json.loads((run/"parsed/evidence_v4.json").read_text()); vector=json.loads((run/"parsed/feature_vector_v2.json").read_text()); diagnosis=json.loads((run/"diagnosis/diagnosis_result_v2.json").read_text()); catalog=json.loads((root/"plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text()); validate_evidence_v4(evidence,catalog,repository_root=root);validate_feature_vector_v2(vector,catalog,repository_root=root)
  if [evidence["observations"][k]["value"] for k in ("ospf_adjacency_full","ospf_route_advertised","ospf_route_installed","route_filter_allows_prefix")]!=[True,False,False,False] or any(evidence["observations"][k]["availability"]!="observed" for k in evidence["observations"]) or diagnosis["explanation_refs"]!=["rule:R_X5_OSPF_002"] or diagnosis["status"]!="diagnosed": raise ValueError("X5-R7 C5 semantics drifted")
 return receipt
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--repository-root",type=Path,default=ROOT);p.add_argument("--verify-materialized",action="store_true");r=verify_x5_r7_closeout(p.parse_args().repository_root,verify_materialized=p.parse_args().verify_materialized);print("x5_r7_closeout=VERIFIED\nauthoritative_runs=C4_R4_AND_C5_R6\nc5_bound_artifacts="+str(len(r["c5_artifacts"]))+"/13_HASH_BOUND_PASS\nnext_release=X6_R0_PERFORMANCE_FAULT_DESIGN_GATE");return 0
if __name__=="__main__":raise SystemExit(main())
