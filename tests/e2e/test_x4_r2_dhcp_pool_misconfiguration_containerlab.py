from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.campaign.phase6_runner import containerlab_containers, require_success, run_command
from src.orchestration.x4_dhcp_pool_misconfiguration_experiment_runner import run_x4_r2_experiment


ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "labs/topologies/x4_r1_dhcp_server_unavailable/topology.clab.yml"
BASELINE = ROOT / "labs/topologies/x4_r1_dhcp_server_unavailable/scripts/validate_baseline.sh"
SCENARIO = ROOT / "scenarios/expansion/X4_R2_DHCP_POOL_MISCONFIGURATION.yml"
pytestmark = [pytest.mark.infrastructure, pytest.mark.skipif(os.environ.get("IND_RUN_X4_R2_E2E") != "1", reason="set IND_RUN_X4_R2_E2E=1 to run X4-R2 real DHCP lifecycle")]


def test_real_dhcp_pool_misconfiguration_cycle_diagnoses_restores_and_cleans_up(tmp_path: Path) -> None:
    assert containerlab_containers(repository_root=ROOT, command_executor=run_command) == []
    deployed = False
    try:
        require_success(run_command(["sudo", "-n", "containerlab", "deploy", "-t", str(TOPOLOGY)], ROOT), "X4-R2 Containerlab deployment"); deployed = True
        require_success(run_command(["bash", str(BASELINE)], ROOT), "X4-R2 image and healthy fresh-DHCP preflight")
        output = Path(os.environ["IND_X4_R2_EVIDENCE_ROOT"]) if os.environ.get("IND_X4_R2_EVIDENCE_ROOT") else tmp_path / "experiments"
        result = run_x4_r2_experiment(SCENARIO, output, BASELINE, experiment_id="x4-r2-real-dhcp-pool-misconfiguration")
        root = Path(str(result["experiment_directory"])); evidence = json.loads((root / "parsed/evidence_v4.json").read_text(encoding="utf-8")); diagnosis = json.loads((root / "diagnosis/diagnosis_result_v2.json").read_text(encoding="utf-8")); configuration = json.loads((root / "raw/v4/service_state_collector_v2/dhcp_pool_configuration.json").read_text(encoding="utf-8"))
        assert result["status"] == "COMPLETED" and result["restoration_confirmed"] is True and result["baseline_valid_after"] is True
        assert evidence["topology_context_id"] == "x4_top_01_dhcp_dns_service_security_dhcp_flow_context_v1"
        assert {name: row["value"] for name, row in evidence["observations"].items()} == {"dhcp_server_reachable": True, "dhcp_lease_obtained": False, "dhcp_lease_matches_expected_scope": False, "dns_server_reachable": True, "dns_query_succeeds": True, "dns_answer_matches_expected": True, "service_process_running": True, "service_port_reachable": True, "service_flow_blocked_by_policy": False}
        assert "dhcp-range=10.40.0.0,static" in str(configuration["command_result"]["stdout"])
        assert diagnosis["prediction"]["fault_type"] == "dhcp_pool_misconfiguration"
    finally:
        if deployed: require_success(run_command(["sudo", "-n", "containerlab", "destroy", "-t", str(TOPOLOGY), "--cleanup"], ROOT), "X4-R2 Containerlab cleanup")
        assert containerlab_containers(repository_root=ROOT, command_executor=run_command, topology_path=TOPOLOGY) == []
