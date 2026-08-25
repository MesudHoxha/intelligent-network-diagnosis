from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.expansion.x5_r1_gate import verify_x5_r1_gate

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X5_R2_ROUTE_FILTERING_OR_ADVERTISEMENT_PROBLEM_V1.json")
SIGNATURE = {"ospf_adjacency_full": True, "ospf_route_advertised": False, "ospf_route_installed": False, "route_filter_allows_prefix": False}


def verify_x5_r2_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    parent = verify_x5_r1_gate(root)
    if parent["track"]["next_release"] != "X5_R2_ROUTE_FILTERING_OR_ADVERTISEMENT_PROBLEM":
        raise ValueError("X5-R1 parent drifted")
    plan = json.loads((root / PLAN).read_text())
    if plan["source_boundary"] != {"parent_commit": "6a969dc22b3fc332c0f4d44baa9cc13354ed4c00", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}:
        raise ValueError("X5-R2 boundary drifted")
    if plan["slice"]["signature"] != SIGNATURE or plan["slice"]["rule_id"] != "R_X5_OSPF_002":
        raise ValueError("X5-R2 C5 signature drifted")
    for binding in plan["source_bindings"]:
        path = root / binding["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != binding["sha256"]:
            raise ValueError("X5-R2 source binding drifted: " + binding["path"])
    enabled = {key for key, value in plan["runtime_authorization"].items() if value}
    if enabled != {"containerlab_execution", "network_mutation", "new_evidence_collection", "method_prediction"}:
        raise ValueError("X5-R2 authorization drifted")
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    plan = verify_x5_r2_gate(parser.parse_args().repository_root)
    print("x5_r0_gate=VERIFIED\nx5_r1_gate=VERIFIED\nx5_r2_gate=VERIFIED\nc5_signature=TRUE_FALSE_FALSE_FALSE_PASS\nsource_bindings=" + str(len(plan["source_bindings"])) + "/" + str(len(plan["source_bindings"])) + "_HASH_BOUND_PASS\nnext_release=X5_R3_CLOSEOUT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
