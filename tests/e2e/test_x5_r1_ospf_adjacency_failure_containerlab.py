from __future__ import annotations
import json, os
from pathlib import Path
import pytest
from src.campaign.phase6_runner import containerlab_containers, require_success, run_command
from src.orchestration.x5_ospf_adjacency_failure_experiment_runner import run_x5_r1_experiment
ROOT=Path(__file__).resolve().parents[2]; TOPOLOGY=ROOT/"labs/topologies/x5_r1_ospf_adjacency_failure/topology.clab.yml"; BASELINE=ROOT/"labs/topologies/x5_r1_ospf_adjacency_failure/scripts/validate_baseline.sh"
pytestmark=[pytest.mark.infrastructure,pytest.mark.skipif(os.environ.get("IND_RUN_X5_R1_E2E")!="1",reason="set IND_RUN_X5_R1_E2E=1 after sudo -v")]
def test_real_ospf_adjacency_failure_cycle(tmp_path:Path)->None:
 assert containerlab_containers(repository_root=ROOT,command_executor=run_command)==[]; deployed=False
 try:
  require_success(run_command(["sudo","-n","containerlab","deploy","-t",str(TOPOLOGY)],ROOT),"X5-R1 deploy"); deployed=True
  result=run_x5_r1_experiment(Path(os.environ.get("IND_X5_R1_EVIDENCE_ROOT",str(tmp_path))),BASELINE); root=Path(result["experiment_directory"]); evidence=json.loads((root/"parsed/evidence_v4.json").read_text()); diagnosis=json.loads((root/"diagnosis/diagnosis_result_v2.json").read_text())
  assert result["status"]=="COMPLETED" and {k:v["value"] for k,v in evidence["observations"].items()}=={"ospf_adjacency_full":False,"ospf_route_advertised":False,"ospf_route_installed":False,"route_filter_allows_prefix":True}; assert diagnosis["prediction"]["fault_type"]=="dynamic_routing_adjacency_failure"
 finally:
  if deployed: require_success(run_command(["sudo","-n","containerlab","destroy","-t",str(TOPOLOGY),"--cleanup"],ROOT),"X5-R1 cleanup")
  assert containerlab_containers(repository_root=ROOT,command_executor=run_command,topology_path=TOPOLOGY)==[]
