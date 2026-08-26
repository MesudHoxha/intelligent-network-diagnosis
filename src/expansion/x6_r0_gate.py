from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from src.expansion.x5_r7_closeout_gate import verify_x5_r7_closeout
ROOT=Path(__file__).resolve().parents[2];PLAN=Path("plans/expansion/X6_R0_PERFORMANCE_FAULT_DESIGN_GATE_V1.json")
def verify_x6_r0_gate(repository_root:Path=ROOT)->dict[str,object]:
 root=Path(repository_root);verify_x5_r7_closeout(root,verify_materialized=False);plan=json.loads((root/PLAN).read_text())
 if plan["source_boundary"]!={"parent_commit":"d51fa89e4d153567efe3c2b1914ec8200dd7fda0","extension_policy":"APPEND_ONLY","runtime_inherited":False} or plan["status"]!="ACCEPTED_DESIGN_ONLY":raise ValueError("X6-R0 boundary drifted")
 if plan["features"]!=["packet_loss_ratio","round_trip_latency_ms_p95","throughput_mbps","interface_utilization_ratio","queue_drop_count","rate_limit_detected"] or [(x["code"],x["fault_type"]) for x in plan["faults"]]!=[("F1","packet_loss"),("F2","high_latency"),("F3","congestion"),("F4","bandwidth_rate_limiting")]:raise ValueError("X6 feature/taxonomy drifted")
 sig={tuple(x["signature"]) for x in plan["faults"]}
 if len(sig)!=4 or len(plan["runtime_authorization"])!=10 or any(plan["runtime_authorization"].values()) or plan["track"]!={"p9_r2_status":"PAUSED_BY_USER","next_release":"X6_R1_PACKET_LOSS"}:raise ValueError("X6 design boundary drifted")
 if plan["release_sequence"]!=["X6_R0_PERFORMANCE_FAULT_DESIGN_GATE","X6_R1_PACKET_LOSS","X6_R2_HIGH_LATENCY","X6_R3_CONGESTION","X6_R4_BANDWIDTH_RATE_LIMITING","X6_R5_PERFORMANCE_CLOSEOUT"]:raise ValueError("X6 release sequence drifted")
 if len(plan["source_bindings"])!=3:raise ValueError("X6 source bindings drifted")
 for row in plan["source_bindings"]:
  path=root/row["path"]
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]:raise ValueError("X6 binding drifted: "+row["path"])
 return plan
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--repository-root",type=Path,default=ROOT);plan=verify_x6_r0_gate(p.parse_args().repository_root);print("x6_r0_gate=VERIFIED\nfault_signatures=4/4_DISJOINT_DESIGN_PASS\nruntime_scientific_authorization=0/10_FALSE_PASS\nnext_release="+plan["track"]["next_release"]);return 0
if __name__=="__main__":raise SystemExit(main())
