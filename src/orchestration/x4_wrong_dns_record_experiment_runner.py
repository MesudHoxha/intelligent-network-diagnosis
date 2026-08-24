from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.collection.service_state_collector_v4 import build_service_feature_vector_v2_r4, collect_wrong_dns_record_evidence_v4
from src.expansion.x4_wrong_dns_record import X4WrongDnsRecordError, load_wrong_dns_record_scenario
from src.fault_injection.phase6_common import utc_now, write_json_atomic
from src.fault_injection.wrong_dns_record import inject_wrong_dns_record, restore_wrong_dns_record
from src.rules.service_security_rule_engine_x4_r4 import diagnose_dhcp_dns_service_security_v2_r4
from src.runtime.subprocesses import run_capture


def _baseline(path: Path) -> dict[str, object]:
    result = run_capture(["bash", str(path)], timeout_seconds=90.0)
    return {"command": ["bash", str(path)], "return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "timestamp_utc": utc_now()}


def run_x4_r4_experiment(scenario_path: Path, output_root: Path, baseline_validator_path: Path, *, experiment_id: str | None = None) -> dict[str, object]:
    binding = load_wrong_dns_record_scenario(scenario_path); run_id = experiment_id or binding.scenario_id.lower() + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex
    root = Path(output_root) / run_id; root.mkdir(parents=True, exist_ok=False); mutation = root / "mutation"; primary = None; restoration_error = None; before_ok = False
    manifest = {"schema_version": 1, "release_id": "X4_R4_WRONG_DNS_RECORD", "experiment_id": run_id, "scenario_id": binding.scenario_id, "topology_context_id": binding.topology_context_id, "truth_model": "single_fault", "current_state": "CREATED", "state_history": [{"state": "CREATED", "timestamp_utc": utc_now()}]}; write_json_atomic(root / "manifest.json", manifest)
    try:
        before = _baseline(baseline_validator_path); write_json_atomic(root / "validation/baseline_before.json", before); before_ok = before["return_code"] == 0
        if not before_ok: raise X4WrongDnsRecordError("X4-R4 baseline validation failed before mutation.")
        inject_wrong_dns_record(scenario_path, mutation); evidence = collect_wrong_dns_record_evidence_v4(root, scenario_path); vector = build_service_feature_vector_v2_r4(root, evidence); diagnosis = diagnose_dhcp_dns_service_security_v2_r4(vector); write_json_atomic(root / "diagnosis/diagnosis_result_v2.json", diagnosis)
        if diagnosis.get("status") != "diagnosed" or diagnosis.get("prediction", {}).get("fault_type") != "wrong_dns_record": raise X4WrongDnsRecordError("X4-R4 exact D4 rule did not diagnose the fault.")
    except BaseException as error:
        primary = error
    if (mutation / "recovery_intent.json").is_file():
        try: restore_wrong_dns_record(scenario_path, mutation)
        except BaseException as error: restoration_error = error
    after = _baseline(baseline_validator_path) if before_ok and restoration_error is None else None
    if after is not None:
        write_json_atomic(root / "validation/baseline_after.json", after)
        if after["return_code"] != 0: restoration_error = X4WrongDnsRecordError("X4-R4 baseline restoration failed.")
    error = restoration_error or primary
    if error is not None:
        manifest["current_state"] = "FAILED"; manifest["error"] = {"type": type(error).__name__, "message": str(error)}; write_json_atomic(root / "manifest.json", manifest)
        raise X4WrongDnsRecordError("X4-R4 experiment failed: " + str(error)) from error
    manifest["current_state"] = "COMPLETED"; manifest["completed_at_utc"] = utc_now(); write_json_atomic(root / "manifest.json", manifest)
    return {"schema_version": 1, "release_id": "X4_R4_WRONG_DNS_RECORD", "status": "COMPLETED", "experiment_directory": str(root), "evidence_schema_version": 4, "diagnosis_created": True, "restoration_confirmed": True, "baseline_valid_after": True, "dataset_row_created": False, "model_operation_performed": False, "metric_created": False}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--scenario", type=Path, required=True); parser.add_argument("--output-root", type=Path, default=Path("data/raw/x4_r4")); parser.add_argument("--baseline-validator", type=Path, required=True); args = parser.parse_args()
    try: print(json.dumps(run_x4_r4_experiment(args.scenario, args.output_root, args.baseline_validator), indent=2, sort_keys=True)); return 0
    except (X4WrongDnsRecordError, OSError) as error: print("[ERROR] " + str(error)); return 1


if __name__ == "__main__": raise SystemExit(main())
