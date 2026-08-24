from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Mapping

from src.expansion.x3_r5_gate import EXPECTED_PARENT, EXPECTED_SLICES, X3R5CloseoutError, _tree_hash, verify_x3_r5_receipt
from src.fault_injection.phase6_common import write_json_atomic


def _load(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X3R5CloseoutError(f"Cannot read {label}: {path}") from error
    if not isinstance(value, dict):
        raise X3R5CloseoutError(f"{label} must be a JSON object.")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(relative: str) -> str:
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or ".." in pure.parts or pure.as_posix() != relative:
        raise X3R5CloseoutError(f"Accepted X3 evidence path is not canonical: {relative}")
    return relative


def _verify_run(root: Path, relative_run: str, release_id: str, fault_type: str, rule_id: str, signature: Mapping[str, object]) -> dict[str, object]:
    run_root = root / _canonical(relative_run)
    if not run_root.is_dir() or run_root.is_symlink():
        raise X3R5CloseoutError(f"Accepted X3 run is unavailable: {relative_run}")
    manifest = _load(run_root / "manifest.json", "runtime manifest")
    truth = _load(run_root / "ground_truth.json", "ground truth")
    evidence = _load(run_root / "parsed/evidence_v4.json", "Evidence v4")
    diagnosis = _load(run_root / "diagnosis/diagnosis_result_v2.json", "diagnosis")
    restoration = _load(run_root / "mutation/restoration_record.json", "restoration")
    before = _load(run_root / "validation/baseline_before.json", "baseline before")
    after = _load(run_root / "validation/baseline_after.json", "baseline after")
    prediction = diagnosis.get("prediction")
    if manifest.get("current_state") != "COMPLETED" or truth.get("fault_type") != fault_type:
        raise X3R5CloseoutError(f"Accepted run identity is incomplete: {release_id}")
    if diagnosis.get("status") != "diagnosed" or not isinstance(prediction, Mapping) or prediction.get("fault_type") != fault_type or diagnosis.get("explanation_refs") != [f"rule:{rule_id}"]:
        raise X3R5CloseoutError(f"Accepted run diagnosis drifted: {release_id}")
    if restoration.get("status") != "RESTORATION_CONFIRMED" or before.get("return_code") != 0 or after.get("return_code") != 0:
        raise X3R5CloseoutError(f"Accepted run restoration or baseline drifted: {release_id}")
    observations = evidence.get("observations")
    if not isinstance(observations, Mapping):
        raise X3R5CloseoutError(f"Accepted run observations are missing: {release_id}")
    for name, expected in signature.items():
        row = observations.get(name)
        if not isinstance(row, Mapping) or row.get("availability") != "observed" or row.get("value") is not expected:
            raise X3R5CloseoutError(f"Accepted run signature drifted: {release_id}/{name}")
    runs = evidence.get("collector_runs")
    if not isinstance(runs, list) or not runs:
        raise X3R5CloseoutError(f"Accepted run collector provenance is missing: {release_id}")
    for collector in runs:
        if not isinstance(collector, Mapping):
            raise X3R5CloseoutError(f"Accepted run collector provenance is invalid: {release_id}")
        for raw in collector.get("raw_artifacts", []):
            if not isinstance(raw, Mapping):
                raise X3R5CloseoutError(f"Accepted run raw artifact is invalid: {release_id}")
            path = run_root / str(raw.get("path", ""))
            if not path.is_file() or path.is_symlink() or _sha256(path) != raw.get("sha256"):
                raise X3R5CloseoutError(f"Accepted run raw hash drifted: {release_id}/{raw.get('path')}")
    artifacts: list[dict[str, object]] = []
    for path in sorted(run_root.rglob("*")):
        if path.is_symlink():
            raise X3R5CloseoutError(f"Symlink is forbidden in accepted evidence: {path}")
        if path.is_file():
            artifacts.append({"path": path.relative_to(run_root).as_posix(), "sha256": _sha256(path), "size_bytes": path.stat().st_size})
    return {"release_id": release_id, "fault_type": fault_type, "rule_id": rule_id, "relative_run_path": relative_run, "run_tree_sha256": _tree_hash(artifacts), "artifacts": artifacts}


def create_x3_r5_receipt(repository_root: Path, output_path: Path, run_paths: Mapping[str, str]) -> dict[str, object]:
    root = Path(repository_root)
    if set(run_paths) != set(EXPECTED_SLICES):
        raise X3R5CloseoutError("Receipt generation requires exactly the four accepted X3 releases.")
    rows = [_verify_run(root, run_paths[release_id], release_id, *EXPECTED_SLICES[release_id]) for release_id in EXPECTED_SLICES]
    receipt = {"schema_version": 1, "receipt_id": "x3_r5_layer2_vlan_evidence_receipt_v1", "source_commit": EXPECTED_PARENT, "created_at_utc": datetime.now(timezone.utc).isoformat(), "runs": rows, "summary": {"run_count": 4, "all_completed": True, "all_diagnosed": True, "all_restored": True, "all_baselines_valid": True, "all_raw_hashes_verified": True}}
    write_json_atomic(Path(output_path), receipt)
    verify_x3_r5_receipt(Path(output_path), repository_root=root, verify_materialized=True)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the X3-R5 accepted-evidence receipt.")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd()); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--run", action="append", required=True, metavar="RELEASE_ID=RELATIVE_PATH")
    args = parser.parse_args(); paths: dict[str, str] = {}
    for value in args.run:
        release, separator, relative = value.partition("=")
        if not separator or not release or not relative or release in paths:
            raise X3R5CloseoutError(f"Invalid --run binding: {value}")
        paths[release] = relative
    print(f"x3_r5_evidence_receipt={len(create_x3_r5_receipt(args.repository_root, args.output, paths)['runs'])}/4_CREATED_AND_VERIFIED_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
