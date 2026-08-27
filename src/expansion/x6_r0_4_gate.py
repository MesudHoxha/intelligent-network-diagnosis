"""Source gate for the append-only X6-R0.4 F1 runtime parameter freeze."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.expansion.x6_r0_3_gate import verify_x6_r0_3_f1_pre_runtime_validation
from src.expansion.x6_r0_4_runtime_parameter_freeze import validate_x6_r0_4_runtime_context


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R0_4_F1_RUNTIME_PARAMETER_FREEZE_V1.json")


class X6R04GateError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X6R04GateError(message)


def verify_x6_r0_4_f1_runtime_parameter_freeze(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    verify_x6_r0_3_f1_pre_runtime_validation(root)
    context = validate_x6_r0_4_runtime_context(root)
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    _require(plan.get("release_id") == "X6_R0_4_F1_RUNTIME_PARAMETER_FREEZE", "X6-R0.4 release drifted")
    _require(plan.get("status") == "ACCEPTED_SOURCE_ONLY_RUNTIME_PARAMETER_FREEZE", "X6-R0.4 status drifted")
    _require(plan.get("source_boundary") == {"parent_commit": "956f0cc5a51e7c11f931843580e00000946c3f23", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}, "X6-R0.4 source boundary drifted")
    _require(plan.get("authoritative_runtime_context") == "labs/topologies/x6_r1_packet_loss/runtime_context_v1.json", "X6-R0.4 context authority drifted")
    _require(context["topology"]["mutation_owner"]["node"] == "r2" and context["topology"]["mutation_owner"]["interface"] == "eth2", "X6-R0.4 mutation owner drifted")
    _require(context["qdisc"]["loss_percent"] == "10.000000" and context["rule"]["rule_id"] == "R_X6_PERFORMANCE_001", "X6-R0.4 loss/rule identity drifted")
    current = plan.get("current_release_authorization")
    _require(isinstance(current, dict) and len(current) == 10 and not any(current.values()), "X6-R0.4 current release must remain 0/10")
    future = plan.get("next_release_authorization")
    _require(isinstance(future, dict) and future.get("x6_r1_source_implementation") is True and future.get("x6_r1_controlled_runtime_pilot") is True and not any(value for key, value in future.items() if key not in {"x6_r1_source_implementation", "x6_r1_controlled_runtime_pilot"}), "X6-R0.4 future authorization overreached")
    _require(plan.get("track") == {"next_release": "X6_R1_PACKET_LOSS", "f3_status": "PAUSED_UNTIL_X6_R3", "f4_status": "PAUSED_UNTIL_X6_R4", "p9_r2_status": "PAUSED_BY_USER"}, "X6-R0.4 track drifted")
    bindings = plan.get("source_bindings")
    _require(isinstance(bindings, list) and len(bindings) == 8, "X6-R0.4 requires eight source bindings")
    for row in bindings:
        _require(isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str), "X6-R0.4 binding malformed")
        path = root / row["path"]
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], "X6-R0.4 binding drifted: " + row["path"])
    rule_id = context["rule"]["rule_id"]
    collisions = [path for path in (root / "src/rules").glob("*.py") if rule_id in path.read_text(encoding="utf-8")]
    _require(not collisions, "X6-R0.4 rule identity collides with implemented rule source")
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    plan = verify_x6_r0_4_f1_runtime_parameter_freeze(parser.parse_args().repository_root)
    print("x6_r0_4_f1_runtime_parameter_freeze=VERIFIED")
    print("source_bindings=" + str(len(plan["source_bindings"])) + "/8_HASH_BOUND_PASS")
    print("current_runtime_scientific_authorization=0/10_FALSE_PASS")
    print("next_release_authorization=X6_R1_PACKET_LOSS_SOURCE_AND_CONTROLLED_PILOT_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
