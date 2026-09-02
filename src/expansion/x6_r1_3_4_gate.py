"""Source gate for R1.3.4; it preserves the 0/10 false authorization boundary."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.expansion.x6_r1_3_3_gate import verify_x6_r1_3_3
from src.orchestration.x6_r1_3_4_baseline_execution import RELEASE_ID

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R1_3_4_BASELINE_ONLY_RUNTIME_EXECUTION_AND_MATERIALIZED_CONTROL_COMPLETION_V1.json")
FALSE_AUTHORIZATION = {"containerlab": False, "measurement": False, "f1_revalidation": False, "f2": False, "f3": False, "f4": False, "dataset": False, "ml_hybrid": False, "api": False, "p9_r2": False}


def verify_x6_r1_3_4(root: Path = ROOT) -> dict[str, object]:
    verify_x6_r1_3_3(root)
    plan = json.loads((Path(root) / PLAN).read_text(encoding="utf-8"))
    if plan.get("release_id") != RELEASE_ID or plan.get("source_boundary") != "4fb867476ffaa8e5ca5b090558b1f0fd5be551e2":
        raise ValueError("X6-R1.3.4 identity/boundary drift")
    if plan.get("runtime_scientific_authorization") != FALSE_AUTHORIZATION:
        raise ValueError("X6-R1.3.4 must preserve 0/10 false authorization")
    if plan.get("future_authorization") != {"scope": "BASELINE_ONLY_QUALIFICATION", "maximum_attempts": 1, "real_authorization_record": "ABSENT", "runtime_enabled": False, "test_authorization_only": True}:
        raise ValueError("X6-R1.3.4 future authorization boundary drift")
    contract = plan.get("execution_contract")
    if not isinstance(contract, dict) or contract.get("mutation") != "FORBIDDEN" or contract.get("threshold_freeze") != "CANONICAL_C01_C10_BEFORE_C11":
        raise ValueError("X6-R1.3.4 frozen execution contract drift")
    rows = plan.get("source_bindings")
    if not isinstance(rows, list) or len(rows) != 6:
        raise ValueError("X6-R1.3.4 requires six source bindings")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("X6-R1.3.4 binding schema drift")
        path = Path(root) / row["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("X6-R1.3.4 source binding drift")
    return plan
