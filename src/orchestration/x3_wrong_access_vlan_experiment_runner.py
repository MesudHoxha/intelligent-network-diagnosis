from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from src.collection.l2_vlan_state_collector import (
    build_l2_vlan_feature_vector_v2,
    collect_wrong_access_vlan_evidence_v4,
)
from src.expansion.x3_wrong_access_vlan import (
    X3WrongAccessVlanError,
    load_wrong_access_vlan_scenario,
)
from src.fault_injection.phase6_common import load_json_object, utc_now, write_json_atomic
from src.fault_injection.wrong_access_vlan import (
    inject_wrong_access_vlan,
    restore_wrong_access_vlan,
)
from src.rules.l2_vlan_rule_engine_v2 import diagnose_wrong_access_vlan_v2
from src.runtime.subprocesses import run_capture


BASELINE_TIMEOUT_SECONDS = 90.0
BaselineValidator = Callable[[Path], dict[str, object]]
FaultMutator = Callable[[Path, Path], dict[str, object]]
EvidenceCollector = Callable[[Path, Path], dict[str, object]]
VectorBuilder = Callable[[Path, Mapping[str, object]], dict[str, object]]
RuleEngine = Callable[..., dict[str, object]]


class X3WrongAccessVlanExperimentError(RuntimeError):
    """Raised when the X3-R1 lifecycle cannot complete safely."""


def run_baseline_validator(path: Path) -> dict[str, object]:
    process = run_capture(["bash", str(path)], timeout_seconds=BASELINE_TIMEOUT_SECONDS)
    return {
        "command": ["bash", str(path)],
        "return_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "timestamp_utc": utc_now(),
    }


def _new_id(scenario_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{scenario_id.lower()}-{timestamp}-{uuid4().hex}"


def _append_state(manifest: dict[str, object], state: str) -> None:
    manifest["current_state"] = state
    history = manifest["state_history"]
    assert isinstance(history, list)
    history.append({"state": state, "timestamp_utc": utc_now()})


def _recovery_exists(mutation_directory: Path) -> bool:
    return (mutation_directory / "recovery_intent.json").is_file() or (
        mutation_directory / "injection_record.json"
    ).is_file()


def _restoration_confirmed(mutation_directory: Path) -> bool:
    path = mutation_directory / "restoration_record.json"
    return path.is_file() and load_json_object(path).get("status") == "RESTORATION_CONFIRMED"


def recover_x3_r1_experiment(
    scenario_path: Path,
    experiment_directory: Path,
    baseline_validator_path: Path,
    *,
    baseline_validator: BaselineValidator = run_baseline_validator,
    fault_restorer: FaultMutator = restore_wrong_access_vlan,
) -> dict[str, object]:
    binding = load_wrong_access_vlan_scenario(scenario_path)
    experiment_directory = Path(experiment_directory)
    mutation_directory = experiment_directory / "mutation"
    if not experiment_directory.is_dir() or not _recovery_exists(mutation_directory):
        raise X3WrongAccessVlanExperimentError(
            "X3-R1 recovery requires an existing matching recovery journal."
        )
    restoration = fault_restorer(scenario_path, mutation_directory)
    if restoration.get("status") != "RESTORATION_CONFIRMED":
        raise X3WrongAccessVlanExperimentError("X3-R1 recovery was not confirmed.")
    baseline = baseline_validator(Path(baseline_validator_path))
    write_json_atomic(
        experiment_directory / "validation/baseline_after_recovery.json", baseline
    )
    if baseline.get("return_code") != 0:
        raise X3WrongAccessVlanExperimentError(
            "X3-R1 restoration completed but baseline recovery failed."
        )
    result = {
        "schema_version": 1,
        "release_id": "X3_R1_WRONG_ACCESS_VLAN",
        "status": "RECOVERY_CONFIRMED",
        "scenario_id": binding.scenario_id,
        "fault_type": "wrong_access_vlan",
        "experiment_directory": str(experiment_directory),
        "restoration_confirmed": True,
        "baseline_restored": True,
        "completed_at_utc": utc_now(),
    }
    write_json_atomic(experiment_directory / "recovery_replay.json", result)
    return result


def run_x3_r1_experiment(
    scenario_path: Path,
    output_root: Path,
    baseline_validator_path: Path,
    *,
    baseline_validator: BaselineValidator = run_baseline_validator,
    fault_injector: FaultMutator = inject_wrong_access_vlan,
    fault_restorer: FaultMutator = restore_wrong_access_vlan,
    evidence_collector: EvidenceCollector = collect_wrong_access_vlan_evidence_v4,
    vector_builder: VectorBuilder = build_l2_vlan_feature_vector_v2,
    rule_engine: RuleEngine = diagnose_wrong_access_vlan_v2,
    experiment_id: str | None = None,
) -> dict[str, object]:
    binding = load_wrong_access_vlan_scenario(scenario_path)
    run_id = experiment_id or _new_id(binding.scenario_id)
    experiment_directory = Path(output_root) / run_id
    experiment_directory.mkdir(parents=True, exist_ok=False)
    mutation_directory = experiment_directory / "mutation"
    created = utc_now()
    manifest: dict[str, object] = {
        "schema_version": 1,
        "release_id": "X3_R1_WRONG_ACCESS_VLAN",
        "experiment_id": run_id,
        "scenario_id": binding.scenario_id,
        "scenario_sha256": binding.sha256,
        "topology_id": binding.topology_id,
        "topology_context_id": binding.topology_context_id,
        "truth_model": "single_fault",
        "diagnostic_method": "rule_based_v2",
        "created_at_utc": created,
        "current_state": "CREATED",
        "state_history": [{"state": "CREATED", "timestamp_utc": created}],
    }
    write_json_atomic(experiment_directory / "manifest.json", manifest)
    write_json_atomic(
        experiment_directory / "ground_truth.json", binding.scenario["ground_truth"]
    )

    primary_error: BaseException | None = None
    restoration_error: BaseException | None = None
    baseline_before_passed = False
    diagnosis: dict[str, object] | None = None
    try:
        before = baseline_validator(Path(baseline_validator_path))
        write_json_atomic(
            experiment_directory / "validation/baseline_before.json", before
        )
        baseline_before_passed = before.get("return_code") == 0
        if not baseline_before_passed:
            raise X3WrongAccessVlanExperimentError(
                "X3-R1 baseline validation failed before mutation."
            )
        _append_state(manifest, "BASELINE_VALIDATED")
        write_json_atomic(experiment_directory / "manifest.json", manifest)

        fault_injector(scenario_path, mutation_directory)
        _append_state(manifest, "FAULT_CONFIRMED")
        write_json_atomic(experiment_directory / "manifest.json", manifest)

        evidence = evidence_collector(experiment_directory, scenario_path)
        _append_state(manifest, "EVIDENCE_V4_COLLECTED")
        write_json_atomic(experiment_directory / "manifest.json", manifest)

        vector = vector_builder(experiment_directory, evidence)
        diagnosis = rule_engine(
            vector,
            location_node=binding.target_switch_node,
            affected_resource=binding.target_access_interface,
        )
        write_json_atomic(
            experiment_directory / "diagnosis/diagnosis_result_v2.json", diagnosis
        )
        if (
            diagnosis.get("status") != "diagnosed"
            or not isinstance(diagnosis.get("prediction"), dict)
            or diagnosis["prediction"].get("fault_type") != "wrong_access_vlan"
        ):
            raise X3WrongAccessVlanExperimentError(
                "X3-R1 exact Wrong Access VLAN rule did not produce the expected diagnosis."
            )
        _append_state(manifest, "DIAGNOSIS_VERIFIED")
        write_json_atomic(experiment_directory / "manifest.json", manifest)
    except BaseException as error:
        primary_error = error

    if _recovery_exists(mutation_directory):
        try:
            restoration = fault_restorer(scenario_path, mutation_directory)
            if restoration.get("status") != "RESTORATION_CONFIRMED":
                raise X3WrongAccessVlanExperimentError(
                    "X3-R1 restoration record is not confirmed."
                )
        except BaseException as error:
            restoration_error = error

    baseline_after: dict[str, object] | None = None
    if baseline_before_passed and restoration_error is None:
        baseline_after = baseline_validator(Path(baseline_validator_path))
        write_json_atomic(
            experiment_directory / "validation/baseline_after.json", baseline_after
        )
        if baseline_after.get("return_code") != 0:
            restoration_error = X3WrongAccessVlanExperimentError(
                "X3-R1 baseline validation failed after restoration."
            )

    final_error = restoration_error or primary_error
    if final_error is not None:
        _append_state(manifest, "FAILED")
        manifest["error"] = {
            "type": type(final_error).__name__,
            "message": str(final_error),
        }
        write_json_atomic(experiment_directory / "manifest.json", manifest)
        raise X3WrongAccessVlanExperimentError(
            f"X3-R1 experiment failed: {final_error}. Artifacts: {experiment_directory}"
        ) from final_error

    if not _restoration_confirmed(mutation_directory):
        raise X3WrongAccessVlanExperimentError(
            "X3-R1 completed without a confirmed restoration record."
        )
    _append_state(manifest, "FAULT_RESTORED")
    _append_state(manifest, "BASELINE_RESTORED")
    _append_state(manifest, "COMPLETED")
    manifest["completed_at_utc"] = utc_now()
    write_json_atomic(experiment_directory / "manifest.json", manifest)
    return {
        "schema_version": 1,
        "release_id": "X3_R1_WRONG_ACCESS_VLAN",
        "status": "COMPLETED",
        "experiment_id": run_id,
        "experiment_directory": str(experiment_directory),
        "scenario_id": binding.scenario_id,
        "fault_type": "wrong_access_vlan",
        "topology_id": binding.topology_id,
        "evidence_schema_version": 4,
        "diagnosis_schema_version": 2,
        "diagnosis_created": diagnosis is not None,
        "restoration_confirmed": True,
        "baseline_valid_after": baseline_after is not None
        and baseline_after.get("return_code") == 0,
        "dataset_row_created": False,
        "model_operation_performed": False,
        "metric_created": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the isolated X3-R1 Wrong Access VLAN lifecycle."
    )
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("data/raw/x3_r1"))
    parser.add_argument("--baseline-validator", type=Path, required=True)
    parser.add_argument("--recover-experiment-directory", type=Path)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        if arguments.recover_experiment_directory is not None:
            result = recover_x3_r1_experiment(
                arguments.scenario,
                arguments.recover_experiment_directory,
                arguments.baseline_validator,
            )
        else:
            result = run_x3_r1_experiment(
                arguments.scenario,
                arguments.output_root,
                arguments.baseline_validator,
            )
    except (X3WrongAccessVlanError, X3WrongAccessVlanExperimentError, OSError) as error:
        print(f"[ERROR] {error}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
