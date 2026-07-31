from __future__ import annotations

import argparse
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.batch.plan import (
    BatchPlan,
    BatchPlanError,
    expand_batch_plan,
    load_batch_plan,
)
from src.dataset.splitter import (
    PARTITION_NAMES,
    allocate_group_counts,
    stable_group_key,
)


CAMPAIGN_PLAN_SCHEMA_VERSION = 1
DATASET_ROW_SCHEMA_VERSION = 2
SPLIT_ALGORITHM = "complete_context_group_hash_v2"
IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
)
DIRECTION_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9_]*_to_[a-z0-9][a-z0-9_]*$"
)


class CampaignPlanError(ValueError):
    """Raised when Dataset Campaign Plan v1 is invalid."""


@dataclass(frozen=True)
class CampaignContext:
    group_slot: str
    topology_id: str
    split_group_id: str
    topology_file: Path
    baseline_validator: Path
    batch_plan_path: Path
    direction: str
    route_observer_node: str
    transit_node: str
    batch_plan: BatchPlan


@dataclass(frozen=True)
class CampaignSplit:
    algorithm: str
    seed: int
    ratios: dict[str, float]
    expected_group_allocation: dict[
        str,
        tuple[str, ...],
    ]


@dataclass(frozen=True)
class DatasetCampaignPlan:
    schema_version: int
    campaign_id: str
    description: str
    execution_order: str
    failure_policy: str
    dataset_row_schema_version: int
    expected_fault_types: tuple[str, ...]
    repetitions_per_class_context: int
    expected_row_count: int
    contexts: tuple[CampaignContext, ...]
    split: CampaignSplit


def _require_mapping(
    value: object,
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CampaignPlanError(
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
        raise CampaignPlanError(
            f"{label} is missing keys: "
            + ", ".join(sorted(missing))
            + "."
        )

    if unexpected:
        raise CampaignPlanError(
            f"{label} has unexpected keys: "
            + ", ".join(
                sorted(str(item) for item in unexpected)
            )
            + "."
        )


def _require_text(
    value: object,
    label: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CampaignPlanError(
            f"{label} must be a non-empty string."
        )

    return value.strip()


def _require_identifier(
    value: object,
    label: str,
) -> str:
    identifier = _require_text(value, label)

    if not IDENTIFIER_PATTERN.fullmatch(identifier):
        raise CampaignPlanError(
            f"{label} contains unsupported characters."
        )

    return identifier


def _require_positive_integer(
    value: object,
    label: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
    ):
        raise CampaignPlanError(
            f"{label} must be a positive integer."
        )

    return value


def _require_relative_file(
    value: object,
    *,
    label: str,
    repository_root: Path,
    required_prefix: str,
    suffixes: set[str],
    executable: bool = False,
) -> Path:
    text = _require_text(value, label)

    if "\\" in text:
        raise CampaignPlanError(
            f"{label} must use forward slashes."
        )

    relative_path = Path(text)

    if relative_path.is_absolute():
        raise CampaignPlanError(
            f"{label} must be relative."
        )

    if ".." in relative_path.parts:
        raise CampaignPlanError(
            f"{label} must not contain '..'."
        )

    if (
        not relative_path.parts
        or relative_path.parts[0]
        != required_prefix
    ):
        raise CampaignPlanError(
            f"{label} must be inside "
            f"{required_prefix}/."
        )

    if relative_path.suffix not in suffixes:
        raise CampaignPlanError(
            f"{label} has an unsupported suffix."
        )

    resolved = (
        repository_root / relative_path
    ).resolve()

    try:
        resolved.relative_to(repository_root)
    except ValueError as error:
        raise CampaignPlanError(
            f"{label} resolves outside the repository."
        ) from error

    if not resolved.is_file():
        raise CampaignPlanError(
            f"{label} does not exist: "
            f"{relative_path.as_posix()}."
        )

    if executable and not (
        resolved.stat().st_mode & 0o111
    ):
        raise CampaignPlanError(
            f"{label} must be executable."
        )

    return Path(relative_path.as_posix())


def _read_mapping_file(
    path: Path,
    label: str,
) -> Mapping[str, Any]:
    try:
        document = yaml.safe_load(
            path.read_text(encoding="utf-8")
        )
    except (OSError, yaml.YAMLError) as error:
        raise CampaignPlanError(
            f"Cannot read {label}: {error}"
        ) from error

    return _require_mapping(document, label)


def _read_scenario(
    repository_root: Path,
    scenario_path: Path,
) -> Mapping[str, Any]:
    document = _read_mapping_file(
        repository_root / scenario_path,
        f"scenario {scenario_path.as_posix()}",
    )
    scenario = document.get("scenario")
    return _require_mapping(
        scenario,
        f"scenario {scenario_path.as_posix()}.scenario",
    )


def _validate_context_batch(
    *,
    repository_root: Path,
    context_label: str,
    topology_id: str,
    split_group_id: str,
    topology_file: Path,
    direction: str,
    route_observer_node: str,
    transit_node: str,
    batch_plan: BatchPlan,
    expected_fault_types: tuple[str, ...],
    repetitions: int,
) -> None:
    entries = batch_plan.entries

    if len(entries) != len(expected_fault_types):
        raise CampaignPlanError(
            f"{context_label} batch must contain "
            "one entry per expected fault type."
        )

    observed_fault_types: list[str] = []

    for entry in entries:
        if entry.repetitions != repetitions:
            raise CampaignPlanError(
                f"{context_label} entry "
                f"{entry.entry_id} must use "
                f"{repetitions} repetitions."
            )

        scenario = _read_scenario(
            repository_root,
            entry.scenario_path,
        )
        scenario_topology = _require_mapping(
            scenario.get("topology"),
            f"{context_label} scenario.topology",
        )
        observation = _require_mapping(
            scenario.get("observation"),
            f"{context_label} scenario.observation",
        )
        ground_truth = _require_mapping(
            scenario.get("ground_truth"),
            f"{context_label} scenario.ground_truth",
        )

        actual_topology_file = _require_text(
            scenario_topology.get("file"),
            f"{context_label} scenario.topology.file",
        )

        expected_values = {
            "scenario.topology.id": (
                scenario_topology.get("id"),
                topology_id,
            ),
            "scenario.topology.file": (
                actual_topology_file,
                topology_file.as_posix(),
            ),
            "scenario.split_group_id": (
                scenario.get("split_group_id"),
                split_group_id,
            ),
            "scenario.observation.direction": (
                observation.get("direction"),
                direction,
            ),
            "scenario.observation.route_observer_node": (
                observation.get(
                    "route_observer_node"
                ),
                route_observer_node,
            ),
            "scenario.observation.transit_node": (
                observation.get("transit_node"),
                transit_node,
            ),
        }

        for field_name, (
            actual,
            expected,
        ) in expected_values.items():
            if actual != expected:
                raise CampaignPlanError(
                    f"{context_label} {field_name} "
                    f"must be {expected!r}; "
                    f"received {actual!r}."
                )

        fault_type = _require_identifier(
            ground_truth.get("fault_type"),
            (
                f"{context_label} "
                "scenario.ground_truth.fault_type"
            ),
        )
        observed_fault_types.append(fault_type)

    if tuple(observed_fault_types) != (
        expected_fault_types
    ):
        raise CampaignPlanError(
            f"{context_label} batch class order "
            "must match campaign expected_fault_types."
        )


def _parse_ratios(
    value: object,
) -> dict[str, float]:
    ratios_mapping = _require_mapping(
        value,
        "campaign.split.ratios",
    )
    _require_exact_keys(
        ratios_mapping,
        set(PARTITION_NAMES),
        "campaign.split.ratios",
    )

    ratios: dict[str, float] = {}

    for partition in PARTITION_NAMES:
        ratio = ratios_mapping[partition]

        if (
            isinstance(ratio, bool)
            or not isinstance(ratio, (int, float))
            or not math.isfinite(ratio)
            or ratio <= 0
        ):
            raise CampaignPlanError(
                "campaign.split.ratios values "
                "must be finite positive numbers."
            )

        ratios[partition] = float(ratio)

    if not math.isclose(
        sum(ratios.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise CampaignPlanError(
            "campaign.split.ratios must sum to 1.0."
        )

    return ratios


def _parse_expected_allocation(
    value: object,
) -> dict[str, tuple[str, ...]]:
    allocation = _require_mapping(
        value,
        (
            "campaign.split."
            "expected_group_allocation"
        ),
    )
    _require_exact_keys(
        allocation,
        set(PARTITION_NAMES),
        (
            "campaign.split."
            "expected_group_allocation"
        ),
    )

    parsed: dict[str, tuple[str, ...]] = {}
    seen_groups: set[str] = set()

    for partition in PARTITION_NAMES:
        values = allocation[partition]

        if (
            not isinstance(values, list)
            or not values
        ):
            raise CampaignPlanError(
                "Every expected partition must "
                "contain at least one group."
            )

        groups = tuple(
            _require_identifier(
                group,
                (
                    "campaign.split."
                    "expected_group_allocation."
                    f"{partition}"
                ),
            )
            for group in values
        )

        duplicates = seen_groups.intersection(
            groups
        )
        if duplicates:
            raise CampaignPlanError(
                "A split group cannot appear in "
                "multiple expected partitions."
            )

        if len(set(groups)) != len(groups):
            raise CampaignPlanError(
                "A partition cannot repeat a "
                "split group."
            )

        seen_groups.update(groups)
        parsed[partition] = groups

    return parsed


def _expected_allocation(
    group_ids: Sequence[str],
    *,
    seed: int,
    ratios: dict[str, float],
) -> dict[str, tuple[str, ...]]:
    counts = allocate_group_counts(
        len(group_ids),
        ratios,
    )
    ordered_groups = sorted(
        group_ids,
        key=lambda group_id: stable_group_key(
            seed,
            group_id,
        ),
    )
    allocation: dict[
        str,
        tuple[str, ...],
    ] = {}
    start = 0

    for partition in PARTITION_NAMES:
        end = start + counts[partition]
        allocation[partition] = tuple(sorted(
            ordered_groups[start:end]
        ))
        start = end

    return allocation


def load_campaign_plan(
    plan_path: Path,
    *,
    repository_root: Path | None = None,
) -> DatasetCampaignPlan:
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
    document = _read_mapping_file(
        resolved_plan_path,
        "Dataset Campaign Plan v1",
    )
    _require_exact_keys(
        document,
        {"schema_version", "campaign"},
        "Dataset Campaign Plan v1",
    )

    schema_version = document["schema_version"]
    if (
        isinstance(schema_version, bool)
        or not isinstance(schema_version, int)
        or schema_version
        != CAMPAIGN_PLAN_SCHEMA_VERSION
    ):
        raise CampaignPlanError(
            "schema_version must be 1."
        )

    campaign = _require_mapping(
        document["campaign"],
        "campaign",
    )
    _require_exact_keys(
        campaign,
        {
            "id",
            "description",
            "execution",
            "dataset",
            "split",
            "contexts",
        },
        "campaign",
    )

    campaign_id = _require_identifier(
        campaign["id"],
        "campaign.id",
    )
    description = _require_text(
        campaign["description"],
        "campaign.description",
    )

    execution = _require_mapping(
        campaign["execution"],
        "campaign.execution",
    )
    _require_exact_keys(
        execution,
        {"order", "failure_policy"},
        "campaign.execution",
    )
    execution_order = _require_text(
        execution["order"],
        "campaign.execution.order",
    )
    failure_policy = _require_text(
        execution["failure_policy"],
        "campaign.execution.failure_policy",
    )

    if execution_order != "listed":
        raise CampaignPlanError(
            "Dataset Campaign Plan v1 supports "
            "only order=listed."
        )

    if failure_policy != "stop":
        raise CampaignPlanError(
            "Dataset Campaign Plan v1 supports "
            "only failure_policy=stop."
        )

    dataset = _require_mapping(
        campaign["dataset"],
        "campaign.dataset",
    )
    _require_exact_keys(
        dataset,
        {
            "row_schema_version",
            "expected_fault_types",
            "repetitions_per_class_context",
            "expected_row_count",
        },
        "campaign.dataset",
    )

    row_schema_version = dataset[
        "row_schema_version"
    ]
    if (
        isinstance(row_schema_version, bool)
        or row_schema_version
        != DATASET_ROW_SCHEMA_VERSION
    ):
        raise CampaignPlanError(
            "campaign.dataset.row_schema_version "
            "must be 2."
        )

    raw_fault_types = dataset[
        "expected_fault_types"
    ]
    if (
        not isinstance(raw_fault_types, list)
        or not raw_fault_types
    ):
        raise CampaignPlanError(
            "campaign.dataset.expected_fault_types "
            "must be a non-empty list."
        )

    expected_fault_types = tuple(
        _require_identifier(
            item,
            (
                "campaign.dataset."
                "expected_fault_types"
            ),
        )
        for item in raw_fault_types
    )
    if len(set(expected_fault_types)) != len(
        expected_fault_types
    ):
        raise CampaignPlanError(
            "campaign.dataset.expected_fault_types "
            "cannot contain duplicates."
        )

    repetitions = _require_positive_integer(
        dataset[
            "repetitions_per_class_context"
        ],
        (
            "campaign.dataset."
            "repetitions_per_class_context"
        ),
    )
    expected_row_count = _require_positive_integer(
        dataset["expected_row_count"],
        "campaign.dataset.expected_row_count",
    )

    split = _require_mapping(
        campaign["split"],
        "campaign.split",
    )
    _require_exact_keys(
        split,
        {
            "algorithm",
            "seed",
            "ratios",
            "expected_group_allocation",
        },
        "campaign.split",
    )
    algorithm = _require_text(
        split["algorithm"],
        "campaign.split.algorithm",
    )
    if algorithm != SPLIT_ALGORITHM:
        raise CampaignPlanError(
            "campaign.split.algorithm must be "
            f"{SPLIT_ALGORITHM}."
        )

    seed = split["seed"]
    if (
        isinstance(seed, bool)
        or not isinstance(seed, int)
    ):
        raise CampaignPlanError(
            "campaign.split.seed must be an integer."
        )

    ratios = _parse_ratios(
        split["ratios"]
    )
    declared_allocation = (
        _parse_expected_allocation(
            split["expected_group_allocation"]
        )
    )

    raw_contexts = campaign["contexts"]
    if (
        not isinstance(raw_contexts, list)
        or not raw_contexts
    ):
        raise CampaignPlanError(
            "campaign.contexts must be a "
            "non-empty list."
        )

    contexts: list[CampaignContext] = []
    slots: set[str] = set()
    group_ids: set[str] = set()
    batch_paths: set[Path] = set()
    total_rows = 0

    for index, raw_context in enumerate(
        raw_contexts
    ):
        label = f"campaign.contexts[{index}]"
        context = _require_mapping(
            raw_context,
            label,
        )
        _require_exact_keys(
            context,
            {
                "group_slot",
                "topology_id",
                "split_group_id",
                "topology_file",
                "baseline_validator",
                "batch_plan",
                "observation",
            },
            label,
        )

        group_slot = _require_identifier(
            context["group_slot"],
            f"{label}.group_slot",
        )
        topology_id = _require_identifier(
            context["topology_id"],
            f"{label}.topology_id",
        )
        split_group_id = _require_identifier(
            context["split_group_id"],
            f"{label}.split_group_id",
        )

        if group_slot in slots:
            raise CampaignPlanError(
                f"Duplicate group_slot: {group_slot}."
            )
        if split_group_id in group_ids:
            raise CampaignPlanError(
                "Duplicate split_group_id: "
                f"{split_group_id}."
            )

        topology_file = _require_relative_file(
            context["topology_file"],
            label=f"{label}.topology_file",
            repository_root=root,
            required_prefix="labs",
            suffixes={".yml", ".yaml"},
        )
        baseline_validator = (
            _require_relative_file(
                context["baseline_validator"],
                label=(
                    f"{label}.baseline_validator"
                ),
                repository_root=root,
                required_prefix="labs",
                suffixes={".sh"},
                executable=True,
            )
        )
        batch_plan_path = _require_relative_file(
            context["batch_plan"],
            label=f"{label}.batch_plan",
            repository_root=root,
            required_prefix="plans",
            suffixes={".yml", ".yaml"},
        )
        if batch_plan_path in batch_paths:
            raise CampaignPlanError(
                "Every context must reference a "
                "different Batch Plan v1 file."
            )

        observation = _require_mapping(
            context["observation"],
            f"{label}.observation",
        )
        _require_exact_keys(
            observation,
            {
                "direction",
                "route_observer_node",
                "transit_node",
            },
            f"{label}.observation",
        )
        direction = _require_text(
            observation["direction"],
            f"{label}.observation.direction",
        )
        if not DIRECTION_PATTERN.fullmatch(
            direction
        ):
            raise CampaignPlanError(
                f"{label}.observation.direction "
                "has an invalid format."
            )
        route_observer_node = _require_identifier(
            observation["route_observer_node"],
            (
                f"{label}.observation."
                "route_observer_node"
            ),
        )
        transit_node = _require_identifier(
            observation["transit_node"],
            f"{label}.observation.transit_node",
        )

        try:
            batch_plan = load_batch_plan(
                root / batch_plan_path,
                repository_root=root,
            )
        except BatchPlanError as error:
            raise CampaignPlanError(
                f"{label} has an invalid batch plan: "
                f"{error}"
            ) from error

        _validate_context_batch(
            repository_root=root,
            context_label=label,
            topology_id=topology_id,
            split_group_id=split_group_id,
            topology_file=topology_file,
            direction=direction,
            route_observer_node=(
                route_observer_node
            ),
            transit_node=transit_node,
            batch_plan=batch_plan,
            expected_fault_types=(
                expected_fault_types
            ),
            repetitions=repetitions,
        )

        planned_count = len(
            expand_batch_plan(batch_plan)
        )
        expected_context_count = (
            len(expected_fault_types)
            * repetitions
        )
        if planned_count != expected_context_count:
            raise CampaignPlanError(
                f"{label} must expand to "
                f"{expected_context_count} experiments."
            )

        total_rows += planned_count
        slots.add(group_slot)
        group_ids.add(split_group_id)
        batch_paths.add(batch_plan_path)
        contexts.append(
            CampaignContext(
                group_slot=group_slot,
                topology_id=topology_id,
                split_group_id=split_group_id,
                topology_file=topology_file,
                baseline_validator=(
                    baseline_validator
                ),
                batch_plan_path=batch_plan_path,
                direction=direction,
                route_observer_node=(
                    route_observer_node
                ),
                transit_node=transit_node,
                batch_plan=batch_plan,
            )
        )

    if total_rows != expected_row_count:
        raise CampaignPlanError(
            "Expanded context batches produce "
            f"{total_rows} rows, not declared "
            f"{expected_row_count}."
        )

    calculated_allocation = (
        _expected_allocation(
            [
                context.split_group_id
                for context in contexts
            ],
            seed=seed,
            ratios=ratios,
        )
    )
    if declared_allocation != (
        calculated_allocation
    ):
        raise CampaignPlanError(
            "Declared expected_group_allocation "
            "does not match the deterministic "
            "split contract."
        )

    return DatasetCampaignPlan(
        schema_version=schema_version,
        campaign_id=campaign_id,
        description=description,
        execution_order=execution_order,
        failure_policy=failure_policy,
        dataset_row_schema_version=(
            row_schema_version
        ),
        expected_fault_types=(
            expected_fault_types
        ),
        repetitions_per_class_context=(
            repetitions
        ),
        expected_row_count=expected_row_count,
        contexts=tuple(contexts),
        split=CampaignSplit(
            algorithm=algorithm,
            seed=seed,
            ratios=ratios,
            expected_group_allocation=(
                declared_allocation
            ),
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Dataset Campaign Plan v1."
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
    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        plan = load_campaign_plan(
            arguments.plan,
            repository_root=(
                arguments.repository_root
            ),
        )
    except CampaignPlanError as error:
        print(f"[ERROR] {error}")
        return 1

    summary = {
        "schema_version": plan.schema_version,
        "campaign_id": plan.campaign_id,
        "execution_order": plan.execution_order,
        "failure_policy": plan.failure_policy,
        "dataset_row_schema_version": (
            plan.dataset_row_schema_version
        ),
        "expected_fault_types": list(
            plan.expected_fault_types
        ),
        "repetitions_per_class_context": (
            plan.repetitions_per_class_context
        ),
        "context_count": len(plan.contexts),
        "planned_experiment_count": (
            plan.expected_row_count
        ),
        "contexts": [
            {
                "group_slot": context.group_slot,
                "topology_id": context.topology_id,
                "split_group_id": (
                    context.split_group_id
                ),
                "batch_plan": (
                    context.batch_plan_path.as_posix()
                ),
                "planned_experiment_count": len(
                    expand_batch_plan(
                        context.batch_plan
                    )
                ),
            }
            for context in plan.contexts
        ],
        "split": {
            "algorithm": plan.split.algorithm,
            "seed": plan.split.seed,
            "ratios": plan.split.ratios,
            "expected_group_allocation": {
                partition: list(groups)
                for partition, groups
                in plan.split
                .expected_group_allocation
                .items()
            },
        },
    }

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
