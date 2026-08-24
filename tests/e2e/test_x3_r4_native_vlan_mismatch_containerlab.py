from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.campaign.phase6_runner import containerlab_containers, require_success, run_command
from src.orchestration.x3_native_vlan_mismatch_experiment_runner import run_x3_r4_experiment


ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "labs/topologies/x3_r1_l2_vlan/topology.clab.yml"
BASELINE = ROOT / "labs/topologies/x3_r1_l2_vlan/scripts/validate_baseline.sh"
SCENARIO = ROOT / "scenarios/expansion/X3_R4_NATIVE_VLAN_MISMATCH.yml"
pytestmark = [pytest.mark.infrastructure, pytest.mark.skipif(os.environ.get("IND_RUN_X3_R4_E2E") != "1", reason="set IND_RUN_X3_R4_E2E=1 to run the X3-R4 Containerlab lifecycle")]


def test_real_native_vlan_mismatch_cycle_diagnoses_restores_and_cleans_up(tmp_path: Path) -> None:
    assert containerlab_containers(repository_root=ROOT, command_executor=run_command) == []
    deployed = False
    primary: BaseException | None = None
    try:
        deployed = True
        require_success(run_command(["sudo", "-n", "containerlab", "deploy", "-t", str(TOPOLOGY)], ROOT), "X3-R4 Containerlab deployment")
        root = Path(os.environ["IND_X3_R4_EVIDENCE_ROOT"]) if os.environ.get("IND_X3_R4_EVIDENCE_ROOT") else tmp_path / "experiments"
        result = run_x3_r4_experiment(SCENARIO, root, BASELINE, experiment_id="x3-r4-real-native-vlan-mismatch")
        experiment = Path(str(result["experiment_directory"]))
        evidence = json.loads((experiment / "parsed/evidence_v4.json").read_text(encoding="utf-8"))
        diagnosis = json.loads((experiment / "diagnosis/diagnosis_result_v2.json").read_text(encoding="utf-8"))
        active = json.loads((experiment / "raw/v4/l2_vlan_state_collector/active_flow_probe.json").read_text(encoding="utf-8"))
        values = evidence["observations"]
        assert result["status"] == "COMPLETED" and result["baseline_valid_after"] is True and result["restoration_confirmed"] is True
        assert {name: row["value"] for name, row in values.items()} == {"access_vlan_matches_expected": True, "vlan_exists_on_target": True, "vlan_allowed_on_trunk": True, "native_vlan_matches_peer": False, "fdb_location_matches_expected": True}
        assert evidence["topology_context_id"] == "x3_top_01_l2_vlan_native_flow_context_v1"
        assert active["native_flow"]["reachable"] is False and active["tagged_control_flow"]["reachable"] is True
        assert diagnosis["prediction"]["fault_type"] == "native_vlan_mismatch" and diagnosis["prediction"]["affected_resource"] == "eth3:native-vlan"
    except BaseException as error:
        primary = error
        raise
    finally:
        if deployed:
            cleanup = run_command(["sudo", "-n", "containerlab", "destroy", "-t", str(TOPOLOGY), "--cleanup"], ROOT)
            if cleanup["return_code"] != 0 and primary is None:
                pytest.fail("X3-R4 Containerlab cleanup failed: " + str(cleanup["stderr"]))
        assert containerlab_containers(repository_root=ROOT, command_executor=run_command, topology_path=TOPOLOGY) == []
