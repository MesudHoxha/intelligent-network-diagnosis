from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.expansion.x5_r7_closeout_gate import verify_x5_r7_closeout


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X5_R8_C5_RUNTIME_SAFETY_CORRECTION_GATE_V1.json")


class X5R8RuntimeSafetyError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X5R8RuntimeSafetyError(message)


def verify_x5_r8_runtime_safety_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    verify_x5_r7_closeout(root, verify_materialized=False)
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    _require(plan.get("status") == "ACCEPTED_SOURCE_ONLY_RUNTIME_SAFETY_CORRECTION", "X5-R8 status drifted")
    _require(plan.get("source_boundary") == {"parent_commit": "84372a5f8cd67196e335538bb7638a1a6426848a", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}, "X5-R8 source boundary drifted")
    _require(plan.get("track") == {"current_release": "X5_R8_C5_RUNTIME_SAFETY_CORRECTION_GATE", "next_release": "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION", "following_release": "X5_R10_C5_CRASH_SAFE_AUTHORITATIVE_CLOSEOUT", "x6_status": "PAUSED_PENDING_X5_C5_RUNTIME_SAFETY_REVALIDATION", "p9_r2_status": "PAUSED_BY_USER"}, "X5-R8 release sequence drifted")
    contract = plan.get("runtime_safety_contract", {})
    _require(contract.get("action_states") == ["PLANNED", "ATTEMPTED", "COMMAND_ACCEPTED", "COMMAND_REJECTED", "MUTATION_EFFECTIVE", "MUTATION_NOT_EFFECTIVE", "RESTORED", "FAILED"], "X5-R8 action states drifted")
    _require("before any mutation command" in str(contract.get("planned_action_journal")), "X5-R8 must journal before a mutation")
    _require("new-process" in str(contract.get("standalone_recovery")), "X5-R8 standalone recovery drifted")
    authorization = plan.get("runtime_authorization")
    _require(isinstance(authorization, dict) and len(authorization) == 10 and all(value is False for value in authorization.values()), "X5-R8 must authorize 0/10 runtime/scientific operations")
    bindings = plan.get("source_bindings")
    _require(isinstance(bindings, list) and len(bindings) == 6, "X5-R8 requires six source bindings")
    for row in bindings:
        _require(isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str), "X5-R8 source binding malformed")
        path = root / row["path"]
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], "X5-R8 source binding drifted: " + row["path"])
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    plan = verify_x5_r8_runtime_safety_gate(parser.parse_args().repository_root)
    print("x5_r8_runtime_safety_gate=VERIFIED")
    print("source_bindings=" + str(len(plan["source_bindings"])) + "/6_HASH_BOUND_PASS")
    print("runtime_scientific_authorization=0/10_FALSE_PASS")
    print("next_release=X5_R9_C5_RUNTIME_SAFETY_REVALIDATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
