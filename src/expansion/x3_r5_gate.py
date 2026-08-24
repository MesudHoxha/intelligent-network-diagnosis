from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker

from src.expansion.x3_gate import verify_x3_gate
from src.expansion.x3_r1_gate import verify_x3_r1_gate
from src.expansion.x3_r2_gate import verify_x3_r2_gate
from src.expansion.x3_r3_gate import verify_x3_r3_gate
from src.expansion.x3_r4_gate import verify_x3_r4_gate


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X3_R5_LAYER2_VLAN_CLOSEOUT_V1.json")
PLAN_SCHEMA = Path("schemas/x3_r5_layer2_vlan_closeout_v1.schema.json")
RECEIPT_SCHEMA = Path("schemas/x3_r5_layer2_vlan_evidence_receipt_v1.schema.json")
EXPECTED_PARENT = "7bddd3abebb9b987cbb98d22977884a5cd161acf"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_SLICES = {
    "X3_R1_WRONG_ACCESS_VLAN": ("wrong_access_vlan", "R_X3_L2_VLAN_001", {"access_vlan_matches_expected": False, "vlan_exists_on_target": True, "vlan_allowed_on_trunk": True, "native_vlan_matches_peer": True, "fdb_location_matches_expected": False}),
    "X3_R2_VLAN_MISSING": ("vlan_missing", "R_X3_L2_VLAN_002", {"access_vlan_matches_expected": False, "vlan_exists_on_target": False, "vlan_allowed_on_trunk": False, "native_vlan_matches_peer": True, "fdb_location_matches_expected": False}),
    "X3_R3_VLAN_NOT_ALLOWED_ON_TRUNK": ("vlan_not_allowed_on_trunk", "R_X3_L2_VLAN_003", {"access_vlan_matches_expected": True, "vlan_exists_on_target": True, "vlan_allowed_on_trunk": False, "native_vlan_matches_peer": True, "fdb_location_matches_expected": True}),
    "X3_R4_NATIVE_VLAN_MISMATCH": ("native_vlan_mismatch", "R_X3_L2_VLAN_004", {"access_vlan_matches_expected": True, "vlan_exists_on_target": True, "vlan_allowed_on_trunk": True, "native_vlan_matches_peer": False, "fdb_location_matches_expected": True}),
}
REQUIRED_RUN_ARTIFACTS = {"manifest.json", "ground_truth.json", "mutation/recovery_intent.json", "mutation/injection_record.json", "mutation/restoration_record.json", "parsed/evidence_v4.json", "parsed/feature_vector_v2.json", "diagnosis/diagnosis_result_v2.json", "validation/baseline_before.json", "validation/baseline_after.json"}


class X3R5CloseoutError(ValueError):
    """Raised when the X3-R5 closeout boundary or receipt drifts."""


def _load(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X3R5CloseoutError(f"Cannot read {label}: {path}") from error
    if not isinstance(value, dict):
        raise X3R5CloseoutError(f"{label} must be a JSON object.")
    return value


def _validate(value: Mapping[str, object], schema_path: Path, label: str) -> None:
    schema = _load(schema_path, f"{label} schema")
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), key=lambda row: list(row.absolute_path))
    if errors:
        raise X3R5CloseoutError(f"{label} schema validation failed: {errors[0].message}")


def _canonical(relative: object, label: str) -> str:
    if not isinstance(relative, str) or not relative:
        raise X3R5CloseoutError(f"{label} path is invalid.")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != relative:
        raise X3R5CloseoutError(f"{label} path is not canonical: {relative}")
    return relative


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_hash(artifacts: list[Mapping[str, object]]) -> str:
    return hashlib.sha256("".join(sorted(f"{row['sha256']}  {row['path']}\n" for row in artifacts)).encode("utf-8")).hexdigest()


def verify_x3_r5_source_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    plan = _load(root / PLAN, "X3-R5 closeout plan")
    _validate(plan, root / PLAN_SCHEMA, "X3-R5 closeout plan")
    boundary = plan.get("source_boundary")
    if not isinstance(boundary, Mapping) or boundary.get("parent_commit") != EXPECTED_PARENT or boundary.get("extension_policy") != "APPEND_ONLY" or boundary.get("runtime_inherited") is not False:
        raise X3R5CloseoutError("X3-R5 parent or append-only source boundary drifted.")
    runtime = plan.get("runtime_authorization")
    if not isinstance(runtime, Mapping) or len(runtime) != 10 or any(runtime.values()):
        raise X3R5CloseoutError("X3-R5 runtime authorization must be 10/10 false.")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 18:
        raise X3R5CloseoutError("X3-R5 requires exactly 18 source bindings.")
    seen: set[str] = set()
    for row in bindings:
        if not isinstance(row, Mapping):
            raise X3R5CloseoutError("X3-R5 source binding is invalid.")
        relative = _canonical(row.get("path"), "source binding")
        if relative in seen or not SHA256.fullmatch(str(row.get("sha256", ""))):
            raise X3R5CloseoutError("X3-R5 source binding is duplicate or unhashed.")
        seen.add(relative); path = root / relative
        if not path.is_file() or path.is_symlink() or _digest(path) != row["sha256"]:
            raise X3R5CloseoutError(f"X3-R5 source binding drifted: {relative}")
    slices = plan.get("accepted_slices")
    if not isinstance(slices, list) or len(slices) != 4:
        raise X3R5CloseoutError("X3-R5 must close exactly four Layer 2/VLAN slices.")
    observed = {row.get("release_id"): (row.get("fault_type"), row.get("rule_id"), row.get("expected_signature")) for row in slices if isinstance(row, Mapping)}
    if observed != EXPECTED_SLICES or len({json.dumps(row["expected_signature"], sort_keys=True) for row in slices if isinstance(row, Mapping)}) != 4:
        raise X3R5CloseoutError("X3-R5 accepted slice signatures drifted or are not disjoint.")
    if verify_x3_gate(root)["status"] != "ACCEPTED_DESIGN_ONLY":
        raise X3R5CloseoutError("X3-R0 gate is not accepted.")
    for verifier in (verify_x3_r1_gate, verify_x3_r2_gate, verify_x3_r3_gate, verify_x3_r4_gate):
        if verifier(root)["status"] != "IMPLEMENTED_RUNTIME_SLICE":
            raise X3R5CloseoutError("An X3 runtime slice is not implemented.")
    return plan


def verify_x3_r5_receipt(receipt_path: Path, *, repository_root: Path = ROOT, schema_root: Path | None = None, verify_materialized: bool = False) -> dict[str, object]:
    root = Path(repository_root); schema_base = Path(schema_root) if schema_root is not None else root
    receipt = _load(Path(receipt_path), "X3-R5 evidence receipt")
    _validate(receipt, schema_base / RECEIPT_SCHEMA, "X3-R5 evidence receipt")
    runs = receipt.get("runs"); assert isinstance(runs, list)
    observed: dict[str, tuple[object, object, object]] = {}
    for run in runs:
        assert isinstance(run, Mapping)
        release = str(run["release_id"]); observed[release] = (run["fault_type"], run["rule_id"], EXPECTED_SLICES.get(release, (None, None, None))[2])
        relative = _canonical(run["relative_run_path"], "runtime evidence"); artifacts = run["artifacts"]; assert isinstance(artifacts, list)
        paths = {_canonical(row["path"], "runtime artifact") for row in artifacts}
        if not REQUIRED_RUN_ARTIFACTS.issubset(paths) or len(paths) != len(artifacts) or any(not SHA256.fullmatch(str(row.get("sha256", ""))) for row in artifacts):
            raise X3R5CloseoutError(f"X3-R5 evidence run is incomplete or invalid: {release}")
        if _tree_hash(artifacts) != run["run_tree_sha256"]:
            raise X3R5CloseoutError(f"X3-R5 run tree hash drifted: {release}")
        if verify_materialized:
            for artifact in artifacts:
                path = root / relative / str(artifact["path"])
                if not path.is_file() or path.is_symlink() or path.stat().st_size != artifact["size_bytes"] or _digest(path) != artifact["sha256"]:
                    raise X3R5CloseoutError(f"X3-R5 materialized evidence drifted: {release}/{artifact['path']}")
    if observed != EXPECTED_SLICES:
        raise X3R5CloseoutError("X3-R5 receipt does not cover the exact four slices.")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the X3-R5 Layer 2/VLAN closeout.")
    parser.add_argument("--repository-root", type=Path, default=ROOT); parser.add_argument("--receipt", type=Path); parser.add_argument("--verify-materialized", action="store_true")
    args = parser.parse_args(); plan = verify_x3_r5_source_gate(args.repository_root)
    print("x3_r5_source_gate=VERIFIED\nl2_vlan_slices=4/4_DISJOINT_HASH_BOUND_PASS\nruntime_authorization=10/10_FALSE_PASS\nclaim_boundary=CONTROLLED_VARIANTS_ONLY_PASS")
    if args.receipt:
        receipt = verify_x3_r5_receipt(args.receipt, repository_root=args.repository_root, verify_materialized=args.verify_materialized)
        print(f"evidence_receipt={len(receipt['runs'])}/4_HASH_BOUND_PASS")
    print(f"next_release={plan['track']['next_release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
