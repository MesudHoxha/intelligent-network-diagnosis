from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Callable

import yaml

from src.collection.evidence_collector_v3 import (
    EVIDENCE_PATH,
    collect_evidence_v3,
    load_observation_profile_v2,
)
from src.fault_injection.phase6_common import (
    load_json_object,
    load_phase6_scenario,
    utc_now,
    write_json_atomic,
)
from src.fault_injection.registry import inject_fault, restore_fault
from src.rules.rule_engine_v3 import diagnose_evidence_v3
from src.verification.fault_evidence_v3 import (
    verify_fault_evidence_v3,
)
from src.verification.healthy_evidence_v3 import (
    verify_healthy_evidence_v3,
)


class Phase6SmokeRunnerError(RuntimeError):
    """Raised when a P6-R4 smoke execution fails."""


BaselineValidator = Callable[[Path], dict[str, object]]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_baseline_validator(script_path: Path) -> dict[str, object]:
    process = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    result = {
        "command": ["bash", str(script_path)],
        "return_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "timestamp_utc": utc_now(),
    }
    if process.returncode != 0:
        raise Phase6SmokeRunnerError(
            "The complete TOP-01 baseline validator failed.\n"
            + process.stdout
            + process.stderr
        )
    return result


def _require_rule_match(
    diagnosis: dict[str, Any],
    binding,
) -> dict[str, object]:
    expected_fault_type = binding.fault["type"]
    expected_location = binding.fault["target_node"]
    expected_prefix = binding.scenario["ground_truth"][
        "affected_prefix"
    ]
    produced = diagnosis.get("diagnosis")
    passed = (
        diagnosis.get("status") == "DIAGNOSIS_PRODUCED"
        and isinstance(produced, dict)
        and produced.get("fault_type") == expected_fault_type
        and produced.get("location") == expected_location
        and produced.get("affected_prefix") == expected_prefix
    )
    evaluation = {
        "schema_version": 1,
        "status": "P6_R4_RULE_MATCH_VERIFIED" if passed else "MISMATCH",
        "expected_fault_type": expected_fault_type,
        "predicted_fault_type": (
            produced.get("fault_type")
            if isinstance(produced, dict)
            else None
        ),
        "expected_location": expected_location,
        "predicted_location": (
            produced.get("location")
            if isinstance(produced, dict)
            else None
        ),
        "expected_affected_prefix": expected_prefix,
        "predicted_affected_prefix": (
            produced.get("affected_prefix")
            if isinstance(produced, dict)
            else None
        ),
        "exact_match": passed,
    }
    if not passed:
        raise Phase6SmokeRunnerError(
            "The Evidence-only Phase 6 rule diagnosis did not match the "
            "reviewed smoke ground truth."
        )
    return evaluation


def _restoration_required(mutation_directory: Path) -> bool:
    injection_path = mutation_directory / "injection_record.json"
    if not injection_path.exists():
        return False
    record = load_json_object(injection_path)
    return (
        record.get("mutation_applied") is True
        and not (
            mutation_directory / "restoration_record.json"
        ).exists()
    )


def run_phase6_smoke(
    scenario_path: Path,
    healthy_scenario_path: Path,
    output_directory: Path,
    baseline_script: Path,
    *,
    baseline_validator: BaselineValidator = run_baseline_validator,
) -> dict[str, object]:
    scenario_path = Path(scenario_path)
    healthy_scenario_path = Path(healthy_scenario_path)
    output_directory = Path(output_directory)
    baseline_script = Path(baseline_script)
    if output_directory.exists():
        raise Phase6SmokeRunnerError(
            f"P6-R4 smoke output already exists: {output_directory}"
        )
    output_directory.mkdir(parents=True)

    # Ground truth is used only by the evaluator after the evidence-only
    # rule prediction has been persisted.
    document = yaml.safe_load(
        scenario_path.read_text(encoding="utf-8")
    )
    fault_type = document["scenario"]["fault"]["type"]
    binding = load_phase6_scenario(scenario_path, fault_type)
    mutation_directory = output_directory / "mutation"
    fault_evidence_directory = output_directory / "fault_evidence"
    restored_healthy_directory = output_directory / "restored_healthy"

    baseline_before = baseline_validator(baseline_script)
    write_json_atomic(
        output_directory / "baseline_before.json",
        baseline_before,
    )
    injection: object | None = None
    fault_verification: dict[str, object] | None = None
    diagnosis: dict[str, Any] | None = None
    evaluation: dict[str, object] | None = None
    primary_error: Exception | None = None

    try:
        injection = inject_fault(
            fault_type,
            scenario_path,
            mutation_directory,
        )
        profile = load_observation_profile_v2(scenario_path)
        collect_evidence_v3(
            fault_evidence_directory,
            profile,
        )
        fault_verification = verify_fault_evidence_v3(
            fault_evidence_directory,
            scenario_path,
        )
        write_json_atomic(
            output_directory / "fault_verification.json",
            fault_verification,
        )
        evidence = load_json_object(
            fault_evidence_directory / EVIDENCE_PATH
        )
        diagnosis = diagnose_evidence_v3(evidence)
        write_json_atomic(
            output_directory / "diagnosis.json",
            diagnosis,
        )
        evaluation = _require_rule_match(diagnosis, binding)
        write_json_atomic(
            output_directory / "rule_evaluation.json",
            evaluation,
        )
    except Exception as error:
        primary_error = error

    restoration: object | None = None
    restoration_error: Exception | None = None
    if _restoration_required(mutation_directory):
        try:
            restoration = restore_fault(
                fault_type,
                scenario_path,
                mutation_directory,
            )
        except Exception as error:
            restoration_error = error
    elif (mutation_directory / "restoration_record.json").exists():
        restoration = load_json_object(
            mutation_directory / "restoration_record.json"
        )

    if restoration_error is not None:
        write_json_atomic(
            output_directory / "smoke_status.json",
            {
                "status": "RESTORATION_FAILED",
                "fault_type": fault_type,
                "error": str(restoration_error),
            },
        )
        raise Phase6SmokeRunnerError(
            "P6-R4 exact restoration failed; no further smoke class is "
            "authorized."
        ) from restoration_error
    if restoration is None:
        write_json_atomic(
            output_directory / "smoke_status.json",
            {
                "status": "INJECTION_OR_RESTORATION_INCOMPLETE",
                "fault_type": fault_type,
                "error": str(primary_error) if primary_error else None,
            },
        )
        raise Phase6SmokeRunnerError(
            "P6-R4 did not produce a confirmed restoration record."
        ) from primary_error

    baseline_after = baseline_validator(baseline_script)
    write_json_atomic(
        output_directory / "baseline_after.json",
        baseline_after,
    )
    healthy_profile = load_observation_profile_v2(
        healthy_scenario_path
    )
    collect_evidence_v3(
        restored_healthy_directory,
        healthy_profile,
    )
    healthy_verification = verify_healthy_evidence_v3(
        restored_healthy_directory,
        healthy_scenario_path,
    )
    write_json_atomic(
        output_directory / "restored_healthy_verification.json",
        healthy_verification,
    )

    if primary_error is not None:
        write_json_atomic(
            output_directory / "smoke_status.json",
            {
                "status": "FAULT_GATE_FAILED_AFTER_SAFE_RESTORATION",
                "fault_type": fault_type,
                "error": str(primary_error),
                "baseline_after_restoration": "PASS",
                "healthy_evidence_after_restoration": "PASS",
            },
        )
        raise Phase6SmokeRunnerError(
            "P6-R4 fault gate failed, but exact restoration and the "
            "healthy baseline were confirmed."
        ) from primary_error

    assert injection is not None
    assert fault_verification is not None
    assert diagnosis is not None
    assert evaluation is not None
    summary = {
        "status": "P6_R4_NEW_CLASS_SMOKE_VERIFIED",
        "fault_type": fault_type,
        "scenario_id": binding.scenario["id"],
        "scenario_sha256": binding.sha256,
        "injection_status": injection["status"],
        "fault_evidence_status": fault_verification["status"],
        "fault_evidence_sha256": fault_verification["evidence_sha256"],
        "raw_artifact_count": fault_verification["raw_artifact_count"],
        "diagnosis_method": diagnosis["method"],
        "matched_rules": diagnosis["matched_rules"],
        "rule_exact_match": evaluation["exact_match"],
        "restoration_status": restoration["status"],
        "baseline_before_return_code": baseline_before["return_code"],
        "baseline_after_return_code": baseline_after["return_code"],
        "restored_healthy_status": healthy_verification["status"],
        "restored_healthy_evidence_sha256": (
            healthy_verification["evidence_sha256"]
        ),
        "injection_record_sha256": _sha256(
            mutation_directory / "injection_record.json"
        ),
        "restoration_record_sha256": _sha256(
            mutation_directory / "restoration_record.json"
        ),
        "diagnosis_sha256": _sha256(
            output_directory / "diagnosis.json"
        ),
    }
    write_json_atomic(
        output_directory / "smoke_status.json",
        summary,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one fail-stop P6-R4 new-class smoke gate."
    )
    parser.add_argument("--scenario", type=Path, required=True)
    parser.add_argument(
        "--healthy-scenario",
        type=Path,
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--baseline-script",
        type=Path,
        required=True,
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        summary = run_phase6_smoke(
            arguments.scenario,
            arguments.healthy_scenario,
            arguments.output,
            arguments.baseline_script,
        )
    except Exception as error:
        print(f"[ERROR] {error}")
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
