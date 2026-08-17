from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from src.expansion.x2_addressing import X2AddressingError
from src.expansion.x2_r5_gate import EXPECTED_PARENT, EXPECTED_SLICES, _tree_hash, verify_x2_r5_receipt
from src.fault_injection.phase6_common import write_json_atomic


def _load(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X2AddressingError(f"Cannot read {label}: {path}") from error
    if not isinstance(value, dict):
        raise X2AddressingError(f"{label} must be a JSON object.")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_run(
    repository_root: Path,
    relative_run: str,
    release_id: str,
    fault_type: str,
    rule_id: str,
    expected_signature: Mapping[str, object],
) -> dict[str, object]:
    run_root = repository_root / relative_run
    if not run_root.is_dir() or run_root.is_symlink():
        raise X2AddressingError(f"Accepted X2 run is unavailable: {relative_run}")
    manifest = _load(run_root / "manifest.json", "runtime manifest")
    ground_truth = _load(run_root / "ground_truth.json", "ground truth")
    evidence = _load(run_root / "parsed/evidence_v4.json", "Evidence v4")
    diagnosis = _load(run_root / "diagnosis/diagnosis_result_v2.json", "diagnosis")
    restoration = _load(run_root / "mutation/restoration_record.json", "restoration")
    before = _load(run_root / "validation/baseline_before.json", "baseline before")
    after = _load(run_root / "validation/baseline_after.json", "baseline after")
    if manifest.get("current_state") != "COMPLETED":
        raise X2AddressingError(f"Accepted run is not complete: {release_id}")
    if ground_truth.get("fault_type") != fault_type:
        raise X2AddressingError(f"Ground truth drifted: {release_id}")
    prediction = diagnosis.get("prediction")
    if (
        diagnosis.get("status") != "diagnosed"
        or not isinstance(prediction, Mapping)
        or prediction.get("fault_type") != fault_type
        or diagnosis.get("explanation_refs") != [f"rule:{rule_id}"]
    ):
        raise X2AddressingError(f"Diagnosis drifted: {release_id}")
    if restoration.get("status") != "RESTORATION_CONFIRMED":
        raise X2AddressingError(f"Restoration is not confirmed: {release_id}")
    if before.get("return_code") != 0 or after.get("return_code") != 0:
        raise X2AddressingError(f"Baseline before/after is invalid: {release_id}")
    observations = evidence.get("observations")
    if not isinstance(observations, Mapping):
        raise X2AddressingError(f"Evidence observations are missing: {release_id}")
    for name, expected in expected_signature.items():
        row = observations.get(name)
        if not isinstance(row, Mapping) or row.get("availability") != "observed" or row.get("value") is not expected:
            raise X2AddressingError(f"Evidence signature drifted: {release_id}/{name}")
    runs = evidence.get("collector_runs")
    if not isinstance(runs, list) or not runs:
        raise X2AddressingError(f"Collector provenance is missing: {release_id}")
    for collector in runs:
        if not isinstance(collector, Mapping):
            raise X2AddressingError(f"Collector provenance is invalid: {release_id}")
        for raw in collector.get("raw_artifacts", []):
            if not isinstance(raw, Mapping):
                raise X2AddressingError(f"Raw artifact binding is invalid: {release_id}")
            path = run_root / str(raw.get("path", ""))
            if not path.is_file() or path.is_symlink() or _sha256(path) != raw.get("sha256"):
                raise X2AddressingError(f"Raw artifact hash drifted: {release_id}/{raw.get('path')}")
    artifacts: list[dict[str, object]] = []
    for path in sorted(run_root.rglob("*")):
        if path.is_symlink():
            raise X2AddressingError(f"Symlink is forbidden in accepted evidence: {path}")
        if path.is_file():
            relative = path.relative_to(run_root).as_posix()
            artifacts.append({"path": relative, "sha256": _sha256(path), "size_bytes": path.stat().st_size})
    return {
        "release_id": release_id,
        "fault_type": fault_type,
        "rule_id": rule_id,
        "relative_run_path": relative_run,
        "run_tree_sha256": _tree_hash(artifacts),
        "artifacts": artifacts,
    }


def create_x2_r5_receipt(
    repository_root: Path,
    output_path: Path,
    run_paths: Mapping[str, str],
) -> dict[str, object]:
    root = Path(repository_root)
    plan = _load(root / "plans/expansion/X2_R5_ADDRESSING_CLOSEOUT_V1.json", "X2-R5 plan")
    slices = {row["release_id"]: row for row in plan["accepted_slices"] if isinstance(row, dict)}
    if set(run_paths) != set(EXPECTED_SLICES):
        raise X2AddressingError("Receipt generation requires exactly the four accepted releases.")
    receipt_runs = []
    for release_id in EXPECTED_SLICES:
        row = slices[release_id]
        receipt_runs.append(_verify_run(root, run_paths[release_id], release_id, row["fault_type"], row["rule_id"], row["expected_signature"]))
    receipt = {
        "schema_version": 1,
        "receipt_id": "x2_r5_addressing_evidence_receipt_v1",
        "source_commit": EXPECTED_PARENT,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runs": receipt_runs,
        "summary": {
            "run_count": 4,
            "all_completed": True,
            "all_diagnosed": True,
            "all_restored": True,
            "all_baselines_valid": True,
            "all_raw_hashes_verified": True,
        },
    }
    write_json_atomic(Path(output_path), receipt)
    verify_x2_r5_receipt(Path(output_path), repository_root=root, verify_materialized=True)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create the X2-R5 accepted-evidence receipt.")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="append", required=True, metavar="RELEASE_ID=RELATIVE_PATH")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_paths: dict[str, str] = {}
    for value in args.run:
        release_id, separator, relative = value.partition("=")
        if not separator or not release_id or not relative or release_id in run_paths:
            raise X2AddressingError(f"Invalid --run binding: {value}")
        run_paths[release_id] = relative
    receipt = create_x2_r5_receipt(args.repository_root, args.output, run_paths)
    print(f"x2_r5_evidence_receipt={len(receipt['runs'])}/4_CREATED_AND_VERIFIED_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
