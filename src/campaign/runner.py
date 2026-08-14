from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from src.runtime.subprocesses import run_capture

from src.batch.plan import expand_batch_plan
from src.batch.runner import run_batch
from src.campaign.plan import (
    CampaignContext,
    CampaignPlanError,
    DatasetCampaignPlan,
    load_campaign_plan,
)
from src.dataset.contract import (
    DatasetContractError,
    build_dataset_row,
    validate_dataset_row_v2,
)
from src.dataset.splitter import (
    DatasetSplitError,
    PARTITION_NAMES,
    read_dataset_jsonl,
    write_group_aware_split,
)


CAMPAIGN_RESULT_SCHEMA_VERSION = 1
FINGERPRINT_MANIFEST_SCHEMA_VERSION = 1
FINGERPRINT_ALGORITHM = (
    "normalized_text_path_bundle_sha256_v1"
)

RUN_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

CAMPAIGN_UNAVAILABLE_FEATURES_BY_FAULT_TYPE = {
    "no_fault": frozenset(),
    "missing_static_route": frozenset({
        "route_next_hop_reachable_from_observer",
    }),
    "wrong_next_hop": frozenset(),
}

CommandExecutor = Callable[
    [Sequence[str], Path],
    dict[str, Any],
]
BatchExecutor = Callable[..., dict[str, Any]]
DatasetRowBuilder = Callable[[Path], dict[str, Any]]
ProgressReporter = Callable[[str], None]


class CampaignRunnerError(RuntimeError):
    """Raised when a campaign cannot be accepted safely."""


def validate_campaign_row_quality(
    row: Mapping[str, Any],
    *,
    row_reference: str,
) -> None:
    quality = row["quality"]
    fault_type = row["labels"]["fault_type"]

    for field_name in (
        "experiment_completed",
        "collector_completed",
        "baseline_before_valid",
        "baseline_after_valid",
    ):
        if quality[field_name] is not True:
            raise CampaignRunnerError(
                f"{row_reference} fails quality.{field_name}."
            )

    expected_unavailable = (
        CAMPAIGN_UNAVAILABLE_FEATURES_BY_FAULT_TYPE.get(
            fault_type
        )
    )
    if expected_unavailable is None:
        raise CampaignRunnerError(
            f"{row_reference} has no unavailable-feature "
            f"policy for fault_type {fault_type!r}."
        )

    observed_unavailable = frozenset(
        feature_name
        for feature_name, value
        in row["features"].items()
        if value == "unavailable"
    )
    if observed_unavailable != expected_unavailable:
        raise CampaignRunnerError(
            f"{row_reference} has invalid unavailable "
            "features: expected "
            f"{sorted(expected_unavailable)!r}, observed "
            f"{sorted(observed_unavailable)!r}."
        )

    if quality["unavailable_feature_count"] != len(
        expected_unavailable
    ):
        raise CampaignRunnerError(
            f"{row_reference} fails "
            "quality.unavailable_feature_count."
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_campaign_run_id(campaign_id: str) -> str:
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S%fZ")

    return (
        f"{campaign_id.lower()}-"
        f"{timestamp}-{uuid4().hex}"
    )


def resolve_path(
    path: Path,
    repository_root: Path,
) -> Path:
    if path.is_absolute():
        return path.resolve()

    return (repository_root / path).resolve()


def display_path(
    path: Path,
    repository_root: Path,
) -> str:
    try:
        return path.relative_to(
            repository_root
        ).as_posix()
    except ValueError:
        return str(path)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise CampaignRunnerError(
            f"Required file does not exist: {path}"
        )

    return sha256_bytes(path.read_bytes())


def normalized_bundle_sha256(
    paths: Sequence[Path],
    *,
    repository_root: Path,
) -> str:
    root = repository_root.resolve()
    normalized_paths: list[Path] = []

    for path in paths:
        resolved = resolve_path(path, root)

        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise CampaignRunnerError(
                "Fingerprint files must stay inside "
                "the repository root."
            ) from error

        if not resolved.is_file():
            raise CampaignRunnerError(
                "Fingerprint file does not exist: "
                f"{relative.as_posix()}"
            )

        normalized_paths.append(relative)

    if len(set(normalized_paths)) != len(
        normalized_paths
    ):
        raise CampaignRunnerError(
            "A fingerprint bundle cannot contain "
            "duplicate file paths."
        )

    payload = bytearray()

    for relative in sorted(normalized_paths):
        content = (root / relative).read_text(
            encoding="utf-8"
        )
        content = content.replace(
            "\r\n", "\n"
        ).replace("\r", "\n")

        payload.extend(
            relative.as_posix().encode("utf-8")
        )
        payload.extend(b"\0")
        payload.extend(content.encode("utf-8"))
        payload.extend(b"\0")

    return sha256_bytes(bytes(payload))


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CampaignRunnerError(
            f"Required JSON file does not exist: {path}"
        )

    try:
        value = json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise CampaignRunnerError(
            f"Invalid JSON file: {path}: {error.msg}"
        ) from error

    if not isinstance(value, dict):
        raise CampaignRunnerError(
            f"Expected a JSON object in: {path}"
        )

    return value


def write_json_atomic(
    path: Path,
    value: object,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    temporary_path = path.with_name(
        f".{path.name}.{uuid4().hex}.tmp"
    )

    try:
        temporary_path.write_text(
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def jsonl_payload(
    rows: Sequence[dict[str, Any]],
) -> str:
    return "".join(
        json.dumps(
            row,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for row in rows
    )


def write_jsonl_atomic(
    path: Path,
    rows: Sequence[dict[str, Any]],
) -> str:
    if path.exists():
        raise CampaignRunnerError(
            f"Merged dataset already exists: {path}"
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    payload = jsonl_payload(rows)
    temporary_path = path.with_name(
        f".{path.name}.{uuid4().hex}.tmp"
    )

    try:
        temporary_path.write_text(
            payload,
            encoding="utf-8",
        )
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    return sha256_bytes(payload.encode("utf-8"))


def run_command(
    command: Sequence[str],
    cwd: Path,
) -> dict[str, Any]:
    completed = run_capture(
        list(command),
        cwd=cwd,
        timeout_seconds=180.0,
    )

    return {
        "command": list(command),
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timestamp_utc": utc_now(),
    }


def require_success(
    result: object,
    label: str,
) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise CampaignRunnerError(
            f"{label} command must return a mapping."
        )

    return_code = result.get("return_code")
    if (
        isinstance(return_code, bool)
        or not isinstance(return_code, int)
    ):
        raise CampaignRunnerError(
            f"{label} command has no valid return_code."
        )

    if return_code != 0:
        stderr = result.get("stderr")
        detail = (
            stderr.strip()
            if isinstance(stderr, str)
            and stderr.strip()
            else "no stderr"
        )
        raise CampaignRunnerError(
            f"{label} failed with return code "
            f"{return_code}: {detail}"
        )

    return result


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    missing = expected - actual
    unexpected = actual - expected

    if missing or unexpected:
        raise CampaignRunnerError(
            f"{label} keys do not match the "
            f"contract: missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}."
        )


def load_fingerprint_manifest(
    path: Path,
    *,
    campaign_plan: DatasetCampaignPlan,
    repository_root: Path,
) -> dict[str, dict[str, Any]]:
    document = read_json(path)
    _require_exact_keys(
        document,
        {
            "schema_version",
            "campaign_id",
            "algorithm",
            "contexts",
        },
        "Fingerprint manifest",
    )

    if (
        document["schema_version"]
        != FINGERPRINT_MANIFEST_SCHEMA_VERSION
    ):
        raise CampaignRunnerError(
            "Fingerprint manifest schema_version "
            "must be 1."
        )

    if document["campaign_id"] != (
        campaign_plan.campaign_id
    ):
        raise CampaignRunnerError(
            "Fingerprint manifest campaign_id does "
            "not match the campaign plan."
        )

    if document["algorithm"] != FINGERPRINT_ALGORITHM:
        raise CampaignRunnerError(
            "Unsupported fingerprint algorithm."
        )

    raw_contexts = document["contexts"]
    if not isinstance(raw_contexts, list):
        raise CampaignRunnerError(
            "Fingerprint contexts must be a list."
        )

    records: dict[str, dict[str, Any]] = {}

    for index, raw_record in enumerate(raw_contexts):
        label = f"Fingerprint context {index + 1}"
        if not isinstance(raw_record, dict):
            raise CampaignRunnerError(
                f"{label} must be a mapping."
            )

        _require_exact_keys(
            raw_record,
            {"group_slot", "files", "sha256"},
            label,
        )
        group_slot = raw_record["group_slot"]
        files = raw_record["files"]
        expected_sha256 = raw_record["sha256"]

        if (
            not isinstance(group_slot, str)
            or not group_slot
        ):
            raise CampaignRunnerError(
                f"{label}.group_slot is invalid."
            )

        if group_slot in records:
            raise CampaignRunnerError(
                "Fingerprint group_slot values must "
                "be unique."
            )

        if (
            not isinstance(files, list)
            or not files
            or any(
                not isinstance(item, str)
                or not item
                for item in files
            )
        ):
            raise CampaignRunnerError(
                f"{label}.files is invalid."
            )

        if (
            not isinstance(expected_sha256, str)
            or not SHA256_PATTERN.fullmatch(
                expected_sha256
            )
        ):
            raise CampaignRunnerError(
                f"{label}.sha256 is invalid."
            )

        records[group_slot] = {
            "files": tuple(Path(item) for item in files),
            "sha256": expected_sha256,
        }

    expected_slots = {
        context.group_slot
        for context in campaign_plan.contexts
    }
    if set(records) != expected_slots:
        raise CampaignRunnerError(
            "Fingerprint context slots do not match "
            "the campaign plan."
        )

    root = repository_root.resolve()

    for context in campaign_plan.contexts:
        record = records[context.group_slot]
        expected_files = {
            context.topology_file,
            context.baseline_validator,
            *(
                entry.scenario_path
                for entry
                in context.batch_plan.entries
            ),
        }
        actual_files = set(record["files"])

        if actual_files != expected_files:
            raise CampaignRunnerError(
                f"{context.group_slot} fingerprint "
                "files do not match its topology, "
                "validator, and scenarios."
            )

        actual_sha256 = normalized_bundle_sha256(
            record["files"],
            repository_root=root,
        )
        if actual_sha256 != record["sha256"]:
            raise CampaignRunnerError(
                f"{context.group_slot} artifact "
                "fingerprint mismatch."
            )

        record["actual_sha256"] = actual_sha256

    return records


def topology_name(
    topology_path: Path,
) -> str:
    try:
        document = yaml.safe_load(
            topology_path.read_text(
                encoding="utf-8"
            )
        )
    except yaml.YAMLError as error:
        raise CampaignRunnerError(
            f"Invalid topology YAML: {topology_path}"
        ) from error

    name = (
        document.get("name")
        if isinstance(document, dict)
        else None
    )
    if not isinstance(name, str) or not name:
        raise CampaignRunnerError(
            f"Topology has no valid name: {topology_path}"
        )

    return name


def active_lab_containers(
    topology_path: Path,
    *,
    repository_root: Path,
    command_executor: CommandExecutor,
) -> list[str]:
    result = require_success(
        command_executor(
            [
                "docker",
                "ps",
                "-a",
                "--format",
                "{{.Names}}",
            ],
            repository_root,
        ),
        "Docker laboratory inspection",
    )
    stdout = result.get("stdout", "")
    if not isinstance(stdout, str):
        raise CampaignRunnerError(
            "Docker inspection stdout must be text."
        )

    prefix = f"clab-{topology_name(topology_path)}-"
    return [
        name
        for name in stdout.splitlines()
        if name.startswith(prefix)
    ]


def _expected_label_sequence(
    campaign_plan: DatasetCampaignPlan,
) -> tuple[str, ...]:
    return tuple(
        fault_type
        for fault_type
        in campaign_plan.expected_fault_types
        for _ in range(
            campaign_plan.
            repetitions_per_class_context
        )
    )


def audit_context_output(
    *,
    campaign_plan: DatasetCampaignPlan,
    context: CampaignContext,
    batch_result: dict[str, Any],
    row_builder: DatasetRowBuilder,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    planned = expand_batch_plan(
        context.batch_plan
    )
    expected_count = len(planned)

    if batch_result.get("status") != "COMPLETED":
        raise CampaignRunnerError(
            f"{context.group_slot} batch is not COMPLETED."
        )

    expected_batch_values = {
        "batch_id": context.batch_plan.batch_id,
        "planned_experiment_count": expected_count,
        "completed_experiment_count": expected_count,
        "dataset_row_count": expected_count,
        "dataset_row_schema_version": (
            campaign_plan.dataset_row_schema_version
        ),
    }
    for key, expected in expected_batch_values.items():
        if batch_result.get(key) != expected:
            raise CampaignRunnerError(
                f"{context.group_slot} batch {key} "
                f"must be {expected!r}."
            )

    dataset_value = batch_result.get("dataset_path")
    experiments = batch_result.get("experiments")
    if (
        not isinstance(dataset_value, str)
        or not dataset_value
    ):
        raise CampaignRunnerError(
            f"{context.group_slot} has no dataset_path."
        )

    if (
        not isinstance(experiments, list)
        or len(experiments) != expected_count
    ):
        raise CampaignRunnerError(
            f"{context.group_slot} batch experiment "
            "records are incomplete."
        )

    dataset_path = Path(dataset_value)
    try:
        rows = read_dataset_jsonl(dataset_path)
    except DatasetSplitError as error:
        raise CampaignRunnerError(
            f"{context.group_slot} dataset is invalid: "
            f"{error}"
        ) from error

    if len(rows) != expected_count:
        raise CampaignRunnerError(
            f"{context.group_slot} dataset must contain "
            f"{expected_count} rows."
        )

    expected_labels = _expected_label_sequence(
        campaign_plan
    )
    observed_labels: list[str] = []
    sample_ids: set[str] = set()
    experiment_directories: set[Path] = set()
    rule_records: list[dict[str, Any]] = []

    for index, (
        planned_experiment,
        experiment_record,
        row,
    ) in enumerate(
        zip(planned, experiments, rows, strict=True),
        start=1,
    ):
        if not isinstance(experiment_record, dict):
            raise CampaignRunnerError(
                f"{context.group_slot} experiment "
                f"record {index} is invalid."
            )

        expected_record_values = {
            "sequence_number": index,
            "entry_id": planned_experiment.entry_id,
            "scenario_path": (
                planned_experiment.
                scenario_path.as_posix()
            ),
            "repetition_index": (
                planned_experiment.repetition_index
            ),
            "status": "COMPLETED",
        }
        for key, expected in (
            expected_record_values.items()
        ):
            if experiment_record.get(key) != expected:
                raise CampaignRunnerError(
                    f"{context.group_slot} experiment "
                    f"{index} has invalid {key}."
                )

        try:
            validate_dataset_row_v2(row)
        except DatasetContractError as error:
            raise CampaignRunnerError(
                f"{context.group_slot} row {index} "
                f"is invalid: {error}"
            ) from error

        sample_id = row["sample_id"]
        metadata = row["metadata"]
        label = row["labels"]["fault_type"]

        if sample_id in sample_ids:
            raise CampaignRunnerError(
                f"Duplicate sample_id in "
                f"{context.group_slot}: {sample_id}"
            )
        sample_ids.add(sample_id)

        if experiment_record.get("sample_id") != sample_id:
            raise CampaignRunnerError(
                f"{context.group_slot} row {index} "
                "does not match its batch sample_id."
            )

        if experiment_record.get("experiment_id") != (
            sample_id
        ):
            raise CampaignRunnerError(
                f"{context.group_slot} row {index} "
                "does not match its experiment_id."
            )

        expected_binding = {
            "topology_id": context.topology_id,
            "direction": context.direction,
            "route_observer_node": (
                context.route_observer_node
            ),
            "transit_node": context.transit_node,
            "split_group_id": context.split_group_id,
        }
        for key, expected in expected_binding.items():
            if metadata.get(key) != expected:
                raise CampaignRunnerError(
                    f"{context.group_slot} row {index} "
                    f"has invalid metadata.{key}."
                )

        if metadata.get("experiment_id") != sample_id:
            raise CampaignRunnerError(
                f"{context.group_slot} row {index} "
                "metadata experiment_id mismatch."
            )

        validate_campaign_row_quality(
            row,
            row_reference=(
                f"{context.group_slot} row {index}"
            ),
        )

        directory_value = experiment_record.get(
            "experiment_directory"
        )
        if (
            not isinstance(directory_value, str)
            or not directory_value
        ):
            raise CampaignRunnerError(
                f"{context.group_slot} experiment "
                f"{index} has no directory."
            )

        experiment_directory = Path(
            directory_value
        ).resolve()
        if experiment_directory in experiment_directories:
            raise CampaignRunnerError(
                "Duplicate experiment directory in "
                f"{context.group_slot}."
            )
        experiment_directories.add(
            experiment_directory
        )

        rebuilt_row = row_builder(
            experiment_directory
        )
        if rebuilt_row != row:
            raise CampaignRunnerError(
                f"{context.group_slot} row {index} "
                "does not match its source artifacts."
            )

        evaluation_path = (
            experiment_directory
            / "evaluation"
            / "rule_based.json"
        )
        evaluation = read_json(evaluation_path)
        metrics = evaluation.get("metrics")
        if not isinstance(metrics, dict):
            raise CampaignRunnerError(
                f"{context.group_slot} experiment "
                f"{index} has no evaluation metrics."
            )

        exact_match = metrics.get("exact_match")
        affected_prefix_correct = metrics.get(
            "affected_prefix_correct"
        )
        if exact_match is not True:
            raise CampaignRunnerError(
                f"{context.group_slot} experiment "
                f"{index} is not an exact rule match."
            )
        if affected_prefix_correct is not True:
            raise CampaignRunnerError(
                f"{context.group_slot} experiment "
                f"{index} fails affected-prefix audit."
            )

        observed_labels.append(label)
        rule_records.append({
            "sequence_number": index,
            "sample_id": sample_id,
            "split_group_id": context.split_group_id,
            "fault_type": label,
            "evaluation_path": str(evaluation_path),
            "exact_match": True,
            "affected_prefix_correct": True,
        })

    if tuple(observed_labels) != expected_labels:
        raise CampaignRunnerError(
            f"{context.group_slot} row class order "
            "does not match the campaign plan."
        )

    class_counts = Counter(observed_labels)
    expected_class_counts = {
        fault_type: (
            campaign_plan.
            repetitions_per_class_context
        )
        for fault_type
        in campaign_plan.expected_fault_types
    }
    if dict(class_counts) != expected_class_counts:
        raise CampaignRunnerError(
            f"{context.group_slot} class counts "
            "do not match the campaign plan."
        )

    return (
        rows,
        rule_records,
        {
            "dataset_path": str(dataset_path),
            "dataset_sha256": sha256_file(dataset_path),
            "dataset_row_count": len(rows),
            "artifact_revalidation_count": len(rows),
            "rule_exact_match_count": len(rule_records),
            "affected_prefix_correct_count": len(
                rule_records
            ),
            "class_row_counts": dict(
                sorted(class_counts.items())
            ),
        },
    )


def audit_merged_rows(
    *,
    campaign_plan: DatasetCampaignPlan,
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    if len(rows) != campaign_plan.expected_row_count:
        raise CampaignRunnerError(
            "Merged dataset row count does not "
            "match the campaign plan."
        )

    contexts = {
        context.split_group_id: context
        for context in campaign_plan.contexts
    }
    sample_ids: set[str] = set()
    experiment_ids: set[str] = set()
    group_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()

    for index, row in enumerate(rows, start=1):
        try:
            validate_dataset_row_v2(row)
        except DatasetContractError as error:
            raise CampaignRunnerError(
                f"Merged row {index} is invalid: {error}"
            ) from error

        sample_id = row["sample_id"]
        experiment_id = row["metadata"][
            "experiment_id"
        ]
        group_id = row["metadata"][
            "split_group_id"
        ]
        fault_type = row["labels"]["fault_type"]

        if sample_id in sample_ids:
            raise CampaignRunnerError(
                f"Duplicate merged sample_id: {sample_id}"
            )
        if experiment_id in experiment_ids:
            raise CampaignRunnerError(
                "Duplicate merged experiment_id: "
                f"{experiment_id}"
            )
        if sample_id != experiment_id:
            raise CampaignRunnerError(
                f"Merged row {index} sample and "
                "experiment identifiers differ."
            )
        if group_id not in contexts:
            raise CampaignRunnerError(
                f"Merged row {index} has an "
                "unexpected split_group_id."
            )
        if fault_type not in (
            campaign_plan.expected_fault_types
        ):
            raise CampaignRunnerError(
                f"Merged row {index} has an "
                "unexpected fault_type."
            )

        context = contexts[group_id]
        metadata = row["metadata"]
        binding = {
            "topology_id": context.topology_id,
            "direction": context.direction,
            "route_observer_node": (
                context.route_observer_node
            ),
            "transit_node": context.transit_node,
        }
        if any(
            metadata.get(key) != expected
            for key, expected in binding.items()
        ):
            raise CampaignRunnerError(
                f"Merged row {index} violates its "
                "frozen observation binding."
            )

        validate_campaign_row_quality(
            row,
            row_reference=f"Merged row {index}",
        )

        sample_ids.add(sample_id)
        experiment_ids.add(experiment_id)
        group_counts[group_id] += 1
        class_counts[fault_type] += 1
        pair_counts[(group_id, fault_type)] += 1

    expected_group_count = (
        len(campaign_plan.expected_fault_types)
        * campaign_plan.repetitions_per_class_context
    )
    if set(group_counts) != set(contexts):
        raise CampaignRunnerError(
            "Merged dataset does not contain the "
            "five frozen context groups."
        )
    if any(
        count != expected_group_count
        for count in group_counts.values()
    ):
        raise CampaignRunnerError(
            "Every merged context must contain six rows."
        )
    if any(
        pair_counts[(group_id, fault_type)]
        != campaign_plan.
        repetitions_per_class_context
        for group_id in contexts
        for fault_type
        in campaign_plan.expected_fault_types
    ):
        raise CampaignRunnerError(
            "Every context/fault_type pair must "
            "contain two rows."
        )

    return {
        "row_count": len(rows),
        "sample_id_count": len(sample_ids),
        "experiment_id_count": len(experiment_ids),
        "group_count": len(group_counts),
        "rows_per_group": dict(
            sorted(group_counts.items())
        ),
        "rows_per_class": dict(
            sorted(class_counts.items())
        ),
        "rows_per_group_and_class": {
            f"{group_id}|{fault_type}": (
                pair_counts[(group_id, fault_type)]
            )
            for group_id in sorted(contexts)
            for fault_type
            in campaign_plan.expected_fault_types
        },
        "unavailable_feature_count": sum(
            row["quality"]["unavailable_feature_count"]
            for row in rows
        ),
        "unavailable_feature_counts_by_fault_type": {
            fault_type: sum(
                row["quality"][
                    "unavailable_feature_count"
                ]
                for row in rows
                if row["labels"]["fault_type"]
                == fault_type
            )
            for fault_type
            in campaign_plan.expected_fault_types
        },
        "expected_unavailable_features_by_fault_type": {
            fault_type: sorted(
                CAMPAIGN_UNAVAILABLE_FEATURES_BY_FAULT_TYPE[
                    fault_type
                ]
            )
            for fault_type
            in campaign_plan.expected_fault_types
        },
    }


def audit_split_output(
    *,
    campaign_plan: DatasetCampaignPlan,
    merged_dataset_sha256: str,
    split_directory: Path,
) -> dict[str, Any]:
    manifest_path = (
        split_directory / "split_manifest.json"
    )
    manifest = read_json(manifest_path)

    expected_scalars = {
        "schema_version": 2,
        "algorithm": campaign_plan.split.algorithm,
        "source_dataset_schema_version": (
            campaign_plan.dataset_row_schema_version
        ),
        "seed": campaign_plan.split.seed,
        "source_row_count": (
            campaign_plan.expected_row_count
        ),
        "source_group_count": len(
            campaign_plan.contexts
        ),
        "class_count": len(
            campaign_plan.expected_fault_types
        ),
    }
    for key, expected in expected_scalars.items():
        if manifest.get(key) != expected:
            raise CampaignRunnerError(
                f"Split manifest {key} must be "
                f"{expected!r}."
            )

    if manifest.get("ratios") != (
        campaign_plan.split.ratios
    ):
        raise CampaignRunnerError(
            "Split ratios do not match the frozen plan."
        )

    if manifest.get("required_fault_types") != sorted(
        campaign_plan.expected_fault_types
    ):
        raise CampaignRunnerError(
            "Split required_fault_types do not "
            "match the campaign plan."
        )

    source = manifest.get("source")
    if (
        not isinstance(source, dict)
        or source.get("sha256")
        != merged_dataset_sha256
    ):
        raise CampaignRunnerError(
            "Split source hash does not match the "
            "accepted merged dataset."
        )

    partitions = manifest.get("partitions")
    outputs = manifest.get("outputs")
    if not isinstance(partitions, dict) or not isinstance(
        outputs, dict
    ):
        raise CampaignRunnerError(
            "Split manifest partitions or outputs "
            "are invalid."
        )

    all_groups: set[str] = set()
    summary_partitions: dict[str, Any] = {}

    for partition_name in PARTITION_NAMES:
        partition = partitions.get(partition_name)
        file_name = f"{partition_name}.jsonl"
        output = outputs.get(file_name)
        if not isinstance(partition, dict) or not isinstance(
            output, dict
        ):
            raise CampaignRunnerError(
                f"Split {partition_name} metadata is invalid."
            )

        expected_groups = sorted(
            campaign_plan.split.
            expected_group_allocation[
                partition_name
            ]
        )
        expected_group_count = len(expected_groups)
        expected_row_count = (
            expected_group_count
            * len(campaign_plan.expected_fault_types)
            * campaign_plan.
            repetitions_per_class_context
        )
        expected_class_rows = {
            fault_type: (
                expected_group_count
                * campaign_plan.
                repetitions_per_class_context
            )
            for fault_type
            in campaign_plan.expected_fault_types
        }

        if sorted(partition.get("group_ids", [])) != (
            expected_groups
        ):
            raise CampaignRunnerError(
                f"Split {partition_name} groups do "
                "not match the frozen allocation."
            )
        if partition.get("group_count") != (
            expected_group_count
        ):
            raise CampaignRunnerError(
                f"Split {partition_name} group count "
                "is invalid."
            )
        if partition.get("row_count") != (
            expected_row_count
        ):
            raise CampaignRunnerError(
                f"Split {partition_name} row count "
                "is invalid."
            )
        if partition.get("class_row_counts") != (
            expected_class_rows
        ):
            raise CampaignRunnerError(
                f"Split {partition_name} class counts "
                "are invalid."
            )

        overlap = all_groups & set(expected_groups)
        if overlap:
            raise CampaignRunnerError(
                "A split_group_id crosses partitions: "
                + ", ".join(sorted(overlap))
            )
        all_groups.update(expected_groups)

        output_path = split_directory / file_name
        actual_output_sha256 = sha256_file(
            output_path
        )
        if output.get("sha256") != (
            actual_output_sha256
        ):
            raise CampaignRunnerError(
                f"Split {file_name} hash mismatch."
            )

        summary_partitions[partition_name] = {
            "row_count": expected_row_count,
            "group_count": expected_group_count,
            "group_ids": expected_groups,
            "sha256": actual_output_sha256,
        }

    expected_all_groups = {
        context.split_group_id
        for context in campaign_plan.contexts
    }
    if all_groups != expected_all_groups:
        raise CampaignRunnerError(
            "Split does not contain every frozen group."
        )

    return {
        "manifest_path": str(manifest_path),
        "source_dataset_sha256": (
            merged_dataset_sha256
        ),
        "no_cross_partition_group": True,
        "partitions": summary_partitions,
    }


def validate_completed_campaign_result(
    result: Mapping[str, Any],
    campaign_plan: DatasetCampaignPlan,
) -> None:
    if result.get("schema_version") != (
        CAMPAIGN_RESULT_SCHEMA_VERSION
    ):
        raise CampaignRunnerError(
            "Campaign result schema_version must be 1."
        )
    if result.get("status") != "COMPLETED":
        raise CampaignRunnerError(
            "Campaign result is not COMPLETED."
        )
    if result.get("campaign_id") != (
        campaign_plan.campaign_id
    ):
        raise CampaignRunnerError(
            "Campaign result id mismatch."
        )
    if result.get("completed_context_count") != len(
        campaign_plan.contexts
    ):
        raise CampaignRunnerError(
            "Campaign result context count mismatch."
        )
    if result.get("completed_experiment_count") != (
        campaign_plan.expected_row_count
    ):
        raise CampaignRunnerError(
            "Campaign result experiment count mismatch."
        )
    if result.get("dataset_row_count") != (
        campaign_plan.expected_row_count
    ):
        raise CampaignRunnerError(
            "Campaign result row count mismatch."
        )

    contexts = result.get("contexts")
    if (
        not isinstance(contexts, list)
        or len(contexts) != len(
            campaign_plan.contexts
        )
        or any(
            not isinstance(item, dict)
            or item.get("status") != "COMPLETED"
            or item.get("cleanup_verified") is not True
            for item in contexts
        )
    ):
        raise CampaignRunnerError(
            "Campaign result contexts are incomplete."
        )

    rule_audit = result.get("rule_audit")
    if (
        not isinstance(rule_audit, dict)
        or rule_audit.get("exact_match_count")
        != campaign_plan.expected_row_count
        or rule_audit.get(
            "affected_prefix_correct_count"
        )
        != campaign_plan.expected_row_count
    ):
        raise CampaignRunnerError(
            "Campaign result rule audit is incomplete."
        )


def run_campaign(
    plan_path: Path,
    fingerprint_manifest_path: Path,
    repository_root: Path,
    output_root: Path,
    processed_root: Path,
    metadata_root: Path,
    reports_root: Path,
    *,
    command_executor: CommandExecutor | None = None,
    batch_executor: BatchExecutor | None = None,
    row_builder: DatasetRowBuilder | None = None,
    campaign_run_id: str | None = None,
    progress: ProgressReporter | None = None,
) -> dict[str, Any]:
    root = repository_root.resolve()
    resolved_plan_path = resolve_path(
        plan_path, root
    )
    resolved_fingerprint_path = resolve_path(
        fingerprint_manifest_path, root
    )
    resolved_output_root = resolve_path(
        output_root, root
    )
    resolved_processed_root = resolve_path(
        processed_root, root
    )
    resolved_metadata_root = resolve_path(
        metadata_root, root
    )
    resolved_reports_root = resolve_path(
        reports_root, root
    )

    campaign_plan = load_campaign_plan(
        resolved_plan_path,
        repository_root=root,
    )
    fingerprints = load_fingerprint_manifest(
        resolved_fingerprint_path,
        campaign_plan=campaign_plan,
        repository_root=root,
    )

    run_id = (
        campaign_run_id
        if campaign_run_id is not None
        else build_campaign_run_id(
            campaign_plan.campaign_id
        )
    )
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise CampaignRunnerError(
            "campaign_run_id contains unsupported "
            "characters."
        )

    result_path = (
        resolved_metadata_root
        / f"{run_id}.campaign.json"
    )
    merged_dataset_path = (
        resolved_processed_root
        / f"{run_id}.jsonl"
    )
    split_directory = (
        resolved_processed_root
        / f"{run_id}-split"
    )
    rule_audit_path = (
        resolved_reports_root
        / f"{run_id}-rule-audit.json"
    )

    for label, path in (
        ("campaign result", result_path),
        ("merged dataset", merged_dataset_path),
        ("split output", split_directory),
        ("rule audit", rule_audit_path),
    ):
        if path.exists():
            raise CampaignRunnerError(
                f"{label} already exists: {path}"
            )

    execute_command = (
        command_executor
        if command_executor is not None
        else run_command
    )
    execute_batch = (
        batch_executor
        if batch_executor is not None
        else run_batch
    )
    build_row = (
        row_builder
        if row_builder is not None
        else build_dataset_row
    )

    result: dict[str, Any] = {
        "schema_version": (
            CAMPAIGN_RESULT_SCHEMA_VERSION
        ),
        "campaign_run_id": run_id,
        "campaign_id": campaign_plan.campaign_id,
        "plan_path": display_path(
            resolved_plan_path, root
        ),
        "campaign_plan_sha256": sha256_file(
            resolved_plan_path
        ),
        "fingerprint_manifest_path": display_path(
            resolved_fingerprint_path, root
        ),
        "fingerprint_manifest_sha256": sha256_file(
            resolved_fingerprint_path
        ),
        "failure_policy": (
            campaign_plan.failure_policy
        ),
        "status": "RUNNING",
        "planned_context_count": len(
            campaign_plan.contexts
        ),
        "completed_context_count": 0,
        "planned_experiment_count": (
            campaign_plan.expected_row_count
        ),
        "completed_experiment_count": 0,
        "dataset_row_schema_version": (
            campaign_plan.dataset_row_schema_version
        ),
        "dataset_row_count": 0,
        "planned_merged_dataset_path": str(
            merged_dataset_path
        ),
        "merged_dataset": None,
        "rule_audit": None,
        "split": None,
        "started_at_utc": utc_now(),
        "completed_at_utc": None,
        "failed_context": None,
        "error": None,
        "contexts": [],
    }
    write_json_atomic(result_path, result)

    all_rows: list[dict[str, Any]] = []
    all_rule_records: list[dict[str, Any]] = []

    def emit(message: str) -> None:
        if progress is not None:
            progress(message)

    try:
        for context_index, context in enumerate(
            campaign_plan.contexts,
            start=1,
        ):
            emit(
                f"[{context_index}/"
                f"{len(campaign_plan.contexts)}] "
                f"{context.group_slot} precheck"
            )
            topology_path = resolve_path(
                context.topology_file, root
            )
            validator_path = resolve_path(
                context.baseline_validator, root
            )
            batch_run_id = (
                f"{run_id}-{context.group_slot.lower()}"
            )
            context_result: dict[str, Any] = {
                "group_slot": context.group_slot,
                "topology_id": context.topology_id,
                "split_group_id": (
                    context.split_group_id
                ),
                "artifact_bundle_sha256": (
                    fingerprints[
                        context.group_slot
                    ]["actual_sha256"]
                ),
                "status": "RUNNING",
                "deploy_return_code": None,
                "initial_baseline_return_code": None,
                "batch_run_id": batch_run_id,
                "batch_result_path": None,
                "dataset_path": None,
                "dataset_sha256": None,
                "completed_experiment_count": 0,
                "dataset_row_count": 0,
                "artifact_revalidation_count": 0,
                "rule_exact_match_count": 0,
                "affected_prefix_correct_count": 0,
                "class_row_counts": {},
                "final_baseline_return_code": None,
                "destroy_return_code": None,
                "cleanup_verified": False,
                "error": None,
            }
            result["contexts"].append(context_result)
            result["failed_context"] = context.group_slot
            write_json_atomic(result_path, result)

            deploy_attempted = False
            context_error: Exception | None = None
            batch_result: dict[str, Any] | None = None

            try:
                active_before = active_lab_containers(
                    topology_path,
                    repository_root=root,
                    command_executor=execute_command,
                )
                if active_before:
                    raise CampaignRunnerError(
                        f"{context.group_slot} laboratory "
                        "already exists: "
                        + ", ".join(active_before)
                    )

                emit(
                    f"[{context_index}/"
                    f"{len(campaign_plan.contexts)}] "
                    f"{context.group_slot} deploy"
                )
                deploy_attempted = True
                deploy_result = execute_command(
                    [
                        "sudo",
                        "containerlab",
                        "deploy",
                        "-t",
                        str(topology_path),
                    ],
                    root,
                )
                context_result["deploy_return_code"] = (
                    deploy_result.get("return_code")
                )
                require_success(
                    deploy_result,
                    f"{context.group_slot} deployment",
                )
                emit(
                    f"[{context_index}/"
                    f"{len(campaign_plan.contexts)}] "
                    f"{context.group_slot} initial baseline"
                )
                initial_baseline = require_success(
                    execute_command(
                        ["bash", str(validator_path)],
                        root,
                    ),
                    (
                        f"{context.group_slot} "
                        "initial baseline"
                    ),
                )
                context_result[
                    "initial_baseline_return_code"
                ] = initial_baseline["return_code"]

                emit(
                    f"[{context_index}/"
                    f"{len(campaign_plan.contexts)}] "
                    f"{context.group_slot} batch 6/6"
                )
                batch_result = execute_batch(
                    plan_path=(
                        context.batch_plan_path
                    ),
                    repository_root=root,
                    output_root=resolved_output_root,
                    processed_root=(
                        resolved_processed_root
                    ),
                    metadata_root=(
                        resolved_metadata_root
                    ),
                    baseline_validator=(
                        context.baseline_validator
                    ),
                    batch_run_id=batch_run_id,
                )

                emit(
                    f"[{context_index}/"
                    f"{len(campaign_plan.contexts)}] "
                    f"{context.group_slot} final baseline"
                )
                final_baseline = require_success(
                    execute_command(
                        ["bash", str(validator_path)],
                        root,
                    ),
                    (
                        f"{context.group_slot} "
                        "final baseline"
                    ),
                )
                context_result[
                    "final_baseline_return_code"
                ] = final_baseline["return_code"]

            except Exception as error:
                context_error = error

            finally:
                if deploy_attempted:
                    emit(
                        f"[{context_index}/"
                        f"{len(campaign_plan.contexts)}] "
                        f"{context.group_slot} destroy"
                    )
                    destroy_result = execute_command(
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
                    return_code = destroy_result.get(
                        "return_code"
                    )
                    context_result[
                        "destroy_return_code"
                    ] = return_code
                    if return_code != 0 and context_error is None:
                        context_error = CampaignRunnerError(
                            f"{context.group_slot} destroy failed."
                        )

                try:
                    active_after = active_lab_containers(
                        topology_path,
                        repository_root=root,
                        command_executor=execute_command,
                    )
                    if active_after:
                        raise CampaignRunnerError(
                            f"{context.group_slot} cleanup "
                            "left containers: "
                            + ", ".join(active_after)
                        )
                    context_result[
                        "cleanup_verified"
                    ] = True
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

            if batch_result is None:
                raise CampaignRunnerError(
                    f"{context.group_slot} has no batch result."
                )

            emit(
                f"[{context_index}/"
                f"{len(campaign_plan.contexts)}] "
                f"{context.group_slot} artifact audit"
            )
            try:
                (
                    context_rows,
                    context_rule_records,
                    context_summary,
                ) = audit_context_output(
                    campaign_plan=campaign_plan,
                    context=context,
                    batch_result=batch_result,
                    row_builder=build_row,
                )
            except Exception as audit_error:
                context_result["status"] = "FAILED"
                context_result["error"] = {
                    "type": type(audit_error).__name__,
                    "message": str(audit_error),
                }
                write_json_atomic(result_path, result)
                raise

            all_rows.extend(context_rows)
            campaign_sequence_start = len(
                all_rule_records
            )
            all_rule_records.extend(
                {
                    **record,
                    "campaign_sequence_number": (
                        campaign_sequence_start + index
                    ),
                    "group_slot": context.group_slot,
                }
                for index, record
                in enumerate(
                    context_rule_records,
                    start=1,
                )
            )

            context_result.update({
                "status": "COMPLETED",
                "batch_result_path": (
                    batch_result.get("batch_result_path")
                ),
                "completed_experiment_count": (
                    len(context_rows)
                ),
                **context_summary,
            })
            result["completed_context_count"] = (
                context_index
            )
            result["completed_experiment_count"] = len(
                all_rows
            )
            result["dataset_row_count"] = len(all_rows)
            result["failed_context"] = None
            write_json_atomic(result_path, result)

        emit("[merge] campaign quality audit")
        quality_summary = audit_merged_rows(
            campaign_plan=campaign_plan,
            rows=all_rows,
        )
        merged_sha256 = write_jsonl_atomic(
            merged_dataset_path,
            all_rows,
        )
        if sha256_file(merged_dataset_path) != (
            merged_sha256
        ):
            raise CampaignRunnerError(
                "Merged dataset hash verification failed."
            )

        rule_audit = {
            "schema_version": 1,
            "campaign_run_id": run_id,
            "campaign_id": campaign_plan.campaign_id,
            "method": "rule_based",
            "record_count": len(all_rule_records),
            "exact_match_count": sum(
                record["exact_match"] is True
                for record in all_rule_records
            ),
            "affected_prefix_correct_count": sum(
                record[
                    "affected_prefix_correct"
                ]
                is True
                for record in all_rule_records
            ),
            "records": all_rule_records,
        }
        if (
            rule_audit["record_count"]
            != campaign_plan.expected_row_count
            or rule_audit["exact_match_count"]
            != campaign_plan.expected_row_count
            or rule_audit[
                "affected_prefix_correct_count"
            ]
            != campaign_plan.expected_row_count
        ):
            raise CampaignRunnerError(
                "Rule-based campaign audit is incomplete."
            )
        write_json_atomic(rule_audit_path, rule_audit)

        emit("[split] deterministic 3/1/1 split")
        temporary_split_directory = (
            split_directory.with_name(
                f".{split_directory.name}."
                f"{uuid4().hex}.tmp"
            )
        )
        try:
            write_group_aware_split(
                merged_dataset_path,
                temporary_split_directory,
                seed=campaign_plan.split.seed,
                train_ratio=(
                    campaign_plan.split.
                    ratios["train"]
                ),
                validation_ratio=(
                    campaign_plan.split.
                    ratios["validation"]
                ),
                test_ratio=(
                    campaign_plan.split.ratios["test"]
                ),
                expected_fault_types=(
                    campaign_plan.expected_fault_types
                ),
            )
            split_summary = audit_split_output(
                campaign_plan=campaign_plan,
                merged_dataset_sha256=(
                    merged_sha256
                ),
                split_directory=(
                    temporary_split_directory
                ),
            )
            temporary_split_directory.replace(
                split_directory
            )
        except Exception:
            if temporary_split_directory.exists():
                for child in (
                    temporary_split_directory.iterdir()
                ):
                    if child.is_file():
                        child.unlink()
                temporary_split_directory.rmdir()
            raise

        split_summary["directory"] = str(
            split_directory
        )
        split_summary["manifest_path"] = str(
            split_directory / "split_manifest.json"
        )

        result["merged_dataset"] = {
            "path": str(merged_dataset_path),
            "sha256": merged_sha256,
            "row_count": len(all_rows),
            "quality": quality_summary,
        }
        result["rule_audit"] = {
            "path": str(rule_audit_path),
            "record_count": (
                rule_audit["record_count"]
            ),
            "exact_match_count": (
                rule_audit["exact_match_count"]
            ),
            "affected_prefix_correct_count": (
                rule_audit[
                    "affected_prefix_correct_count"
                ]
            ),
        }
        result["split"] = split_summary
        result["status"] = "COMPLETED"
        result["completed_at_utc"] = utc_now()
        result["failed_context"] = None
        result["error"] = None

        validate_completed_campaign_result(
            result,
            campaign_plan,
        )
        write_json_atomic(result_path, result)
        emit("[complete] campaign 30/30 accepted")
        return result

    except Exception as error:
        result["status"] = "FAILED"
        result["completed_at_utc"] = utc_now()
        result["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }
        write_json_atomic(result_path, result)

        raise CampaignRunnerError(
            f"Campaign {run_id} failed. "
            f"Artifacts: {result_path}. "
            f"Cause: {error}"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute Dataset Campaign Plan v1, "
            "merge and audit Dataset Row v2, and "
            "write the frozen group-aware split."
        )
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path(
            "plans/campaigns/"
            "P2_ROUTING_5CTX_V1.yml"
        ),
    )
    parser.add_argument(
        "--fingerprints",
        type=Path,
        default=Path(
            "plans/campaigns/"
            "P2_ROUTING_5CTX_V1.fingerprints.json"
        ),
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path("."),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/raw"),
    )
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=Path("data/processed"),
    )
    parser.add_argument(
        "--metadata-root",
        type=Path,
        default=Path("data/metadata"),
    )
    parser.add_argument(
        "--reports-root",
        type=Path,
        default=Path("reports/experiments"),
    )
    parser.add_argument(
        "--campaign-run-id",
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        result = run_campaign(
            plan_path=arguments.plan,
            fingerprint_manifest_path=(
                arguments.fingerprints
            ),
            repository_root=(
                arguments.repository_root
            ),
            output_root=arguments.output_root,
            processed_root=(
                arguments.processed_root
            ),
            metadata_root=(
                arguments.metadata_root
            ),
            reports_root=arguments.reports_root,
            campaign_run_id=(
                arguments.campaign_run_id
            ),
            progress=lambda message: print(
                message,
                flush=True,
            ),
        )
    except (
        CampaignPlanError,
        CampaignRunnerError,
        DatasetSplitError,
        OSError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
