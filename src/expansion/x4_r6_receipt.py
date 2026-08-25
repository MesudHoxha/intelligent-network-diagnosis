from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Mapping

from src.expansion.x4_r6_gate import EXPECTED_PARENT, EXPECTED_SLICES, FEATURES, X4R6CloseoutError, _tree, verify_x4_r6_receipt
from src.fault_injection.phase6_common import write_json_atomic

def _load(path: Path) -> dict[str, object]:
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error: raise X4R6CloseoutError("Cannot read accepted revalidation artifact: " + str(path)) from error
    if not isinstance(value, dict): raise X4R6CloseoutError("Accepted revalidation artifact must be a JSON object.")
    return value
def _digest(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def _canonical(value: str) -> str:
    pure = PurePosixPath(value)
    if not value or pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value: raise X4R6CloseoutError("Revalidation path is not canonical: " + value)
    return value
def _verify_run(root: Path, relative: str, release: str) -> dict[str, object]:
    fault, rule, signature, context = EXPECTED_SLICES[release]; run_root = root / _canonical(relative)
    if not run_root.is_dir() or run_root.is_symlink(): raise X4R6CloseoutError("Revalidation run is unavailable: " + relative)
    manifest = _load(run_root / "manifest.json"); evidence = _load(run_root / "parsed/evidence_v4.json"); diagnosis = _load(run_root / "diagnosis/diagnosis_result_v2.json"); restoration = _load(run_root / "mutation/restoration_record.json"); before = _load(run_root / "validation/baseline_before.json"); after = _load(run_root / "validation/baseline_after.json")
    prediction = diagnosis.get("prediction")
    if manifest.get("current_state") != "COMPLETED" or evidence.get("topology_context_id") != context: raise X4R6CloseoutError("Revalidation manifest/context drifted: " + release)
    if diagnosis.get("status") != "diagnosed" or not isinstance(prediction, Mapping) or prediction.get("fault_type") != fault or diagnosis.get("explanation_refs") != ["rule:" + rule]: raise X4R6CloseoutError("Revalidation diagnosis drifted: " + release)
    if restoration.get("status") != "RESTORATION_CONFIRMED" or before.get("return_code") != 0 or after.get("return_code") != 0: raise X4R6CloseoutError("Revalidation restoration/baseline drifted: " + release)
    observations = evidence.get("observations")
    if not isinstance(observations, Mapping) or tuple(observations.get(name, {}).get("value") if isinstance(observations.get(name), Mapping) else None for name in FEATURES) != signature or any(not isinstance(observations.get(name), Mapping) or observations[name].get("availability") != "observed" for name in FEATURES): raise X4R6CloseoutError("Revalidation signature drifted: " + release)
    collectors = evidence.get("collector_runs")
    if not isinstance(collectors, list) or not collectors: raise X4R6CloseoutError("Revalidation raw provenance missing: " + release)
    for collector in collectors:
        if not isinstance(collector, Mapping): raise X4R6CloseoutError("Revalidation collector invalid: " + release)
        for raw in collector.get("raw_artifacts", []):
            if not isinstance(raw, Mapping): raise X4R6CloseoutError("Revalidation raw invalid: " + release)
            path = run_root / str(raw.get("path", ""))
            if not path.is_file() or path.is_symlink() or _digest(path) != raw.get("sha256"): raise X4R6CloseoutError("Revalidation raw hash drifted: " + release + "/" + str(raw.get("path")))
    artifacts = []
    for path in sorted(run_root.rglob("*")):
        if path.is_symlink(): raise X4R6CloseoutError("Symlink forbidden in revalidation evidence: " + str(path))
        if path.is_file(): artifacts.append({"path": path.relative_to(run_root).as_posix(), "sha256": _digest(path), "size_bytes": path.stat().st_size})
    return {"release_id": release, "fault_type": fault, "rule_id": rule, "topology_context_id": context, "relative_run_path": relative, "run_tree_sha256": _tree(artifacts), "artifacts": artifacts}
def create_x4_r6_receipt(repository_root: Path, output_path: Path, run_paths: Mapping[str, str]) -> dict[str, object]:
    root = Path(repository_root)
    if set(run_paths) != set(EXPECTED_SLICES): raise X4R6CloseoutError("Receipt generation requires exactly X4-R1 through X4-R5 revalidations.")
    receipt = {"schema_version": 1, "receipt_id": "x4_r6_dhcp_dns_service_security_evidence_receipt_v1", "source_commit": EXPECTED_PARENT, "created_at_utc": datetime.now(timezone.utc).isoformat(), "evidence_kind": "REPRODUCIBILITY_REVALIDATION_NOT_ORIGINAL_ACCEPTANCE_ARCHIVE", "runs": [_verify_run(root, run_paths[release], release) for release in EXPECTED_SLICES], "summary": {"run_count": 5, "all_completed": True, "all_diagnosed": True, "all_restored": True, "all_baselines_valid": True, "all_raw_hashes_verified": True}}
    write_json_atomic(Path(output_path), receipt); verify_x4_r6_receipt(Path(output_path), repository_root=root, verify_materialized=True); return receipt
def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repository-root", type=Path, default=Path.cwd()); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--run", action="append", required=True); args = parser.parse_args(); paths = {}
    for value in args.run:
        release, separator, relative = value.partition("=")
        if not separator or not release or not relative or release in paths: raise X4R6CloseoutError("Invalid --run binding: " + value)
        paths[release] = relative
    print("x4_r6_evidence_receipt=" + str(len(create_x4_r6_receipt(args.repository_root, args.output, paths)["runs"])) + "/5_CREATED_AND_VERIFIED_PASS"); return 0
if __name__ == "__main__": raise SystemExit(main())
