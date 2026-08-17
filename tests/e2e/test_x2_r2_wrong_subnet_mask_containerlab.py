from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.campaign.phase6_runner import (
    containerlab_containers,
    require_success,
    run_command,
)
from src.orchestration.x2_subnet_mask_experiment_runner import (
    run_x2_r2_experiment,
)


ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "labs/topologies/x2_r1_addressing/topology.clab.yml"
BASELINE = ROOT / "labs/topologies/x2_r1_addressing/scripts/validate_baseline.sh"
SCENARIO = ROOT / "scenarios/expansion/X2_R2_WRONG_SUBNET_MASK.yml"
RUN_INFRASTRUCTURE = os.environ.get("IND_RUN_X2_R2_E2E") == "1"

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.skipif(
        not RUN_INFRASTRUCTURE,
        reason="set IND_RUN_X2_R2_E2E=1 to run the X2-R2 Containerlab lifecycle",
    ),
]


def test_real_wrong_mask_cycle_diagnoses_restores_and_cleans_up(
    tmp_path: Path,
) -> None:
    assert containerlab_containers(
        repository_root=ROOT,
        command_executor=run_command,
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
            "X2-R2 Containerlab deployment",
        )
        configured_evidence_root = os.environ.get("IND_X2_R2_EVIDENCE_ROOT")
        output_root = (
            Path(configured_evidence_root)
            if configured_evidence_root
            else tmp_path / "experiments"
        )
        result = run_x2_r2_experiment(
            SCENARIO,
            output_root,
            BASELINE,
            experiment_id="x2-r2-real-wrong-subnet-mask",
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
        restoration = json.loads(
            (experiment / "mutation/restoration_record.json").read_text(
                encoding="utf-8"
            )
        )
        values = evidence["observations"]
        assert result["status"] == "COMPLETED"
        assert result["baseline_valid_after"] is True
        assert result["restoration_confirmed"] is True
        assert values["source_address_matches_expected"]["value"] is True
        assert values["source_prefix_matches_expected"]["value"] is False
        assert values["source_default_route_present"]["value"] is True
        assert values["duplicate_address_detected"]["value"] is False
        assert diagnosis["status"] == "diagnosed"
        assert diagnosis["prediction"]["fault_type"] == "wrong_subnet_mask"
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
                pytest.fail("X2-R2 Containerlab cleanup failed: " + str(cleanup["stderr"]))
        assert containerlab_containers(
            repository_root=ROOT,
            command_executor=run_command,
            topology_path=TOPOLOGY,
        ) == []
