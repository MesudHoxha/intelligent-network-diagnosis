from __future__ import annotations

import argparse
import json
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.batch.plan import (
    BatchPlanError,
    expand_batch_plan,
    load_batch_plan,
)
from src.dataset.contract import (
    build_dataset_row,
    validate_dataset_row,
)
from src.orchestration.experiment_runner import (
    run_experiment,
)


BATCH_RESULT_SCHEMA_VERSION = 1

RUN_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
)

ExperimentExecutor = Callable[
    ...,
    dict[str, Any],
]
DatasetRowBuilder = Callable[
    [Path],
    dict[str, Any],
]


class BatchRunnerError(RuntimeError):
    """Raised when a batch cannot be completed safely."""


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def build_batch_run_id(
    batch_id: str,
) -> str:
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S%fZ")

    return (
        f"{batch_id.lower()}-"
        f"{timestamp}-"
        f"{uuid4().hex}"
    )


def resolve_path(
    path: Path,
    repository_root: Path,
) -> Path:
    if path.is_absolute():
        return path.resolve()

    return (
        repository_root / path
    ).resolve()


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


def write_json(
    path: Path,
    value: object,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def write_jsonl_atomic(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    if path.exists():
        raise BatchRunnerError(
            f"Dataset output already exists: {path}"
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_name(
        f".{path.name}.{uuid4().hex}.tmp"
    )

    try:
        content = "".join(
            json.dumps(
                row,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for row in rows
        )

        temporary_path.write_text(
            content,
            encoding="utf-8",
        )
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def require_completed_experiment(
    value: object,
) -> tuple[str, Path]:
    if not isinstance(value, dict):
        raise BatchRunnerError(
            "Experiment runner must return a mapping."
        )

    if value.get("status") != "COMPLETED":
        raise BatchRunnerError(
            "Experiment runner returned a "
            "non-completed result."
        )

    experiment_id = value.get(
        "experiment_id"
    )
    directory_value = value.get(
        "experiment_directory"
    )

    if (
        not isinstance(experiment_id, str)
        or not experiment_id
    ):
        raise BatchRunnerError(
            "Completed experiment is missing "
            "experiment_id."
        )

    if (
        not isinstance(directory_value, str)
        or not directory_value
    ):
        raise BatchRunnerError(
            "Completed experiment is missing "
            "experiment_directory."
        )

    return (
        experiment_id,
        Path(directory_value),
    )


def run_batch(
    plan_path: Path,
    repository_root: Path,
    output_root: Path,
    processed_root: Path,
    metadata_root: Path,
    baseline_validator: Path,
    *,
    experiment_executor: (
        ExperimentExecutor | None
    ) = None,
    dataset_row_builder: (
        DatasetRowBuilder | None
    ) = None,
    batch_run_id: str | None = None,
) -> dict[str, Any]:
    root = repository_root.resolve()

    resolved_plan_path = resolve_path(
        plan_path,
        root,
    )
    resolved_output_root = resolve_path(
        output_root,
        root,
    )
    resolved_processed_root = resolve_path(
        processed_root,
        root,
    )
    resolved_metadata_root = resolve_path(
        metadata_root,
        root,
    )
    resolved_baseline_validator = resolve_path(
        baseline_validator,
        root,
    )

    plan = load_batch_plan(
        resolved_plan_path,
        repository_root=root,
    )
    planned_experiments = expand_batch_plan(
        plan
    )

    if plan.failure_policy != "stop":
        raise BatchRunnerError(
            "Batch Runner v1 supports only "
            "failure_policy=stop."
        )

    run_id = (
        batch_run_id
        if batch_run_id is not None
        else build_batch_run_id(plan.batch_id)
    )

    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise BatchRunnerError(
            "batch_run_id contains unsupported "
            "characters."
        )

    dataset_path = (
        resolved_processed_root
        / f"{run_id}.jsonl"
    )
    result_path = (
        resolved_metadata_root
        / f"{run_id}.json"
    )

    if dataset_path.exists():
        raise BatchRunnerError(
            "Dataset output already exists: "
            f"{dataset_path}"
        )

    if result_path.exists():
        raise BatchRunnerError(
            "Batch result already exists: "
            f"{result_path}"
        )

    executor = (
        experiment_executor
        if experiment_executor is not None
        else run_experiment
    )
    row_builder = (
        dataset_row_builder
        if dataset_row_builder is not None
        else build_dataset_row
    )

    started_at_utc = utc_now()

    result: dict[str, Any] = {
        "schema_version": (
            BATCH_RESULT_SCHEMA_VERSION
        ),
        "batch_run_id": run_id,
        "batch_id": plan.batch_id,
        "plan_path": display_path(
            resolved_plan_path,
            root,
        ),
        "failure_policy": (
            plan.failure_policy
        ),
        "status": "RUNNING",
        "planned_experiment_count": len(
            planned_experiments
        ),
        "completed_experiment_count": 0,
        "dataset_row_count": 0,
        "dataset_row_schema_version": None,
        "planned_dataset_path": str(
            dataset_path
        ),
        "dataset_path": None,
        "batch_result_path": str(
            result_path
        ),
        "started_at_utc": started_at_utc,
        "completed_at_utc": None,
        "failed_sequence_number": None,
        "error": None,
        "experiments": [],
    }

    write_json(result_path, result)

    rows: list[dict[str, Any]] = []
    sample_ids: set[str] = set()
    experiment_directories: set[Path] = set()

    active_sequence_number: int | None = None
    active_entry_id: str | None = None

    try:
        for planned in planned_experiments:
            active_sequence_number = (
                planned.sequence_number
            )
            active_entry_id = planned.entry_id

            scenario_path = (
                root / planned.scenario_path
            ).resolve()

            experiment_result = executor(
                scenario_path=scenario_path,
                output_root=resolved_output_root,
                baseline_validator=(
                    resolved_baseline_validator
                ),
            )

            (
                experiment_id,
                experiment_directory,
            ) = require_completed_experiment(
                experiment_result
            )

            resolved_experiment_directory = (
                experiment_directory.resolve()
            )

            if (
                resolved_experiment_directory
                in experiment_directories
            ):
                raise BatchRunnerError(
                    "Duplicate experiment_directory "
                    f"detected: "
                    f"{resolved_experiment_directory}"
                )

            row = row_builder(
                resolved_experiment_directory
            )

            # Accept the supported versioned dataset contracts at
            # the batch boundary. New real executions use the
            # canonical Dataset Row v2 builder by default.
            validate_dataset_row(row)

            sample_id = row.get("sample_id")
            row_schema_version = row.get(
                "schema_version"
            )

            batch_schema_version = result[
                "dataset_row_schema_version"
            ]

            if batch_schema_version is None:
                result[
                    "dataset_row_schema_version"
                ] = row_schema_version
            elif (
                batch_schema_version
                != row_schema_version
            ):
                raise BatchRunnerError(
                    "A batch dataset cannot mix "
                    "Dataset Row schema versions."
                )

            if sample_id != experiment_id:
                raise BatchRunnerError(
                    "Dataset sample_id does not match "
                    "the experiment_id."
                )

            if sample_id in sample_ids:
                raise BatchRunnerError(
                    "Duplicate dataset sample_id "
                    f"detected: {sample_id}"
                )

            sample_ids.add(sample_id)
            experiment_directories.add(
                resolved_experiment_directory
            )
            rows.append(row)

            result["experiments"].append(
                {
                    "sequence_number": (
                        planned.sequence_number
                    ),
                    "entry_id": (
                        planned.entry_id
                    ),
                    "scenario_path": (
                        planned.scenario_path.as_posix()
                    ),
                    "repetition_index": (
                        planned.repetition_index
                    ),
                    "experiment_id": (
                        experiment_id
                    ),
                    "experiment_directory": str(
                        resolved_experiment_directory
                    ),
                    "sample_id": sample_id,
                    "status": "COMPLETED",
                }
            )
            result[
                "completed_experiment_count"
            ] = len(rows)
            result["dataset_row_count"] = len(
                rows
            )

            write_json(result_path, result)

        active_sequence_number = None
        active_entry_id = None

        write_jsonl_atomic(
            dataset_path,
            rows,
        )

    except Exception as error:
        result["status"] = "FAILED"
        result["completed_at_utc"] = utc_now()
        result[
            "failed_sequence_number"
        ] = active_sequence_number
        result["error"] = {
            "type": type(error).__name__,
            "message": str(error),
            "entry_id": active_entry_id,
        }

        write_json(result_path, result)

        location = (
            ""
            if active_sequence_number is None
            else (
                " at sequence "
                f"{active_sequence_number}"
            )
        )

        raise BatchRunnerError(
            f"Batch {run_id} failed"
            f"{location}. "
            f"Artifacts: {result_path}"
        ) from error

    result["status"] = "COMPLETED"
    result["dataset_path"] = str(
        dataset_path
    )
    result["completed_at_utc"] = utc_now()

    write_json(result_path, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute a validated Batch Plan v1 "
            "and aggregate Dataset Row v2 records."
        )
    )

    parser.add_argument(
        "--plan",
        type=Path,
        required=True,
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
        "--baseline-validator",
        type=Path,
        default=Path(
            "labs/topologies/top01_routed/"
            "scripts/validate_baseline.sh"
        ),
    )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        result = run_batch(
            plan_path=arguments.plan,
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
            baseline_validator=(
                arguments.baseline_validator
            ),
        )
    except (
        BatchPlanError,
        BatchRunnerError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
