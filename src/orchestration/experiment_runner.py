from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

import yaml

from src.collection.evidence_collector import collect_evidence
from src.contracts.experiment_manifest import (
    validate_experiment_manifest,
)
from src.contracts.observation_profile import (
    ObservationProfile,
    ObservationProfileContractError,
    validate_observation_profile,
)
from src.evaluation.evaluator import evaluate_experiment
from src.fault_injection.common import FaultInjectionError
from src.fault_injection.registry import inject_fault
from src.rules.rule_engine import run_rule_engine


class ExperimentRunnerError(RuntimeError):
    """Raised when an experiment cannot be completed safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()



def build_experiment_id(
    scenario_id: str,
) -> str:
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S%fZ")

    return (
        f"{scenario_id.lower()}-"
        f"{timestamp}-"
        f"{uuid4().hex}"
    )


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_command(command: Sequence[str]) -> dict[str, Any]:
    process = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=False,
    )

    return {
        "command": list(command),
        "return_code": process.returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "timestamp_utc": utc_now(),
    }


def load_scenario_definition(
    path: Path,
) -> tuple[int, dict[str, Any], ObservationProfile]:
    if not path.exists():
        raise ExperimentRunnerError(
            f"Scenario file does not exist: {path}"
        )

    document = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(document, dict):
        raise ExperimentRunnerError(
            "Scenario document must be a YAML object."
        )

    schema_version = document.get("schema_version")

    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version < 1
    ):
        raise ExperimentRunnerError(
            "Scenario schema_version must be "
            "a positive integer."
        )

    scenario = document.get("scenario")

    if not isinstance(scenario, dict):
        raise ExperimentRunnerError(
            "Scenario document does not contain 'scenario'."
        )

    try:
        profile = validate_observation_profile(scenario)
    except ObservationProfileContractError as error:
        raise ExperimentRunnerError(
            f"Invalid Observation Profile v1: {error}"
        ) from error

    return schema_version, scenario, profile


def load_scenario(path: Path) -> dict[str, Any]:
    _, scenario, _ = load_scenario_definition(path)
    return scenario

def append_state(
    manifest: dict[str, Any],
    state: str,
) -> None:
    manifest["current_state"] = state
    manifest.setdefault("state_history", []).append(
        {
            "state": state,
            "timestamp_utc": utc_now(),
        }
    )


def save_manifest(
    experiment_directory: Path,
    manifest: dict[str, Any],
) -> None:
    validate_experiment_manifest(manifest)

    write_json(
        experiment_directory / "manifest.json",
        manifest,
    )


def validate_baseline(script_path: Path) -> dict[str, Any]:
    return run_command([str(script_path)])


def restore_fault(
    scenario: dict[str, Any],
) -> dict[str, Any]:
    fault = scenario["fault"]
    restoration = scenario["restoration"]

    target_container = str(fault["target_container"])
    restoration_command = restoration["command"]

    if not isinstance(restoration_command, list):
        raise ExperimentRunnerError(
            "Restoration command must be a list."
        )

    return run_command(
        [
            "docker",
            "exec",
            target_container,
            *[str(item) for item in restoration_command],
        ]
    )


def run_experiment(
    scenario_path: Path,
    output_root: Path,
    baseline_validator: Path,
) -> dict[str, Any]:
    (
        scenario_schema_version,
        scenario,
        observation_profile,
    ) = load_scenario_definition(scenario_path)

    scenario_id = scenario.get("id")

    if not isinstance(scenario_id, str) or not scenario_id:
        raise ExperimentRunnerError(
            "Scenario id must be a non-empty string."
        )

    scenario_kind = scenario.get("kind", "fault")

    if scenario_kind not in {"fault", "normal"}:
        raise ExperimentRunnerError(
            "Scenario kind must be 'fault' or 'normal'."
        )

    topology = scenario.get("topology")

    if not isinstance(topology, dict):
        raise ExperimentRunnerError(
            "Scenario topology must be an object."
        )

    topology_id = topology.get("id")

    if not isinstance(topology_id, str) or not topology_id:
        raise ExperimentRunnerError(
            "Topology id must be a non-empty string."
        )

    variant_id = scenario.get(
        "variant_id",
        "canonical",
    )

    if not isinstance(variant_id, str) or not variant_id:
        raise ExperimentRunnerError(
            "variant_id must be a non-empty string."
        )

    split_group_id = scenario.get(
        "split_group_id",
        (
            f"{topology_id}:"
            f"{scenario_id}:"
            f"{variant_id}"
        ),
    )

    if (
        not isinstance(split_group_id, str)
        or not split_group_id
    ):
        raise ExperimentRunnerError(
            "split_group_id must be a non-empty string."
        )

    diagnostic_method = "rule_based"

    experiment_id = build_experiment_id(
        scenario_id
    )
    experiment_directory = output_root / experiment_id

    experiment_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    created_at_utc = utc_now()

    manifest: dict[str, Any] = {
        "schema_version": 2,
        "experiment_id": experiment_id,
        "scenario_id": scenario_id,
        "scenario_schema_version": (
            scenario_schema_version
        ),
        "scenario_kind": scenario_kind,
        "topology_id": topology_id,
        "variant_id": variant_id,
        "split_group_id": split_group_id,
        "diagnostic_method": diagnostic_method,
        "scenario_path": str(scenario_path),
        "experiment_directory": str(
            experiment_directory
        ),
        "created_at_utc": created_at_utc,
        "current_state": "CREATED",
        "state_history": [
            {
                "state": "CREATED",
                "timestamp_utc": created_at_utc,
            }
        ],
    }

    save_manifest(experiment_directory, manifest)

    experiment_error: Exception | None = None
    baseline_after: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None
    fault_injection_attempted = False

    try:
        baseline_before = validate_baseline(
            baseline_validator
        )

        write_json(
            experiment_directory
            / "validation"
            / "baseline_before.json",
            baseline_before,
        )

        if baseline_before["return_code"] != 0:
            raise ExperimentRunnerError(
                "Baseline validation failed before execution."
            )

        append_state(
            manifest,
            "BASELINE_VALIDATED",
        )
        save_manifest(
            experiment_directory,
            manifest,
        )

        if scenario_kind == "fault":
            fault = scenario.get("fault")

            if not isinstance(fault, dict):
                raise ExperimentRunnerError(
                    "Fault scenarios must contain a fault object."
                )

            fault_type = fault.get("type")

            if (
                not isinstance(fault_type, str)
                or not fault_type
            ):
                raise ExperimentRunnerError(
                    "Fault type must be a non-empty string."
                )

            fault_injection_attempted = True

            inject_fault(
                fault_type,
                scenario_path=scenario_path,
                output_directory=experiment_directory,
            )

            append_state(
                manifest,
                "FAULT_CONFIRMED",
            )
        else:
            ground_truth = scenario.get("ground_truth")

            if not isinstance(ground_truth, dict):
                raise ExperimentRunnerError(
                    "Normal scenarios must contain ground_truth."
                )

            if ground_truth.get("fault_type") != "no_fault":
                raise ExperimentRunnerError(
                    "Normal ground truth must use "
                    "fault_type 'no_fault'."
                )

            write_json(
                experiment_directory / "ground_truth.json",
                ground_truth,
            )

            write_json(
                experiment_directory / "control_record.json",
                {
                    "schema_version": 1,
                    "scenario_kind": "normal",
                    "fault_injected": False,
                    "status": "NORMAL_CONFIRMED",
                    "timestamp_utc": utc_now(),
                },
            )

            append_state(
                manifest,
                "NORMAL_CONFIRMED",
            )

        save_manifest(
            experiment_directory,
            manifest,
        )

        collect_evidence(
            experiment_directory,
            observation_profile,
        )

        append_state(
            manifest,
            "EVIDENCE_COLLECTED",
        )
        save_manifest(
            experiment_directory,
            manifest,
        )

        run_rule_engine(experiment_directory)

        append_state(
            manifest,
            "DIAGNOSIS_PRODUCED",
        )
        save_manifest(
            experiment_directory,
            manifest,
        )

        evaluation = evaluate_experiment(
            experiment_directory=experiment_directory,
            method=diagnostic_method,
        )

        append_state(
            manifest,
            "EVALUATED",
        )
        save_manifest(
            experiment_directory,
            manifest,
        )

    except (
        ExperimentRunnerError,
        FaultInjectionError,
        FileNotFoundError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
        KeyError,
    ) as error:
        experiment_error = error

    finally:
        if (
            scenario_kind == "fault"
            and fault_injection_attempted
        ):
            try:
                restoration_result = restore_fault(
                    scenario
                )
            except (
                ExperimentRunnerError,
                FileNotFoundError,
                KeyError,
            ) as error:
                restoration_result = {
                    "return_code": 1,
                    "stdout": "",
                    "stderr": str(error),
                    "timestamp_utc": utc_now(),
                }

            write_json(
                experiment_directory
                / "restoration"
                / "restoration_result.json",
                restoration_result,
            )

            if restoration_result["return_code"] == 0:
                append_state(
                    manifest,
                    "FAULT_RESTORED",
                )

                baseline_after = validate_baseline(
                    baseline_validator
                )

                write_json(
                    experiment_directory
                    / "validation"
                    / "baseline_after.json",
                    baseline_after,
                )

                if baseline_after["return_code"] == 0:
                    append_state(
                        manifest,
                        "BASELINE_RESTORED",
                    )
                else:
                    experiment_error = ExperimentRunnerError(
                        "Baseline validation failed "
                        "after restoration."
                    )
            else:
                experiment_error = ExperimentRunnerError(
                    "Fault restoration failed."
                )

        elif scenario_kind == "normal":
            baseline_after = validate_baseline(
                baseline_validator
            )

            write_json(
                experiment_directory
                / "validation"
                / "baseline_after.json",
                baseline_after,
            )

            if baseline_after["return_code"] == 0:
                append_state(
                    manifest,
                    "POST_RUN_VALIDATED",
                )
            else:
                experiment_error = ExperimentRunnerError(
                    "Baseline validation failed "
                    "after the normal run."
                )

    if experiment_error is not None:
        append_state(
            manifest,
            "FAILED",
        )
        manifest["error"] = {
            "type": type(
                experiment_error
            ).__name__,
            "message": str(experiment_error),
        }

        save_manifest(
            experiment_directory,
            manifest,
        )

        raise ExperimentRunnerError(
            f"Experiment failed: {experiment_error}. "
            f"Artifacts: {experiment_directory}"
        )

    append_state(
        manifest,
        "COMPLETED",
    )
    manifest["completed_at_utc"] = utc_now()

    save_manifest(
        experiment_directory,
        manifest,
    )

    metrics = (
        evaluation.get("metrics", {})
        if isinstance(evaluation, dict)
        else {}
    )

    baseline_valid_after = (
        baseline_after is not None
        and baseline_after["return_code"] == 0
    )

    return {
        "experiment_id": experiment_id,
        "experiment_directory": str(
            experiment_directory
        ),
        "status": "COMPLETED",
        "scenario_id": scenario_id,
        "scenario_kind": scenario_kind,
        "variant_id": variant_id,
        "split_group_id": split_group_id,
        "diagnostic_method": diagnostic_method,
        "exact_match": metrics.get(
            "exact_match"
        ),
        "baseline_restored": (
            scenario_kind == "fault"
            and baseline_valid_after
        ),
        "baseline_valid_after": baseline_valid_after,
    }

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete controlled TOP-01 experiment."
        )
    )

    parser.add_argument(
        "--scenario",
        type=Path,
        default=Path(
            "scenarios/routing/"
            "C1_MISSING_STATIC_ROUTE.yml"
        ),
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/raw"),
    )

    parser.add_argument(
        "--baseline-validator",
        type=Path,
        default=Path(
            "labs/topologies/top01_routed/"
            "scripts/validate_baseline.sh"
        ),
    )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        result = run_experiment(
            scenario_path=arguments.scenario,
            output_root=arguments.output_root,
            baseline_validator=arguments.baseline_validator,
        )
    except ExperimentRunnerError as error:
        print(f"[ERROR] {error}")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
