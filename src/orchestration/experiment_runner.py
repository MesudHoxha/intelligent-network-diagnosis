from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import yaml

from src.collection.evidence_collector import collect_evidence
from src.evaluation.evaluator import evaluate_experiment
from src.fault_injection.missing_route import FaultInjectionError
from src.fault_injection.registry import inject_fault
from src.rules.rule_engine import run_rule_engine


class ExperimentRunnerError(RuntimeError):
    """Raised when an experiment cannot be completed safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def load_scenario(path: Path) -> dict[str, Any]:
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

    scenario = document.get("scenario")

    if not isinstance(scenario, dict):
        raise ExperimentRunnerError(
            "Scenario document does not contain 'scenario'."
        )

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
    scenario = load_scenario(scenario_path)

    scenario_id = str(scenario["id"])
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

    experiment_id = (
        f"{scenario_id.lower()}-{timestamp}"
    )
    experiment_directory = output_root / experiment_id

    experiment_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "scenario_id": scenario_id,
        "scenario_path": str(scenario_path),
        "experiment_directory": str(
            experiment_directory
        ),
        "created_at_utc": utc_now(),
        "current_state": "CREATED",
        "state_history": [
            {
                "state": "CREATED",
                "timestamp_utc": utc_now(),
            }
        ],
    }

    save_manifest(experiment_directory, manifest)

    experiment_error: Exception | None = None
    restoration_result: dict[str, Any] | None = None
    baseline_after: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None

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
                "Baseline validation failed before injection."
            )

        append_state(
            manifest,
            "BASELINE_VALIDATED",
        )
        save_manifest(
            experiment_directory,
            manifest,
        )

        fault_type = scenario["fault"]["type"]

        inject_fault(
            fault_type,
            scenario_path=scenario_path,
            output_directory=experiment_directory,
        )

        append_state(
            manifest,
            "FAULT_CONFIRMED",
        )
        save_manifest(
            experiment_directory,
            manifest,
        )

        collect_evidence(experiment_directory)

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
            method="rule_based",
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
        json.JSONDecodeError,
        KeyError,
    ) as error:
        experiment_error = error

    finally:
        try:
            restoration_result = restore_fault(
                scenario
            )
        except (
            ExperimentRunnerError,
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
                    "Baseline validation failed after restoration."
                )
        else:
            experiment_error = ExperimentRunnerError(
                "Fault restoration failed."
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

    return {
        "experiment_id": experiment_id,
        "experiment_directory": str(
            experiment_directory
        ),
        "status": "COMPLETED",
        "scenario_id": scenario_id,
        "diagnostic_method": "rule_based",
        "exact_match": metrics.get(
            "exact_match"
        ),
        "baseline_restored": (
            baseline_after is not None
            and baseline_after["return_code"] == 0
        ),
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
