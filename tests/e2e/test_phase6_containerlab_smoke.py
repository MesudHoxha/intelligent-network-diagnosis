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
from src.orchestration.phase6_experiment_runner import run_phase6_experiment
from src.rules.rule_engine_v3 import diagnose_evidence_v3


ROOT = Path(__file__).resolve().parents[2]
TOPOLOGY = ROOT / "labs/topologies/p6_e01_top01/topology.clab.yml"
BASELINE = ROOT / "labs/topologies/p6_e01_top01/scripts/validate_baseline.sh"
SCENARIO = ROOT / "scenarios/phase6/E01_C1_MISSING_STATIC_ROUTE.yml"
RUN_INFRASTRUCTURE = os.environ.get("IND_RUN_INFRA_E2E") == "1"

pytestmark = [
    pytest.mark.infrastructure,
    pytest.mark.skipif(
        not RUN_INFRASTRUCTURE,
        reason="set IND_RUN_INFRA_E2E=1 to run Docker/Containerlab smoke",
    ),
]


def test_real_phase6_cycle_restores_and_cleans_up(tmp_path: Path) -> None:
    active_before = containerlab_containers(
        repository_root=ROOT,
        command_executor=run_command,
    )
    assert active_before == [], (
        "Infrastructure smoke requires zero active clab-* containers."
    )

    deploy_attempted = False
    primary_error: BaseException | None = None
    try:
        deploy_attempted = True
        require_success(
            run_command(
                [
                    "sudo",
                    "-n",
                    "containerlab",
                    "deploy",
                    "-t",
                    str(TOPOLOGY),
                ],
                ROOT,
            ),
            "Containerlab E2E deployment",
        )
        result = run_phase6_experiment(
            SCENARIO,
            tmp_path / "experiments",
            BASELINE,
            experiment_id="h1-e2e-missing-static-route",
        )
        experiment = Path(str(result["experiment_directory"]))
        evidence = json.loads(
            (experiment / "parsed/evidence.json").read_text(
                encoding="utf-8"
            )
        )
        diagnosis = diagnose_evidence_v3(evidence)
        restoration = json.loads(
            (experiment / "mutation/restoration_record.json").read_text(
                encoding="utf-8"
            )
        )

        assert result["status"] == "COMPLETED"
        assert result["baseline_valid_after"] is True
        assert result["restoration_confirmed"] is True
        assert restoration["status"] == "RESTORATION_CONFIRMED"
        assert diagnosis["status"] == "DIAGNOSIS_PRODUCED"
        assert diagnosis["diagnosis"]["fault_type"] == (
            "missing_static_route"
        )
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
                pytest.fail(
                    "Containerlab E2E cleanup failed: "
                    + str(cleanup["stderr"])
                )
        active_after = containerlab_containers(
            repository_root=ROOT,
            command_executor=run_command,
            topology_path=TOPOLOGY,
        )
        assert active_after == []
