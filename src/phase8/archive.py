"""Build the P8-R1 immutable registry and deterministic private archive.

The module only inventories, hashes, and copies already accepted bytes.  In
particular, the selected estimator is treated as an opaque file: this module
does not import joblib or pickle and never deserializes the model.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from src.phase7.catalog import ArtifactCatalog
from src.runtime.subprocesses import run_capture


REGISTRY_ID = "p8_r1_final_evidence_registry_v1"
RECEIPT_ID = "p8_r1_private_archive_receipt_v1"
ARCHIVE_DIRECTORY_NAME = "P8_R1_FINAL_EVIDENCE_ARCHIVE_V1"
ARCHIVE_FILE_NAME = "P8-R1-final-evidence-private.tar.gz"
DEFAULT_REGISTRY_PATH = Path(
    "plans/phase8/P8_R1_FINAL_EVIDENCE_REGISTRY_V1.json"
)
DEFAULT_RECEIPT_PATH = Path(
    "plans/phase8/P8_R1_PRIVATE_ARCHIVE_RECEIPT_V1.json"
)
P8_SCOPE_PATH = Path("plans/phase8/P8_R0_EVIDENCE_CLAIM_SCOPE_V1.json")
P7_CATALOG_PATH = Path(
    "plans/phase7/P7_R1_ACCEPTED_ARTIFACT_CATALOG_V1.json"
)
P7_CONTRACT_PATH = Path("plans/phase7/P7_R0_READ_ONLY_INTERFACE_V1.json")
GATE_PATH = Path("data/metadata/p6_r6_six_class_method_gate_v1.json")
MODEL_ROOT = Path("models/p6_r6_six_class_v1")
REPORT_ROOT = Path("reports/experiments/p6_r6_six_class_v1")

# D-083 accepted bindings are repeated here deliberately so archival code does
# not import the runtime coordinator (and therefore does not import joblib).
ACCEPTED_CAMPAIGN_RUN_ID = "p6_r5_clean_campaign_recovery-20260811T070536Z"
ACCEPTED_CAMPAIGN_RESULT_SHA256 = (
    "c4c45e19e8b98d00a3fa2ed3b4d4a8ad2ba6debd04baae05c2d7d7377f9df4d2"
)
ACCEPTED_MERGED_DATASET_SHA256 = (
    "50dd030e51e4873eac7665980e033a0236e4ddf26e446b66bd3d11613c4a0a9d"
)
ACCEPTED_SPLIT_MANIFEST_SHA256 = (
    "adf70942a740be43e085aca67f9acb4085dd118827ceba8482913dbc6adb5f9f"
)
ACCEPTED_PARTITION_SHA256 = {
    "train": "128e3b6316a2f9065db0d8478b9571cd0474c39f3cec1c0e766e8f489884fec7",
    "validation": "8ae10a384f318e4e01a18da386585300547456ed32004eacd39054899176e60b",
    "test": "4757ba82cbe939fadb2491b1907f0f13cc70be9d3f0117758896931484bcfee7",
}

MODEL_FILE_NAMES = frozenset(
    {
        "train_inputs.jsonl",
        "train_targets.jsonl",
        "validation_inputs.jsonl",
        "validation_targets.jsonl",
        "validation_rule_predictions.jsonl",
        "validation_ml_predictions.jsonl",
        "validation_hybrid_predictions.jsonl",
        "development_summary.json",
        "ml_selection.json",
        "hybrid_selection.json",
        "selected_estimator.joblib",
        "freeze_manifest.json",
        "freeze_receipt.json",
    }
)
REPORT_FILE_NAMES = frozenset(
    {
        "test_inputs.jsonl",
        "test_targets.jsonl",
        "rule_predictions.jsonl",
        "ml_predictions.jsonl",
        "hybrid_predictions.jsonl",
        "rule_report.json",
        "ml_report.json",
        "hybrid_report.json",
        "cross_method_comparison.json",
        "run_manifest.json",
    }
)
SPLIT_FILE_NAMES = frozenset(
    {"split_manifest.json", "train.jsonl", "validation.jsonl", "test.jsonl"}
)
CONTEXT_FILE_NAMES = frozenset(f"E{index:02d}.jsonl" for index in range(1, 7))

PUBLIC_EVIDENCE_PATHS = (
    "docs/HANDOFF_P6_R5.md",
    "docs/HANDOFF_P6_R6.md",
    "docs/HANDOFF_P7_R4.md",
    "docs/HANDOFF_P8_R0.md",
    "plans/campaigns/P6_EXTENDED_6CLASS_6CTX_V1.fingerprints.json",
    "plans/campaigns/P6_EXTENDED_6CLASS_6CTX_V1.yml",
    "plans/phase6/P6_R6_METHOD_PROTOCOL_V1.json",
    P7_CONTRACT_PATH.as_posix(),
    P7_CATALOG_PATH.as_posix(),
    P8_SCOPE_PATH.as_posix(),
    "plans/taxonomies/P6_EXTENDED_FAULT_TAXONOMY_V1.json",
)

ARCHIVE_README = """# P8-R1 Final Evidence Archive\n\nThis private archive preserves the accepted P6-R5 to P6-R6 final\nexperimental chain. `REGISTRY.json` binds every archived runtime file to its\nrepository-relative path, byte size, SHA-256 digest, stage, and role.\n\nThe tracked Git source checkpoint is a separate public-source archive. The\nselected estimator in this bundle is an opaque byte artifact; archiving and\nverification do not deserialize it. No experiment, inference, refit, policy\nselection, metric calculation, or test-guided revision is performed here.\n"""


class EvidenceArchiveError(RuntimeError):
    """Raised when the accepted evidence boundary is absent or has drifted."""


@dataclass(frozen=True, slots=True)
class ArchiveContract:
    campaign_run_id: str
    campaign_result_sha256: str
    merged_dataset_sha256: str
    split_manifest_sha256: str
    partition_sha256: Mapping[str, str]
    expected_experiment_count: int = 72
    expected_context_count: int = 6


DEFAULT_CONTRACT = ArchiveContract(
    campaign_run_id=ACCEPTED_CAMPAIGN_RUN_ID,
    campaign_result_sha256=ACCEPTED_CAMPAIGN_RESULT_SHA256,
    merged_dataset_sha256=ACCEPTED_MERGED_DATASET_SHA256,
    split_manifest_sha256=ACCEPTED_SPLIT_MANIFEST_SHA256,
    partition_sha256=dict(ACCEPTED_PARTITION_SHA256),
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceArchiveError(message)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise EvidenceArchiveError(f"Cannot read artifact bytes: {path}") from error
    return digest.hexdigest()


def _canonical_relative(root: Path, path: Path) -> str:
    resolved_root = root.resolve()
    _require(path.exists(), f"Required artifact is missing: {path}")
    _require(not path.is_symlink(), f"Symbolic links are forbidden: {path}")
    try:
        relative = path.resolve().relative_to(resolved_root).as_posix()
    except ValueError as error:
        raise EvidenceArchiveError(f"Artifact escaped the repository: {path}") from error
    candidate = PurePosixPath(relative)
    _require(
        relative not in ("", ".")
        and not candidate.is_absolute()
        and ".." not in candidate.parts,
        f"Artifact path is not canonical: {relative}",
    )
    return relative


def _safe_path(root: Path, relative: str) -> Path:
    candidate = PurePosixPath(relative)
    _require(
        relative == candidate.as_posix()
        and not candidate.is_absolute()
        and ".." not in candidate.parts,
        f"Registry path is not canonical: {relative}",
    )
    path = root / Path(*candidate.parts)
    _canonical_relative(root, path)
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceArchiveError(f"Invalid JSON artifact: {path}") from error
    _require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def _artifact(path: Path, root: Path) -> dict[str, Any]:
    _require(path.is_file(), f"Required artifact is not a regular file: {path}")
    relative = _canonical_relative(root, path)
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _iter_files(root: Path, directory: Path) -> list[Path]:
    _require(directory.is_dir(), f"Required artifact directory is missing: {directory}")
    _require(not directory.is_symlink(), f"Symbolic directory is forbidden: {directory}")
    files: list[Path] = []
    for path in directory.rglob("*"):
        _require(not path.is_symlink(), f"Symbolic links are forbidden: {path}")
        if path.is_file():
            _canonical_relative(root, path)
            files.append(path)
        else:
            _require(path.is_dir(), f"Unsupported filesystem entry: {path}")
    return sorted(files, key=lambda item: _canonical_relative(root, item))


def _verify_exact_names(directory: Path, expected: frozenset[str], label: str) -> None:
    observed = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    }
    _require(observed == expected, f"{label} file set drifted: {sorted(observed)}")


def _verify_reference(root: Path, value: Any, label: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), f"{label} is not an artifact reference.")
    relative = value.get("path")
    digest = value.get("sha256")
    size = value.get("size_bytes")
    _require(isinstance(relative, str), f"{label} has no path.")
    path = _safe_path(root, relative)
    observed = _artifact(path, root)
    _require(digest == observed["sha256"], f"{label} SHA-256 drifted.")
    if size is not None:
        _require(size == observed["size_bytes"], f"{label} size drifted.")
    return observed


def _git(root: Path, *arguments: str) -> str:
    result = run_capture(
        ["git", "-C", str(root), *arguments],
        timeout_seconds=30.0,
    )
    if result.returncode != 0:
        raise EvidenceArchiveError(
            f"Git checkpoint query failed: {' '.join(arguments)}: "
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _source_checkpoint(root: Path) -> dict[str, Any]:
    full = _git(root, "rev-parse", "HEAD")
    short = _git(root, "rev-parse", "--short=7", "HEAD")
    branch = _git(root, "branch", "--show-current")
    _require(branch == "main", "P8-R1 source checkpoint must be on main.")
    return {
        "branch": branch,
        "commit": full,
        "commit_short": short,
        "public_archive": "GIT_TRACKED_SOURCE_AT_CHECKPOINT",
    }


def _campaign_paths(root: Path, contract: ArchiveContract) -> dict[str, Path]:
    run_id = contract.campaign_run_id
    return {
        "campaign_result": root / "data/metadata" / f"{run_id}.phase6-campaign.json",
        "raw_root": root / "data/raw" / run_id,
        "contexts_root": root / "data/processed" / f"{run_id}-contexts",
        "merged_dataset": root / "data/processed" / f"{run_id}.dataset-row-v3.jsonl",
        "split_root": root / "data/processed" / f"{run_id}-split",
    }


def _validate_campaign(
    root: Path, contract: ArchiveContract
) -> tuple[dict[str, Path], list[Path]]:
    paths = _campaign_paths(root, contract)
    campaign_path = paths["campaign_result"]
    _require(
        sha256_file(campaign_path) == contract.campaign_result_sha256,
        "Accepted P6-R5 campaign-result SHA-256 drifted.",
    )
    campaign = _read_json(campaign_path)
    expected = {
        "campaign_run_id": contract.campaign_run_id,
        "status": "COMPLETED",
        "completed_context_count": contract.expected_context_count,
        "completed_experiment_count": contract.expected_experiment_count,
        "dataset_row_count": contract.expected_experiment_count,
        "diagnosis_count": 0,
        "prediction_count": 0,
        "metric_count": 0,
        "masked_row_count": 0,
        "test_partition_status": "SEALED_FOR_P6_R6_REPORT_ONLY",
    }
    for name, expected_value in expected.items():
        _require(campaign.get(name) == expected_value, f"Campaign field drifted: {name}")

    merged = paths["merged_dataset"]
    _require(
        sha256_file(merged) == contract.merged_dataset_sha256,
        "Accepted merged Dataset Row v3 SHA-256 drifted.",
    )
    merged_binding = campaign.get("merged_dataset")
    _require(
        isinstance(merged_binding, Mapping)
        and merged_binding.get("sha256") == contract.merged_dataset_sha256
        and merged_binding.get("row_count") == contract.expected_experiment_count,
        "Campaign merged-dataset binding drifted.",
    )

    split_root = paths["split_root"]
    _verify_exact_names(split_root, SPLIT_FILE_NAMES, "P6-R5 split")
    _require(
        sha256_file(split_root / "split_manifest.json")
        == contract.split_manifest_sha256,
        "Accepted split-manifest SHA-256 drifted.",
    )
    for partition in ("train", "validation", "test"):
        _require(
            sha256_file(split_root / f"{partition}.jsonl")
            == contract.partition_sha256[partition],
            f"Accepted {partition} partition SHA-256 drifted.",
        )

    contexts_root = paths["contexts_root"]
    _verify_exact_names(contexts_root, CONTEXT_FILE_NAMES, "P6-R5 context dataset")
    contexts = campaign.get("contexts")
    _require(
        isinstance(contexts, list) and len(contexts) == contract.expected_context_count,
        "Campaign context set drifted.",
    )
    for context in contexts:
        _require(isinstance(context, Mapping), "Campaign context is not an object.")
        slot = context.get("group_slot")
        _require(isinstance(slot, str), "Campaign context has no group slot.")
        path = contexts_root / f"{slot}.jsonl"
        _require(path.is_file(), f"Campaign context dataset is missing: {slot}")
        _require(
            context.get("dataset_sha256") == sha256_file(path),
            f"Campaign context dataset SHA-256 drifted: {slot}",
        )

    raw_files = _iter_files(root, paths["raw_root"])
    manifest_count = sum(path.name == "manifest.json" for path in raw_files)
    _require(
        manifest_count == contract.expected_experiment_count,
        f"Accepted raw experiment count drifted: {manifest_count}",
    )
    all_files = [campaign_path, merged]
    all_files.extend(_iter_files(root, contexts_root))
    all_files.extend(_iter_files(root, split_root))
    all_files.extend(raw_files)
    return paths, all_files


def _validate_method_chain(root: Path) -> tuple[list[Path], ArtifactCatalog]:
    _verify_exact_names(root / MODEL_ROOT, MODEL_FILE_NAMES, "P6-R6 model")
    _verify_exact_names(root / REPORT_ROOT, REPORT_FILE_NAMES, "P6-R6 report")
    model_files = _iter_files(root, root / MODEL_ROOT)
    report_files = _iter_files(root, root / REPORT_ROOT)

    manifest = _read_json(root / MODEL_ROOT / "freeze_manifest.json")
    _require(
        manifest.get("freeze_id") == "p6_r6_six_class_method_freeze_v1",
        "P6-R6 freeze identity drifted.",
    )
    _require(manifest.get("test_inputs_read") == 0, "Freeze contains test access.")
    _require(
        manifest.get("test_predictions_or_metrics") == "ABSENT",
        "Freeze contains test-derived output.",
    )
    development = manifest.get("development_artifacts")
    _require(
        isinstance(development, Mapping)
        and set(development) == MODEL_FILE_NAMES - {"freeze_manifest.json", "freeze_receipt.json"},
        "Freeze development artifact set drifted.",
    )
    for name, reference in development.items():
        observed = _verify_reference(root, reference, f"development_artifacts.{name}")
        _require(
            observed["path"] == (MODEL_ROOT / name).as_posix(),
            f"Development artifact path drifted: {name}",
        )

    receipt = _read_json(root / MODEL_ROOT / "freeze_receipt.json")
    _require(
        receipt.get("authorization") == "ONE_REPORT_ONLY_TEST_EVALUATION",
        "P6-R6 freeze receipt authorization drifted.",
    )
    for name, file_name in (
        ("freeze_manifest", "freeze_manifest.json"),
        ("selected_estimator", "selected_estimator.joblib"),
        ("ml_selection", "ml_selection.json"),
        ("hybrid_selection", "hybrid_selection.json"),
    ):
        observed = _verify_reference(root, receipt.get(name), f"freeze_receipt.{name}")
        _require(
            observed["path"] == (MODEL_ROOT / file_name).as_posix(),
            f"Freeze receipt path drifted: {name}",
        )

    gate_path = root / GATE_PATH
    gate = _read_json(gate_path)
    _require(gate.get("status") == "COMPLETED", "P6-R6 method gate is not complete.")
    _require(
        gate.get("test_evaluation_attempt_count") == 1,
        "P6-R6 test attempt count drifted.",
    )
    _require(
        gate.get("development_freeze_verified") is True,
        "P6-R6 development freeze is not verified.",
    )
    artifacts = gate.get("artifacts")
    _require(
        isinstance(artifacts, Mapping) and set(artifacts) == REPORT_FILE_NAMES,
        "P6-R6 report artifact set drifted.",
    )
    for name, reference in artifacts.items():
        observed = _verify_reference(root, reference, f"method_gate.artifacts.{name}")
        _require(
            observed["path"] == (REPORT_ROOT / name).as_posix(),
            f"Method-gate report path drifted: {name}",
        )

    run_manifest = _read_json(root / REPORT_ROOT / "run_manifest.json")
    _require(run_manifest.get("status") == "COMPLETED", "Run manifest is not complete.")
    _require(
        run_manifest.get("test_use") == "ONE_REPORT_ONLY_EVALUATION",
        "Run-manifest test role drifted.",
    )
    _require(run_manifest.get("test_guided_revision") is False, "Test revision drifted.")
    _require(run_manifest.get("model_refit_after_freeze") is False, "Refit drifted.")
    _require(
        run_manifest.get("policy_reselection_after_freeze") is False,
        "Policy reselection drifted.",
    )
    for name, file_name in (
        ("freeze_manifest", "freeze_manifest.json"),
        ("freeze_receipt", "freeze_receipt.json"),
        ("selected_estimator", "selected_estimator.joblib"),
        ("ml_selection", "ml_selection.json"),
        ("hybrid_selection", "hybrid_selection.json"),
    ):
        observed = _verify_reference(root, run_manifest.get(name), f"run_manifest.{name}")
        _require(
            observed["path"] == (MODEL_ROOT / file_name).as_posix(),
            f"Run-manifest model path drifted: {name}",
        )

    catalog = ArtifactCatalog.load(repository_root=root)
    _require(len(catalog.artifacts_by_path) == 15, "P7 catalog is not 15/15.")
    for path, verified in catalog.artifacts_by_path.items():
        _require(
            sha256_file(root / path) == verified.sha256,
            f"P7 catalog source drifted: {path}",
        )
    return [gate_path, *model_files, *report_files], catalog


def _classify(relative: str, contract: ArchiveContract) -> tuple[str, str]:
    run_id = contract.campaign_run_id
    if relative == f"data/metadata/{run_id}.phase6-campaign.json":
        return "P6-R5", "campaign_result"
    if relative.startswith(f"data/raw/{run_id}/"):
        return "P6-R5", "raw_experiment_artifact"
    if relative.startswith(f"data/processed/{run_id}-contexts/"):
        return "P6-R5", "context_dataset"
    if relative == f"data/processed/{run_id}.dataset-row-v3.jsonl":
        return "P6-R5", "merged_dataset"
    if relative.endswith("-split/split_manifest.json"):
        return "P6-R5", "split_manifest"
    if f"data/processed/{run_id}-split/" in relative:
        return "P6-R5", "dataset_partition"
    if relative == GATE_PATH.as_posix():
        return "P6-R6", "method_gate"
    if relative == (MODEL_ROOT / "selected_estimator.joblib").as_posix():
        return "P6-R6", "opaque_selected_estimator"
    if relative.startswith(f"{MODEL_ROOT.as_posix()}/"):
        return "P6-R6", "development_freeze_artifact"
    if relative.startswith(f"{REPORT_ROOT.as_posix()}/"):
        return "P6-R6", "report_only_evaluation_artifact"
    raise EvidenceArchiveError(f"Unclassified runtime artifact: {relative}")


def _public_bindings(root: Path) -> list[dict[str, Any]]:
    manifest = _read_json(root / MODEL_ROOT / "freeze_manifest.json")
    paths = set(PUBLIC_EVIDENCE_PATHS)
    protocol = manifest.get("protocol")
    if isinstance(protocol, Mapping) and isinstance(protocol.get("path"), str):
        paths.add(str(protocol["path"]))
    implementation = manifest.get("implementation")
    _require(isinstance(implementation, Mapping), "Freeze implementation set is absent.")
    paths.update(str(path) for path in implementation)

    bindings: list[dict[str, Any]] = []
    for index, relative in enumerate(sorted(paths), start=1):
        path = _safe_path(root, relative)
        _require(
            _git(root, "ls-files", "--error-unmatch", "--", relative) == relative,
            f"Public evidence path is not tracked: {relative}",
        )
        binding = _artifact(path, root)
        binding.update({"source_id": f"S{index:03d}", "archive_member": False})
        bindings.append(binding)
    return bindings


def build_registry(
    repository_root: Path,
    *,
    contract: ArchiveContract = DEFAULT_CONTRACT,
    source_checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the fail-closed registry for the accepted final evidence chain."""

    root = repository_root.resolve()
    _require((root / ".git").exists(), "Repository metadata is missing.")
    _, campaign_files = _validate_campaign(root, contract)
    method_files, catalog = _validate_method_chain(root)

    scope = _read_json(root / P8_SCOPE_PATH)
    _require(scope.get("decision") == "NO_NEW_EXPERIMENT_REQUIRED", "P8-R0 decision drifted.")
    _require(scope.get("status") == "FROZEN", "P8-R0 scope is not frozen.")
    catalog_binding = scope.get("final_evaluation_snapshot", {}).get("catalog_binding")
    _require(isinstance(catalog_binding, Mapping), "P8-R0 catalog binding is absent.")
    _require(
        catalog_binding.get("sha256") == sha256_file(root / P7_CATALOG_PATH),
        "P8-R0 catalog binding drifted.",
    )

    unique: dict[str, Path] = {}
    for path in [*campaign_files, *method_files]:
        relative = _canonical_relative(root, path)
        _require(relative not in unique or unique[relative] == path, "Duplicate path drifted.")
        unique[relative] = path

    runtime: list[dict[str, Any]] = []
    for index, relative in enumerate(sorted(unique), start=1):
        stage, role = _classify(relative, contract)
        item = _artifact(unique[relative], root)
        item.update(
            {
                "artifact_id": f"A{index:04d}",
                "archive_path": f"artifacts/{relative}",
                "stage": stage,
                "role": role,
                "archive_member": True,
            }
        )
        runtime.append(item)

    by_path = {item["path"]: item for item in runtime}
    root_paths = (
        f"data/metadata/{contract.campaign_run_id}.phase6-campaign.json",
        f"data/processed/{contract.campaign_run_id}.dataset-row-v3.jsonl",
        f"data/processed/{contract.campaign_run_id}-split/split_manifest.json",
        (MODEL_ROOT / "freeze_manifest.json").as_posix(),
        (MODEL_ROOT / "freeze_receipt.json").as_posix(),
        GATE_PATH.as_posix(),
        (REPORT_ROOT / "run_manifest.json").as_posix(),
        (REPORT_ROOT / "cross_method_comparison.json").as_posix(),
    )
    _require(set(root_paths) <= set(by_path), "An accepted archive root is absent.")

    public = _public_bindings(root)
    checkpoint = dict(source_checkpoint or _source_checkpoint(root))
    _require(checkpoint.get("branch") == "main", "Source checkpoint branch drifted.")
    checkpoint_commit = checkpoint.get("commit")
    _require(isinstance(checkpoint_commit, str), "Source checkpoint commit is absent.")
    _git(root, "cat-file", "-e", f"{checkpoint_commit}^{{commit}}")
    _git(root, "merge-base", "--is-ancestor", checkpoint_commit, "HEAD")
    registry: dict[str, Any] = {
        "schema_version": 1,
        "registry_id": REGISTRY_ID,
        "status": "ACCEPTED_IMMUTABLE",
        "archive_scope": "FINAL_P6_R5_TO_P6_R6_EXPERIMENTAL_CHAIN",
        "source_checkpoint": checkpoint,
        "accepted_roots": [
            {
                "root_id": f"R{index:02d}",
                "path": relative,
                "sha256": by_path[relative]["sha256"],
                "size_bytes": by_path[relative]["size_bytes"],
            }
            for index, relative in enumerate(root_paths, start=1)
        ],
        "runtime_artifact_count": len(runtime),
        "runtime_payload_size_bytes": sum(item["size_bytes"] for item in runtime),
        "raw_experiment_count": contract.expected_experiment_count,
        "runtime_artifacts": runtime,
        "public_source_binding_count": len(public),
        "public_source_bindings": public,
        "p7_projection_catalog": _artifact(root / P7_CATALOG_PATH, root),
        "p8_scope_gate": _artifact(root / P8_SCOPE_PATH, root),
        "archive_layout": {
            "directory": ARCHIVE_DIRECTORY_NAME,
            "registry_member": "REGISTRY.json",
            "readme_member": "README.md",
            "runtime_prefix": "artifacts/",
            "archive_file_name": ARCHIVE_FILE_NAME,
            "deterministic_metadata": {
                "mtime": 0,
                "uid": 0,
                "gid": 0,
                "file_mode": "0644",
            },
        },
        "integrity": {
            "algorithm": "SHA-256",
            "missing_or_drifted_artifact": "FAIL_CLOSED",
            "estimator_handling": "OPAQUE_BYTES_HASHED_AND_COPIED_NOT_DESERIALIZED",
            "test_partition_handling": "HASHED_AND_COPIED_WITHOUT_EVALUATION",
            "archive_rebuild": "DETERMINISTIC_FROM_REGISTRY_AND_ACCEPTED_BYTES",
        },
        "runtime_authorization": {
            "containerlab": False,
            "network_mutation": False,
            "diagnosis_execution": False,
            "model_deserialization": False,
            "model_refit": False,
            "policy_reselection": False,
            "test_evaluation": False,
            "metric_recalculation": False,
            "new_metric": False,
            "accepted_artifact_mutation": False,
        },
        "excluded_from_private_runtime_archive": [
            {
                "category": "TRACKED_PUBLIC_SOURCE",
                "reason": "Bound to the Git checkpoint and recorded separately; not duplicated as private runtime payload.",
            },
            {
                "category": "FAILED_OR_DIAGNOSTIC_CAMPAIGNS",
                "reason": "Not part of the accepted P6-R5 final dataset boundary.",
            },
            {
                "category": "P1_TO_P5_DEVELOPMENT_RUNTIME",
                "reason": "Historical method-development evidence remains hash-bound in tracked HANDOFFs; the final numerical chain is P6-R5/P6-R6.",
            },
            {
                "category": "P7_SELFTEST_OR_INTERFACE_FIXTURES",
                "reason": "Not accepted empirical evidence.",
            },
        ],
        "next_milestone": "P8-R2",
    }

    # The catalog loader is the semantic verification gate. Referencing the
    # count here makes that execution visible without copying its documents.
    _require(
        registry["p7_projection_catalog"]["sha256"]
        == sha256_file(root / P7_CATALOG_PATH)
        and len(catalog.artifacts_by_path) == 15,
        "P7 catalog identity drifted after loading.",
    )
    return registry


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_registry(path: Path, registry: Mapping[str, Any]) -> None:
    _require(not path.exists(), f"Registry output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(registry))


def _tar_info(name: str, size: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.size = size
    info.mode = 0o644
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    archive.addfile(_tar_info(name, len(payload)), io.BytesIO(payload))


def create_archive(
    repository_root: Path,
    registry_path: Path,
    archive_path: Path,
) -> dict[str, Any]:
    root = repository_root.resolve()
    _require(registry_path.is_file(), "Tracked registry is missing before archive creation.")
    _require(not archive_path.exists(), f"Private archive already exists: {archive_path}")
    registry_bytes = registry_path.read_bytes()
    registry = _read_json(registry_path)
    runtime = registry.get("runtime_artifacts")
    _require(isinstance(runtime, list), "Registry runtime artifacts are invalid.")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive_path.with_name(f".{archive_path.name}.tmp")
    _require(not temporary.exists(), f"Archive temporary path already exists: {temporary}")
    try:
        with temporary.open("xb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                with tarfile.open(
                    fileobj=compressed,
                    mode="w",
                    format=tarfile.PAX_FORMAT,
                ) as archive:
                    prefix = ARCHIVE_DIRECTORY_NAME
                    _add_bytes(archive, f"{prefix}/REGISTRY.json", registry_bytes)
                    _add_bytes(
                        archive,
                        f"{prefix}/README.md",
                        ARCHIVE_README.encode("utf-8"),
                    )
                    for item in runtime:
                        _require(isinstance(item, Mapping), "Invalid registry artifact.")
                        source = _safe_path(root, str(item["path"]))
                        _require(
                            sha256_file(source) == item["sha256"]
                            and source.stat().st_size == item["size_bytes"],
                            f"Artifact drifted before archive copy: {item['path']}",
                        )
                        payload = source.read_bytes()
                        _add_bytes(
                            archive,
                            f"{prefix}/{item['archive_path']}",
                            payload,
                        )
        temporary.replace(archive_path)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return verify_archive(repository_root=root, registry_path=registry_path, archive_path=archive_path)


def verify_archive(
    repository_root: Path,
    registry_path: Path,
    archive_path: Path,
) -> dict[str, Any]:
    del repository_root  # Verification uses only registry and archive bytes.
    registry_bytes = registry_path.read_bytes()
    registry = _read_json(registry_path)
    runtime = registry.get("runtime_artifacts")
    _require(isinstance(runtime, list), "Registry runtime artifacts are invalid.")
    expected: dict[str, tuple[str, int]] = {
        f"{ARCHIVE_DIRECTORY_NAME}/REGISTRY.json": (
            _sha256_bytes(registry_bytes),
            len(registry_bytes),
        ),
        f"{ARCHIVE_DIRECTORY_NAME}/README.md": (
            _sha256_bytes(ARCHIVE_README.encode("utf-8")),
            len(ARCHIVE_README.encode("utf-8")),
        ),
    }
    for item in runtime:
        _require(isinstance(item, Mapping), "Invalid registry artifact.")
        expected[f"{ARCHIVE_DIRECTORY_NAME}/{item['archive_path']}"] = (
            str(item["sha256"]),
            int(item["size_bytes"]),
        )

    observed: dict[str, tuple[str, int]] = {}
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            for member in archive.getmembers():
                _require(member.isfile(), f"Archive contains a non-file member: {member.name}")
                _require(
                    member.name in expected and member.name not in observed,
                    f"Archive contains an unexpected or duplicate member: {member.name}",
                )
                _require(
                    member.mode == 0o644
                    and member.uid == 0
                    and member.gid == 0
                    and member.mtime == 0,
                    f"Archive metadata drifted: {member.name}",
                )
                stream = archive.extractfile(member)
                _require(stream is not None, f"Cannot read archive member: {member.name}")
                digest = hashlib.sha256()
                size = 0
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                _require(
                    (digest.hexdigest(), size) == expected[member.name],
                    f"Archive member drifted: {member.name}",
                )
                observed[member.name] = (digest.hexdigest(), size)
    except (OSError, tarfile.TarError) as error:
        raise EvidenceArchiveError(f"Cannot verify private archive: {archive_path}") from error
    _require(set(observed) == set(expected), "Private archive member set is incomplete.")
    return {
        "archive_sha256": sha256_file(archive_path),
        "archive_size_bytes": archive_path.stat().st_size,
        "archive_member_count": len(observed),
        "runtime_artifact_count": len(runtime),
    }


def build_receipt(
    *,
    registry_path: Path,
    archive_path: Path,
    verification: Mapping[str, Any],
) -> dict[str, Any]:
    registry = _read_json(registry_path)
    return {
        "schema_version": 1,
        "receipt_id": RECEIPT_ID,
        "status": "VERIFIED",
        "archive_file_name": archive_path.name,
        "archive_sha256": verification["archive_sha256"],
        "archive_size_bytes": verification["archive_size_bytes"],
        "archive_member_count": verification["archive_member_count"],
        "runtime_artifact_count": verification["runtime_artifact_count"],
        "registry": {
            "path": DEFAULT_REGISTRY_PATH.as_posix(),
            "sha256": sha256_file(registry_path),
            "size_bytes": registry_path.stat().st_size,
            "registry_id": registry["registry_id"],
        },
        "source_checkpoint": registry["source_checkpoint"],
        "estimator_deserialized": False,
        "experiment_executed": False,
        "metric_recalculated": False,
        "next_milestone": "P8-R2",
    }


def write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    _require(not path.exists(), f"Archive receipt already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(receipt))


def _build_command(arguments: argparse.Namespace) -> None:
    root = arguments.repository_root.resolve()
    registry_path = (root / arguments.registry).resolve()
    receipt_path = (root / arguments.receipt).resolve()
    archive_path = arguments.archive.resolve()
    registry = build_registry(root)
    write_registry(registry_path, registry)
    verification = create_archive(root, registry_path, archive_path)
    write_receipt(
        receipt_path,
        build_receipt(
            registry_path=registry_path,
            archive_path=archive_path,
            verification=verification,
        ),
    )
    print(
        json.dumps(
            {
                **verification,
                "archive_path": str(archive_path),
                "registry_path": str(registry_path),
                "receipt_path": str(receipt_path),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _verify_command(arguments: argparse.Namespace) -> None:
    root = arguments.repository_root.resolve()
    registry_path = (root / arguments.registry).resolve()
    receipt_path = (root / arguments.receipt).resolve()
    archive_path = arguments.archive.resolve()
    tracked = _read_json(registry_path)
    _require(
        tracked
        == build_registry(
            root,
            source_checkpoint=tracked.get("source_checkpoint"),
        ),
        "Tracked registry no longer matches accepted bytes.",
    )
    verification = verify_archive(root, registry_path, archive_path)
    expected_receipt = build_receipt(
        registry_path=registry_path,
        archive_path=archive_path,
        verification=verification,
    )
    _require(_read_json(receipt_path) == expected_receipt, "Archive receipt drifted.")
    print(json.dumps(verification, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="P8-R1 final evidence archive gate")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--repository-root", type=Path, default=Path.cwd())
        subparser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
        subparser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
        subparser.add_argument("--archive", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "build":
        _build_command(arguments)
    else:
        _verify_command(arguments)


if __name__ == "__main__":
    main()
