from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.expansion.x5_r4_closeout_gate import verify_x5_r4_corrected_successor_receipt


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X5_R5_C5_OPERATIONAL_POLICY_CORRECTION_DESIGN_GATE_V1.json")
FEATURES = ("ospf_adjacency_full", "ospf_route_advertised", "ospf_route_installed", "route_filter_allows_prefix")
SIGNATURE = (True, False, False, False)
POLICY_CONFIG = Path("labs/topologies/x5_r5_c5_operational_policy/configs/r3.conf")


class X5R5CorrectionDesignError(ValueError):
    pass


def _load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X5R5CorrectionDesignError("Cannot read X5-R5 design artifact: " + str(path)) from error
    if not isinstance(value, dict):
        raise X5R5CorrectionDesignError("X5-R5 design artifact must be an object: " + str(path))
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X5R5CorrectionDesignError(message)


def verify_x5_r5_c5_operational_policy_correction_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    parent = verify_x5_r4_corrected_successor_receipt(repository_root=root, verify_materialized=False)
    _require(parent["summary"]["corrected_c4_authoritative"] is True, "X5-R4 C4 parent drifted")
    plan = _load(root / PLAN)
    _require(plan.get("status") == "ACCEPTED_SOURCE_ONLY_CORRECTION_DESIGN", "X5-R5 status drifted")
    _require(plan.get("source_boundary") == {"parent_commit": "671ce01fcf5ee48e3cbd65aa1182d1e54a509792", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}, "X5-R5 source boundary drifted")
    track = plan.get("track")
    _require(isinstance(track, dict) and track == {"current_release": "X5_R5_C5_OPERATIONAL_POLICY_CORRECTION_DESIGN_GATE", "next_release": "X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION", "following_release": "X5_R7_C5_CORRECTED_SUCCESSOR_CLOSEOUT", "x6_status": "PAUSED_PENDING_X5_C5_CORRECTION", "p9_r2_status": "PAUSED_BY_USER"}, "X5-R5 release sequence drifted")
    historical = plan.get("historical_evidence")
    _require(historical == {"x5_r4_c4": "AUTHORITATIVE_UNCHANGED", "x5_r2_c5": "RETAINED_HISTORICAL_NON_AUTHORITATIVE_FOR_POLICY_FEATURE_SCIENTIFIC_USE", "x5_r3_and_x5_r4_receipts": "RETAINED_HISTORICAL_NOT_REWRITTEN"}, "X5-R5 historical boundary drifted")
    contract = plan.get("frozen_feature_contract")
    _require(isinstance(contract, dict) and tuple(contract.get("feature_order", ())) == FEATURES and tuple(contract.get("conditional_runtime_signature", ())) == SIGNATURE, "X5-R5 C5 feature signature drifted")
    _require(contract.get("rule") == {"rule_id": "R_X5_OSPF_002", "fault_type": "route_filtering_or_advertisement_problem"}, "X5-R5 C5 rule identity drifted")
    authorization = plan.get("runtime_authorization")
    _require(isinstance(authorization, dict) and len(authorization) == 10 and all(value is False for value in authorization.values()), "X5-R5 must authorize 0/10 runtime/scientific operations")
    config = (root / POLICY_CONFIG).read_text(encoding="utf-8")
    _require("network 10.51.3.0/24 area 0" not in config, "X5-R5 policy baseline must not directly originate expected prefix")
    for line in ("redistribute connected route-map X5-R5-C5-EXPORT", "ip prefix-list X5-R5-C5-TARGET seq 5 permit 10.51.3.0/24", "route-map X5-R5-C5-EXPORT permit 10", "match ip address prefix-list X5-R5-C5-TARGET"):
        _require(line in config, "X5-R5 operational policy attachment drifted: " + line)
    bindings = plan.get("source_bindings")
    _require(isinstance(bindings, list) and len(bindings) == 6, "X5-R5 must bind six source artifacts")
    for row in bindings:
        _require(isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str), "X5-R5 source binding malformed")
        path = root / row["path"]
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], "X5-R5 source binding drifted: " + row["path"])
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    plan = verify_x5_r5_c5_operational_policy_correction_gate(parser.parse_args().repository_root)
    print("x5_r5_c5_operational_policy_correction_gate=VERIFIED")
    print("operational_policy=REDISTRIBUTE_CONNECTED_ROUTE_MAP_PREFIX_LIST_PASS")
    print("conditional_c5_signature=true,false,false,false")
    print("runtime_scientific_authorization=0/10_FALSE_PASS")
    print("source_bindings=" + str(len(plan["source_bindings"])) + "/6_HASH_BOUND_PASS")
    print("next_release=X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
