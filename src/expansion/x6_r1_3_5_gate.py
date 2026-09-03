"""Append-only R1.3.5 source gate."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from src.expansion.x6_r1_3_4_gate import verify_x6_r1_3_4
from src.orchestration.x6_r1_3_5_baseline_provenance import AUTHORIZATION_VECTOR, RELEASE_ID
ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION_V1.json")
def verify_x6_r1_3_5(root: Path = ROOT) -> dict[str, object]:
    verify_x6_r1_3_4(root)
    plan = json.loads((Path(root)/PLAN).read_text(encoding="utf-8"))
    if plan.get("release_id") != RELEASE_ID or plan.get("runtime_scientific_authorization") != AUTHORIZATION_VECTOR or plan.get("future_authorization",{}).get("real_authorization_record") != "ABSENT": raise ValueError("X6-R1.3.5 authorization boundary drift")
    for row in plan.get("source_bindings", []):
        path = Path(root)/row["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]: raise ValueError("X6-R1.3.5 source binding drift")
    if len(plan.get("source_bindings", [])) < 4: raise ValueError("X6-R1.3.5 bindings incomplete")
    return plan
