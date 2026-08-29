from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import yaml
from src.expansion.x6_r0_4_gate import verify_x6_r0_4_f1_runtime_parameter_freeze
ROOT=Path(__file__).resolve().parents[2];PLAN=Path("plans/expansion/X6_R0_5_TOPOLOGY_BOOTSTRAP_CORRECTION_V1.json");CONTEXT=Path("labs/topologies/x6_r1_packet_loss_r0_5/bootstrap_context_v1.json")
class X6R05GateError(ValueError):pass
def require(v:bool,m:str)->None:
 if not v:raise X6R05GateError(m)
def verify_x6_r0_5(repository_root:Path=ROOT)->dict[str,object]:
 root=Path(repository_root);verify_x6_r0_4_f1_runtime_parameter_freeze(root); plan=json.loads((root/PLAN).read_text());context=json.loads((root/CONTEXT).read_text());old=root/context["historical_topology"]["path"];new=root/context["topology"]["path"]
 require(hashlib.sha256(old.read_bytes()).hexdigest()==context["historical_topology"]["sha256"],"historical X6-R0.4 topology drifted")
 require(new!=old and hashlib.sha256(new.read_bytes()).hexdigest()==context["topology"]["sha256"],"X6-R0.5 corrected topology hash drifted")
 parsed=yaml.safe_load(new.read_text()); nodes=parsed["topology"]["nodes"]; require(parsed["name"]=="x6r1","Containerlab name drifted")
 require("ip route replace 10.61.3.2/32 via 10.61.1.1 dev eth1 src 10.61.1.2" in nodes["hosta"]["exec"] and "ip route replace 10.61.1.2/32 via 10.61.3.1 dev eth1 src 10.61.3.2" in nodes["hostb"]["exec"],"endpoint bootstrap routes drifted")
 require(not any("default" in command for node in ("hosta","hostb") for command in nodes[node]["exec"]),"endpoint default route bootstrap is forbidden")
 require(all("ip route replace" in command for node in ("r1","r2","r3") for command in nodes[node]["exec"] if command.startswith("ip route")),"router static routes must be idempotent")
 inherited=json.loads((root/context["inherited_r0_4_context"]).read_text()); require(inherited["topology"]["mutation_owner"]=={"node":"r2","container":"clab-x6r1-r2","interface":"eth2","peer":"r3:eth1","direction":"hosta_to_hostb"} and inherited["qdisc"]["loss_percent"]=="10.000000" and inherited["rule"]["rule_id"]=="R_X6_PERFORMANCE_001","unrelated X6-R0.4 freeze drifted")
 auth=context["bootstrap_only_authorization"];require(auth["containerlab_bootstrap_smoke"] and not any(auth[k] for k in ("netem_or_pfifo","iperf3","measurement_windows","threshold_freeze","evidence_v4","rule_or_diagnosis","scientific_claim")),"X6-R0.5 authorization drifted")
 bindings=plan["source_bindings"];require(len(bindings)==6,"X6-R0.5 needs six bindings")
 for row in bindings:
  path=root/row["path"];require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==row["sha256"],"binding drifted: "+row["path"])
 return plan
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--repository-root",type=Path,default=ROOT);args=p.parse_args();verify_x6_r0_5(args.repository_root);print("x6_r0_5=VERIFIED");print("source_bindings=6/6_HASH_BOUND_PASS");print("runtime_scientific_authorization=0/7_FALSE_PASS");return 0
if __name__=="__main__":raise SystemExit(main())
