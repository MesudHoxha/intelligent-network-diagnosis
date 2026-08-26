from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.expansion.x5_r5_gate import verify_x5_r5_c5_operational_policy_correction_gate


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION_V1.json")
SIGNATURE = {"ospf_adjacency_full": True, "ospf_route_advertised": False, "ospf_route_installed": False, "route_filter_allows_prefix": False}


class X5R6GateError(ValueError): pass


def verify_x5_r6_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root); parent = verify_x5_r5_c5_operational_policy_correction_gate(root); plan = json.loads((root / PLAN).read_text())
    if parent["track"]["next_release"] != "X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION": raise X5R6GateError("X5-R5 parent sequence drifted")
    if plan.get("source_boundary") != {"parent_commit": "8ff7a1e788c3571518d97a342918bd9094f32ebd", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}: raise X5R6GateError("X5-R6 source boundary drifted")
    if plan.get("slice", {}).get("signature") != SIGNATURE or plan["slice"].get("rule_id") != "R_X5_OSPF_002": raise X5R6GateError("X5-R6 C5 contract drifted")
    mutation = plan.get("mutation", {})
    if mutation.get("approved_action") != "add ip prefix-list X5-R5-C5-TARGET seq 1 deny 10.51.3.0/24" or mutation.get("attachment_must_remain") != "redistribute connected route-map X5-R5-C5-EXPORT" or mutation.get("forbidden_action") != "remove network 10.51.3.0/24 area 0": raise X5R6GateError("X5-R6 operational policy mutation drifted")
    enabled = {name for name, value in plan.get("runtime_authorization", {}).items() if value}
    if enabled != {"containerlab_execution", "network_mutation", "new_evidence_collection", "method_prediction"}: raise X5R6GateError("X5-R6 runtime authorization drifted")
    if plan.get("track") != {"next_release": "X5_R7_C5_CORRECTED_SUCCESSOR_CLOSEOUT", "x6_status": "PAUSED_UNTIL_X5_R7", "p9_r2_status": "PAUSED_BY_USER"}: raise X5R6GateError("X5-R6 track drifted")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 7: raise X5R6GateError("X5-R6 needs seven source bindings")
    for row in bindings:
        path = root / str(row.get("path")); digest = row.get("sha256")
        if not path.is_file() or not isinstance(digest, str) or hashlib.sha256(path.read_bytes()).hexdigest() != digest: raise X5R6GateError("X5-R6 source binding drifted: " + str(row.get("path")))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repository-root", type=Path, default=ROOT); plan = verify_x5_r6_gate(parser.parse_args().repository_root)
    print("x5_r6_gate=VERIFIED\nc5_signature=TRUE_FALSE_FALSE_FALSE_PASS\nsource_bindings=" + str(len(plan["source_bindings"])) + "/7_HASH_BOUND_PASS\nnext_release=X5_R7_C5_CORRECTED_SUCCESSOR_CLOSEOUT"); return 0


if __name__ == "__main__": raise SystemExit(main())
