from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.expansion.x5_r10_closeout_gate import verify_x5_r10_closeout


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X5_R11_CLEAN_CHECKOUT_TEST_CORRECTION_V1.json")


class X5R11CleanCheckoutError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X5R11CleanCheckoutError(message)


def verify_x5_r11_clean_checkout_test_correction(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    verify_x5_r10_closeout(root)
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    _require(plan.get("status") == "ACCEPTED_SOURCE_ONLY_TEST_CORRECTION", "X5-R11 status drifted")
    _require(plan.get("source_boundary") == {"parent_commit": "c198db3237daaef578c34677d293e764d0607e97", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}, "X5-R11 source boundary drifted")
    _require(plan.get("preserved_boundaries") == {"authoritative_c4": "X5_R4_OSPF_CORRECTION_AND_REVALIDATION:false,false,false,true:R_X5_OSPF_001", "authoritative_c5": "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION:true,false,false,false:R_X5_OSPF_002", "production_diagnosis_orchestration_and_feature_vector_semantics": "UNCHANGED", "accepted_evidence_receipts_and_x6_r0_1_methodology": "UNCHANGED"}, "X5-R11 preservation boundary drifted")
    _require(plan.get("track") == {"next_release": "X6_R1_PACKET_LOSS", "x6_r1_status": "PAUSED_BY_USER", "p9_r2_status": "PAUSED_BY_USER"}, "X5-R11 pause boundary drifted")
    authorization = plan.get("runtime_authorization")
    _require(isinstance(authorization, dict) and len(authorization) == 10 and not any(authorization.values()), "X5-R11 must authorize 0/10 runtime/scientific operations")
    bindings = plan.get("source_bindings")
    _require(isinstance(bindings, list) and len(bindings) == 2, "X5-R11 requires two source bindings")
    for binding in bindings:
        _require(isinstance(binding, dict) and isinstance(binding.get("path"), str) and isinstance(binding.get("sha256"), str), "X5-R11 source binding malformed")
        path = root / binding["path"]
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == binding["sha256"], "X5-R11 source binding drifted: " + binding["path"])
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    args = parser.parse_args()
    plan = verify_x5_r11_clean_checkout_test_correction(args.repository_root)
    print("x5_r11_clean_checkout_test_correction=VERIFIED")
    print("source_bindings=" + str(len(plan["source_bindings"])) + "/2_HASH_BOUND_PASS")
    print("runtime_scientific_authorization=0/10_FALSE_PASS")
    print("next_release=X6_R1_PACKET_LOSS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
