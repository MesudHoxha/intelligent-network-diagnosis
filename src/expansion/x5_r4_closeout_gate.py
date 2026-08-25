from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Mapping

from src.expansion.x5_r3_gate import verify_x5_r3_receipt
from src.expansion.x5_r4_gate import verify_x5_r4_gate

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = Path("plans/expansion/X5_R4_OSPF_CORRECTED_SUCCESSOR_RECEIPT_V1.json")
FEATURES = ("ospf_adjacency_full", "ospf_route_advertised", "ospf_route_installed", "route_filter_allows_prefix")
EXPECTED = {
    "X5_R4_OSPF_CORRECTION_AND_REVALIDATION": ("dynamic_routing_adjacency_failure", "R_X5_OSPF_001", (False, False, False, True), 9),
    "X5_R2_ROUTE_FILTERING_OR_ADVERTISEMENT_PROBLEM": ("route_filtering_or_advertisement_problem", "R_X5_OSPF_002", (True, False, False, False), 8),
}
REQUIRED = {
    "manifest.json", "mutation/recovery_intent.json", "mutation/injection_record.json",
    "mutation/mutation_effectiveness.json", "mutation/restoration_record.json",
    "parsed/evidence_v4.json", "parsed/feature_vector_v2.json",
    "diagnosis/diagnosis_result_v2.json", "validation/baseline_before.json",
    "validation/baseline_after.json",
}


class X5R4CloseoutError(ValueError):
    pass


def _load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X5R4CloseoutError("Cannot read X5-R4 closeout artifact: " + str(path)) from error
    if not isinstance(value, dict):
        raise X5R4CloseoutError("X5-R4 closeout artifact must be a JSON object: " + str(path))
    return value


def _canonical(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise X5R4CloseoutError("Receipt path is invalid.")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value:
        raise X5R4CloseoutError("Receipt path is not canonical: " + value)
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree(rows: list[Mapping[str, object]]) -> str:
    return hashlib.sha256("".join(sorted(str(row["sha256"]) + "  " + str(row["path"]) + "\n" for row in rows)).encode()).hexdigest()


def verify_x5_r4_corrected_successor_receipt(
    receipt_path: Path = RECEIPT, *, repository_root: Path = ROOT, verify_materialized: bool = False
) -> dict[str, object]:
    root = Path(repository_root)
    plan = verify_x5_r4_gate(root)
    if plan.get("status") != "ACCEPTED_CORRECTED_SUCCESSOR_CLOSEOUT" or plan.get("track", {}).get("next_release") != "X6_R0_PERFORMANCE_FAULT_DESIGN_GATE":
        raise X5R4CloseoutError("X5-R4 acceptance or next-milestone boundary drifted.")
    if plan.get("corrections", {}).get("historical_x5_r1") != "RETAINED_HISTORICAL_NOT_AUTHORITATIVE_FOR_TARGETED_C4_SCIENTIFIC_USE":
        raise X5R4CloseoutError("X5-R1 historical retention boundary drifted.")
    verify_x5_r3_receipt(root / "plans/expansion/X5_R3_OSPF_DYNAMIC_ROUTING_EVIDENCE_RECEIPT_V1.json", repository_root=root, verify_materialized=verify_materialized)
    receipt = _load(root / receipt_path)
    if receipt.get("source_commit") != "c6f6080981c4ed98338b66c28d5049c6a82d28dd" or receipt.get("evidence_kind") != "CORRECTED_C4_RUNTIME_REVALIDATION_AND_UNCHANGED_ACCEPTED_C5_RUNTIME_NOT_RECOVERED_OR_REPLACED":
        raise X5R4CloseoutError("X5-R4 receipt identity or append-only evidence boundary drifted.")
    if receipt.get("historical_evidence", {}).get("x5_r1_c4") != "RETAINED_HISTORICAL_NOT_AUTHORITATIVE_FOR_TARGETED_C4_SCIENTIFIC_USE":
        raise X5R4CloseoutError("X5-R4 receipt does not preserve historical X5-R1 status.")
    observed: set[str] = set()
    for run in receipt.get("runs", []):
        if not isinstance(run, Mapping):
            raise X5R4CloseoutError("X5-R4 receipt run is invalid.")
        release = str(run.get("release_id")); expected = EXPECTED.get(release)
        if expected is None or (run.get("fault_type"), run.get("rule_id")) != expected[:2]:
            raise X5R4CloseoutError("X5-R4 receipt identity drifted: " + release)
        artifacts = run.get("artifacts")
        if not isinstance(artifacts, list) or not all(isinstance(row, Mapping) for row in artifacts):
            raise X5R4CloseoutError("X5-R4 receipt artifacts are invalid: " + release)
        paths = {_canonical(row.get("path")) for row in artifacts}
        if len(paths) != len(artifacts) or not REQUIRED.issubset(paths) or _tree(artifacts) != run.get("run_tree_sha256"):
            raise X5R4CloseoutError("X5-R4 receipt tree drifted: " + release)
        if verify_materialized:
            run_root = root / _canonical(run.get("relative_run_path"))
            for artifact in artifacts:
                path = run_root / str(artifact["path"])
                if not path.is_file() or path.is_symlink() or path.stat().st_size != artifact["size_bytes"] or _digest(path) != artifact["sha256"]:
                    raise X5R4CloseoutError("X5-R4 materialized hash drifted: " + release + "/" + str(artifact["path"]))
            evidence = _load(run_root / "parsed/evidence_v4.json")
            diagnosis = _load(run_root / "diagnosis/diagnosis_result_v2.json")
            effectiveness = _load(run_root / "mutation/mutation_effectiveness.json")
            restoration = _load(run_root / "mutation/restoration_record.json")
            before = _load(run_root / "validation/baseline_before.json"); after = _load(run_root / "validation/baseline_after.json")
            signature = tuple(evidence.get("observations", {}).get(feature, {}).get("value") for feature in FEATURES)
            raw = evidence.get("collector_runs", [{}])[0].get("raw_artifacts", [])
            if signature != expected[2] or diagnosis.get("status") != "diagnosed" or diagnosis.get("explanation_refs") != ["rule:" + expected[1]] or effectiveness.get("status") != "MUTATION_EFFECTIVE" or restoration.get("status") != "RESTORATION_CONFIRMED" or before.get("return_code") != 0 or after.get("return_code") != 0 or len(raw) != expected[3]:
                raise X5R4CloseoutError("X5-R4 materialized evidence semantics drifted: " + release)
            if release == "X5_R4_OSPF_CORRECTION_AND_REVALIDATION":
                controls = _load(run_root / "validation/targeted_adjacency_controls.json")
                if controls.get("r2_r3_full") is not False or controls.get("r1_r2_full") is not True:
                    raise X5R4CloseoutError("X5-R4 targeted/control adjacency proof drifted.")
        observed.add(release)
    if observed != set(EXPECTED):
        raise X5R4CloseoutError("X5-R4 receipt does not cover corrected C4 plus unchanged C5.")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--verify-materialized", action="store_true")
    args = parser.parse_args()
    receipt = verify_x5_r4_corrected_successor_receipt(args.receipt, repository_root=args.repository_root, verify_materialized=args.verify_materialized)
    print("x5_r4_corrected_successor_gate=VERIFIED")
    print("receipt_runs=" + str(len(receipt["runs"])) + "/2_CORRECTED_C4_PLUS_UNCHANGED_C5_HASH_BOUND_PASS")
    print("next_release=X6_R0_PERFORMANCE_FAULT_DESIGN_GATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
