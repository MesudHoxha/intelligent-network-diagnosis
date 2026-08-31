"""Source and materialized failure-closeout gate for the consumed X6-R1 pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from src.expansion.x6_r1_1_failure_audit import audit_baseline_after
from src.expansion.x6_r1_gate import verify_x6_r1_source

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R1_1_FAILED_PILOT_TERMINALIZATION_AND_BASELINE_RECOVERY_AUDIT_V1.json")
RECEIPT = Path("plans/expansion/X6_R1_1_FAILED_PILOT_FAILURE_RECEIPT_V1.json")


class X6R11GateError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X6R11GateError("cannot read: " + str(path)) from error
    if not isinstance(value, dict):
        raise X6R11GateError("object required: " + str(path))
    return value


def _relative(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise X6R11GateError("canonical relative path required")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise X6R11GateError("unsafe receipt path: " + value)
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_x6_r1_1(repository_root: Path = ROOT, *, verify_materialized: bool = False) -> dict[str, object]:
    root = Path(repository_root)
    verify_x6_r1_source(root)
    plan = _load(root / PLAN)
    receipt = _load(root / RECEIPT)
    if plan.get("release_id") != "X6_R1_1_FAILED_PILOT_TERMINALIZATION_AND_BASELINE_RECOVERY_AUDIT" or plan.get("source_boundary") != "430333f4cc78ebad5aa3bdc1a1e7a24b1d991c11":
        raise X6R11GateError("X6-R1.1 identity or boundary drifted")
    authorization = plan.get("runtime_scientific_authorization")
    if not isinstance(authorization, dict) or len(authorization) != 10 or any(authorization.values()):
        raise X6R11GateError("X6-R1.1 must grant no runtime/scientific authorization")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 4:
        raise X6R11GateError("X6-R1.1 requires four source bindings")
    for row in bindings:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str):
            raise X6R11GateError("source binding malformed")
        if _digest(root / row["path"]) != row["sha256"]:
            raise X6R11GateError("source binding drifted: " + row["path"])
    if receipt.get("classification") != "DIAGNOSTIC_NON_AUTHORITATIVE" or receipt.get("pilot_authorization") != "PILOT_CONSUMED" or receipt.get("baseline_after_status") != "BASELINE_INVALID_AFTER":
        raise X6R11GateError("failure classification drifted")
    run = _relative(receipt.get("relative_run_path")); run_root = root / run
    if not run_root.is_dir():
        if verify_materialized:
            raise X6R11GateError("required materialized consumed tree is absent: " + run)
        return {"source": plan, "materialized": "SKIPPED_PRIVATE_ARCHIVE_ABSENT"}
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 32:
        raise X6R11GateError("receipt must bind all 32 existing artifacts")
    listed: set[str] = set()
    for row in artifacts:
        if not isinstance(row, dict):
            raise X6R11GateError("receipt artifact malformed")
        relative = _relative(row.get("path")); path = run_root / relative
        if relative in listed or not path.is_file() or path.is_symlink() or path.stat().st_size != row.get("size_bytes") or _digest(path) != row.get("sha256"):
            raise X6R11GateError("materialized artifact drifted: " + relative)
        listed.add(relative)
    actual = {str(path.relative_to(run_root)) for path in run_root.rglob("*") if path.is_file()}
    if actual != listed:
        raise X6R11GateError("receipt artifact inventory is incomplete or includes a non-existent artifact")
    absent = {"manifest.json", "parsed/evidence_v4.json", "parsed/feature_vector_v2.json", "diagnosis/diagnosis_result_v2.json", "validation/raw_hashes.json"}
    if set(receipt.get("expected_absent_artifacts", [])) != absent or any((run_root / item).exists() for item in absent):
        raise X6R11GateError("missing acceptance artifacts are misstated")
    if receipt.get("run_tree_sha256") != hashlib.sha256("".join(sorted(str(row["sha256"]) + "  " + str(row["path"]) + "\n" for row in artifacts)).encode()).hexdigest():
        raise X6R11GateError("receipt tree hash drifted")
    audit = audit_baseline_after(run_root)
    if audit["baseline_after_status"] != "BASELINE_INVALID_AFTER" or audit["recomputed_status"] != "BASELINE_INVALID_AFTER" or audit["classification"] != "C_INSUFFICIENT_EVIDENCE":
        raise X6R11GateError("baseline-after audit drifted")
    return {"source": plan, "materialized": "32/32_HASH_BOUND_PASS", "audit": audit}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repository-root", type=Path, default=ROOT); parser.add_argument("--materialized", action="store_true")
    args = parser.parse_args()
    result = verify_x6_r1_1(args.repository_root, verify_materialized=args.materialized)
    print("x6_r1_1=VERIFIED"); print("materialized=" + str(result["materialized"])); print("runtime_scientific_authorization=0/10_FALSE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
