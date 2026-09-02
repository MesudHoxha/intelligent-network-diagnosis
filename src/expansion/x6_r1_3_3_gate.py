"""Source gate for X6-R1.3.3; preparation never enables runtime."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from src.expansion.x6_r1_3_2_gate import verify_x6_r1_3_2
from src.orchestration.x6_r1_3_3_baseline_only_runner import RELEASE_ID, SCOPE, frozen_schedule

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R1_3_3_BASELINE_ONLY_RUNTIME_HARNESS_AND_CONTROL_EVIDENCE_PREPARATION_V1.json")

def verify_x6_r1_3_3(root: Path = ROOT) -> dict[str, object]:
    verify_x6_r1_3_2(root)
    plan = json.loads((Path(root) / PLAN).read_text())
    if plan.get("release_id") != RELEASE_ID or plan.get("source_boundary") != "b0abfcb1803229bd7940456da1f3307c6ea489ff": raise ValueError("X6-R1.3.3 identity/boundary drift")
    if plan.get("runtime_scientific_authorization") != {"containerlab": False, "measurement": False, "f1_revalidation": False, "f2": False, "f3": False, "f4": False, "dataset": False, "ml_hybrid": False, "api": False, "p9_r2": False}: raise ValueError("X6-R1.3.3 must retain 0/10 authorization")
    if plan.get("future_authorization") != {"scope": SCOPE, "maximum_attempts": 1, "real_authorization_record": "ABSENT", "runtime_enabled": False}: raise ValueError("X6-R1.3.3 authorization preparation drift")
    if plan.get("schedule") != frozen_schedule(): raise ValueError("X6-R1.3.3 frozen schedule drift")
    for row in plan.get("source_bindings", []):
        path = Path(root) / row.get("path", "")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.get("sha256"): raise ValueError("X6-R1.3.3 source binding drift")
    if len(plan.get("source_bindings", [])) != 6: raise ValueError("X6-R1.3.3 requires six bindings")
    return plan
