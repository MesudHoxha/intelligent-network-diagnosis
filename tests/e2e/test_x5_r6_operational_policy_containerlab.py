from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.campaign.phase6_runner import containerlab_containers, require_success, run_command
from src.orchestration.x5_r6_operational_policy_revalidation_runner import run_x5_r6_experiment


ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "labs/topologies/x5_r5_c5_operational_policy/topology.clab.yml"
BASELINE = ROOT / "labs/topologies/x5_r5_c5_operational_policy/scripts/validate_baseline.sh"
pytestmark = [pytest.mark.infrastructure, pytest.mark.skipif(os.environ.get("IND_RUN_X5_R6_E2E") != "1", reason="set IND_RUN_X5_R6_E2E=1 after sudo -v")]


def test_x5_r6_operational_policy_c5_cycle(tmp_path: Path) -> None:
    assert containerlab_containers(repository_root=ROOT, command_executor=run_command) == []; deployed = False
    try:
        require_success(run_command(["sudo", "-n", "containerlab", "deploy", "-t", str(TOPOLOGY)], ROOT), "X5-R6 deploy"); deployed = True
        result = run_x5_r6_experiment(Path(os.environ.get("IND_X5_R6_EVIDENCE_ROOT", str(tmp_path))), BASELINE); root = Path(result["experiment_directory"])
        evidence = json.loads((root / "parsed/evidence_v4.json").read_text()); controls = json.loads((root / "validation/control_exclusions.json").read_text()); diagnosis = json.loads((root / "diagnosis/diagnosis_result_v2.json").read_text()); mutation = json.loads((root / "mutation/mutation_effectiveness.json").read_text()); restore = json.loads((root / "mutation/restoration_record.json").read_text())
        assert result["status"] == "COMPLETED" and {key: row["value"] for key, row in evidence["observations"].items()} == {"ospf_adjacency_full": True, "ospf_route_advertised": False, "ospf_route_installed": False, "route_filter_allows_prefix": False}
        assert controls["attachment_present"] and controls["active_deny_present"] and controls["direct_expected_network_absent"] and controls["control_r1_r2_full"] and controls["target_r2_r3_full"]
        assert mutation["status"] == "MUTATION_EFFECTIVE" and diagnosis["status"] == "diagnosed" and diagnosis["explanation_refs"] == ["rule:R_X5_OSPF_002"] and restore["status"] == "RESTORATION_CONFIRMED"
    finally:
        if deployed: require_success(run_command(["sudo", "-n", "containerlab", "destroy", "-t", str(TOPOLOGY), "--cleanup"], ROOT), "X5-R6 cleanup")
        assert containerlab_containers(repository_root=ROOT, command_executor=run_command, topology_path=TOPOLOGY) == []
