"""Source-only gate for the X6-R1.3.2 enforcement correction."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.expansion.x6_r1_3_1_gate import verify_x6_r1_3_1


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R1_3_2_BASELINE_EXECUTION_AND_PROVENANCE_ENFORCEMENT_CORRECTION_V1.json")


def verify_x6_r1_3_2(root: Path = ROOT) -> dict[str, object]:
    verify_x6_r1_3_1(root)
    plan = json.loads((Path(root) / PLAN).read_text(encoding="utf-8"))
    if plan.get("release_id") != "X6_R1_3_2_BASELINE_EXECUTION_AND_PROVENANCE_ENFORCEMENT_CORRECTION":
        raise ValueError("X6-R1.3.2 identity drift")
    if plan.get("source_boundary") != "770ed88a80ddc6b9441d376cd5b46f7506b38566" or plan.get("extension_policy") != "APPEND_ONLY_SOURCE_ONLY_PROSPECTIVE_METHODOLOGY":
        raise ValueError("X6-R1.3.2 append-only boundary drift")
    authorization = plan.get("runtime_scientific_authorization")
    if not isinstance(authorization, dict) or len(authorization) != 10 or any(authorization.values()):
        raise ValueError("X6-R1.3.2 must retain 0/10 authorization")
    if plan.get("next_action") != "X6_R1_4_BASELINE_ONLY_RUNTIME_AUTHORIZATION_REVIEW":
        raise ValueError("X6-R1.3.2 next milestone drift")
    required = {
        "physical_schedule": "MATERIALIZED_AND_INDEPENDENTLY_VERIFIED",
        "provenance": "STRUCTURAL_AND_MATERIALIZED_VERIFICATION_SEPARATED",
        "terminal": "QUALIFIED_REQUIRES_MATERIALIZED_DERIVATION",
        "threshold_math": "X6_R0_2_R0_3_UNCHANGED",
    }
    if plan.get("enforcement") != required:
        raise ValueError("X6-R1.3.2 enforcement boundary drift")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 4:
        raise ValueError("X6-R1.3.2 requires four source bindings")
    for row in bindings:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str):
            raise ValueError("X6-R1.3.2 source binding malformed")
        path = Path(root) / row["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("X6-R1.3.2 source binding drifted: " + row["path"])
    return plan


__all__ = ["verify_x6_r1_3_2"]
