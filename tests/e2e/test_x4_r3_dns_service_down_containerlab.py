from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.campaign.phase6_runner import containerlab_containers, require_success, run_command
from src.orchestration.x4_dns_service_down_experiment_runner import run_x4_r3_experiment


ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "labs/topologies/x4_r3_dns_service_unavailable/topology.clab.yml"
BASELINE = ROOT / "labs/topologies/x4_r3_dns_service_unavailable/scripts/validate_baseline.sh"
SCENARIO = ROOT / "scenarios/expansion/X4_R3_DNS_SERVICE_DOWN.yml"
pytestmark = [pytest.mark.infrastructure, pytest.mark.skipif(os.environ.get("IND_RUN_X4_R3_E2E") != "1", reason="set IND_RUN_X4_R3_E2E=1 to run canonical X4-R3 DNS lifecycle")]


def test_real_dns_service_down_cycle_diagnoses_restores_and_cleans_up(tmp_path: Path) -> None:
    assert containerlab_containers(repository_root=ROOT, command_executor=run_command) == []
    deployed = False
    try:
        require_success(run_command(["sudo", "-n", "containerlab", "deploy", "-t", str(TOPOLOGY)], ROOT), "X4-R3 Containerlab deployment"); deployed = True
        require_success(run_command(["bash", str(BASELINE)], ROOT), "X4-R3 image/tools and healthy DNS preflight")
        output = Path(os.environ["IND_X4_R3_EVIDENCE_ROOT"]) if os.environ.get("IND_X4_R3_EVIDENCE_ROOT") else tmp_path / "experiments"
        result = run_x4_r3_experiment(SCENARIO, output, BASELINE, experiment_id="x4-r3-real-dns-service-down")
        root = Path(str(result["experiment_directory"])); evidence = json.loads((root / "parsed/evidence_v4.json").read_text(encoding="utf-8")); diagnosis = json.loads((root / "diagnosis/diagnosis_result_v2.json").read_text(encoding="utf-8")); query = json.loads((root / "raw/v4/service_state_collector_v3/dns_query_response.json").read_text(encoding="utf-8"))
        assert result["status"] == "COMPLETED" and result["restoration_confirmed"] is True and result["baseline_valid_after"] is True
        assert result["release_id"] == "X4_R3_DNS_SERVICE_DOWN" and result["compatibility_alias"] == "X4_R3_DNS_SERVICE_UNAVAILABLE"
        assert evidence["topology_context_id"] == "x4_top_01_dhcp_dns_service_security_dns_flow_context_v1"
        assert {name: row["value"] for name, row in evidence["observations"].items()} == {"dhcp_server_reachable": True, "dhcp_lease_obtained": True, "dhcp_lease_matches_expected_scope": True, "dns_server_reachable": True, "dns_query_succeeds": False, "dns_answer_matches_expected": False, "service_process_running": False, "service_port_reachable": False, "service_flow_blocked_by_policy": False}
        assert query["probe_id"] == "real_dns_query_and_response" and query["command_result"]["return_code"] in (1, 9)
        assert diagnosis["prediction"]["fault_type"] == "dns_service_down"
    finally:
        if deployed: require_success(run_command(["sudo", "-n", "containerlab", "destroy", "-t", str(TOPOLOGY), "--cleanup"], ROOT), "X4-R3 Containerlab cleanup")
        assert containerlab_containers(repository_root=ROOT, command_executor=run_command, topology_path=TOPOLOGY) == []
