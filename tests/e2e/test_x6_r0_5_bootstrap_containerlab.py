from __future__ import annotations
import os
from pathlib import Path
import pytest
from src.campaign.phase6_runner import containerlab_containers,require_success,run_command
from src.orchestration.x6_r0_5_bootstrap_smoke import run_bootstrap_smoke
ROOT=Path(__file__).resolve().parents[2];TOPOLOGY=ROOT/"labs/topologies/x6_r1_packet_loss_r0_5/topology.clab.yml"
pytestmark=[pytest.mark.infrastructure,pytest.mark.skipif(os.environ.get("IND_RUN_X6_R0_5_BOOTSTRAP")!="1",reason="set IND_RUN_X6_R0_5_BOOTSTRAP=1 after sudo -v")]
def test_x6_r0_5_topology_bootstrap_smoke(tmp_path):
 assert containerlab_containers(repository_root=ROOT,command_executor=run_command)==[]; deployed=False
 try:
  require_success(run_command(["sudo","-n","containerlab","deploy","-t",str(TOPOLOGY)],ROOT),"X6-R0.5 deploy");deployed=True;result=run_bootstrap_smoke(Path(os.environ.get("IND_X6_R0_5_BOOTSTRAP_ROOT",str(tmp_path))));assert result["status"]=="TOPOLOGY_BOOTSTRAP_VALIDATED_NON_SCIENTIFIC"
 finally:
  if deployed:require_success(run_command(["sudo","-n","containerlab","destroy","-t",str(TOPOLOGY),"--cleanup"],ROOT),"X6-R0.5 cleanup")
  assert containerlab_containers(repository_root=ROOT,command_executor=run_command,topology_path=TOPOLOGY)==[]
