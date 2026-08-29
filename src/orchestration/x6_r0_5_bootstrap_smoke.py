from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Callable
from src.collection.x6_r0_5_route_bootstrap import validate_management_default,validate_route_get
from src.fault_injection.phase6_common import utc_now,write_json_atomic
from src.runtime.subprocesses import run_capture
ROOT=Path(__file__).resolve().parents[2]
Executor=Callable[[list[str]],dict[str,object]]
def capture(command:list[str])->dict[str,object]:
 result=run_capture(command,timeout_seconds=15);return {"command":command,"return_code":result.returncode,"stdout":result.stdout,"stderr":result.stderr,"captured_at_utc":utc_now()}
def _ok(row:dict[str,object],label:str)->None:
 if row["return_code"]!=0:raise RuntimeError(label+": "+str(row["stderr"]))
def run_bootstrap_smoke(output_root:Path,*,executor:Executor=capture)->dict[str,object]:
 root=Path(output_root)/("x6-r0-5-bootstrap-"+utc_now().replace(":","").replace("+00:00","Z"));root.mkdir(parents=True,exist_ok=False);(root/"raw").mkdir();context=json.loads((ROOT/"labs/topologies/x6_r1_packet_loss_r0_5/bootstrap_context_v1.json").read_text())
 identity=executor(["docker","image","inspect","ind-linux:0.1"]);_ok(identity,"image identity")
 routes={"hosta_forward":(["docker","exec","clab-x6r1-hosta","ip","-j","route","get","10.61.3.2"],context["endpoint_routes"]["hosta"]),"hostb_reverse":(["docker","exec","clab-x6r1-hostb","ip","-j","route","get","10.61.1.2"],context["endpoint_routes"]["hostb"]),"r1_forward":(["docker","exec","clab-x6r1-r1","ip","-j","route","get","10.61.3.2"],{"destination":"10.61.3.2","via":"10.61.12.2","dev":"eth2","src":"10.61.12.1"}),"r2_forward":(["docker","exec","clab-x6r1-r2","ip","-j","route","get","10.61.3.2"],{"destination":"10.61.3.2","via":"10.61.23.2","dev":"eth2","src":"10.61.23.1"}),"r2_reverse":(["docker","exec","clab-x6r1-r2","ip","-j","route","get","10.61.1.2"],{"destination":"10.61.1.2","via":"10.61.12.1","dev":"eth1","src":"10.61.12.2"}),"r3_reverse":(["docker","exec","clab-x6r1-r3","ip","-j","route","get","10.61.1.2"],{"destination":"10.61.1.2","via":"10.61.23.1","dev":"eth1","src":"10.61.23.2"})}; records={"image_identity":identity}
 records["management_defaults"]={}
 for host in ("hosta","hostb"):
  row=executor(["docker","exec","clab-x6r1-"+host,"ip","-j","route","show","default"]);records["management_defaults"][host]=row;validate_management_default(row)
 for name,(command,expected) in routes.items():
  row=executor(command);validate_route_get(row,destination=expected["destination"].split("/")[0],via=expected["via"],dev=expected["dev"],src=expected["src"]);records[name]=row
 records["forwarding"]=[executor(["docker","exec","clab-x6r1-"+node,"sysctl","-n","net.ipv4.ip_forward"]) for node in ("r1","r2","r3")]
 if any(row["return_code"]!=0 or str(row["stdout"]).strip()!="1" for row in records["forwarding"]):raise RuntimeError("forwarding unavailable")
 records["bidirectional"]=[executor(["docker","exec","clab-x6r1-hosta","ping","-c","1","-W","2","10.61.3.2"]),executor(["docker","exec","clab-x6r1-hostb","ping","-c","1","-W","2","10.61.1.2"])]
 for row in records["bidirectional"]:_ok(row,"experiment reachability")
 qdisc=executor(["docker","exec","clab-x6r1-r2","/usr/sbin/tc","-j","qdisc","show","dev","eth2"]);_ok(qdisc,"qdisc query"); rows=json.loads(str(qdisc["stdout"]));
 if not isinstance(rows,list) or len(rows)!=1 or rows[0].get("kind")!="noqueue" or rows[0].get("handle")!="0:":raise RuntimeError("qdisc is not frozen noqueue pre-state")
 filters=executor(["docker","exec","clab-x6r1-r2","/usr/sbin/tc","-j","filter","show","dev","eth2"]);_ok(filters,"qdisc filter query")
 try: filter_rows=json.loads(str(filters["stdout"]))
 except json.JSONDecodeError as error: raise RuntimeError("qdisc filter output malformed") from error
 if filter_rows != []:raise RuntimeError("qdisc has unexpected filters")
 records["qdisc"]={"state":qdisc,"filters":filters};write_json_atomic(root/"bootstrap_provenance.json",{"schema_version":1,"status":"TOPOLOGY_BOOTSTRAP_VALIDATED_NON_SCIENTIFIC","topology_sha256":context["topology"]["sha256"],"records":records,"raw_sha256":hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest(),"collected_at_utc":utc_now()});return {"status":"TOPOLOGY_BOOTSTRAP_VALIDATED_NON_SCIENTIFIC","directory":str(root)}
