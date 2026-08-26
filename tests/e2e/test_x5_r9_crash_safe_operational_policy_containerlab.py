from __future__ import annotations
import hashlib,json,os
from pathlib import Path
import pytest
from src.campaign.phase6_runner import containerlab_containers,require_success,run_command
from src.orchestration.x5_r9_c5_runtime_safety_revalidation_runner import run_x5_r9_experiment
ROOT=Path(__file__).resolve().parents[2];TOPOLOGY=ROOT/"labs/topologies/x5_r5_c5_operational_policy/topology.clab.yml";BASELINE=ROOT/"labs/topologies/x5_r5_c5_operational_policy/scripts/validate_baseline.sh";pytestmark=[pytest.mark.infrastructure,pytest.mark.skipif(os.environ.get("IND_RUN_X5_R9_E2E")!="1",reason="set IND_RUN_X5_R9_E2E=1 after sudo -v")]
def test_x5_r9_crash_safe_operational_policy_c5_cycle(tmp_path:Path)->None:
 assert containerlab_containers(repository_root=ROOT,command_executor=run_command)==[];deployed=False
 try:
  require_success(run_command(["sudo","-n","containerlab","deploy","-t",str(TOPOLOGY)],ROOT),"X5-R9 deploy");deployed=True;result=run_x5_r9_experiment(Path(os.environ.get("IND_X5_R9_EVIDENCE_ROOT",str(tmp_path))),BASELINE);root=Path(result["experiment_directory"]);evidence=json.loads((root/"parsed/evidence_v4.json").read_text());vector=json.loads((root/"parsed/feature_vector_v2.json").read_text());diagnosis=json.loads((root/"diagnosis/diagnosis_result_v2.json").read_text());journal=json.loads((root/"mutation/mutation_journal.json").read_text());effective=json.loads((root/"mutation/mutation_effectiveness.json").read_text());restore=json.loads((root/"mutation/restoration_record.json").read_text());image=json.loads((root/"validation/runtime_image_identity.json").read_text())
  assert result["status"]=="COMPLETED" and journal["events"][0]["state"]=="PLANNED" and journal["events"][0]["detail"]=="durable_before_forward_command" and journal["actions"][0]["status"]=="RESTORED" and effective["status"]=="MUTATION_EFFECTIVE" and restore["status"]=="RESTORATION_CONFIRMED" and restore["standalone_replay"]["status"]=="STANDALONE_REPLAY_APPLIED" and image["expected_digest_match"] is True
  assert {name:item["value"] for name,item in evidence["observations"].items()}=={"ospf_adjacency_full":True,"ospf_route_advertised":False,"ospf_route_installed":False,"route_filter_allows_prefix":False} and all(item["availability"]=="observed" for item in vector["values"].values()) and diagnosis["status"]=="diagnosed" and diagnosis["explanation_refs"]==["rule:R_X5_OSPF_002"]
  for collector in evidence["collector_runs"]:
   for artifact in collector["raw_artifacts"]:
    path=root/artifact["path"];assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==artifact["sha256"]
 finally:
  if deployed:require_success(run_command(["sudo","-n","containerlab","destroy","-t",str(TOPOLOGY),"--cleanup"],ROOT),"X5-R9 cleanup")
  assert containerlab_containers(repository_root=ROOT,command_executor=run_command,topology_path=TOPOLOGY)==[]
