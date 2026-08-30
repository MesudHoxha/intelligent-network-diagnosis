"""Source gate for the X6-R0.7 NetEm prerequisite correction."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.expansion.x6_r0_6_gate import verify_x6_r0_6

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R0_7_NETEM_RUNTIME_PREREQUISITE_CORRECTION_V1.json")


class X6R07GateError(ValueError):
    pass


def verify_x6_r0_7(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root); verify_x6_r0_6(root)
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    if plan.get("release_id") != "X6_R0_7_NETEM_RUNTIME_PREREQUISITE_CORRECTION": raise X6R07GateError("X6-R0.7 release identity drifted")
    if plan.get("source_boundary") != {"parent_commit": "f737c05fde265610e2cddf0b536b4a30fe37bb5b", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}: raise X6R07GateError("X6-R0.7 source boundary drifted")
    if plan.get("root_cause") != "HOST_SCH_NETEM_MODULE_UNLOADED_BEFORE_X6_R1_MUTATION" or plan.get("existing_image_and_topology_changed") is not False: raise X6R07GateError("X6-R0.7 root-cause or immutability boundary drifted")
    if plan.get("replacement_pilot") != {"authorization": "ONE_AFTER_X6_R0_7_PUBLICATION_ONLY", "classification": "PREREQUISITE_RECOVERY_NOT_OUTCOME_BASED_TUNING", "prior_attempt": "DIAGNOSTIC_NON_AUTHORITATIVE_NO_FAULT_WINDOW"}: raise X6R07GateError("X6-R0.7 replacement-pilot boundary drifted")
    authorization = plan.get("runtime_scientific_authorization")
    if not isinstance(authorization, dict) or len(authorization) != 10 or any(authorization.values()): raise X6R07GateError("X6-R0.7 must retain 0/10 authorization")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 5: raise X6R07GateError("X6-R0.7 requires five source bindings")
    for row in bindings:
        path = root / row["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]: raise X6R07GateError("X6-R0.7 source binding drifted: " + row["path"])
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repository-root", type=Path, default=ROOT)
    plan = verify_x6_r0_7(parser.parse_args().repository_root)
    print("x6_r0_7=VERIFIED"); print("source_bindings=" + str(len(plan["source_bindings"])) + "/5_HASH_BOUND_PASS"); print("runtime_scientific_authorization=0/10_FALSE_PASS")
    return 0


if __name__ == "__main__": raise SystemExit(main())
