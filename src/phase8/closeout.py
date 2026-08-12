"""Fail-closed Phase 8 acceptance closeout and Phase 9 handoff manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from src.phase8.archive import verify_archive


SCOPE_PATH = Path("plans/phase8/P8_R0_EVIDENCE_CLAIM_SCOPE_V1.json")
REGISTRY_PATH = Path("plans/phase8/P8_R1_FINAL_EVIDENCE_REGISTRY_V1.json")
RECEIPT_PATH = Path("plans/phase8/P8_R1_PRIVATE_ARCHIVE_RECEIPT_V1.json")
SYNTHESIS_PATH = Path("plans/phase8/P8_R2_THESIS_EVALUATION_SYNTHESIS_V1.json")
CLOSEOUT_PATH = Path("plans/phase8/P8_R3_PHASE8_CLOSEOUT_V1.json")

SOURCE_PREFIX = "cb489a3"
EXPECTED_PARENT = "c55c803dbb42752f1597b2276026204267e35e0f"
EXPECTED_ARCHIVE_SHA256 = (
    "e9eea5fe520779eee4f4eba4df442ae46c0fd43ea382eed9f5ad5de94cbd14b6"
)


class Phase8CloseoutError(RuntimeError):
    """Raised when an accepted Phase 8 boundary fails closed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase8CloseoutError(f"Cannot read accepted JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Phase8CloseoutError(f"Accepted JSON root is not an object: {path}")
    return value


def _binding(root: Path, relative_path: Path) -> dict[str, Any]:
    path = root / relative_path
    if not path.is_file() or path.is_symlink():
        raise Phase8CloseoutError(f"Accepted file is missing or unsafe: {relative_path}")
    return {
        "path": relative_path.as_posix(),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _require_binding(root: Path, value: dict[str, Any]) -> None:
    relative = Path(value["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise Phase8CloseoutError(f"Non-canonical accepted path: {relative}")
    observed = _binding(root, relative)
    if observed["sha256"] != value["sha256"]:
        raise Phase8CloseoutError(f"Accepted SHA-256 drifted: {relative}")
    if observed["size_bytes"] != value["size_bytes"]:
        raise Phase8CloseoutError(f"Accepted byte size drifted: {relative}")


def _require_all_false(name: str, value: dict[str, Any]) -> None:
    if not value or set(value.values()) != {False}:
        raise Phase8CloseoutError(f"Runtime authorization is not closed: {name}")


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_closeout_manifest(
    repository_root: Path,
    source_commit: str,
) -> dict[str, Any]:
    """Build the deterministic tracked closeout from accepted tracked inputs."""

    root = repository_root.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise Phase8CloseoutError("The source commit must be a full lowercase SHA-1.")
    if not source_commit.startswith(SOURCE_PREFIX):
        raise Phase8CloseoutError("The source commit is not the accepted cb489a3 boundary.")

    scope = _load_json(root / SCOPE_PATH)
    registry = _load_json(root / REGISTRY_PATH)
    receipt = _load_json(root / RECEIPT_PATH)
    synthesis = _load_json(root / SYNTHESIS_PATH)

    if scope.get("decision") != "NO_NEW_EXPERIMENT_REQUIRED":
        raise Phase8CloseoutError("P8-R0 decision drifted.")
    if registry.get("status") != "ACCEPTED_IMMUTABLE":
        raise Phase8CloseoutError("P8-R1 registry status drifted.")
    if receipt.get("status") != "VERIFIED":
        raise Phase8CloseoutError("P8-R1 receipt status drifted.")
    if synthesis.get("status") != "THESIS_READY":
        raise Phase8CloseoutError("P8-R2 synthesis status drifted.")

    scope_binding = _binding(root, SCOPE_PATH)
    registry_binding = _binding(root, REGISTRY_PATH)
    receipt_binding = _binding(root, RECEIPT_PATH)
    synthesis_binding = _binding(root, SYNTHESIS_PATH)
    if scope_binding != registry.get("p8_scope_gate"):
        raise Phase8CloseoutError("P8-R0 is not the registry-bound scope gate.")
    if registry_binding != {
        key: receipt["registry"][key]
        for key in ("path", "sha256", "size_bytes")
    }:
        raise Phase8CloseoutError("P8-R1 registry is not receipt-bound.")

    synthesis_sources = {
        item["path"]: item for item in synthesis.get("accepted_sources", [])
    }
    for accepted in (scope_binding, registry_binding, receipt_binding):
        source = synthesis_sources.get(accepted["path"])
        if source is None:
            raise Phase8CloseoutError("P8-R2 accepted-source chain is incomplete.")
        if any(source[key] != accepted[key] for key in ("sha256", "size_bytes")):
            raise Phase8CloseoutError("P8-R2 accepted-source binding drifted.")

    assets = synthesis.get("assets", [])
    if len(assets) != 5:
        raise Phase8CloseoutError("P8-R2 must bind exactly five thesis assets.")
    for asset in assets:
        _require_binding(root, asset)

    _require_all_false("P8-R0", scope["runtime_authorization"])
    _require_all_false("P8-R1", registry["runtime_authorization"])
    _require_all_false("P8-R2", synthesis["runtime_authorization"])

    claim_ids = [item["claim_id"] for item in synthesis["claim_matrix"]]
    blocked_ids = [item["claim_id"] for item in synthesis["blocked_claims"]]
    if claim_ids != [f"C0{index}" for index in range(1, 9)]:
        raise Phase8CloseoutError("Supported claim boundary drifted.")
    if blocked_ids != [f"B0{index}" for index in range(1, 9)]:
        raise Phase8CloseoutError("Blocked claim boundary drifted.")

    comparison = synthesis["comparison"]
    if comparison["methods"]["machine_learning_p6_v1"] != comparison["methods"]["hybrid_p6_v1"]:
        raise Phase8CloseoutError("Accepted ML/Hybrid aggregate equality drifted.")
    if comparison["statistical_superiority_test"] != "NOT_PERFORMED":
        raise Phase8CloseoutError("Statistical-superiority boundary drifted.")

    if receipt["archive_sha256"] != EXPECTED_ARCHIVE_SHA256:
        raise Phase8CloseoutError("Private archive receipt SHA-256 drifted.")
    if receipt["runtime_artifact_count"] != 1488:
        raise Phase8CloseoutError("Accepted runtime artifact count drifted.")

    runtime_authorization = {
        "accepted_artifact_mutation": False,
        "containerlab": False,
        "diagnosis_execution": False,
        "metric_recalculation": False,
        "model_deserialization": False,
        "model_refit": False,
        "network_mutation": False,
        "new_experiment": False,
        "new_metric": False,
        "policy_reselection": False,
        "test_evaluation": False,
        "thesis_claim_broadening": False,
    }

    return {
        "schema_version": 1,
        "closeout_id": "p8_r3_phase8_closeout_v1",
        "status": "PHASE8_ACCEPTED_CLOSED",
        "source_checkpoint": {
            "branch": "main",
            "commit": source_commit,
            "commit_short": SOURCE_PREFIX,
            "parent_commit": EXPECTED_PARENT,
        },
        "accepted_inputs": [
            {"milestone": "P8-R0", **scope_binding},
            {"milestone": "P8-R1-REGISTRY", **registry_binding},
            {"milestone": "P8-R1-RECEIPT", **receipt_binding},
            {"milestone": "P8-R2", **synthesis_binding},
        ],
        "accepted_chain": {
            "scope_decision": "NO_NEW_EXPERIMENT_REQUIRED",
            "runtime_artifact_count": 1488,
            "archive_member_count": receipt["archive_member_count"],
            "private_archive_file_name": receipt["archive_file_name"],
            "private_archive_sha256": receipt["archive_sha256"],
            "private_archive_size_bytes": receipt["archive_size_bytes"],
            "thesis_asset_count": 5,
            "supported_claim_count": 8,
            "blocked_claim_count": 8,
            "estimator_deserialized": False,
            "test_partition_reopened": False,
            "metric_recalculated": False,
        },
        "thesis_assets": assets,
        "claim_boundary": {
            "supported_claim_ids": claim_ids,
            "blocked_claim_ids": blocked_ids,
            "comparison_type": "DESCRIPTIVE_ONLY",
            "hybrid_interpretation": "OPERATIONALLY_DISTINCT_NUMERICALLY_EQUAL_TO_ML",
            "masked_inputs": "TRANSFORMATIONS_NOT_INDEPENDENT_EXPERIMENTS",
            "external_generalization": "NOT_ESTABLISHED",
        },
        "phase9_handoff": {
            "next_milestone": "P9-R0",
            "entry_gate": "THESIS_STRUCTURE_AND_SOURCE_CITATION_GATE",
            "chapter_map": [
                {"chapter_id": "CH01", "purpose": "Introduction and bounded research question", "evidence_ids": ["E01", "E04", "E05"]},
                {"chapter_id": "CH02", "purpose": "Networking and intelligent-diagnosis background", "evidence_ids": ["E01", "E03"]},
                {"chapter_id": "CH03", "purpose": "Controlled methodology and evaluation protocol", "evidence_ids": ["E02", "E04", "E05"]},
                {"chapter_id": "CH04", "purpose": "System architecture and implementation", "evidence_ids": ["E01", "E03", "E06"]},
                {"chapter_id": "CH05", "purpose": "Final evaluation results", "evidence_ids": ["E04", "E05"], "asset_ids": ["T01", "T02", "F01", "F02"]},
                {"chapter_id": "CH06", "purpose": "Discussion, limitations, and validity", "evidence_ids": ["E05", "E06"], "asset_ids": ["T03"]},
                {"chapter_id": "CH07", "purpose": "Conclusions and bounded future work", "evidence_ids": ["E01", "E05", "E06"]},
            ],
            "writing_constraints": [
                "PRESERVE_EXACT_ACCEPTED_VALUES",
                "CITE_EACH_SUPPORTED_CLAIM_WITH_ITS_LIMIT",
                "KEEP_ALL_BLOCKED_CLAIMS_PROHIBITED",
                "DISTINGUISH_IMPLEMENTED_TESTED_AND_PROPOSED_WORK",
                "DO_NOT_TREAT_MASKS_AS_INDEPENDENT_EXPERIMENTS",
                "DO_NOT_CLAIM_HYBRID_OR_STATISTICAL_SUPERIORITY",
            ],
        },
        "runtime_authorization": runtime_authorization,
        "next_milestone": "P9-R0",
    }


def verify_private_archive_boundary(
    repository_root: Path,
    private_archive: Path,
) -> dict[str, Any]:
    """Verify the accepted external archive without loading the estimator."""

    root = repository_root.resolve()
    archive = private_archive.resolve()
    receipt = _load_json(root / RECEIPT_PATH)
    if not archive.is_file() or archive.is_symlink():
        raise Phase8CloseoutError("The accepted private archive is missing or unsafe.")
    if archive.stat().st_size != receipt["archive_size_bytes"]:
        raise Phase8CloseoutError("The accepted private archive size drifted.")
    if _sha256(archive) != receipt["archive_sha256"]:
        raise Phase8CloseoutError("The accepted private archive SHA-256 drifted.")
    result = verify_archive(root, root / REGISTRY_PATH, archive)
    for key in (
        "archive_sha256",
        "archive_size_bytes",
        "archive_member_count",
        "runtime_artifact_count",
    ):
        if result[key] != receipt[key]:
            raise Phase8CloseoutError(f"Private archive verification drifted: {key}")
    return result


def write_closeout_manifest(
    repository_root: Path,
    source_commit: str,
    private_archive: Path,
) -> Path:
    """Verify the full chain and atomically write the deterministic manifest."""

    root = repository_root.resolve()
    verify_private_archive_boundary(root, private_archive)
    manifest = build_closeout_manifest(root, source_commit)
    destination = root / CLOSEOUT_PATH
    if destination.exists():
        raise Phase8CloseoutError(f"Closeout manifest already exists: {CLOSEOUT_PATH}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_canonical_bytes(manifest))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, destination)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return destination


def verify_closeout_manifest(
    repository_root: Path,
    private_archive: Path | None = None,
) -> dict[str, Any]:
    """Rebuild and byte-verify the tracked closeout; optionally verify archive."""

    root = repository_root.resolve()
    destination = root / CLOSEOUT_PATH
    observed = _load_json(destination)
    expected = build_closeout_manifest(root, observed["source_checkpoint"]["commit"])
    if destination.read_bytes() != _canonical_bytes(expected):
        raise Phase8CloseoutError("Tracked P8-R3 closeout is not byte-identical.")
    if private_archive is not None:
        verify_private_archive_boundary(root, private_archive)
    return observed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--private-archive", type=Path)
    parser.add_argument("--source-commit")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.write:
        if args.private_archive is None or args.source_commit is None:
            raise SystemExit("--write requires --private-archive and --source-commit")
        path = write_closeout_manifest(
            args.repository_root, args.source_commit, args.private_archive
        )
        print(f"closeout_manifest={path}")
    else:
        verify_closeout_manifest(args.repository_root, args.private_archive)
        print("phase8_closeout=VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
