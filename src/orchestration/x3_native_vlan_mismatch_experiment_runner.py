from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping
from uuid import uuid4

from src.collection.l2_vlan_state_collector_v4 import build_l2_vlan_feature_vector_v2, collect_native_vlan_mismatch_evidence_v4
from src.expansion.x3_native_vlan_mismatch import X3NativeVlanMismatchError, load_native_vlan_mismatch_scenario
from src.fault_injection.native_vlan_mismatch import inject_native_vlan_mismatch, restore_native_vlan_mismatch
from src.fault_injection.phase6_common import load_json_object, utc_now, write_json_atomic
from src.rules.l2_vlan_rule_engine_x3_r4 import diagnose_l2_vlan_x3_r4_v2
from src.runtime.subprocesses import run_capture


BASELINE_TIMEOUT_SECONDS = 90.0
BaselineValidator = Callable[[Path], dict[str, object]]
FaultMutator = Callable[[Path, Path], dict[str, object]]
EvidenceCollector = Callable[[Path, Path], dict[str, object]]
VectorBuilder = Callable[[Path, Mapping[str, object]], dict[str, object]]
RuleEngine = Callable[..., dict[str, object]]


class X3NativeVlanMismatchExperimentError(RuntimeError):
    """Raised when the X3-R4 lifecycle cannot complete safely."""


def run_baseline_validator(path: Path) -> dict[str, object]:
    process = run_capture(["bash", str(path)], timeout_seconds=BASELINE_TIMEOUT_SECONDS)
    return {"command": ["bash", str(path)], "return_code": process.returncode, "stdout": process.stdout, "stderr": process.stderr, "timestamp_utc": utc_now()}


def _new_id(scenario_id: str) -> str:
    return f"{scenario_id.lower()}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex}"


def _append(manifest: dict[str, object], state: str) -> None:
    manifest["current_state"] = state
    history = manifest["state_history"]
    assert isinstance(history, list)
    history.append({"state": state, "timestamp_utc": utc_now()})


def _recovery_exists(mutation: Path) -> bool:
    return (mutation / "recovery_intent.json").is_file() or (mutation / "injection_record.json").is_file()


def _restored(mutation: Path) -> bool:
    return (mutation / "restoration_record.json").is_file() and load_json_object(mutation / "restoration_record.json").get("status") == "RESTORATION_CONFIRMED"


def recover_x3_r4_experiment(scenario_path: Path, experiment_directory: Path, baseline_validator_path: Path, *, baseline_validator: BaselineValidator = run_baseline_validator, fault_restorer: FaultMutator = restore_native_vlan_mismatch) -> dict[str, object]:
    binding = load_native_vlan_mismatch_scenario(scenario_path)
    experiment = Path(experiment_directory)
    mutation = experiment / "mutation"
    if not experiment.is_dir() or not _recovery_exists(mutation):
        raise X3NativeVlanMismatchExperimentError("X3-R4 recovery requires an existing matching recovery journal.")
    restoration = fault_restorer(scenario_path, mutation)
    baseline = baseline_validator(Path(baseline_validator_path))
    write_json_atomic(experiment / "validation/baseline_after_recovery.json", baseline)
    if restoration.get("status") != "RESTORATION_CONFIRMED" or baseline.get("return_code") != 0:
        raise X3NativeVlanMismatchExperimentError("X3-R4 recovery or baseline validation failed.")
    result = {"schema_version": 1, "release_id": "X3_R4_NATIVE_VLAN_MISMATCH", "status": "RECOVERY_CONFIRMED", "scenario_id": binding.scenario_id, "fault_type": "native_vlan_mismatch", "experiment_directory": str(experiment), "restoration_confirmed": True, "baseline_restored": True, "completed_at_utc": utc_now()}
    write_json_atomic(experiment / "recovery_replay.json", result)
    return result


def run_x3_r4_experiment(scenario_path: Path, output_root: Path, baseline_validator_path: Path, *, baseline_validator: BaselineValidator = run_baseline_validator, fault_injector: FaultMutator = inject_native_vlan_mismatch, fault_restorer: FaultMutator = restore_native_vlan_mismatch, evidence_collector: EvidenceCollector = collect_native_vlan_mismatch_evidence_v4, vector_builder: VectorBuilder = build_l2_vlan_feature_vector_v2, rule_engine: RuleEngine = diagnose_l2_vlan_x3_r4_v2, experiment_id: str | None = None) -> dict[str, object]:
    binding = load_native_vlan_mismatch_scenario(scenario_path)
    run_id = experiment_id or _new_id(binding.scenario_id)
    experiment = Path(output_root) / run_id
    experiment.mkdir(parents=True, exist_ok=False)
    mutation = experiment / "mutation"
    created = utc_now()
    manifest: dict[str, object] = {"schema_version": 1, "release_id": "X3_R4_NATIVE_VLAN_MISMATCH", "experiment_id": run_id, "scenario_id": binding.scenario_id, "scenario_sha256": binding.sha256, "topology_id": binding.topology_id, "topology_context_id": binding.topology_context_id, "truth_model": "single_fault", "diagnostic_method": "rule_based_v2", "created_at_utc": created, "current_state": "CREATED", "state_history": [{"state": "CREATED", "timestamp_utc": created}]}
    write_json_atomic(experiment / "manifest.json", manifest)
    write_json_atomic(experiment / "ground_truth.json", binding.scenario["ground_truth"])
    primary: BaseException | None = None
    restoration_error: BaseException | None = None
    baseline_before = False
    diagnosis: dict[str, object] | None = None
    try:
        before = baseline_validator(Path(baseline_validator_path))
        write_json_atomic(experiment / "validation/baseline_before.json", before)
        baseline_before = before.get("return_code") == 0
        if not baseline_before:
            raise X3NativeVlanMismatchExperimentError("X3-R4 baseline validation failed before mutation.")
        _append(manifest, "BASELINE_VALIDATED"); write_json_atomic(experiment / "manifest.json", manifest)
        fault_injector(scenario_path, mutation)
        _append(manifest, "FAULT_CONFIRMED"); write_json_atomic(experiment / "manifest.json", manifest)
        evidence = evidence_collector(experiment, scenario_path)
        _append(manifest, "EVIDENCE_V4_COLLECTED"); write_json_atomic(experiment / "manifest.json", manifest)
        vector = vector_builder(experiment, evidence)
        diagnosis = rule_engine(vector, location_node=binding.target_switch_node, affected_resource=binding.affected_resource)
        write_json_atomic(experiment / "diagnosis/diagnosis_result_v2.json", diagnosis)
        if diagnosis.get("status") != "diagnosed" or not isinstance(diagnosis.get("prediction"), dict) or diagnosis["prediction"].get("fault_type") != "native_vlan_mismatch":
            raise X3NativeVlanMismatchExperimentError("X3-R4 exact Native VLAN Mismatch rule did not produce the expected diagnosis.")
        _append(manifest, "DIAGNOSIS_VERIFIED"); write_json_atomic(experiment / "manifest.json", manifest)
    except BaseException as error:
        primary = error
    if _recovery_exists(mutation):
        try:
            if fault_restorer(scenario_path, mutation).get("status") != "RESTORATION_CONFIRMED":
                raise X3NativeVlanMismatchExperimentError("X3-R4 restoration record is not confirmed.")
        except BaseException as error:
            restoration_error = error
    after: dict[str, object] | None = None
    if baseline_before and restoration_error is None:
        after = baseline_validator(Path(baseline_validator_path))
        write_json_atomic(experiment / "validation/baseline_after.json", after)
        if after.get("return_code") != 0:
            restoration_error = X3NativeVlanMismatchExperimentError("X3-R4 baseline validation failed after restoration.")
    final = restoration_error or primary
    if final is not None:
        _append(manifest, "FAILED"); manifest["error"] = {"type": type(final).__name__, "message": str(final)}; write_json_atomic(experiment / "manifest.json", manifest)
        raise X3NativeVlanMismatchExperimentError(f"X3-R4 experiment failed: {final}. Artifacts: {experiment}") from final
    if not _restored(mutation):
        raise X3NativeVlanMismatchExperimentError("X3-R4 completed without confirmed restoration.")
    for state in ("FAULT_RESTORED", "BASELINE_RESTORED", "COMPLETED"):
        _append(manifest, state)
    manifest["completed_at_utc"] = utc_now(); write_json_atomic(experiment / "manifest.json", manifest)
    return {"schema_version": 1, "release_id": "X3_R4_NATIVE_VLAN_MISMATCH", "status": "COMPLETED", "experiment_id": run_id, "experiment_directory": str(experiment), "scenario_id": binding.scenario_id, "fault_type": "native_vlan_mismatch", "topology_id": binding.topology_id, "evidence_schema_version": 4, "diagnosis_schema_version": 2, "diagnosis_created": diagnosis is not None, "restoration_confirmed": True, "baseline_valid_after": after is not None and after.get("return_code") == 0, "dataset_row_created": False, "model_operation_performed": False, "metric_created": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated X3-R4 Native VLAN Mismatch lifecycle.")
    parser.add_argument("--scenario", type=Path, required=True); parser.add_argument("--output-root", type=Path, default=Path("data/raw/x3_r4")); parser.add_argument("--baseline-validator", type=Path, required=True); parser.add_argument("--recover-experiment-directory", type=Path)
    args = parser.parse_args()
    try:
        result = recover_x3_r4_experiment(args.scenario, args.recover_experiment_directory, args.baseline_validator) if args.recover_experiment_directory else run_x3_r4_experiment(args.scenario, args.output_root, args.baseline_validator)
    except (X3NativeVlanMismatchError, X3NativeVlanMismatchExperimentError, OSError) as error:
        print(f"[ERROR] {error}"); return 1
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
