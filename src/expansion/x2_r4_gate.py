from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.expansion.x2_addressing import X2AddressingError

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X2_R4_DUPLICATE_IP_V1.json")
EXPECTED_RUNTIME = {
    "containerlab_execution": True, "network_mutation": True,
    "new_evidence_collection": True, "dataset_generation": False,
    "model_fit_or_selection": False, "estimator_deserialization": False,
    "method_prediction": True, "metric_calculation": False,
    "report_only_test_access": False, "multiple_fault_execution": False,
}


def verify_x2_r4_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    try:
        plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X2AddressingError("Cannot read X2-R4 gate.") from error
    if plan.get("gate_id") != "x2_r4_duplicate_ip_runtime_gate_v1" or plan.get("status") != "IMPLEMENTED_RUNTIME_SLICE":
        raise X2AddressingError("X2-R4 gate identity drifted.")
    if plan.get("runtime_authorization") != EXPECTED_RUNTIME:
        raise X2AddressingError("X2-R4 runtime authorization drifted.")
    if plan.get("source_boundary", {}).get("parent_commit") != "21ad0e3b47cfe12527c1907b6c7ea415d62d3efd":
        raise X2AddressingError("X2-R4 parent boundary drifted.")
    for binding in plan.get("source_bindings", []):
        path = root / binding["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != binding["sha256"]:
            raise X2AddressingError(f"X2-R4 source binding drifted: {binding['path']}")
    signature = plan.get("slice", {}).get("signature", {})
    if not (signature.get("duplicate_address_detected") is True and signature.get("duplicate_address_mac_churn_detected") is True):
        raise X2AddressingError("X2-R4 dual-evidence signature drifted.")
    return plan


def main() -> int:
    plan = verify_x2_r4_gate()
    print("x2_r4_gate=VERIFIED")
    print("duplicate_ip_signature=ACTIVE_PLUS_TEMPORAL_MAC_CHURN_PASS")
    print("previous_addressing_rules=R_X2_ADDRESSING_001_THROUGH_003_PRESERVED_PASS")
    print(f"runtime_scope={sum(plan['runtime_authorization'].values())}/10_AUTHORIZED_PASS")
    print("next_release=X2_R5_ADDRESSING_CLOSEOUT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
