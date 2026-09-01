"""Source-only gate for the X6-R1.3.1 execution-contract freeze."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.expansion.x6_r1_3_gate import verify_x6_r1_3

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R1_3_1_BASELINE_ONLY_EXECUTION_CONTRACT_FREEZE_V1.json")


def verify_x6_r1_3_1(root: Path = ROOT) -> dict[str, object]:
    verify_x6_r1_3(root)
    plan = json.loads((Path(root) / PLAN).read_text(encoding="utf-8"))
    if plan.get("release_id") != "X6_R1_3_1_BASELINE_ONLY_EXECUTION_CONTRACT_FREEZE":
        raise ValueError("X6-R1.3.1 identity drift")
    if plan.get("threshold_cohorts") != {"construction": [f"C{i:02d}" for i in range(1, 11)], "calibration_validation": [f"C{i:02d}" for i in range(11, 21)], "independent_holdout": [f"H{i:02d}" for i in range(1, 11)]}:
        raise ValueError("X6-R1.3.1 cohort boundary drift")
    authorization = plan.get("runtime_scientific_authorization")
    if not isinstance(authorization, dict) or len(authorization) != 10 or any(authorization.values()):
        raise ValueError("X6-R1.3.1 must retain 0/10 authorization")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 4:
        raise ValueError("X6-R1.3.1 requires four source bindings")
    for row in bindings:
        path = Path(root) / row["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("X6-R1.3.1 source binding drifted: " + row["path"])
    return plan
