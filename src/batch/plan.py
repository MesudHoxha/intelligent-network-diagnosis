from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


BATCH_PLAN_SCHEMA_VERSION = 1
MAX_REPETITIONS_PER_ENTRY = 1000
MAX_BATCH_ENTRIES = 1000
MAX_PLANNED_EXPERIMENTS = 10000

IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
)


class BatchPlanError(ValueError):
    """Raised when a batch plan violates Batch Plan v1."""


@dataclass(frozen=True)
class BatchPlanEntry:
    entry_id: str
    scenario_path: Path
    repetitions: int


@dataclass(frozen=True)
class BatchPlan:
    schema_version: int
    batch_id: str
    description: str
    execution_order: str
    failure_policy: str
    entries: tuple[BatchPlanEntry, ...]


@dataclass(frozen=True)
class PlannedExperiment:
    sequence_number: int
    entry_id: str
    scenario_path: Path
    repetition_index: int


def _require_mapping(
    value: object,
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BatchPlanError(
            f"{label} must be a mapping."
        )

    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    label: str,
) -> None:
    actual = set(value)
    missing = expected - actual
    unexpected = actual - expected

    if missing:
        names = ", ".join(sorted(missing))
        raise BatchPlanError(
            f"{label} is missing keys: {names}."
        )

    if unexpected:
        names = ", ".join(
            sorted(str(item) for item in unexpected)
        )
        raise BatchPlanError(
            f"{label} has unexpected keys: {names}."
        )


def _require_text(
    value: object,
    label: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BatchPlanError(
            f"{label} must be a non-empty string."
        )

    return value.strip()


def _require_identifier(
    value: object,
    label: str,
) -> str:
    identifier = _require_text(value, label)

    if not IDENTIFIER_PATTERN.fullmatch(identifier):
        raise BatchPlanError(
            f"{label} contains unsupported characters."
        )

    return identifier


def _resolve_scenario_path(
    raw_path: object,
    repository_root: Path,
) -> Path:
    path_text = _require_text(
        raw_path,
        "scenario_path",
    )

    if "\\" in path_text:
        raise BatchPlanError(
            "scenario_path must use forward slashes."
        )

    relative_path = Path(path_text)

    if relative_path.is_absolute():
        raise BatchPlanError(
            "scenario_path must be relative."
        )

    if ".." in relative_path.parts:
        raise BatchPlanError(
            "scenario_path must not contain '..'."
        )

    if (
        not relative_path.parts
        or relative_path.parts[0] != "scenarios"
    ):
        raise BatchPlanError(
            "scenario_path must be inside scenarios/."
        )

    if relative_path.suffix not in {".yml", ".yaml"}:
        raise BatchPlanError(
            "scenario_path must reference YAML."
        )

    resolved_path = (
        repository_root / relative_path
    ).resolve()

    try:
        resolved_path.relative_to(repository_root)
    except ValueError as error:
        raise BatchPlanError(
            "scenario_path resolves outside the repository."
        ) from error

    if not resolved_path.is_file():
        raise BatchPlanError(
            f"Scenario file does not exist: "
            f"{relative_path.as_posix()}."
        )

    return Path(relative_path.as_posix())


def load_batch_plan(
    plan_path: Path,
    *,
    repository_root: Path | None = None,
) -> BatchPlan:
    root = (
        repository_root.resolve()
        if repository_root is not None
        else Path.cwd().resolve()
    )

    resolved_plan_path = (
        plan_path.resolve()
        if plan_path.is_absolute()
        else (root / plan_path).resolve()
    )

    try:
        document = yaml.safe_load(
            resolved_plan_path.read_text(
                encoding="utf-8"
            )
        )
    except (OSError, yaml.YAMLError) as error:
        raise BatchPlanError(
            f"Cannot read batch plan: {error}"
        ) from error

    root_document = _require_mapping(
        document,
        "Batch plan document",
    )
    _require_exact_keys(
        root_document,
        {"schema_version", "batch"},
        "Batch plan document",
    )

    schema_version = root_document["schema_version"]

    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version
        != BATCH_PLAN_SCHEMA_VERSION
    ):
        raise BatchPlanError(
            "schema_version must be 1."
        )

    batch = _require_mapping(
        root_document["batch"],
        "batch",
    )
    _require_exact_keys(
        batch,
        {
            "id",
            "description",
            "execution",
            "entries",
        },
        "batch",
    )

    batch_id = _require_identifier(
        batch["id"],
        "batch.id",
    )
    description = _require_text(
        batch["description"],
        "batch.description",
    )

    execution = _require_mapping(
        batch["execution"],
        "batch.execution",
    )
    _require_exact_keys(
        execution,
        {"order", "failure_policy"},
        "batch.execution",
    )

    execution_order = _require_text(
        execution["order"],
        "batch.execution.order",
    )
    failure_policy = _require_text(
        execution["failure_policy"],
        "batch.execution.failure_policy",
    )

    if execution_order != "listed":
        raise BatchPlanError(
            "Batch Plan v1 supports only order=listed."
        )

    if failure_policy != "stop":
        raise BatchPlanError(
            "Batch Plan v1 supports only "
            "failure_policy=stop."
        )

    raw_entries = batch["entries"]

    if (
        not isinstance(raw_entries, list)
        or not raw_entries
    ):
        raise BatchPlanError(
            "batch.entries must be a non-empty list."
        )

    if len(raw_entries) > MAX_BATCH_ENTRIES:
        raise BatchPlanError(
            "batch.entries must contain at most 1000 entries."
        )
    entries: list[BatchPlanEntry] = []
    entry_ids: set[str] = set()
    scenario_paths: set[Path] = set()
    total_experiments = 0

    for index, raw_entry in enumerate(raw_entries):
        label = f"batch.entries[{index}]"
        entry = _require_mapping(
            raw_entry,
            label,
        )
        _require_exact_keys(
            entry,
            {
                "entry_id",
                "scenario_path",
                "repetitions",
            },
            label,
        )

        entry_id = _require_identifier(
            entry["entry_id"],
            f"{label}.entry_id",
        )

        if entry_id in entry_ids:
            raise BatchPlanError(
                f"Duplicate entry_id: {entry_id}."
            )

        scenario_path = _resolve_scenario_path(
            entry["scenario_path"],
            root,
        )

        if scenario_path in scenario_paths:
            raise BatchPlanError(
                "Duplicate scenario_path; use repetitions "
                "instead of duplicate entries."
            )

        repetitions = entry["repetitions"]

        if (
            not isinstance(repetitions, int)
            or isinstance(repetitions, bool)
            or repetitions < 1
            or repetitions
            > MAX_REPETITIONS_PER_ENTRY
        ):
            raise BatchPlanError(
                f"{label}.repetitions must be an "
                "integer from 1 to 1000."
            )

        total_experiments += repetitions

        if (
            total_experiments
            > MAX_PLANNED_EXPERIMENTS
        ):
            raise BatchPlanError(
                "Batch plan exceeds 10000 experiments."
            )

        entry_ids.add(entry_id)
        scenario_paths.add(scenario_path)
        entries.append(
            BatchPlanEntry(
                entry_id=entry_id,
                scenario_path=scenario_path,
                repetitions=repetitions,
            )
        )

    return BatchPlan(
        schema_version=schema_version,
        batch_id=batch_id,
        description=description,
        execution_order=execution_order,
        failure_policy=failure_policy,
        entries=tuple(entries),
    )


def expand_batch_plan(
    plan: BatchPlan,
) -> tuple[PlannedExperiment, ...]:
    experiments: list[PlannedExperiment] = []
    sequence_number = 0

    for entry in plan.entries:
        for repetition_index in range(
            1,
            entry.repetitions + 1,
        ):
            sequence_number += 1
            experiments.append(
                PlannedExperiment(
                    sequence_number=sequence_number,
                    entry_id=entry.entry_id,
                    scenario_path=entry.scenario_path,
                    repetition_index=(
                        repetition_index
                    ),
                )
            )

    return tuple(experiments)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and expand Batch Plan v1."
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
    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        plan = load_batch_plan(
            arguments.plan,
            repository_root=(
                arguments.repository_root
            ),
        )
    except BatchPlanError as error:
        print(f"[ERROR] {error}")
        return 1

    experiments = expand_batch_plan(plan)

    summary = {
        "schema_version": plan.schema_version,
        "batch_id": plan.batch_id,
        "execution_order": plan.execution_order,
        "failure_policy": plan.failure_policy,
        "planned_experiment_count": len(
            experiments
        ),
        "experiments": [
            {
                "sequence_number": (
                    experiment.sequence_number
                ),
                "entry_id": experiment.entry_id,
                "scenario_path": (
                    experiment.scenario_path.as_posix()
                ),
                "repetition_index": (
                    experiment.repetition_index
                ),
            }
            for experiment in experiments
        ],
    }

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
