from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from src.dataset.contract_v3 import (
    DatasetRowV3ContractError,
    validate_dataset_row_v3,
)


PARTITION_NAMES = ("train", "validation", "test")
ALGORITHM = "explicit_complete_context_v1"


class ExplicitSplitV3Error(ValueError):
    """Raised when the frozen Phase 6 split cannot be produced."""


@dataclass(frozen=True)
class ExplicitSplitV3Result:
    partitions: dict[str, tuple[dict[str, Any], ...]]
    manifest: dict[str, Any]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _jsonl_payload(rows: Sequence[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _normalize_allocation(
    allocation: Mapping[str, Sequence[str]],
) -> dict[str, tuple[str, ...]]:
    if set(allocation) != set(PARTITION_NAMES):
        raise ExplicitSplitV3Error(
            "Explicit allocation must contain train, validation, and test."
        )
    normalized: dict[str, tuple[str, ...]] = {}
    seen: set[str] = set()
    for partition in PARTITION_NAMES:
        values = allocation[partition]
        if isinstance(values, (str, bytes)) or not values:
            raise ExplicitSplitV3Error(
                f"Explicit {partition} allocation must be non-empty."
            )
        groups = tuple(values)
        if any(not isinstance(group, str) or not group for group in groups):
            raise ExplicitSplitV3Error(
                f"Explicit {partition} allocation contains an invalid group."
            )
        if len(set(groups)) != len(groups):
            raise ExplicitSplitV3Error(
                f"Explicit {partition} allocation contains duplicate groups."
            )
        overlap = seen.intersection(groups)
        if overlap:
            raise ExplicitSplitV3Error(
                "A split_group_id crosses partitions: "
                + ", ".join(sorted(overlap))
            )
        seen.update(groups)
        normalized[partition] = groups
    return normalized


def plan_explicit_complete_context_split_v3(
    rows: Sequence[dict[str, Any]],
    *,
    allocation: Mapping[str, Sequence[str]],
    expected_fault_types: Sequence[str],
    repetitions_per_class_context: int = 2,
    expected_rows: Mapping[str, int] | None = None,
) -> ExplicitSplitV3Result:
    groups_by_partition = _normalize_allocation(allocation)
    if (
        isinstance(expected_fault_types, (str, bytes))
        or not expected_fault_types
        or any(
            not isinstance(fault_type, str) or not fault_type
            for fault_type in expected_fault_types
        )
        or len(set(expected_fault_types)) != len(expected_fault_types)
    ):
        raise ExplicitSplitV3Error(
            "expected_fault_types must be unique non-empty strings."
        )
    if (
        isinstance(repetitions_per_class_context, bool)
        or not isinstance(repetitions_per_class_context, int)
        or repetitions_per_class_context < 1
    ):
        raise ExplicitSplitV3Error(
            "repetitions_per_class_context must be a positive integer."
        )

    all_expected_groups = {
        group
        for partition_groups in groups_by_partition.values()
        for group in partition_groups
    }
    expected_total = (
        len(all_expected_groups)
        * len(expected_fault_types)
        * repetitions_per_class_context
    )
    if len(rows) != expected_total:
        raise ExplicitSplitV3Error(
            f"Source must contain exactly {expected_total} Dataset Row v3 records."
        )

    sample_ids: set[str] = set()
    group_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()
    validated_rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=1):
        try:
            validate_dataset_row_v3(row)
        except DatasetRowV3ContractError as error:
            raise ExplicitSplitV3Error(
                f"Invalid Dataset Row v3 at row {row_number}: {error}"
            ) from error
        sample_id = row["sample_id"]
        group_id = row["metadata"]["split_group_id"]
        fault_type = row["labels"]["fault_type"]
        if sample_id in sample_ids:
            raise ExplicitSplitV3Error(f"Duplicate sample_id: {sample_id}")
        if group_id not in all_expected_groups:
            raise ExplicitSplitV3Error(
                f"Row {row_number} has an unexpected split_group_id."
            )
        if fault_type not in expected_fault_types:
            raise ExplicitSplitV3Error(
                f"Row {row_number} has an unexpected fault_type."
            )
        if row["provenance"]["mask_id"] is not None:
            raise ExplicitSplitV3Error(
                "The clean Phase 6 split cannot contain masked rows."
            )
        if row["quality"]["masked_missing_count"] != 0:
            raise ExplicitSplitV3Error(
                "The clean Phase 6 split cannot contain masked evidence."
            )
        for quality_field in (
            "experiment_completed",
            "collector_completed",
            "baseline_before_valid",
            "baseline_after_valid",
        ):
            if row["quality"][quality_field] is not True:
                raise ExplicitSplitV3Error(
                    f"Row {row_number} fails quality.{quality_field}."
                )
        sample_ids.add(sample_id)
        group_counts[group_id] += 1
        class_counts[fault_type] += 1
        pair_counts[(group_id, fault_type)] += 1
        validated_rows.append(row)

    if set(group_counts) != all_expected_groups:
        raise ExplicitSplitV3Error(
            "Source groups do not match the frozen explicit allocation."
        )
    expected_rows_per_group = (
        len(expected_fault_types) * repetitions_per_class_context
    )
    if any(count != expected_rows_per_group for count in group_counts.values()):
        raise ExplicitSplitV3Error(
            "Every Phase 6 context must contain a complete class set."
        )
    if any(
        pair_counts[(group_id, fault_type)]
        != repetitions_per_class_context
        for group_id in all_expected_groups
        for fault_type in expected_fault_types
    ):
        raise ExplicitSplitV3Error(
            "Every context/fault_type pair must contain exactly two rows."
        )

    group_partition = {
        group_id: partition
        for partition, group_ids in groups_by_partition.items()
        for group_id in group_ids
    }
    partition_rows: dict[str, list[dict[str, Any]]] = {
        partition: [] for partition in PARTITION_NAMES
    }
    for row in validated_rows:
        partition_rows[
            group_partition[row["metadata"]["split_group_id"]]
        ].append(row)
    for partition in PARTITION_NAMES:
        partition_rows[partition].sort(key=lambda row: row["sample_id"])

    expected_partition_rows = (
        dict(expected_rows)
        if expected_rows is not None
        else {
            partition: len(groups_by_partition[partition])
            * expected_rows_per_group
            for partition in PARTITION_NAMES
        }
    )
    if set(expected_partition_rows) != set(PARTITION_NAMES):
        raise ExplicitSplitV3Error(
            "expected_rows must contain train, validation, and test."
        )

    manifest_partitions: dict[str, dict[str, Any]] = {}
    for partition in PARTITION_NAMES:
        partition_count = len(partition_rows[partition])
        if partition_count != expected_partition_rows[partition]:
            raise ExplicitSplitV3Error(
                f"{partition} must contain exactly "
                f"{expected_partition_rows[partition]} rows."
            )
        group_ids = groups_by_partition[partition]
        manifest_partitions[partition] = {
            "row_count": partition_count,
            "group_count": len(group_ids),
            "group_ids": list(group_ids),
            "class_row_counts": {
                fault_type: len(group_ids) * repetitions_per_class_context
                for fault_type in expected_fault_types
            },
            "usage": (
                "sealed_report_only_after_p6_r6_freeze"
                if partition == "test"
                else "development"
            ),
        }

    manifest = {
        "schema_version": 3,
        "algorithm": ALGORITHM,
        "source_dataset_schema_version": 3,
        "source_row_count": len(validated_rows),
        "source_group_count": len(all_expected_groups),
        "class_count": len(expected_fault_types),
        "required_fault_types": list(expected_fault_types),
        "repetitions_per_class_context": repetitions_per_class_context,
        "clean_unmasked_rows_only": True,
        "no_cross_partition_group": True,
        "partitions": manifest_partitions,
    }
    return ExplicitSplitV3Result(
        partitions={
            partition: tuple(partition_rows[partition])
            for partition in PARTITION_NAMES
        },
        manifest=manifest,
    )


def read_dataset_v3_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ExplicitSplitV3Error(f"Dataset does not exist: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ExplicitSplitV3Error(
                f"Invalid JSON on line {line_number}: {error.msg}"
            ) from error
        if not isinstance(row, dict):
            raise ExplicitSplitV3Error(
                f"Line {line_number} is not a JSON object."
            )
        rows.append(row)
    return rows


def write_explicit_complete_context_split_v3(
    input_path: Path,
    output_directory: Path,
    *,
    allocation: Mapping[str, Sequence[str]],
    expected_fault_types: Sequence[str],
    repetitions_per_class_context: int = 2,
    expected_rows: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    input_path = Path(input_path)
    output_directory = Path(output_directory)
    if output_directory.exists():
        raise ExplicitSplitV3Error(
            f"Output directory already exists: {output_directory}"
        )
    source_text = input_path.read_text(encoding="utf-8")
    result = plan_explicit_complete_context_split_v3(
        read_dataset_v3_jsonl(input_path),
        allocation=allocation,
        expected_fault_types=expected_fault_types,
        repetitions_per_class_context=repetitions_per_class_context,
        expected_rows=expected_rows,
    )
    payloads = {
        f"{partition}.jsonl": _jsonl_payload(result.partitions[partition])
        for partition in PARTITION_NAMES
    }
    manifest = dict(result.manifest)
    manifest["source"] = {
        "path": str(input_path),
        "sha256": _sha256_text(source_text),
    }
    manifest["outputs"] = {
        file_name: {"sha256": _sha256_text(payload)}
        for file_name, payload in payloads.items()
    }

    temporary = output_directory.with_name(
        f".{output_directory.name}.{uuid4().hex}.tmp"
    )
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        for file_name, payload in payloads.items():
            (temporary / file_name).write_text(payload, encoding="utf-8")
        (temporary / "split_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(output_directory)
    except Exception:
        for child in temporary.iterdir() if temporary.exists() else ():
            child.unlink()
        if temporary.exists():
            temporary.rmdir()
        raise
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Write a frozen explicit complete-context Dataset Row v3 split."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allocation-json", type=Path, required=True)
    parser.add_argument(
        "--required-fault-type", dest="expected_fault_types", action="append"
    )
    parser.add_argument("--repetitions", type=int, default=2)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        allocation = json.loads(
            arguments.allocation_json.read_text(encoding="utf-8")
        )
        if not isinstance(allocation, dict):
            raise ExplicitSplitV3Error("Allocation JSON must be an object.")
        manifest = write_explicit_complete_context_split_v3(
            arguments.input,
            arguments.output_dir,
            allocation=allocation,
            expected_fault_types=arguments.expected_fault_types or (),
            repetitions_per_class_context=arguments.repetitions,
        )
    except (ExplicitSplitV3Error, OSError, json.JSONDecodeError) as error:
        print(f"[ERROR] {error}")
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
