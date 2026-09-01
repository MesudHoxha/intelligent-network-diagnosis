"""Source-only gate for X6-R1.3 prospective baseline methodology."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.expansion.x6_r1_2_gate import verify_x6_r1_2


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R1_3_BASELINE_STABILITY_AND_HOST_PROVENANCE_METHOD_GATE_V1.json")


def verify_x6_r1_3(root: Path = ROOT) -> dict[str, object]:
    verify_x6_r1_2(root)
    plan = json.loads((Path(root) / PLAN).read_text(encoding="utf-8"))
    if not isinstance(plan, dict) or plan.get("release_id") != "X6_R1_3_BASELINE_STABILITY_AND_HOST_PROVENANCE_METHOD_GATE":
        raise ValueError("X6-R1.3 identity drift")
    authorization = plan.get("runtime_scientific_authorization")
    if not isinstance(authorization, dict) or len(authorization) != 10 or any(authorization.values()):
        raise ValueError("X6-R1.3 must retain 0/10 authorization")
    if plan.get("numeric_limits_status") != "UNRESOLVED_NO_RUNTIME_DERIVATION" or plan.get("next_action") != "SEPARATE_REVIEWED_BASELINE_ONLY_RUNTIME_AUTHORIZATION":
        raise ValueError("X6-R1.3 cannot manufacture qualification limits or pilot authority")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 5:
        raise ValueError("X6-R1.3 requires five source bindings")
    for row in bindings:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str):
            raise ValueError("X6-R1.3 source binding malformed")
        path = Path(root) / row["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("X6-R1.3 source binding drifted: " + row["path"])
    return plan
