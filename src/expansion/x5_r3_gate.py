from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Mapping

from src.expansion.x5_gate import verify_x5_gate
from src.expansion.x5_r1_gate import verify_x5_r1_gate
from src.expansion.x5_r2_gate import verify_x5_r2_gate

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X5_R3_OSPF_DYNAMIC_ROUTING_CLOSEOUT_V1.json")
RECEIPT = Path("plans/expansion/X5_R3_OSPF_DYNAMIC_ROUTING_EVIDENCE_RECEIPT_V1.json")
PARENT = "258022fd5d4148889d3b581f16e3e1eb380c14fd"
FEATURES = ("ospf_adjacency_full", "ospf_route_advertised", "ospf_route_installed", "route_filter_allows_prefix")
SLICES = {"X5_R1_OSPF_ADJACENCY_FAILURE": ("dynamic_routing_adjacency_failure", "R_X5_OSPF_001", (False, False, False, True)), "X5_R2_ROUTE_FILTERING_OR_ADVERTISEMENT_PROBLEM": ("route_filtering_or_advertisement_problem", "R_X5_OSPF_002", (True, False, False, False))}
REQUIRED = {"manifest.json", "mutation/recovery_intent.json", "mutation/injection_record.json", "mutation/restoration_record.json", "parsed/evidence_v4.json", "parsed/feature_vector_v2.json", "diagnosis/diagnosis_result_v2.json", "validation/baseline_before.json", "validation/baseline_after.json"}


class X5R3CloseoutError(ValueError):
    pass


def _load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X5R3CloseoutError("Cannot read closeout artifact: " + str(path)) from error
    if not isinstance(value, dict):
        raise X5R3CloseoutError("Closeout artifact must be a JSON object: " + str(path))
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise X5R3CloseoutError("Receipt path is invalid.")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value:
        raise X5R3CloseoutError("Receipt path is not canonical: " + value)
    return value


def _tree(rows: list[Mapping[str, object]]) -> str:
    return hashlib.sha256("".join(sorted(str(row["sha256"]) + "  " + str(row["path"]) + "\n" for row in rows)).encode()).hexdigest()


def verify_x5_r3_source_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    plan = _load(root / PLAN)
    if plan.get("source_boundary") != {"parent_commit": PARENT, "extension_policy": "APPEND_ONLY", "runtime_inherited": False}:
        raise X5R3CloseoutError("X5-R3 source boundary drifted.")
    flags = plan.get("runtime_authorization")
    if not isinstance(flags, Mapping) or len(flags) != 10 or any(flags.values()):
        raise X5R3CloseoutError("X5-R3 authorization must be 10/10 false.")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 13:
        raise X5R3CloseoutError("X5-R3 requires exactly 13 source bindings.")
    seen: set[str] = set()
    for binding in bindings:
        if not isinstance(binding, Mapping):
            raise X5R3CloseoutError("X5-R3 source binding is invalid.")
        path = _canonical(binding.get("path"))
        if path in seen or not isinstance(binding.get("sha256"), str) or len(binding["sha256"]) != 64:
            raise X5R3CloseoutError("X5-R3 source binding is duplicate or unhashed.")
        seen.add(path)
        materialized = root / path
        if not materialized.is_file() or materialized.is_symlink() or _digest(materialized) != binding["sha256"]:
            raise X5R3CloseoutError("X5-R3 source binding drifted: " + path)
    observed = {row.get("release_id"): (row.get("fault_type"), row.get("rule_id"), tuple(row.get("expected_signature", {}).get(feature) for feature in FEATURES)) for row in plan.get("accepted_slices", []) if isinstance(row, Mapping)}
    if observed != SLICES or len({value[2] for value in observed.values()}) != 2:
        raise X5R3CloseoutError("X5-R3 C4/C5 signatures drifted or are not disjoint.")
    if verify_x5_gate(root)["status"] != "ACCEPTED_DESIGN_ONLY" or verify_x5_r1_gate(root)["status"] != "IMPLEMENTED_RUNTIME_SLICE" or verify_x5_r2_gate(root)["status"] != "IMPLEMENTED_RUNTIME_SLICE":
        raise X5R3CloseoutError("An X5 parent gate is not accepted.")
    return plan


def verify_x5_r3_receipt(receipt_path: Path, *, repository_root: Path = ROOT, verify_materialized: bool = False) -> dict[str, object]:
    root = Path(repository_root)
    receipt = _load(Path(receipt_path))
    if receipt.get("source_commit") != PARENT or receipt.get("evidence_kind") != "ACCEPTED_RUNTIME_EVIDENCE_NOT_RECOVERED_OR_REPLACED":
        raise X5R3CloseoutError("X5-R3 receipt identity or evidence-kind drifted.")
    observed: dict[str, tuple[str, str, tuple[bool, ...]]] = {}
    for run in receipt.get("runs", []):
        if not isinstance(run, Mapping):
            raise X5R3CloseoutError("X5-R3 receipt run is invalid.")
        release = str(run.get("release_id")); expected = SLICES.get(release)
        if expected is None or (run.get("fault_type"), run.get("rule_id")) != expected[:2]:
            raise X5R3CloseoutError("X5-R3 receipt identity drifted: " + release)
        artifacts = run.get("artifacts")
        if not isinstance(artifacts, list):
            raise X5R3CloseoutError("X5-R3 receipt artifacts are invalid: " + release)
        paths = {_canonical(row.get("path")) for row in artifacts if isinstance(row, Mapping)}
        if len(paths) != len(artifacts) or not REQUIRED.issubset(paths) or _tree(artifacts) != run.get("run_tree_sha256"):
            raise X5R3CloseoutError("X5-R3 receipt tree drifted: " + release)
        relative = _canonical(run.get("relative_run_path"))
        if verify_materialized:
            run_root = root / relative
            for artifact in artifacts:
                path = run_root / str(artifact["path"])
                if not path.is_file() or path.is_symlink() or path.stat().st_size != artifact["size_bytes"] or _digest(path) != artifact["sha256"]:
                    raise X5R3CloseoutError("X5-R3 materialized hash drifted: " + release + "/" + str(artifact["path"]))
            evidence = _load(run_root / "parsed/evidence_v4.json"); diagnosis = _load(run_root / "diagnosis/diagnosis_result_v2.json"); restoration = _load(run_root / "mutation/restoration_record.json"); before = _load(run_root / "validation/baseline_before.json"); after = _load(run_root / "validation/baseline_after.json")
            signature = tuple(evidence.get("observations", {}).get(feature, {}).get("value") for feature in FEATURES)
            raw = evidence.get("collector_runs", [{}])[0].get("raw_artifacts", [])
            if signature != expected[2] or diagnosis.get("status") != "diagnosed" or diagnosis.get("explanation_refs") != ["rule:" + expected[1]] or restoration.get("status") != "RESTORATION_CONFIRMED" or before.get("return_code") != 0 or after.get("return_code") != 0 or len(raw) != 8:
                raise X5R3CloseoutError("X5-R3 materialized evidence semantics drifted: " + release)
        observed[release] = expected
    if observed != SLICES:
        raise X5R3CloseoutError("X5-R3 receipt does not cover exact C4/C5 releases.")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--verify-materialized", action="store_true")
    args = parser.parse_args()
    plan = verify_x5_r3_source_gate(args.repository_root)
    print("x5_r3_source_gate=VERIFIED")
    receipt = verify_x5_r3_receipt(args.repository_root / args.receipt, repository_root=args.repository_root, verify_materialized=args.verify_materialized)
    print("evidence_receipt=" + str(len(receipt["runs"])) + "/2_ACCEPTED_RUNTIME_HASH_BOUND_PASS")
    print("next_release=" + str(plan["track"]["next_release"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
