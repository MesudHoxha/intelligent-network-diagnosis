from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from src.contracts.expansion import (
    validate_diagnosis_result_v2,
    validate_evidence_v4,
    validate_feature_vector_v2,
)
from src.expansion.x5_r4_gate import verify_x5_r4_gate
from src.expansion.x5_r9_gate import verify_x5_r9_gate


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X5_R10_C5_CRASH_SAFE_AUTHORITATIVE_CLOSEOUT_V1.json")
RECEIPT = Path("plans/expansion/X5_R10_CRASH_SAFE_AUTHORITATIVE_SUCCESSOR_RECEIPT_V1.json")
R4_RECEIPT = Path("plans/expansion/X5_R4_OSPF_CORRECTED_SUCCESSOR_RECEIPT_V1.json")
FEATURES = (
    "ospf_adjacency_full",
    "ospf_route_advertised",
    "ospf_route_installed",
    "route_filter_allows_prefix",
)
C4_SIGNATURE = (False, False, False, True)
C5_SIGNATURE = (True, False, False, False)
HISTORY = {
    "x5_r1_c4": "RETAINED_HISTORICAL_NON_AUTHORITATIVE_FOR_CORRECTED_C4_SCIENTIFIC_USE",
    "x5_r2_c5": "RETAINED_HISTORICAL_NON_AUTHORITATIVE_FOR_POLICY_FEATURE_SCIENTIFIC_USE",
    "x5_r6_c5": "RETAINED_OBSERVATIONALLY_VALID_BUT_NON_AUTHORITATIVE_FOR_CRASH_SAFETY_AND_COMPLETE_RAW_CHAIN_CLAIMS",
    "x5_r7_receipt": "RETAINED_OBSERVATIONALLY_VALID_BUT_NON_AUTHORITATIVE_FOR_CRASH_SAFETY_AND_COMPLETE_RAW_CHAIN_CLAIMS",
    "x5_r9_first_tree": "RETAINED_DIAGNOSTIC_NON_AUTHORITATIVE_AFTER_SOURCE_GATE_FAILURE",
}
REQUIRED_C5 = {
    "manifest.json",
    "mutation/injection_record.json",
    "mutation/mutation_effectiveness.json",
    "mutation/mutation_journal.json",
    "mutation/recovery_intent.json",
    "mutation/restoration_record.json",
    "mutation/standalone_replay_record.json",
    "parsed/evidence_v4.json",
    "parsed/feature_vector_v2.json",
    "diagnosis/diagnosis_result_v2.json",
    "validation/baseline_before.json",
    "validation/baseline_after.json",
    "validation/control_exclusions.json",
    "validation/runtime_image_identity.json",
}


class X5R10CloseoutError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X5R10CloseoutError("Cannot read X5-R10 artifact: " + str(path)) from error
    if not isinstance(value, dict):
        raise X5R10CloseoutError("X5-R10 artifact must be an object: " + str(path))
    return value


def _canonical(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise X5R10CloseoutError("Receipt path is invalid.")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise X5R10CloseoutError("Receipt path is not canonical: " + value)
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree(rows: list[Mapping[str, object]]) -> str:
    return hashlib.sha256(
        "".join(
            sorted(str(row["sha256"]) + "  " + str(row["path"]) + "\n" for row in rows)
        ).encode()
    ).hexdigest()


def _artifacts(run: Mapping[str, object]) -> list[Mapping[str, object]]:
    rows = run.get("artifacts")
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise X5R10CloseoutError("Receipt artifacts are invalid.")
    return list(rows)


def _verify_hashes(root: Path, run: Mapping[str, object]) -> dict[str, str]:
    run_root = root / _canonical(run.get("relative_run_path"))
    digests: dict[str, str] = {}
    for artifact in _artifacts(run):
        relative = _canonical(artifact.get("path"))
        path = run_root / relative
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size != artifact.get("size_bytes")
            or _digest(path) != artifact.get("sha256")
        ):
            raise X5R10CloseoutError("Materialized hash drifted: " + relative)
        digests[relative] = str(artifact["sha256"])
    if _tree(_artifacts(run)) != run.get("run_tree_sha256"):
        raise X5R10CloseoutError("Receipt tree digest drifted.")
    return digests


def _verify_evidence_chain(
    root: Path, run: Mapping[str, object], digests: Mapping[str, str], expected: tuple[bool, bool, bool, bool], rule: str
) -> None:
    run_root = root / _canonical(run.get("relative_run_path"))
    catalog = _load(root / "plans/expansion/X1_FEATURE_CATALOG_V1.json")
    evidence = _load(run_root / "parsed/evidence_v4.json")
    vector = _load(run_root / "parsed/feature_vector_v2.json")
    diagnosis = _load(run_root / "diagnosis/diagnosis_result_v2.json")
    validate_evidence_v4(evidence, catalog, repository_root=root)
    validate_feature_vector_v2(vector, catalog, repository_root=root)
    validate_diagnosis_result_v2(diagnosis, repository_root=root)
    if hashlib.sha256((run_root / "parsed/evidence_v4.json").read_bytes()).hexdigest() != vector.get("provenance", {}).get("evidence_sha256"):
        raise X5R10CloseoutError("Feature vector evidence hash drifted.")
    if hashlib.sha256((root / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_bytes()).hexdigest() != vector.get("provenance", {}).get("feature_catalog_sha256"):
        raise X5R10CloseoutError("Feature vector catalog hash drifted.")
    collector_raw: set[tuple[str, str]] = set()
    for collector in evidence.get("collector_runs", []):
        if not isinstance(collector, Mapping):
            raise X5R10CloseoutError("Collector record is invalid.")
        for raw in collector.get("raw_artifacts", []):
            if not isinstance(raw, Mapping):
                raise X5R10CloseoutError("Collector raw record is invalid.")
            pair = (_canonical(raw.get("path")), str(raw.get("sha256")))
            if digests.get(pair[0]) != pair[1]:
                raise X5R10CloseoutError("Collector raw artifact is not receipt-bound: " + pair[0])
            collector_raw.add(pair)
    values: list[object] = []
    for feature in FEATURES:
        observation = evidence.get("observations", {}).get(feature)
        vector_value = vector.get("values", {}).get(feature)
        if not isinstance(observation, Mapping) or not isinstance(vector_value, Mapping):
            raise X5R10CloseoutError("Feature observation/vector link is absent: " + feature)
        pair = (_canonical(observation.get("raw_artifact")), str(observation.get("raw_artifact_sha256")))
        if observation.get("availability") != "observed" or pair not in collector_raw or vector_value != {"availability": "observed", "value": observation.get("value")}:
            raise X5R10CloseoutError("Observation-to-raw chain drifted: " + feature)
        values.append(observation.get("value"))
    if tuple(values) != expected or diagnosis.get("status") != "diagnosed" or diagnosis.get("explanation_refs") != ["rule:" + rule]:
        raise X5R10CloseoutError("Signature or diagnosis drifted.")


def _verify_c4(root: Path, receipt: Mapping[str, object], run: Mapping[str, object]) -> None:
    r4_runs = receipt.get("runs")
    if not isinstance(r4_runs, list):
        raise X5R10CloseoutError("X5-R4 receipt runs are invalid.")
    c4 = next((item for item in r4_runs if isinstance(item, Mapping) and item.get("release_id") == "X5_R4_OSPF_CORRECTION_AND_REVALIDATION"), None)
    if c4 is None or run.get("relative_run_path") != c4.get("relative_run_path"):
        raise X5R10CloseoutError("Authoritative C4 receipt link drifted.")
    digests = _verify_hashes(root, c4)
    _verify_evidence_chain(root, c4, digests, C4_SIGNATURE, "R_X5_OSPF_001")
    controls = _load(root / str(c4["relative_run_path"]) / "validation/targeted_adjacency_controls.json")
    if controls.get("r2_r3_full") is not False or controls.get("r1_r2_full") is not True:
        raise X5R10CloseoutError("Corrected C4 targeted/control adjacency proof drifted.")


def _verify_c5(root: Path, run: Mapping[str, object]) -> None:
    artifacts = _artifacts(run)
    paths = {_canonical(row.get("path")) for row in artifacts}
    if len(paths) != len(artifacts) or not REQUIRED_C5.issubset(paths) or len(paths) != 22:
        raise X5R10CloseoutError("Crash-safe C5 receipt scope drifted.")
    digests = _verify_hashes(root, run)
    _verify_evidence_chain(root, run, digests, C5_SIGNATURE, "R_X5_OSPF_002")
    run_root = root / str(run["relative_run_path"])
    manifest = _load(run_root / "manifest.json")
    injection = _load(run_root / "mutation/injection_record.json")
    effectiveness = _load(run_root / "mutation/mutation_effectiveness.json")
    restoration = _load(run_root / "mutation/restoration_record.json")
    replay = _load(run_root / "mutation/standalone_replay_record.json")
    before = _load(run_root / "validation/baseline_before.json")
    after = _load(run_root / "validation/baseline_after.json")
    controls = _load(run_root / "validation/control_exclusions.json")
    image = _load(run_root / "validation/runtime_image_identity.json")
    required_controls = {
        "target_r2_r3_full", "control_r1_r2_full", "attachment_present", "route_map_match_present",
        "active_deny_present", "direct_expected_network_absent", "lsa_absent", "route_absent",
        "structured_lsdb_valid", "structured_route_valid", "interface_healthy", "no_static_override", "no_acl_block",
    }
    if (
        manifest.get("release_id") != "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION"
        or manifest.get("status") != "COMPLETED"
        or injection.get("status") != "COMMAND_ACCEPTED"
        or injection.get("command_acceptance_only") is not True
        or injection.get("physical_effectiveness_status") != "NOT_YET_OBSERVED"
        or effectiveness.get("status") != "MUTATION_EFFECTIVE"
        or not all(effectiveness.get("postcondition", {}).get(key) is True for key in required_controls - {"interface_healthy", "no_static_override", "no_acl_block"})
        or restoration.get("status") != "RESTORATION_CONFIRMED"
        or restoration.get("recovery", {}).get("status") != "RECOVERY_APPLIED"
        or replay.get("status") != "STANDALONE_REPLAY_APPLIED"
        or before.get("return_code") != 0
        or after.get("return_code") != 0
        or not all(controls.get(key) is True for key in required_controls)
        or image.get("status") != "IMAGE_IDENTITY_RECORDED"
        or image.get("expected_digest_match") is not True
    ):
        raise X5R10CloseoutError("Crash-safe C5 effectiveness, recovery, or controls drifted.")


def verify_x5_r10_closeout(repository_root: Path = ROOT, *, verify_materialized: bool = False) -> dict[str, object]:
    root = Path(repository_root)
    verify_x5_r4_gate(root)
    verify_x5_r9_gate(root)
    plan = _load(root / PLAN)
    receipt = _load(root / RECEIPT)
    if (
        plan.get("source_boundary") != {"parent_commit": "e2ae10c9789145c1e3124588ace7c0349b2a3edc", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}
        or plan.get("authoritative_runs") != {"c4": "X5_R4_OSPF_CORRECTION_AND_REVALIDATION", "c5": "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION"}
        or plan.get("historical_evidence") != HISTORY
        or plan.get("verification") != {
            "receipt_hash_binding_required": True,
            "evidence_v4_and_feature_vector_validation_required": True,
            "observation_collector_raw_receipt_chain_required": True,
            "command_acceptance_and_effectiveness_required": True,
            "restoration_baselines_and_controls_required": True,
            "clean_clone_skip_only_when_ignored_archives_absent": True,
        }
        or plan.get("track") != {"next_release": "X6_R1_PACKET_LOSS", "x6_status": "PAUSED_BY_USER_PENDING_X5_R10_ACCEPTANCE", "p9_r2_status": "PAUSED_BY_USER"}
        or len(plan.get("runtime_authorization", {})) != 10
        or any(plan["runtime_authorization"].values())
    ):
        raise X5R10CloseoutError("X5-R10 authority or pause boundary drifted.")
    runs = receipt.get("runs")
    if (
        not isinstance(runs, list)
        or len(runs) != 2
        or receipt.get("source_commit") != plan["source_boundary"]["parent_commit"]
        or receipt.get("evidence_kind") != "CORRECTED_C4_AND_CRASH_SAFE_C5_RUNTIME_EVIDENCE_NOT_RECOVERED_OR_REPLACED"
        or receipt.get("historical_evidence") != HISTORY
        or receipt.get("summary", {}).get("authoritative_run_count") != 2
        or receipt.get("summary", {}).get("claim_limit") != plan.get("claim_limit")
    ):
        raise X5R10CloseoutError("X5-R10 receipt identity drifted.")
    c4, c5 = runs
    if (
        not isinstance(c4, Mapping) or not isinstance(c5, Mapping)
        or c4.get("release_id") != "X5_R4_OSPF_CORRECTION_AND_REVALIDATION" or c4.get("authority") != "AUTHORITATIVE_CORRECTED_C4"
        or c5.get("release_id") != "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION" or c5.get("authority") != "AUTHORITATIVE_CRASH_SAFE_C5"
        or receipt.get("summary", {}).get("c4_signature") != list(C4_SIGNATURE) or receipt.get("summary", {}).get("c5_signature") != list(C5_SIGNATURE)
    ):
        raise X5R10CloseoutError("X5-R10 authoritative run identity drifted.")
    if verify_materialized:
        _verify_c4(root, _load(root / R4_RECEIPT), c4)
        _verify_c5(root, c5)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--verify-materialized", action="store_true")
    args = parser.parse_args()
    receipt = verify_x5_r10_closeout(args.repository_root, verify_materialized=args.verify_materialized)
    print("x5_r10_closeout=VERIFIED")
    print("authoritative_runs=C4_R4_AND_C5_R9")
    print("c5_bound_artifacts=" + str(len(receipt["runs"][1]["artifacts"])) + "/22_HASH_BOUND_PASS")
    print("next_release=X6_R1_PACKET_LOSS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
