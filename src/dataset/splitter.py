from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from src.dataset.contract import (
    DatasetContractError,
    validate_dataset_row,
)


PARTITION_NAMES = (
    "train",
    "validation",
    "test",
)
DEFAULT_SEED = 20260730


class DatasetSplitError(ValueError):
    """Raised when a leakage-safe split cannot be produced."""


@dataclass(frozen=True)
class SplitResult:
    partitions: dict[
        str,
        tuple[dict[str, Any], ...],
    ]
    manifest: dict[str, Any]


def validate_ratios(
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
) -> dict[str, float]:
    ratios = {
        "train": train_ratio,
        "validation": validation_ratio,
        "test": test_ratio,
    }

    for name, value in ratios.items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise DatasetSplitError(
                f"{name}_ratio must be a finite "
                "positive number."
            )

    if not math.isclose(
        sum(ratios.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise DatasetSplitError(
            "Split ratios must sum to 1.0."
        )

    return ratios


def allocate_group_counts(
    group_count: int,
    ratios: dict[str, float],
) -> dict[str, int]:
    if group_count < len(PARTITION_NAMES):
        raise DatasetSplitError(
            "At least three groups are required."
        )

    counts = {
        name: 1
        for name in PARTITION_NAMES
    }
    quotas = {
        name: ratios[name] * group_count
        for name in PARTITION_NAMES
    }

    for _ in range(
        group_count - len(PARTITION_NAMES)
    ):
        selected = max(
            enumerate(PARTITION_NAMES),
            key=lambda item: (
                quotas[item[1]]
                - counts[item[1]],
                ratios[item[1]],
                -item[0],
            ),
        )[1]

        counts[selected] += 1

    return counts


def stable_group_key(
    seed: int,
    group_id: str,
) -> tuple[str, str]:
    payload = (
        f"{seed}\0{group_id}"
        .encode("utf-8")
    )

    return (
        hashlib.sha256(payload).hexdigest(),
        group_id,
    )


def plan_group_aware_split(
    rows: Sequence[dict[str, Any]],
    *,
    seed: int = DEFAULT_SEED,
    train_ratio: float = 0.6,
    validation_ratio: float = 0.2,
    test_ratio: float = 0.2,
    expected_fault_types: (
        Sequence[str] | None
    ) = None,
) -> SplitResult:
    if (
        isinstance(seed, bool)
        or not isinstance(seed, int)
    ):
        raise DatasetSplitError(
            "seed must be an integer."
        )

    ratios = validate_ratios(
        train_ratio,
        validation_ratio,
        test_ratio,
    )

    if not rows:
        raise DatasetSplitError(
            "The source dataset is empty."
        )

    seen_sample_ids: set[str] = set()
    dataset_schema_version: int | None = None
    group_labels: dict[
        str,
        set[str],
    ] = defaultdict(set)

    validated_rows: list[
        dict[str, Any]
    ] = []

    for row_number, row in enumerate(
        rows,
        start=1,
    ):
        try:
            validate_dataset_row(row)
        except DatasetContractError as error:
            raise DatasetSplitError(
                "Invalid Dataset Row at row "
                f"{row_number}: {error}"
            ) from error

        row_schema_version = row[
            "schema_version"
        ]

        if dataset_schema_version is None:
            dataset_schema_version = (
                row_schema_version
            )
        elif (
            dataset_schema_version
            != row_schema_version
        ):
            raise DatasetSplitError(
                "A source dataset cannot mix "
                "Dataset Row schema versions."
            )

        sample_id = row.get("sample_id")
        metadata = row.get("metadata")
        labels = row.get("labels")

        group_id = (
            metadata.get("split_group_id")
            if isinstance(metadata, dict)
            else None
        )
        label = (
            labels.get("fault_type")
            if isinstance(labels, dict)
            else None
        )

        for name, value in (
            ("sample_id", sample_id),
            (
                "metadata.split_group_id",
                group_id,
            ),
            ("labels.fault_type", label),
        ):
            if (
                not isinstance(value, str)
                or not value.strip()
            ):
                raise DatasetSplitError(
                    f"Row {row_number} has "
                    f"invalid {name}."
                )

        assert isinstance(sample_id, str)
        assert isinstance(group_id, str)
        assert isinstance(label, str)

        if sample_id in seen_sample_ids:
            raise DatasetSplitError(
                "Duplicate sample_id: "
                f"{sample_id}"
            )

        seen_sample_ids.add(sample_id)

        group_labels[group_id].add(label)
        validated_rows.append(row)

    observed_fault_types = {
        label
        for labels in group_labels.values()
        for label in labels
    }

    if expected_fault_types is None:
        required_fault_types = sorted(
            observed_fault_types
        )
    else:
        if (
            isinstance(
                expected_fault_types,
                (str, bytes),
            )
            or not expected_fault_types
        ):
            raise DatasetSplitError(
                "expected_fault_types must be a "
                "non-empty sequence of strings."
            )

        normalized_fault_types: list[str] = []

        for fault_type in expected_fault_types:
            if (
                not isinstance(fault_type, str)
                or not fault_type.strip()
            ):
                raise DatasetSplitError(
                    "expected_fault_types must "
                    "contain non-empty strings."
                )

            normalized_fault_types.append(
                fault_type
            )

        if (
            len(set(normalized_fault_types))
            != len(normalized_fault_types)
        ):
            raise DatasetSplitError(
                "expected_fault_types cannot "
                "contain duplicates."
            )

        required_fault_types = sorted(
            normalized_fault_types
        )
        required_fault_type_set = set(
            required_fault_types
        )
        missing_fault_types = sorted(
            required_fault_type_set
            - observed_fault_types
        )
        unexpected_fault_types = sorted(
            observed_fault_types
            - required_fault_type_set
        )

        if (
            missing_fault_types
            or unexpected_fault_types
        ):
            raise DatasetSplitError(
                "Source fault_type coverage does "
                "not match expected_fault_types: "
                "missing="
                f"{missing_fault_types}, "
                "unexpected="
                f"{unexpected_fault_types}."
            )

    required_fault_type_set = set(
        required_fault_types
    )
    incomplete_groups = {
        group_id: sorted(
            required_fault_type_set - labels
        )
        for group_id, labels
        in sorted(group_labels.items())
        if labels != required_fault_type_set
    }

    if incomplete_groups:
        details = ", ".join(
            f"{group_id} missing "
            f"{'/'.join(missing_labels)}"
            for group_id, missing_labels
            in incomplete_groups.items()
        )

        raise DatasetSplitError(
            "Every evaluation-context "
            "split_group_id must contain every "
            "fault_type present in the source "
            f"dataset; {details}."
        )

    if len(group_labels) < len(PARTITION_NAMES):
        raise DatasetSplitError(
            "Insufficient evaluation-context "
            "split groups for a three-way split: "
            f"found {len(group_labels)}, require "
            f"at least {len(PARTITION_NAMES)}."
        )

    ordered_groups = sorted(
        group_labels,
        key=lambda group_id: (
            stable_group_key(
                seed,
                group_id,
            )
        ),
    )

    counts = allocate_group_counts(
        len(ordered_groups),
        ratios,
    )
    group_partitions: dict[str, str] = {}
    start = 0

    for partition_name in PARTITION_NAMES:
        end = (
            start
            + counts[partition_name]
        )

        for group_id in ordered_groups[
            start:end
        ]:
            group_partitions[group_id] = (
                partition_name
            )

        start = end

    partition_rows: dict[
        str,
        list[dict[str, Any]],
    ] = {
        name: []
        for name in PARTITION_NAMES
    }

    for row in validated_rows:
        group_id = row[
            "metadata"
        ]["split_group_id"]

        partition_rows[
            group_partitions[group_id]
        ].append(row)

    for rows_in_partition in (
        partition_rows.values()
    ):
        rows_in_partition.sort(
            key=lambda item: item["sample_id"]
        )

    manifest_partitions: dict[
        str,
        dict[str, Any],
    ] = {}

    for partition_name in PARTITION_NAMES:
        rows_in_partition = partition_rows[
            partition_name
        ]

        group_ids = sorted({
            row["metadata"]["split_group_id"]
            for row in rows_in_partition
        })

        manifest_partitions[
            partition_name
        ] = {
            "row_count": len(
                rows_in_partition
            ),
            "group_count": len(group_ids),
            "group_ids": group_ids,
            "class_row_counts": dict(sorted(
                Counter(
                    row["labels"]["fault_type"]
                    for row in rows_in_partition
                ).items()
            )),
            "class_group_counts": {
                label: sum(
                    label in group_labels[
                        group_id
                    ]
                    for group_id in group_ids
                )
                for label in required_fault_types
            },
        }

    return SplitResult(
        partitions={
            name: tuple(partition_rows[name])
            for name in PARTITION_NAMES
        },
        manifest={
            "schema_version": 2,
            "algorithm": (
                "complete_context_group_hash_v2"
            ),
            "source_dataset_schema_version": (
                dataset_schema_version
            ),
            "seed": seed,
            "ratios": ratios,
            "source_row_count": len(
                validated_rows
            ),
            "source_group_count": len(
                group_partitions
            ),
            "class_count": len(
                required_fault_types
            ),
            "required_fault_types": (
                required_fault_types
            ),
            "source_group_class_coverage": {
                group_id: sorted(labels)
                for group_id, labels
                in sorted(group_labels.items())
            },
            "partitions": (
                manifest_partitions
            ),
        },
    )


def read_dataset_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    if not path.is_file():
        raise DatasetSplitError(
            f"Dataset does not exist: {path}"
        )

    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(
            encoding="utf-8"
        ).splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise DatasetSplitError(
                "Invalid JSON on line "
                f"{line_number}: {error.msg}"
            ) from error

        if not isinstance(row, dict):
            raise DatasetSplitError(
                f"Line {line_number} is not "
                "a JSON object."
            )

        rows.append(row)

    return rows


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


def sha256_text(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def write_group_aware_split(
    input_path: Path,
    output_directory: Path,
    *,
    seed: int = DEFAULT_SEED,
    train_ratio: float = 0.6,
    validation_ratio: float = 0.2,
    test_ratio: float = 0.2,
    expected_fault_types: (
        Sequence[str] | None
    ) = None,
) -> dict[str, Any]:
    if output_directory.exists():
        raise DatasetSplitError(
            "Output directory already exists: "
            f"{output_directory}"
        )

    if not input_path.is_file():
        raise DatasetSplitError(
            f"Dataset does not exist: "
            f"{input_path}"
        )

    source_text = input_path.read_text(
        encoding="utf-8"
    )
    rows = read_dataset_jsonl(input_path)

    result = plan_group_aware_split(
        rows,
        seed=seed,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        test_ratio=test_ratio,
        expected_fault_types=(
            expected_fault_types
        ),
    )

    payloads = {
        f"{name}.jsonl": jsonl_payload(
            result.partitions[name]
        )
        for name in PARTITION_NAMES
    }

    manifest = dict(result.manifest)
    manifest["source"] = {
        "path": str(input_path),
        "sha256": sha256_text(source_text),
    }
    manifest["outputs"] = {
        file_name: {
            "sha256": sha256_text(payload),
        }
        for file_name, payload
        in payloads.items()
    }

    output_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    for file_name, payload in (
        payloads.items()
    ):
        (
            output_directory / file_name
        ).write_text(
            payload,
            encoding="utf-8",
        )

    (
        output_directory
        / "split_manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create a deterministic, "
            "complete-context, group-aware "
            "train/validation/test split."
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.6,
    )
    parser.add_argument(
        "--validation-ratio",
        type=float,
        default=0.2,
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.2,
    )
    parser.add_argument(
        "--required-fault-type",
        dest="expected_fault_types",
        action="append",
        help=(
            "Required source fault_type. Repeat "
            "once per expected class."
        ),
    )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        manifest = write_group_aware_split(
            arguments.input,
            arguments.output_dir,
            seed=arguments.seed,
            train_ratio=(
                arguments.train_ratio
            ),
            validation_ratio=(
                arguments.validation_ratio
            ),
            test_ratio=(
                arguments.test_ratio
            ),
            expected_fault_types=(
                arguments.expected_fault_types
            ),
        )
    except (
        DatasetSplitError,
        OSError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1

    print(
        json.dumps(
            manifest,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
