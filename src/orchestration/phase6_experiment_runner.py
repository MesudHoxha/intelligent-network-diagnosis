from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import yaml

from src.collection.evidence_collector_v3 import (
    collect_evidence_v3,
    load_observation_profile_v2,
)
from src.contracts.experiment_manifest import validate_experiment_manifest
from src.fault_injection.phase6_common import (
    load_json_object,
    utc_now,
    write_json_atomic,
)
from src.fault_injection.phase6_registry import (
    inject_phase6_fault,
    restore_phase6_fault,
)
from src.verification.fault_evidence_v3 import verify_fault_evidence_v3
from src.verification.healthy_evidence_v3 import verify_healthy_evidence_v3


class Phase6ExperimentRunnerError(RuntimeError):
    """Raised when one clean Phase 6 experiment cannot be accepted."""


BaselineValidator = Callable[[Path], dict[str, object]]
FaultMutator = Callable[..., object]
EvidenceCollector = Callable[..., object]
EvidenceVerifier = Callable[..., dict[str, object]]


def build_experiment_id(scenario_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{scenario_id.lower()}-{timestamp}-{uuid4().hex}"


def run_baseline_validator(script_path: Path) -> dict[str, object]:
    process = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "command": ["bash", str(script_path)],
        "return_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "timestamp_utc": utc_now(),
    }


def _load_scenario(path: Path) -> tuple[int, dict[str, Any]]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise Phase6ExperimentRunnerError(
            f"Cannot read Phase 6 scenario: {path}"
        ) from error
    if not isinstance(document, dict):
        raise Phase6ExperimentRunnerError(
            "Phase 6 scenario document must be an object."
        )
    schema_version = document.get("schema_version")
    scenario = document.get("scenario")
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version < 1
        or not isinstance(scenario, dict)
    ):
        raise Phase6ExperimentRunnerError(
            "Phase 6 scenario has no valid versioned scenario object."
        )
    load_observation_profile_v2(path)
    return schema_version, scenario


def _append_state(manifest: dict[str, Any], state: str) -> None:
    manifest["current_state"] = state
    manifest["state_history"].append(
        {"state": state, "timestamp_utc": utc_now()}
    )


def _save_manifest(directory: Path, manifest: dict[str, Any]) -> None:
    validate_experiment_manifest(manifest)
    write_json_atomic(directory / "manifest.json", manifest)


def _mutation_applied(mutation_directory: Path) -> bool:
    path = mutation_directory / "injection_record.json"
    if not path.exists():
        return False
    return load_json_object(path).get("mutation_applied") is True


def _restoration_confirmed(mutation_directory: Path) -> bool:
    path = mutation_directory / "restoration_record.json"
    if not path.exists():
        return False
    return load_json_object(path).get("status") == "RESTORATION_CONFIRMED"


def run_phase6_experiment(
    scenario_path: Path,
    output_root: Path,
    baseline_validator_path: Path,
    *,
    baseline_validator: BaselineValidator = run_baseline_validator,
    fault_injector: FaultMutator = inject_phase6_fault,
    fault_restorer: FaultMutator = restore_phase6_fault,
    evidence_collector: EvidenceCollector = collect_evidence_v3,
    fault_verifier: EvidenceVerifier = verify_fault_evidence_v3,
    healthy_verifier: EvidenceVerifier = verify_healthy_evidence_v3,
    experiment_id: str | None = None,
) -> dict[str, object]:
    scenario_path = Path(scenario_path)
    output_root = Path(output_root)
    baseline_validator_path = Path(baseline_validator_path)
    scenario_schema_version, scenario = _load_scenario(scenario_path)

    scenario_id = scenario.get("id")
    scenario_kind = scenario.get("kind")
    topology = scenario.get("topology")
    variant_id = scenario.get("variant_id")
    split_group_id = scenario.get("split_group_id")
    ground_truth = scenario.get("ground_truth")
    if (
        not isinstance(scenario_id, str)
        or not scenario_id
        or scenario_kind not in {"normal", "fault"}
        or not isinstance(topology, dict)
        or not isinstance(topology.get("id"), str)
        or not isinstance(variant_id, str)
        or not isinstance(split_group_id, str)
        or not isinstance(ground_truth, dict)
    ):
        raise Phase6ExperimentRunnerError(
            "Phase 6 scenario metadata or ground truth is invalid."
        )
    if ground_truth.get("fault_type") == "no_fault":
        if scenario_kind != "normal":
            raise Phase6ExperimentRunnerError(
                "no_fault ground truth requires scenario.kind=normal."
            )
    elif scenario_kind != "fault":
        raise Phase6ExperimentRunnerError(
            "Fault ground truth requires scenario.kind=fault."
        )

    run_id = experiment_id or build_experiment_id(scenario_id)
    experiment_directory = output_root / run_id
    experiment_directory.mkdir(parents=True, exist_ok=False)
    mutation_directory = experiment_directory / "mutation"
    verification_directory = experiment_directory / "verification"

    created_at = utc_now()
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "experiment_id": run_id,
        "scenario_id": scenario_id,
        "scenario_schema_version": scenario_schema_version,
        "scenario_kind": scenario_kind,
        "topology_id": topology["id"],
        "variant_id": variant_id,
        "split_group_id": split_group_id,
        "diagnostic_method": "data_collection_only",
        "scenario_path": str(scenario_path),
        "experiment_directory": str(experiment_directory),
        "created_at_utc": created_at,
        "current_state": "CREATED",
        "state_history": [{"state": "CREATED", "timestamp_utc": created_at}],
    }
    _save_manifest(experiment_directory, manifest)
    write_json_atomic(experiment_directory / "ground_truth.json", ground_truth)

    primary_error: Exception | None = None
    fault_type: str | None = None
    restoration: object | None = None
    baseline_before_passed = False

    try:
        baseline_before = baseline_validator(baseline_validator_path)
        write_json_atomic(
            experiment_directory / "validation" / "baseline_before.json",
            baseline_before,
        )
        baseline_before_passed = baseline_before.get("return_code") == 0
        if not baseline_before_passed:
            raise Phase6ExperimentRunnerError(
                "Phase 6 baseline validation failed before collection."
            )
        _append_state(manifest, "BASELINE_VALIDATED")
        _save_manifest(experiment_directory, manifest)

        profile = load_observation_profile_v2(scenario_path)
        if scenario_kind == "fault":
            fault = scenario.get("fault")
            if not isinstance(fault, dict) or not isinstance(
                fault.get("type"), str
            ):
                raise Phase6ExperimentRunnerError(
                    "Phase 6 fault scenario has no fault type."
                )
            fault_type = fault["type"]
            fault_injector(
                fault_type,
                scenario_path,
                mutation_directory,
            )
            _append_state(manifest, "FAULT_CONFIRMED")
        else:
            write_json_atomic(
                experiment_directory / "control_record.json",
                {
                    "schema_version": 1,
                    "scenario_kind": "normal",
                    "fault_injected": False,
                    "status": "NORMAL_CONFIRMED",
                    "timestamp_utc": utc_now(),
                },
            )
            _append_state(manifest, "NORMAL_CONFIRMED")
        _save_manifest(experiment_directory, manifest)

        evidence_collector(experiment_directory, profile)
        _append_state(manifest, "EVIDENCE_COLLECTED")
        _save_manifest(experiment_directory, manifest)

        if scenario_kind == "fault":
            verification = fault_verifier(experiment_directory, scenario_path)
            write_json_atomic(
                verification_directory / "fault_evidence_v3.json",
                verification,
            )
        else:
            verification = healthy_verifier(experiment_directory, scenario_path)
            write_json_atomic(
                verification_directory / "healthy_evidence_v3.json",
                verification,
            )
    except Exception as error:
        primary_error = error

    restoration_error: Exception | None = None
    if scenario_kind == "fault" and fault_type is not None:
        try:
            if _restoration_confirmed(mutation_directory):
                restoration = load_json_object(
                    mutation_directory / "restoration_record.json"
                )
            elif _mutation_applied(mutation_directory):
                restoration = fault_restorer(
                    fault_type,
                    scenario_path,
                    mutation_directory,
                )
            if _mutation_applied(mutation_directory) and not (
                isinstance(restoration, dict)
                and restoration.get("status") == "RESTORATION_CONFIRMED"
            ):
                raise Phase6ExperimentRunnerError(
                    "Applied Phase 6 mutation lacks a confirmed restoration."
                )
        except Exception as error:
            restoration_error = error

    baseline_after: dict[str, object] | None = None
    if baseline_before_passed and restoration_error is None:
        baseline_after = baseline_validator(baseline_validator_path)
        write_json_atomic(
            experiment_directory / "validation" / "baseline_after.json",
            baseline_after,
        )
        if baseline_after.get("return_code") != 0:
            restoration_error = Phase6ExperimentRunnerError(
                "Phase 6 baseline validation failed after the experiment."
            )

    final_error = restoration_error or primary_error
    if final_error is not None:
        _append_state(manifest, "FAILED")
        manifest["error"] = {
            "type": type(final_error).__name__,
            "message": str(final_error),
        }
        _save_manifest(experiment_directory, manifest)
        raise Phase6ExperimentRunnerError(
            f"Phase 6 experiment failed: {final_error}. "
            f"Artifacts: {experiment_directory}"
        ) from final_error

    if scenario_kind == "fault":
        _append_state(manifest, "FAULT_RESTORED")
        _append_state(manifest, "BASELINE_RESTORED")
    else:
        _append_state(manifest, "POST_RUN_VALIDATED")
    _append_state(manifest, "COMPLETED")
    manifest["completed_at_utc"] = utc_now()
    _save_manifest(experiment_directory, manifest)

    return {
        "status": "COMPLETED",
        "experiment_id": run_id,
        "experiment_directory": str(experiment_directory),
        "scenario_id": scenario_id,
        "scenario_kind": scenario_kind,
        "fault_type": ground_truth["fault_type"],
        "topology_id": topology["id"],
        "split_group_id": split_group_id,
        "evidence_schema_version": 3,
        "baseline_valid_after": baseline_after is not None
        and baseline_after.get("return_code") == 0,
        "restoration_confirmed": (
            True
            if scenario_kind == "normal"
            else isinstance(restoration, dict)
            and restoration.get("status") == "RESTORATION_CONFIRMED"
        ),
        "diagnosis_created": False,
        "prediction_created": False,
        "metric_created": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one clean Evidence v3 Phase 6 experiment."
    )
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--baseline-validator", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        result = run_phase6_experiment(
            arguments.scenario,
            arguments.output_root,
            arguments.baseline_validator,
        )
    except Exception as error:
        print(f"[ERROR] {error}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
