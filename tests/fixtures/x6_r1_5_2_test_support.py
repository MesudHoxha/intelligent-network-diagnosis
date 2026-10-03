"""Synthetic fixture worker. All networking executable names resolve to substitutes."""
from pathlib import Path
import json,os,sys
from src.orchestration.x6_r1_5_1_contract import canonical,digest,current_boot_id,load
from src.orchestration.x6_r1_5_1_durable import save
from src.orchestration.x6_r1_5_2_campaign import source_identity
from src.orchestration.x6_r1_5_2_contract import accepted_inventory,observe_epoch,runtime_bindings,CAMPAIGN_ID,CONTRACT_PROPOSAL_SHA256,INVENTORY_SHA256
from src.orchestration.x6_r1_5_2_source_test import SyntheticContext
from src.orchestration.x6_r1_5_2_campaign import main

root=Path(sys.argv[1]).resolve();mode=sys.argv[2]
SyntheticContext().validate(root)
# Controlled monotonic context is shared across successive synthetic processes.
from src.orchestration import x6_r1_5_1_durable as clock
points=[]
def collect(value):
 if isinstance(value,dict):
  if type(value.get("monotonic_ns")) is int and value.get("boot_id")==current_boot_id(): points.append(value["monotonic_ns"])
  for item in value.values():collect(item)
 elif isinstance(value,list):
  for item in value:collect(item)
for path in root.rglob("*.json"):
 try:collect(json.loads(path.read_text()))
 except (ValueError,OSError):pass
clock._CLOCK_NS=max(points,default=0)
source=source_identity()
if mode=="epoch":
 path,value=observe_epoch(root,"DEVELOPMENT",source,root/"readiness/initial",simulation=True)
 print(str(path));raise SystemExit(0)
index=int(sys.argv[3]);slot=accepted_inventory()["slots"][index]
if mode=="prepare":
 path=root/"readiness/initial/epoch.json";epoch=load(path)
 value={"schema_version":1,"record_kind":"X6_R1_5_2_CAMPAIGN_SLOT_AUTHORIZATION_V1","authorization_id":slot["slot_id"]+"_SYNTHETIC",
        "campaign_id":CAMPAIGN_ID,"campaign_contract_sha256":CONTRACT_PROPOSAL_SHA256,"inventory_sha256":INVENTORY_SHA256,
        "slot":slot,"run_id":slot["run_id"],"output_root":str(root/"slots"/slot["run_id"]),"source":source,
        "issued_ns":0,"expires_ns":2**63-1,"boot_id":current_boot_id(),"scope":"N0_CONTROL" if slot["assignment"]=="N0" else "F1_PACKET_LOSS_SINGLE_FAULT",
        "artifact_inventory":["raw","parsed","state","terminal"],"source_test_only":True,"runtime_image":runtime_bindings()["image"],"runtime_bindings":runtime_bindings(),
        "epoch":{"path":str(path),"sha256":digest(path.read_bytes()),"epoch_id":epoch["epoch_id"]},"development_freeze_sha256":None}
 value["authorization_sha256"]=digest(canonical(value))
 save(root/(slot["slot_id"]+"-authorization.json"),value,exclusive=True)
 save(root/(slot["slot_id"]+"-input.json"),{"slot":slot,"slot_id":slot["slot_id"]},exclusive=True)
 raise SystemExit(0)
if mode in {"run","run-pause-running","run-terminal-event-crash","signal-child","run-pause-window","run-authorization-crash","run-consumed-crash","run-reservation-crash","run-admission-crash"}:
    from src.orchestration.x6_r1_5_2_launcher import launch
    os.environ["X6_R1_5_2_SOURCE_TEST_MODE"]=mode
    raise SystemExit(launch(root,root/(slot["slot_id"]+"-input.json"),
                           root/(slot["slot_id"]+"-authorization.json"),
                           timeout_seconds=90,synthetic=True))
args=[{"run":"run-slot","verify":"verify-slot","recover":"recover-slot"}[mode],"--campaign-root",str(root),"--input",str(root/(slot["slot_id"]+"-input.json"))]
if mode=="run":args += ["--authorization",str(root/(slot["slot_id"]+"-authorization.json"))]
raise SystemExit(main(args,_synthetic_context=SyntheticContext()))
