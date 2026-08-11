from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from src.batch.plan import expand_batch_plan
from src.campaign.phase6_plan import (
    CLASS_ORDER,
    Phase6CampaignPlan,
    Phase6CampaignPlanError,
    Phase6Context,
    load_phase6_campaign_plan,
)
from src.dataset.contract_v3 import (
    DatasetRowV3ContractError,
    build_dataset_row_v3,
    validate_dataset_row_v3,
)
from src.dataset.explicit_splitter_v3 import (
    ExplicitSplitV3Error,
    PARTITION_NAMES,
    write_explicit_complete_context_split_v3,
)
from src.orchestration.phase6_experiment_runner import run_phase6_experiment
from src.planning.fault_taxonomy import EXPECTED_SIGNATURES, FEATURE_ORDER


CAMPAIGN_RESULT_SCHEMA_VERSION = 1
FINGERPRINT_MANIFEST_SCHEMA_VERSION = 1
FINGERPRINT_ALGORITHM = "normalized_text_path_bundle_sha256_v1"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_RUNTIME_PARTS = frozenset(
    {"diagnosis", "diagnoses", "prediction", "predictions", "evaluation", "metrics"}
)

CommandExecutor = Callable[[Sequence[str], Path], dict[str, Any]]
ExperimentExecutor = Callable[..., dict[str, Any]]
DatasetRowBuilder = Callable[[Path], dict[str, Any]]
ProgressReporter = Callable[[str], None]


class Phase6CampaignRunnerError(RuntimeError):
    """Raised when the frozen P6-R5 campaign cannot be accepted."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_campaign_run_id(campaign_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{campaign_id.lower()}-{timestamp}-{uuid4().hex}"


def resolve_path(path: Path, repository_root: Path) -> Path:
    return path.resolve() if path.is_absolute() else (repository_root / path).resolve()


def display_path(path: Path, repository_root: Path) -> str:
    try:
        return path.relative_to(repository_root).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise Phase6CampaignRunnerError(f"Required file does not exist: {path}")
    return sha256_bytes(path.read_bytes())


def normalized_bundle_sha256(
    paths: Sequence[Path], *, repository_root: Path
) -> str:
    root = repository_root.resolve()
    relative_paths: list[Path] = []
    for path in paths:
        resolved = resolve_path(path, root)
        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise Phase6CampaignRunnerError(
                "Fingerprint files must stay inside the repository root."
            ) from error
        if not resolved.is_file():
            raise Phase6CampaignRunnerError(
                f"Fingerprint file does not exist: {relative.as_posix()}"
            )
        relative_paths.append(relative)
    if len(set(relative_paths)) != len(relative_paths):
        raise Phase6CampaignRunnerError(
            "A fingerprint bundle cannot contain duplicate paths."
        )
    payload = bytearray()
    for relative in sorted(relative_paths):
        content = (root / relative).read_text(encoding="utf-8")
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        payload.extend(relative.as_posix().encode("utf-8"))
        payload.extend(b"\0")
        payload.extend(content.encode("utf-8"))
        payload.extend(b"\0")
    return sha256_bytes(bytes(payload))


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise Phase6CampaignRunnerError(f"Required JSON file does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise Phase6CampaignRunnerError(f"Invalid JSON in {path}: {error.msg}") from error
    if not isinstance(value, dict):
        raise Phase6CampaignRunnerError(f"Expected a JSON object in: {path}")
    return value


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def jsonl_payload(rows: Sequence[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def write_jsonl_exclusive(path: Path, rows: Sequence[dict[str, Any]]) -> str:
    if path.exists():
        raise Phase6CampaignRunnerError(f"Dataset already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = jsonl_payload(rows)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return sha256_bytes(payload.encode("utf-8"))


def run_command(command: Sequence[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            list(command), cwd=cwd, check=False, capture_output=True, text=True
        )
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except OSError as error:
        return_code = 127
        stdout = ""
        stderr = f"{type(error).__name__}: {error}"
    return {
        "command": list(command),
        "return_code": return_code,
        "stdout": stdout,
        "stderr": stderr,
        "timestamp_utc": utc_now(),
    }


def require_success(result: object, label: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise Phase6CampaignRunnerError(f"{label} must return an object.")
    return_code = result.get("return_code")
    if isinstance(return_code, bool) or not isinstance(return_code, int):
        raise Phase6CampaignRunnerError(f"{label} has no valid return_code.")
    if return_code != 0:
        stderr = result.get("stderr")
        detail = stderr.strip() if isinstance(stderr, str) and stderr.strip() else "no stderr"
        raise Phase6CampaignRunnerError(
            f"{label} failed with return code {return_code}: {detail}"
        )
    return result


def topology_name(topology_path: Path) -> str:
    try:
        document = yaml.safe_load(topology_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise Phase6CampaignRunnerError(
            f"Cannot read topology YAML: {topology_path}"
        ) from error
    name = document.get("name") if isinstance(document, dict) else None
    if not isinstance(name, str) or not name:
        raise Phase6CampaignRunnerError(f"Topology has no valid name: {topology_path}")
    return name


def containerlab_containers(
    *,
    repository_root: Path,
    command_executor: CommandExecutor,
    topology_path: Path | None = None,
) -> list[str]:
    result = require_success(
        command_executor(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            repository_root,
        ),
        "Docker laboratory inspection",
    )
    stdout = result.get("stdout")
    if not isinstance(stdout, str):
        raise Phase6CampaignRunnerError("Docker inspection stdout must be text.")
    names = [name for name in stdout.splitlines() if name.startswith("clab-")]
    if topology_path is None:
        return names
    prefix = f"clab-{topology_name(topology_path)}-"
    return [name for name in names if name.startswith(prefix)]


def _expected_fingerprint_files(context: Phase6Context) -> set[Path]:
    return {
        context.topology_file,
        context.baseline_validator,
        context.batch_plan_path,
        *(entry.scenario_path for entry in context.batch_plan.entries),
    }


def load_fingerprint_manifest(
    path: Path,
    *,
    campaign_plan: Phase6CampaignPlan,
    repository_root: Path,
) -> dict[str, dict[str, Any]]:
    document = read_json(path)
    if set(document) != {"schema_version", "campaign_id", "algorithm", "contexts"}:
        raise Phase6CampaignRunnerError("Fingerprint manifest keys drifted.")
    if document["schema_version"] != FINGERPRINT_MANIFEST_SCHEMA_VERSION:
        raise Phase6CampaignRunnerError("Fingerprint manifest version must be 1.")
    if document["campaign_id"] != campaign_plan.campaign_id:
        raise Phase6CampaignRunnerError("Fingerprint campaign_id mismatch.")
    if document["algorithm"] != FINGERPRINT_ALGORITHM:
        raise Phase6CampaignRunnerError("Unsupported fingerprint algorithm.")
    raw_contexts = document["contexts"]
    if not isinstance(raw_contexts, list) or len(raw_contexts) != 6:
        raise Phase6CampaignRunnerError("Six fingerprint contexts are required.")
    records: dict[str, dict[str, Any]] = {}
    for index, raw_record in enumerate(raw_contexts, start=1):
        if not isinstance(raw_record, dict) or set(raw_record) != {
            "group_slot",
            "files",
            "sha256",
        }:
            raise Phase6CampaignRunnerError(f"Fingerprint context {index} is invalid.")
        slot = raw_record["group_slot"]
        files = raw_record["files"]
        digest = raw_record["sha256"]
        if not isinstance(slot, str) or slot in records:
            raise Phase6CampaignRunnerError("Fingerprint slots must be unique strings.")
        if (
            not isinstance(files, list)
            or not files
            or any(not isinstance(item, str) or not item for item in files)
        ):
            raise Phase6CampaignRunnerError(f"{slot} fingerprint files are invalid.")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise Phase6CampaignRunnerError(f"{slot} fingerprint digest is invalid.")
        records[slot] = {"files": tuple(Path(item) for item in files), "sha256": digest}
    expected_slots = {context.group_slot for context in campaign_plan.contexts}
    if set(records) != expected_slots:
        raise Phase6CampaignRunnerError("Fingerprint context slots drifted.")
    for context in campaign_plan.contexts:
        record = records[context.group_slot]
        if set(record["files"]) != _expected_fingerprint_files(context):
            raise Phase6CampaignRunnerError(
                f"{context.group_slot} fingerprint bundle does not bind its "
                "topology, validator, batch plan, and six scenarios."
            )
        actual = normalized_bundle_sha256(
            record["files"], repository_root=repository_root
        )
        if actual != record["sha256"]:
            raise Phase6CampaignRunnerError(
                f"{context.group_slot} artifact fingerprint mismatch."
            )
        record["actual_sha256"] = actual
    return records


def validate_phase6_campaign_row(
    row: Mapping[str, Any],
    *,
    context: Phase6Context,
    expected_fault_type: str,
    row_reference: str,
) -> None:
    try:
        validate_dataset_row_v3(dict(row))
    except DatasetRowV3ContractError as error:
        raise Phase6CampaignRunnerError(f"{row_reference} is invalid: {error}") from error
    metadata = row["metadata"]
    expected_bindings = {
        "topology_id": context.topology_id,
        "split_group_id": context.split_group_id,
        "direction": context.direction,
        "source_node": context.source_node,
        "route_observer_node": context.route_observer_node,
        "transit_node": context.transit_node,
    }
    for field_name, expected in expected_bindings.items():
        if metadata.get(field_name) != expected:
            raise Phase6CampaignRunnerError(
                f"{row_reference} has invalid metadata.{field_name}."
            )
    if row["labels"]["fault_type"] != expected_fault_type:
        raise Phase6CampaignRunnerError(
            f"{row_reference} does not match its planned class."
        )
    if row["provenance"]["mask_id"] is not None:
        raise Phase6CampaignRunnerError(f"{row_reference} is unexpectedly masked.")
    quality = row["quality"]
    for field_name in (
        "experiment_completed",
        "collector_completed",
        "baseline_before_valid",
        "baseline_after_valid",
    ):
        if quality[field_name] is not True:
            raise Phase6CampaignRunnerError(
                f"{row_reference} fails quality.{field_name}."
            )
    if quality["collection_unavailable_count"] != 0:
        raise Phase6CampaignRunnerError(
            f"{row_reference} contains collection-unavailable evidence."
        )
    expected_signature = dict(
        zip(FEATURE_ORDER, EXPECTED_SIGNATURES[expected_fault_type], strict=True)
    )
    if row["features"] != expected_signature:
        raise Phase6CampaignRunnerError(
            f"{row_reference} does not match the frozen complete-evidence signature."
        )
    availability = row["provenance"]["feature_availability"]
    for feature_name, expected_value in expected_signature.items():
        expected_state = (
            "structurally_unavailable"
            if expected_value == "unavailable"
            else "observed"
        )
        if availability[feature_name] != expected_state:
            raise Phase6CampaignRunnerError(
                f"{row_reference} has invalid availability.{feature_name}."
            )


def _assert_no_forbidden_runtime_outputs(experiment_directory: Path) -> None:
    forbidden = [
        path
        for path in experiment_directory.rglob("*")
        if path.name.lower() in FORBIDDEN_RUNTIME_PARTS
    ]
    if forbidden:
        raise Phase6CampaignRunnerError(
            "P6-R5 created a forbidden diagnosis, prediction, evaluation, or metric output."
        )


def audit_merged_rows(
    *, campaign_plan: Phase6CampaignPlan, rows: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    if len(rows) != campaign_plan.expected_row_count:
        raise Phase6CampaignRunnerError("Merged dataset must contain exactly 72 rows.")
    contexts = {context.split_group_id: context for context in campaign_plan.contexts}
    sample_ids: set[str] = set()
    group_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()
    for index, row in enumerate(rows, start=1):
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or sample_id in sample_ids:
            raise Phase6CampaignRunnerError(
                f"Merged row {index} has a duplicate or invalid sample_id."
            )
        group_id = row["metadata"]["split_group_id"]
        fault_type = row["labels"]["fault_type"]
        if group_id not in contexts or fault_type not in CLASS_ORDER:
            raise Phase6CampaignRunnerError(
                f"Merged row {index} violates the frozen group/class universe."
            )
        validate_phase6_campaign_row(
            row,
            context=contexts[group_id],
            expected_fault_type=fault_type,
            row_reference=f"Merged row {index}",
        )
        sample_ids.add(sample_id)
        group_counts[group_id] += 1
        class_counts[fault_type] += 1
        pair_counts[(group_id, fault_type)] += 1
    if set(group_counts) != set(contexts) or any(
        count != 12 for count in group_counts.values()
    ):
        raise Phase6CampaignRunnerError("Every frozen context must contain 12 rows.")
    if any(
        pair_counts[(group_id, fault_type)] != 2
        for group_id in contexts
        for fault_type in CLASS_ORDER
    ):
        raise Phase6CampaignRunnerError(
            "Every context/fault_type pair must contain exactly two rows."
        )
    return {
        "row_count": len(rows),
        "sample_id_count": len(sample_ids),
        "group_count": len(group_counts),
        "rows_per_group": dict(sorted(group_counts.items())),
        "rows_per_class": {
            fault_type: class_counts[fault_type] for fault_type in CLASS_ORDER
        },
        "rows_per_group_and_class": {
            f"{group_id}|{fault_type}": pair_counts[(group_id, fault_type)]
            for group_id in sorted(contexts)
            for fault_type in CLASS_ORDER
        },
        "masked_row_count": 0,
        "collection_unavailable_row_count": 0,
    }


def _existing_completed_campaign(metadata_root: Path, campaign_id: str) -> Path | None:
    if not metadata_root.exists():
        return None
    for path in sorted(metadata_root.glob("*.phase6-campaign.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(document, dict)
            and document.get("campaign_id") == campaign_id
            and document.get("status") == "COMPLETED"
        ):
            return path
    return None


def _split_summary(split_directory: Path, merged_sha256: str) -> dict[str, Any]:
    manifest_path = split_directory / "split_manifest.json"
    manifest = read_json(manifest_path)
    source = manifest.get("source")
    if not isinstance(source, dict) or source.get("sha256") != merged_sha256:
        raise Phase6CampaignRunnerError("Split source hash mismatch.")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise Phase6CampaignRunnerError("Split outputs are invalid.")
    partitions: dict[str, Any] = {}
    for partition in PARTITION_NAMES:
        file_name = f"{partition}.jsonl"
        output = outputs.get(file_name)
        if not isinstance(output, dict):
            raise Phase6CampaignRunnerError(f"Split {file_name} metadata is invalid.")
        digest = sha256_file(split_directory / file_name)
        if output.get("sha256") != digest:
            raise Phase6CampaignRunnerError(f"Split {file_name} hash mismatch.")
        partitions[partition] = {
            **manifest["partitions"][partition],
            "sha256": digest,
        }
    return {
        "directory": str(split_directory),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "source_dataset_sha256": merged_sha256,
        "no_cross_partition_group": True,
        "test_partition_status": "SEALED_FOR_P6_R6_REPORT_ONLY",
        "partitions": partitions,
    }


def validate_completed_campaign_result(
    result: Mapping[str, Any], campaign_plan: Phase6CampaignPlan
) -> None:
    expected = {
        "schema_version": CAMPAIGN_RESULT_SCHEMA_VERSION,
        "campaign_id": campaign_plan.campaign_id,
        "status": "COMPLETED",
        "planned_context_count": 6,
        "completed_context_count": 6,
        "planned_experiment_count": 72,
        "completed_experiment_count": 72,
        "dataset_row_schema_version": 3,
        "dataset_row_count": 72,
        "diagnosis_count": 0,
        "prediction_count": 0,
        "metric_count": 0,
        "masked_row_count": 0,
        "test_partition_status": "SEALED_FOR_P6_R6_REPORT_ONLY",
    }
    for field_name, expected_value in expected.items():
        if result.get(field_name) != expected_value:
            raise Phase6CampaignRunnerError(
                f"Completed campaign result {field_name} must be {expected_value!r}."
            )
    contexts = result.get("contexts")
    if not isinstance(contexts, list) or len(contexts) != 6 or any(
        not isinstance(context, dict)
        or context.get("status") != "COMPLETED"
        or context.get("completed_experiment_count") != 12
        or context.get("dataset_row_count") != 12
        or context.get("cleanup_verified") is not True
        for context in contexts
    ):
        raise Phase6CampaignRunnerError("Completed campaign contexts are incomplete.")
    split = result.get("split")
    if not isinstance(split, dict) or split.get("test_partition_status") != (
        "SEALED_FOR_P6_R6_REPORT_ONLY"
    ):
        raise Phase6CampaignRunnerError("Completed campaign test split is not sealed.")


def run_phase6_campaign(
    plan_path: Path,
    fingerprint_manifest_path: Path,
    repository_root: Path,
    output_root: Path,
    processed_root: Path,
    metadata_root: Path,
    *,
    command_executor: CommandExecutor | None = None,
    experiment_executor: ExperimentExecutor | None = None,
    row_builder: DatasetRowBuilder | None = None,
    campaign_run_id: str | None = None,
    progress: ProgressReporter | None = None,
    enforce_single_completed_campaign: bool = True,
) -> dict[str, Any]:
    root = repository_root.resolve()
    resolved_plan = resolve_path(plan_path, root)
    resolved_fingerprints = resolve_path(fingerprint_manifest_path, root)
    resolved_output = resolve_path(output_root, root)
    resolved_processed = resolve_path(processed_root, root)
    resolved_metadata = resolve_path(metadata_root, root)
    campaign_plan = load_phase6_campaign_plan(resolved_plan, repository_root=root)
    fingerprints = load_fingerprint_manifest(
        resolved_fingerprints,
        campaign_plan=campaign_plan,
        repository_root=root,
    )
    existing = (
        _existing_completed_campaign(resolved_metadata, campaign_plan.campaign_id)
        if enforce_single_completed_campaign
        else None
    )
    if existing is not None:
        raise Phase6CampaignRunnerError(
            f"The one clean P6-R5 campaign is already completed: {existing}"
        )
    run_id = campaign_run_id or build_campaign_run_id(campaign_plan.campaign_id)
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise Phase6CampaignRunnerError("campaign_run_id contains invalid characters.")

    result_path = resolved_metadata / f"{run_id}.phase6-campaign.json"
    merged_dataset_path = resolved_processed / f"{run_id}.dataset-row-v3.jsonl"
    context_dataset_directory = resolved_processed / f"{run_id}-contexts"
    split_directory = resolved_processed / f"{run_id}-split"
    campaign_experiment_root = resolved_output / run_id
    for label, path in (
        ("campaign result", result_path),
        ("merged dataset", merged_dataset_path),
        ("context datasets", context_dataset_directory),
        ("split", split_directory),
        ("experiment root", campaign_experiment_root),
    ):
        if path.exists():
            raise Phase6CampaignRunnerError(f"{label} already exists: {path}")

    execute_command = command_executor or run_command
    execute_experiment = experiment_executor or run_phase6_experiment
    build_row = row_builder or build_dataset_row_v3

    active_before = containerlab_containers(
        repository_root=root, command_executor=execute_command
    )
    if active_before:
        raise Phase6CampaignRunnerError(
            "P6-R5 requires zero active containerlab containers: "
            + ", ".join(active_before)
        )

    result: dict[str, Any] = {
        "schema_version": CAMPAIGN_RESULT_SCHEMA_VERSION,
        "campaign_run_id": run_id,
        "campaign_id": campaign_plan.campaign_id,
        "plan_path": display_path(resolved_plan, root),
        "campaign_plan_sha256": sha256_file(resolved_plan),
        "fingerprint_manifest_path": display_path(resolved_fingerprints, root),
        "fingerprint_manifest_sha256": sha256_file(resolved_fingerprints),
        "failure_policy": "stop",
        "status": "RUNNING",
        "planned_context_count": 6,
        "completed_context_count": 0,
        "planned_experiment_count": 72,
        "completed_experiment_count": 0,
        "dataset_row_schema_version": 3,
        "dataset_row_count": 0,
        "diagnosis_count": 0,
        "prediction_count": 0,
        "metric_count": 0,
        "masked_row_count": 0,
        "test_partition_status": "NOT_CREATED",
        "started_at_utc": utc_now(),
        "completed_at_utc": None,
        "failed_context": None,
        "error": None,
        "merged_dataset": None,
        "split": None,
        "contexts": [],
    }
    write_json_atomic(result_path, result)
    all_rows: list[dict[str, Any]] = []

    def emit(message: str) -> None:
        if progress is not None:
            progress(message)

    try:
        for context_index, context in enumerate(campaign_plan.contexts, start=1):
            topology_path = root / context.topology_file
            validator_path = root / context.baseline_validator
            context_output_root = campaign_experiment_root / context.group_slot
            context_dataset_path = (
                context_dataset_directory / f"{context.group_slot}.jsonl"
            )
            context_result: dict[str, Any] = {
                "group_slot": context.group_slot,
                "topology_id": context.topology_id,
                "split_group_id": context.split_group_id,
                "artifact_bundle_sha256": fingerprints[context.group_slot][
                    "actual_sha256"
                ],
                "status": "RUNNING",
                "deploy_return_code": None,
                "initial_baseline_return_code": None,
                "completed_experiment_count": 0,
                "dataset_row_count": 0,
                "dataset_path": None,
                "dataset_sha256": None,
                "class_row_counts": {},
                "final_baseline_return_code": None,
                "destroy_return_code": None,
                "cleanup_verified": False,
                "error": None,
            }
            result["contexts"].append(context_result)
            result["failed_context"] = context.group_slot
            write_json_atomic(result_path, result)
            context_rows: list[dict[str, Any]] = []
            context_error: Exception | None = None
            deploy_attempted = False
            try:
                if containerlab_containers(
                    repository_root=root,
                    command_executor=execute_command,
                    topology_path=topology_path,
                ):
                    raise Phase6CampaignRunnerError(
                        f"{context.group_slot} laboratory already exists."
                    )
                emit(f"[{context_index}/6] {context.group_slot} deploy")
                deploy_attempted = True
                deploy = execute_command(
                    ["sudo", "containerlab", "deploy", "-t", str(topology_path)],
                    root,
                )
                context_result["deploy_return_code"] = deploy.get("return_code")
                require_success(deploy, f"{context.group_slot} deployment")
                initial = require_success(
                    execute_command(["bash", str(validator_path)], root),
                    f"{context.group_slot} initial baseline",
                )
                context_result["initial_baseline_return_code"] = initial["return_code"]
                planned = expand_batch_plan(context.batch_plan)
                for experiment_index, planned_experiment in enumerate(planned, start=1):
                    expected_fault_type = CLASS_ORDER[(experiment_index - 1) // 2]
                    emit(
                        f"[{context_index}/6] {context.group_slot} "
                        f"experiment {experiment_index}/12 {expected_fault_type}"
                    )
                    experiment_result = execute_experiment(
                        root / planned_experiment.scenario_path,
                        context_output_root,
                        validator_path,
                    )
                    if not isinstance(experiment_result, dict):
                        raise Phase6CampaignRunnerError(
                            f"{context.group_slot} experiment {experiment_index} "
                            "returned no result."
                        )
                    expected_result_values = {
                        "status": "COMPLETED",
                        "fault_type": expected_fault_type,
                        "topology_id": context.topology_id,
                        "split_group_id": context.split_group_id,
                        "evidence_schema_version": 3,
                        "baseline_valid_after": True,
                        "restoration_confirmed": True,
                        "diagnosis_created": False,
                        "prediction_created": False,
                        "metric_created": False,
                    }
                    for field_name, expected_value in expected_result_values.items():
                        if experiment_result.get(field_name) != expected_value:
                            raise Phase6CampaignRunnerError(
                                f"{context.group_slot} experiment {experiment_index} "
                                f"has invalid {field_name}."
                            )
                    directory_value = experiment_result.get("experiment_directory")
                    if not isinstance(directory_value, str) or not directory_value:
                        raise Phase6CampaignRunnerError(
                            f"{context.group_slot} experiment {experiment_index} "
                            "has no artifact directory."
                        )
                    experiment_directory = Path(directory_value).resolve()
                    try:
                        experiment_directory.relative_to(context_output_root.resolve())
                    except ValueError as error:
                        raise Phase6CampaignRunnerError(
                            "Experiment directory escaped its campaign context root."
                        ) from error
                    _assert_no_forbidden_runtime_outputs(experiment_directory)
                    row = build_row(experiment_directory)
                    validate_phase6_campaign_row(
                        row,
                        context=context,
                        expected_fault_type=expected_fault_type,
                        row_reference=(
                            f"{context.group_slot} row {experiment_index}"
                        ),
                    )
                    if row["metadata"]["scenario_id"] != experiment_result.get(
                        "scenario_id"
                    ):
                        raise Phase6CampaignRunnerError(
                            f"{context.group_slot} row {experiment_index} "
                            "scenario_id mismatch."
                        )
                    write_json_atomic(
                        experiment_directory / "dataset_row_v3.json", row
                    )
                    context_rows.append(row)
                    context_result["completed_experiment_count"] = len(context_rows)
                    context_result["dataset_row_count"] = len(context_rows)
                    result["completed_experiment_count"] = len(all_rows) + len(
                        context_rows
                    )
                    result["dataset_row_count"] = result[
                        "completed_experiment_count"
                    ]
                    write_json_atomic(result_path, result)
                expected_label_sequence = tuple(
                    fault_type for fault_type in CLASS_ORDER for _ in range(2)
                )
                if tuple(
                    row["labels"]["fault_type"] for row in context_rows
                ) != expected_label_sequence:
                    raise Phase6CampaignRunnerError(
                        f"{context.group_slot} class sequence drifted."
                    )
                final = require_success(
                    execute_command(["bash", str(validator_path)], root),
                    f"{context.group_slot} final baseline",
                )
                context_result["final_baseline_return_code"] = final["return_code"]
            except Exception as error:
                context_error = error
            finally:
                if deploy_attempted:
                    emit(f"[{context_index}/6] {context.group_slot} destroy")
                    destroy = execute_command(
                        [
                            "sudo",
                            "containerlab",
                            "destroy",
                            "-t",
                            str(topology_path),
                            "--cleanup",
                        ],
                        root,
                    )
                    context_result["destroy_return_code"] = destroy.get("return_code")
                    if destroy.get("return_code") != 0 and context_error is None:
                        context_error = Phase6CampaignRunnerError(
                            f"{context.group_slot} destroy failed."
                        )
                try:
                    active_after = containerlab_containers(
                        repository_root=root,
                        command_executor=execute_command,
                        topology_path=topology_path,
                    )
                    if active_after:
                        raise Phase6CampaignRunnerError(
                            f"{context.group_slot} cleanup left containers: "
                            + ", ".join(active_after)
                        )
                    context_result["cleanup_verified"] = True
                except Exception as cleanup_error:
                    if context_error is None:
                        context_error = cleanup_error
            if context_error is not None:
                context_result["status"] = "FAILED"
                context_result["error"] = {
                    "type": type(context_error).__name__,
                    "message": str(context_error),
                }
                write_json_atomic(result_path, result)
                raise context_error
            context_digest = write_jsonl_exclusive(context_dataset_path, context_rows)
            context_counts = Counter(
                row["labels"]["fault_type"] for row in context_rows
            )
            context_result.update(
                {
                    "status": "COMPLETED",
                    "dataset_path": str(context_dataset_path),
                    "dataset_sha256": context_digest,
                    "class_row_counts": {
                        fault_type: context_counts[fault_type]
                        for fault_type in CLASS_ORDER
                    },
                }
            )
            all_rows.extend(context_rows)
            result["completed_context_count"] = context_index
            result["completed_experiment_count"] = len(all_rows)
            result["dataset_row_count"] = len(all_rows)
            result["failed_context"] = None
            write_json_atomic(result_path, result)

        emit("[merge] audit 72 Dataset Row v3 records")
        quality_summary = audit_merged_rows(campaign_plan=campaign_plan, rows=all_rows)
        merged_sha256 = write_jsonl_exclusive(merged_dataset_path, all_rows)
        if sha256_file(merged_dataset_path) != merged_sha256:
            raise Phase6CampaignRunnerError("Merged Dataset Row v3 hash mismatch.")
        emit("[split] explicit 36/12/24 complete-context allocation")
        write_explicit_complete_context_split_v3(
            merged_dataset_path,
            split_directory,
            allocation=campaign_plan.split_allocation,
            expected_fault_types=campaign_plan.expected_fault_types,
            repetitions_per_class_context=(
                campaign_plan.repetitions_per_class_context
            ),
            expected_rows=campaign_plan.split_expected_rows,
        )
        split_summary = _split_summary(split_directory, merged_sha256)
        result["merged_dataset"] = {
            "path": str(merged_dataset_path),
            "sha256": merged_sha256,
            "row_count": len(all_rows),
            "quality": quality_summary,
        }
        result["split"] = split_summary
        result["status"] = "COMPLETED"
        result["completed_at_utc"] = utc_now()
        result["failed_context"] = None
        result["error"] = None
        result["test_partition_status"] = "SEALED_FOR_P6_R6_REPORT_ONLY"
        validate_completed_campaign_result(result, campaign_plan)
        write_json_atomic(result_path, result)
        emit("[complete] P6-R5 campaign 72/72 accepted; test sealed")
        return result
    except Exception as error:
        result["status"] = "FAILED"
        result["completed_at_utc"] = utc_now()
        result["error"] = {"type": type(error).__name__, "message": str(error)}
        write_json_atomic(result_path, result)
        raise Phase6CampaignRunnerError(
            f"Campaign {run_id} failed. Artifacts: {result_path}. Cause: {error}"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the one clean P6-R5 Evidence v3 campaign and write the "
            "frozen 36/12/24 Dataset Row v3 split without evaluation."
        )
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("plans/campaigns/P6_EXTENDED_6CLASS_6CTX_V1.yml"),
    )
    parser.add_argument(
        "--fingerprints",
        type=Path,
        default=Path(
            "plans/campaigns/P6_EXTENDED_6CLASS_6CTX_V1.fingerprints.json"
        ),
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--output-root", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--processed-root", type=Path, default=Path("data/processed")
    )
    parser.add_argument("--metadata-root", type=Path, default=Path("data/metadata"))
    parser.add_argument("--campaign-run-id")
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        result = run_phase6_campaign(
            plan_path=arguments.plan,
            fingerprint_manifest_path=arguments.fingerprints,
            repository_root=arguments.repository_root,
            output_root=arguments.output_root,
            processed_root=arguments.processed_root,
            metadata_root=arguments.metadata_root,
            campaign_run_id=arguments.campaign_run_id,
            progress=lambda message: print(message, flush=True),
        )
    except (
        Phase6CampaignPlanError,
        Phase6CampaignRunnerError,
        ExplicitSplitV3Error,
        OSError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
