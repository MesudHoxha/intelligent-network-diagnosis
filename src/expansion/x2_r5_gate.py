from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker

from src.expansion.x2_addressing import X2AddressingError
from src.expansion.x2_gate import verify_x2_gate
from src.expansion.x2_r1_gate import verify_x2_r1_gate
from src.expansion.x2_r2_gate import verify_x2_r2_gate
from src.expansion.x2_r3_gate import verify_x2_r3_gate
from src.expansion.x2_r4_gate import verify_x2_r4_gate

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X2_R5_ADDRESSING_CLOSEOUT_V1.json")
PLAN_SCHEMA = Path("schemas/x2_r5_addressing_closeout_v1.schema.json")
RECEIPT_SCHEMA = Path("schemas/x2_r5_addressing_evidence_receipt_v1.schema.json")
EXPECTED_PARENT = "cb8a9feaccc8a040a3a1f7fe472cbc9c0d70ecb1"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_SLICES = {
    "X2_R1_WRONG_IP_ADDRESS": ("wrong_ip_address", "R_X2_ADDRESSING_001"),
    "X2_R2_WRONG_SUBNET_MASK": ("wrong_subnet_mask", "R_X2_ADDRESSING_002"),
    "X2_R3_MISSING_DEFAULT_ROUTE": ("missing_default_route", "R_X2_ADDRESSING_003"),
    "X2_R4_DUPLICATE_IP": ("duplicate_ip", "R_X2_ADDRESSING_004"),
}
REQUIRED_RUN_ARTIFACTS = {
    "manifest.json",
    "ground_truth.json",
    "mutation/recovery_intent.json",
    "mutation/injection_record.json",
    "mutation/restoration_record.json",
    "parsed/evidence_v4.json",
    "parsed/feature_vector_v2.json",
    "diagnosis/diagnosis_result_v2.json",
    "validation/baseline_before.json",
    "validation/baseline_after.json",
}


def _load(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X2AddressingError(f"Cannot read {label}: {path}") from error
    if not isinstance(value, dict):
        raise X2AddressingError(f"{label} must be a JSON object.")
    return value


def _validate(value: Mapping[str, object], schema_path: Path, label: str) -> None:
    schema = _load(schema_path, f"{label} schema")
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda row: list(row.absolute_path),
    )
    if errors:
        raise X2AddressingError(f"{label} schema validation failed: {errors[0].message}")


def _canonical(relative: object, label: str) -> str:
    if not isinstance(relative, str) or not relative:
        raise X2AddressingError(f"{label} path is invalid.")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != relative:
        raise X2AddressingError(f"{label} path is not canonical: {relative}")
    return relative


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_x2_r5_source_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    plan = _load(root / PLAN, "X2-R5 closeout plan")
    _validate(plan, root / PLAN_SCHEMA, "X2-R5 closeout plan")
    boundary = plan.get("source_boundary")
    if not isinstance(boundary, Mapping) or boundary.get("parent_commit") != EXPECTED_PARENT:
        raise X2AddressingError("X2-R5 parent source boundary drifted.")
    if boundary.get("runtime_inherited") is not False:
        raise X2AddressingError("X2-R5 must not inherit runtime authorization.")
    runtime = plan.get("runtime_authorization")
    if not isinstance(runtime, Mapping) or len(runtime) != 10 or any(runtime.values()):
        raise X2AddressingError("X2-R5 runtime authorization must be 10/10 false.")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 18:
        raise X2AddressingError("X2-R5 requires exactly 18 source bindings.")
    seen: set[str] = set()
    for row in bindings:
        if not isinstance(row, Mapping):
            raise X2AddressingError("X2-R5 source binding is invalid.")
        relative = _canonical(row.get("path"), "source binding")
        if relative in seen or not SHA256.fullmatch(str(row.get("sha256", ""))):
            raise X2AddressingError("X2-R5 source binding is duplicate or unhashed.")
        seen.add(relative)
        path = root / relative
        if not path.is_file() or path.is_symlink() or _digest(path) != row["sha256"]:
            raise X2AddressingError(f"X2-R5 source binding drifted: {relative}")
    slices = plan.get("accepted_slices")
    if not isinstance(slices, list) or len(slices) != 4:
        raise X2AddressingError("X2-R5 must close exactly four addressing slices.")
    observed = {
        row.get("release_id"): (row.get("fault_type"), row.get("rule_id"))
        for row in slices
        if isinstance(row, Mapping)
    }
    if observed != EXPECTED_SLICES:
        raise X2AddressingError("X2-R5 accepted slice set drifted.")
    signatures = [json.dumps(row["expected_signature"], sort_keys=True) for row in slices]
    if len(set(signatures)) != 4:
        raise X2AddressingError("X2-R5 addressing signatures are not disjoint.")
    if verify_x2_gate(root)["status"] != "ACCEPTED_DESIGN_ONLY":
        raise X2AddressingError("X2-R0 gate is not accepted.")
    for verifier in (verify_x2_r1_gate, verify_x2_r2_gate, verify_x2_r3_gate, verify_x2_r4_gate):
        if verifier(root)["status"] != "IMPLEMENTED_RUNTIME_SLICE":
            raise X2AddressingError("An X2 runtime slice is not implemented.")
    return plan


def _tree_hash(artifacts: list[Mapping[str, object]]) -> str:
    rows = [f"{row['sha256']}  {row['path']}\n" for row in artifacts]
    return hashlib.sha256("".join(sorted(rows)).encode("utf-8")).hexdigest()


def verify_x2_r5_receipt(
    receipt_path: Path,
    *,
    repository_root: Path = ROOT,
    schema_root: Path | None = None,
    verify_materialized: bool = False,
) -> dict[str, object]:
    root = Path(repository_root)
    schema_base = Path(schema_root) if schema_root is not None else root
    receipt = _load(Path(receipt_path), "X2-R5 evidence receipt")
    _validate(receipt, schema_base / RECEIPT_SCHEMA, "X2-R5 evidence receipt")
    runs = receipt.get("runs")
    assert isinstance(runs, list)
    observed: dict[str, tuple[object, object]] = {}
    for run in runs:
        assert isinstance(run, Mapping)
        release_id = str(run["release_id"])
        observed[release_id] = (run["fault_type"], run["rule_id"])
        relative_run = _canonical(run["relative_run_path"], "runtime evidence")
        artifacts = run["artifacts"]
        assert isinstance(artifacts, list)
        paths = {_canonical(row["path"], "runtime artifact") for row in artifacts}
        if not REQUIRED_RUN_ARTIFACTS.issubset(paths):
            raise X2AddressingError(f"X2-R5 evidence run is incomplete: {release_id}")
        if len(paths) != len(artifacts) or any(
            not SHA256.fullmatch(str(row.get("sha256", ""))) for row in artifacts
        ):
            raise X2AddressingError(f"X2-R5 artifact binding is invalid: {release_id}")
        if _tree_hash(artifacts) != run["run_tree_sha256"]:
            raise X2AddressingError(f"X2-R5 run tree hash drifted: {release_id}")
        if verify_materialized:
            run_root = root / relative_run
            for artifact in artifacts:
                path = run_root / str(artifact["path"])
                if (
                    not path.is_file()
                    or path.is_symlink()
                    or path.stat().st_size != artifact["size_bytes"]
                    or _digest(path) != artifact["sha256"]
                ):
                    raise X2AddressingError(
                        f"X2-R5 materialized evidence drifted: {release_id}/{artifact['path']}"
                    )
    if observed != EXPECTED_SLICES:
        raise X2AddressingError("X2-R5 receipt does not cover the exact four slices.")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify the X2-R5 addressing closeout.")
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--verify-materialized", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    plan = verify_x2_r5_source_gate(args.repository_root)
    print("x2_r5_source_gate=VERIFIED")
    print("addressing_slices=4/4_DISJOINT_HASH_BOUND_PASS")
    print("runtime_authorization=10/10_FALSE_PASS")
    print("claim_boundary=CONTROLLED_VARIANTS_ONLY_PASS")
    if args.receipt:
        receipt = verify_x2_r5_receipt(
            args.receipt,
            repository_root=args.repository_root,
            verify_materialized=args.verify_materialized,
        )
        print(f"evidence_receipt={len(receipt['runs'])}/4_HASH_BOUND_PASS")
    print(f"next_release={plan['track']['next_release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
