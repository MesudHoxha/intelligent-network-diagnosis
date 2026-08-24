from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from src.collection.service_state_collector_v3 import build_service_feature_vector_v2_r3, collect_dns_service_down_evidence_v4
from src.expansion.x4_dns_service_down import X4DnsServiceDownError, load_dns_service_down_scenario
from src.fault_injection.dns_service_down import inject_dns_service_down, restore_dns_service_down
from src.fault_injection.phase6_common import utc_now, write_json_atomic
from src.rules.service_security_rule_engine_x4_r3 import diagnose_dhcp_dns_service_security_v2
from src.runtime.subprocesses import run_capture


def _baseline(path: Path) -> dict[str, object]:
    result = run_capture(["bash", str(path)], timeout_seconds=90.0)
    return {"command": ["bash", str(path)], "return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "timestamp_utc": utc_now()}


def run_x4_r3_experiment(scenario_path: Path, output_root: Path, baseline_validator_path: Path, *, experiment_id: str | None = None) -> dict[str, object]:
    binding = load_dns_service_down_scenario(scenario_path); run_id = experiment_id or binding.scenario_id.lower() + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex
    root = Path(output_root) / run_id; root.mkdir(parents=True, exist_ok=False); mutation = root / "mutation"; primary = None; restoration_error = None; before_ok = False
    manifest = {"schema_version": 1, "release_id": binding.scenario_id, "compatibility_alias": binding.compatibility_alias, "experiment_id": run_id, "scenario_id": binding.scenario_id, "topology_context_id": binding.topology_context_id, "truth_model": "single_fault", "current_state": "CREATED", "state_history": [{"state": "CREATED", "timestamp_utc": utc_now()}]}
    write_json_atomic(root / "manifest.json", manifest)
    try:
        before = _baseline(baseline_validator_path); write_json_atomic(root / "validation/baseline_before.json", before); before_ok = before["return_code"] == 0
        if not before_ok: raise X4DnsServiceDownError("X4-R3 baseline validation failed before mutation.")
        inject_dns_service_down(scenario_path, mutation)
        evidence = collect_dns_service_down_evidence_v4(root, scenario_path)
        vector = build_service_feature_vector_v2_r3(root, evidence); diagnosis = diagnose_dhcp_dns_service_security_v2(vector)
        write_json_atomic(root / "diagnosis/diagnosis_result_v2.json", diagnosis)
        if diagnosis.get("status") != "diagnosed" or diagnosis.get("prediction", {}).get("fault_type") != "dns_service_down": raise X4DnsServiceDownError("X4-R3 exact D3 rule did not diagnose the fault.")
    except BaseException as error:
        primary = error
    if (mutation / "recovery_intent.json").is_file():
        try: restore_dns_service_down(scenario_path, mutation)
        except BaseException as error: restoration_error = error
    after = _baseline(baseline_validator_path) if before_ok and restoration_error is None else None
    if after is not None:
        write_json_atomic(root / "validation/baseline_after.json", after)
        if after["return_code"] != 0: restoration_error = X4DnsServiceDownError("X4-R3 baseline restoration failed.")
    error = restoration_error or primary
    if error is not None:
        manifest["current_state"] = "FAILED"; manifest["error"] = {"type": type(error).__name__, "message": str(error)}; write_json_atomic(root / "manifest.json", manifest)
        raise X4DnsServiceDownError("X4-R3 experiment failed: " + str(error)) from error
    manifest["current_state"] = "COMPLETED"; manifest["completed_at_utc"] = utc_now(); write_json_atomic(root / "manifest.json", manifest)
    return {"schema_version": 1, "release_id": binding.scenario_id, "compatibility_alias": binding.compatibility_alias, "status": "COMPLETED", "experiment_directory": str(root), "evidence_schema_version": 4, "diagnosis_created": True, "restoration_confirmed": True, "baseline_valid_after": True, "dataset_row_created": False, "model_operation_performed": False, "metric_created": False}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--scenario", type=Path, required=True); parser.add_argument("--output-root", type=Path, default=Path("data/raw/x4_r3")); parser.add_argument("--baseline-validator", type=Path, required=True); args = parser.parse_args()
    try: print(json.dumps(run_x4_r3_experiment(args.scenario, args.output_root, args.baseline_validator), indent=2, sort_keys=True)); return 0
    except (X4DnsServiceDownError, OSError) as error: print("[ERROR] " + str(error)); return 1


if __name__ == "__main__": raise SystemExit(main())
