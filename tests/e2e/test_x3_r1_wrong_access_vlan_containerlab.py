from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.campaign.phase6_runner import containerlab_containers, require_success, run_command
from src.orchestration.x3_wrong_access_vlan_experiment_runner import run_x3_r1_experiment


ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "labs/topologies/x3_r1_l2_vlan/topology.clab.yml"
BASELINE = ROOT / "labs/topologies/x3_r1_l2_vlan/scripts/validate_baseline.sh"
SCENARIO = ROOT / "scenarios/expansion/X3_R1_WRONG_ACCESS_VLAN.yml"
RUN_INFRASTRUCTURE = os.environ.get("IND_RUN_X3_R1_E2E") == "1"

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.skipif(
        not RUN_INFRASTRUCTURE,
        reason="set IND_RUN_X3_R1_E2E=1 to run the X3-R1 Containerlab lifecycle",
    ),
]


def test_real_wrong_access_vlan_cycle_diagnoses_restores_and_cleans_up(
    tmp_path: Path,
) -> None:
    assert containerlab_containers(
        repository_root=ROOT, command_executor=run_command
    ) == []
    deploy_attempted = False
    primary_error: BaseException | None = None
    try:
        deploy_attempted = True
        require_success(
            run_command(
                ["sudo", "-n", "containerlab", "deploy", "-t", str(TOPOLOGY)],
                ROOT,
            ),
            "X3-R1 Containerlab deployment",
        )
        configured_root = os.environ.get("IND_X3_R1_EVIDENCE_ROOT")
        output_root = Path(configured_root) if configured_root else tmp_path / "experiments"
        result = run_x3_r1_experiment(
            SCENARIO,
            output_root,
            BASELINE,
            experiment_id="x3-r1-real-wrong-access-vlan",
        )
        experiment = Path(str(result["experiment_directory"]))
        evidence = json.loads(
            (experiment / "parsed/evidence_v4.json").read_text(encoding="utf-8")
        )
        diagnosis = json.loads(
            (experiment / "diagnosis/diagnosis_result_v2.json").read_text(
                encoding="utf-8"
            )
        )
        injection = json.loads(
            (experiment / "mutation/injection_record.json").read_text(encoding="utf-8")
        )
        restoration = json.loads(
            (experiment / "mutation/restoration_record.json").read_text(
                encoding="utf-8"
            )
        )
        active = json.loads(
            (
                experiment
                / "raw/v4/l2_vlan_state_collector/active_flow_probe.json"
            ).read_text(encoding="utf-8")
        )
        values = evidence["observations"]
        assert result["status"] == "COMPLETED"
        assert result["baseline_valid_after"] is True
        assert result["restoration_confirmed"] is True
        assert values["access_vlan_matches_expected"]["value"] is False
        assert values["vlan_exists_on_target"]["value"] is True
        assert values["vlan_allowed_on_trunk"]["value"] is True
        assert values["native_vlan_matches_peer"]["value"] is True
        assert values["fdb_location_matches_expected"]["value"] is False
        assert active["tagged_flow"]["reachable"] is False
        assert active["native_flow"]["reachable"] is True
        assert injection["status"] == "FAULT_CONFIRMED"
        assert diagnosis["status"] == "diagnosed"
        assert diagnosis["prediction"]["fault_type"] == "wrong_access_vlan"
        assert diagnosis["prediction"]["location"] == "sw1"
        assert restoration["status"] == "RESTORATION_CONFIRMED"
    except BaseException as error:
        primary_error = error
        raise
    finally:
        if deploy_attempted:
            cleanup = run_command(
                [
                    "sudo",
                    "-n",
                    "containerlab",
                    "destroy",
                    "-t",
                    str(TOPOLOGY),
                    "--cleanup",
                ],
                ROOT,
            )
            if cleanup["return_code"] != 0 and primary_error is None:
                pytest.fail("X3-R1 Containerlab cleanup failed: " + str(cleanup["stderr"]))
        assert containerlab_containers(
            repository_root=ROOT,
            command_executor=run_command,
            topology_path=TOPOLOGY,
        ) == []
