from __future__ import annotations
import hashlib,json,os
from pathlib import Path
import pytest
from src.campaign.phase6_runner import containerlab_containers,require_success,run_command
from src.orchestration.x6_r1_packet_loss_runner import run_x6_r1,verify_x6_r0_7_host_netem_prerequisite
ROOT=Path(__file__).resolve().parents[2];TOPOLOGY=ROOT/"labs/topologies/x6_r1_packet_loss_r0_5/topology.clab.yml"
pytestmark=[pytest.mark.infrastructure,pytest.mark.skipif(os.environ.get("IND_RUN_X6_R1_E2E")!="1",reason="set IND_RUN_X6_R1_E2E=1 after sudo -v")]
def test_x6_r1_packet_loss_controlled_pilot(tmp_path):
 assert containerlab_containers(repository_root=ROOT,command_executor=run_command)==[];deployed=False
 try:
  prerequisite=verify_x6_r0_7_host_netem_prerequisite(lambda command:run_command(command,ROOT));image=run_command(["docker","image","inspect","ind-linux:0.1"],ROOT);require_success(image,"X6-R1 pre-deployment image identity");require_success(run_command(["sudo","-n","containerlab","deploy","-t",str(TOPOLOGY)],ROOT),"X6-R1 deploy");deployed=True;result=run_x6_r1(Path(os.environ.get("IND_X6_R1_EVIDENCE_ROOT",str(tmp_path))),predeployment_image_identity=image,predeployment_netem_prerequisite=prerequisite);root=Path(result["experiment_directory"])
  manifest=json.loads((root/"manifest.json").read_text());effect=json.loads((root/"mutation/mutation_effectiveness.json").read_text());diagnosis=json.loads((root/"diagnosis/diagnosis_result_v2.json").read_text());predicates=json.loads((root/"diagnosis/conditional_predicates.json").read_text());restoration=json.loads((root/"mutation/restoration_record.json").read_text());replay=json.loads((root/"mutation/standalone_replay.json").read_text());hashes=json.loads((root/"validation/raw_hashes.json").read_text())
  assert result["status"]==manifest["status"]=="AUTHORITATIVE" and 6<=effect["lost_packet_count"]<=25 and effect["pfifo_drop_delta"]==0 and effect["status"]=="MUTATION_EFFECTIVE"
  assert diagnosis["status"]=="diagnosed" and diagnosis["explanation_refs"]==["rule:R_X6_PERFORMANCE_001"] and all(predicates["predicates"].values())
  assert restoration["status"]=="RESTORATION_CONFIRMED" and replay["status"]=="STANDALONE_REPLAY_CONFIRMED"
  assert all(hashlib.sha256((root/path).read_bytes()).hexdigest()==digest for path,digest in hashes["artifacts"].items())
 finally:
  if deployed: require_success(run_command(["sudo","-n","containerlab","destroy","-t",str(TOPOLOGY),"--cleanup"],ROOT),"X6-R1 cleanup")
  assert containerlab_containers(repository_root=ROOT,command_executor=run_command,topology_path=TOPOLOGY)==[]
