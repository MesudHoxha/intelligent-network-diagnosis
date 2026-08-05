from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from jsonschema import Draft202012Validator

from src.dataset.contract import (
    DatasetContractError,
    validate_dataset_row,
)
from src.dataset.splitter import PARTITION_NAMES


METHOD_EVALUATION_RESULT_SCHEMA_VERSION = 1
SUPPORTED_METHODS = (
    "rule_based",
    "machine_learning",
    "hybrid",
)
DEFAULT_CLASS_ORDER = (
    "no_fault",
    "missing_static_route",
    "wrong_next_hop",
)
PARTITION_USES = {
    "train": "development",
    "validation": "selection",
    "test": "report_only",
}


class EvaluationReportingError(ValueError):
    """Raised when comparable evaluation reporting is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise EvaluationReportingError(
            f"Required artifact does not exist: {path}"
        )

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise EvaluationReportingError(
            f"Required JSON artifact does not exist: {path}"
        )

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise EvaluationReportingError(
            f"Invalid JSON in {path}: {error.msg}"
        ) from error

    if not isinstance(value, dict):
        raise EvaluationReportingError(
            f"Expected a JSON object in: {path}"
        )

    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise EvaluationReportingError(
            f"Required JSONL artifact does not exist: {path}"
        )

    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise EvaluationReportingError(
                f"Invalid JSON on line {line_number} "
                f"of {path}: {error.msg}"
            ) from error

        if not isinstance(value, dict):
            raise EvaluationReportingError(
                f"Line {line_number} of {path} is not "
                "a JSON object."
            )

        rows.append(value)

    return rows


def require_mapping(
    value: object,
    reference: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvaluationReportingError(
            f"{reference} must be an object."
        )

    return value


def require_non_empty_string(
    value: object,
    reference: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationReportingError(
            f"{reference} must be a non-empty string."
        )

    return value


def require_boolean(
    value: object,
    reference: str,
) -> bool:
    if not isinstance(value, bool):
        raise EvaluationReportingError(
            f"{reference} must be a boolean."
        )

    return value


def safe_rate(
    numerator: int,
    denominator: int,
) -> float:
    if denominator == 0:
        return 0.0

    return numerator / denominator


def compute_classification_metrics(
    records: Sequence[Mapping[str, Any]],
    class_order: Sequence[str],
) -> dict[str, Any]:
    labels = tuple(class_order)

    if not labels or len(set(labels)) != len(labels):
        raise EvaluationReportingError(
            "class_order must contain unique labels."
        )

    label_set = set(labels)
    matrix = [
        [0 for _ in labels]
        for _ in labels
    ]
    label_indexes = {
        label: index
        for index, label in enumerate(labels)
    }

    for index, record in enumerate(records, start=1):
        expected = record.get("expected_fault_type")
        predicted = record.get("predicted_fault_type")

        if expected not in label_set:
            raise EvaluationReportingError(
                f"Record {index} has unsupported expected class: "
                f"{expected!r}."
            )
        if predicted not in label_set:
            raise EvaluationReportingError(
                f"Record {index} has unsupported predicted class: "
                f"{predicted!r}."
            )

        assert isinstance(expected, str)
        assert isinstance(predicted, str)
        matrix[label_indexes[expected]][
            label_indexes[predicted]
        ] += 1

    total = len(records)
    correct = sum(
        matrix[index][index]
        for index in range(len(labels))
    )
    per_class: dict[str, Any] = {}

    for index, label in enumerate(labels):
        true_positive = matrix[index][index]
        false_positive = sum(
            matrix[row][index]
            for row in range(len(labels))
            if row != index
        )
        false_negative = sum(
            matrix[index][column]
            for column in range(len(labels))
            if column != index
        )
        support = sum(matrix[index])
        precision = safe_rate(
            true_positive,
            true_positive + false_positive,
        )
        recall = safe_rate(
            true_positive,
            true_positive + false_negative,
        )
        f1 = safe_rate(
            2 * precision * recall,
            precision + recall,
        )

        per_class[label] = {
            "support": support,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    class_count = len(labels)
    macro = {
        metric: sum(
            per_class[label][metric]
            for label in labels
        ) / class_count
        for metric in (
            "precision",
            "recall",
            "f1",
        )
    }

    return {
        "sample_count": total,
        "correct_count": correct,
        "accuracy": safe_rate(correct, total),
        "macro": macro,
        "per_class": per_class,
        "confusion_matrix": {
            "actual_labels": list(labels),
            "predicted_labels": list(labels),
            "values": matrix,
        },
        "zero_division_policy": 0.0,
    }


def compute_diagnostic_checks(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    exact_values = [
        require_boolean(
            record.get("exact_match"),
            "record.exact_match",
        )
        for record in records
    ]
    fault_records = [
        record
        for record in records
        if record.get("expected_fault_type") != "no_fault"
    ]
    prefix_values = [
        require_boolean(
            record.get("affected_prefix_correct"),
            "record.affected_prefix_correct",
        )
        for record in fault_records
    ]

    exact_correct = sum(exact_values)
    prefix_correct = sum(prefix_values)

    return {
        "exact_diagnosis_match": {
            "applicable_count": len(exact_values),
            "correct_count": exact_correct,
            "rate": safe_rate(
                exact_correct,
                len(exact_values),
            ),
        },
        "affected_prefix_fault_only": {
            "applicable_count": len(prefix_values),
            "correct_count": prefix_correct,
            "rate": safe_rate(
                prefix_correct,
                len(prefix_values),
            ),
        },
    }


def build_metrics_summary(
    records: Sequence[Mapping[str, Any]],
    class_order: Sequence[str],
) -> dict[str, Any]:
    return {
        "classification": compute_classification_metrics(
            records,
            class_order,
        ),
        "diagnostic_checks": compute_diagnostic_checks(
            records
        ),
    }


def artifact_reference(path: Path) -> dict[str, str]:
    return {
        "path": str(path),
        "sha256": sha256_file(path),
    }


def normalize_predicted_fault_type(
    evaluation: Mapping[str, Any],
) -> str:
    predicted = require_mapping(
        evaluation.get("predicted"),
        "evaluation.predicted",
    )
    predicted_status = predicted.get("status")
    predicted_fault_type = predicted.get("fault_type")

    if predicted_status == "NO_FAULT_DETECTED":
        if predicted_fault_type is not None:
            raise EvaluationReportingError(
                "NO_FAULT_DETECTED cannot include a predicted "
                "fault_type."
            )
        return "no_fault"

    return require_non_empty_string(
        predicted_fault_type,
        "evaluation.predicted.fault_type",
    )


def validate_method_evaluation_result(
    result: Mapping[str, Any],
) -> None:
    if result.get("schema_version") != (
        METHOD_EVALUATION_RESULT_SCHEMA_VERSION
    ):
        raise EvaluationReportingError(
            "Method evaluation schema_version must be 1."
        )

    method = require_mapping(
        result.get("method"),
        "method",
    )
    method_id = method.get("method_id")
    if method_id not in SUPPORTED_METHODS:
        raise EvaluationReportingError(
            "Unsupported method_id."
        )

    policy = require_mapping(
        result.get("evaluation_policy"),
        "evaluation_policy",
    )
    if policy.get("selection_partitions") != [
        "train",
        "validation",
    ]:
        raise EvaluationReportingError(
            "Only train and validation may be used for "
            "method selection."
        )
    if policy.get("held_out_partition") != "test":
        raise EvaluationReportingError(
            "The held-out partition must be test."
        )
    if policy.get("test_use") != "report_only":
        raise EvaluationReportingError(
            "The test partition must be report_only."
        )

    class_order_value = policy.get("class_order")
    if (
        not isinstance(class_order_value, list)
        or not class_order_value
        or any(
            not isinstance(label, str) or not label
            for label in class_order_value
        )
        or len(set(class_order_value))
        != len(class_order_value)
    ):
        raise EvaluationReportingError(
            "evaluation_policy.class_order is invalid."
        )

    records_value = result.get("records")
    if not isinstance(records_value, list) or not records_value:
        raise EvaluationReportingError(
            "records must be a non-empty array."
        )

    seen_samples: set[str] = set()
    partition_records: dict[str, list[Mapping[str, Any]]] = {
        name: []
        for name in PARTITION_NAMES
    }

    for index, value in enumerate(records_value, start=1):
        record = require_mapping(
            value,
            f"records[{index}]",
        )
        sample_id = require_non_empty_string(
            record.get("sample_id"),
            f"records[{index}].sample_id",
        )
        if sample_id in seen_samples:
            raise EvaluationReportingError(
                f"Duplicate sample_id: {sample_id}"
            )
        seen_samples.add(sample_id)

        partition = record.get("partition")
        if partition not in PARTITION_NAMES:
            raise EvaluationReportingError(
                f"records[{index}].partition is invalid."
            )

        expected_fault_type = record.get(
            "expected_fault_type"
        )
        predicted_fault_type = record.get(
            "predicted_fault_type"
        )
        if expected_fault_type not in class_order_value:
            raise EvaluationReportingError(
                f"records[{index}].expected_fault_type "
                "is invalid."
            )
        if predicted_fault_type not in class_order_value:
            raise EvaluationReportingError(
                f"records[{index}].predicted_fault_type "
                "is invalid."
            )
        classification_correct = require_boolean(
            record.get("classification_correct"),
            f"records[{index}].classification_correct",
        )
        if classification_correct is not (
            expected_fault_type == predicted_fault_type
        ):
            raise EvaluationReportingError(
                f"records[{index}].classification_correct "
                "does not match its classes."
            )
        require_boolean(
            record.get("exact_match"),
            f"records[{index}].exact_match",
        )
        require_boolean(
            record.get("affected_prefix_correct"),
            f"records[{index}].affected_prefix_correct",
        )
        assert isinstance(partition, str)
        partition_records[partition].append(record)

    partitions = require_mapping(
        result.get("partitions"),
        "partitions",
    )
    if set(partitions) != set(PARTITION_NAMES):
        raise EvaluationReportingError(
            "partitions must contain train, validation, and test."
        )

    for partition_name in PARTITION_NAMES:
        summary = require_mapping(
            partitions[partition_name],
            f"partitions.{partition_name}",
        )
        if summary.get("use") != (
            PARTITION_USES[partition_name]
        ):
            raise EvaluationReportingError(
                f"partitions.{partition_name}.use is invalid."
            )
        if summary.get("row_count") != len(
            partition_records[partition_name]
        ):
            raise EvaluationReportingError(
                f"partitions.{partition_name}.row_count "
                "does not match records."
            )
        observed_group_ids = sorted({
            require_non_empty_string(
                record.get("split_group_id"),
                "record.split_group_id",
            )
            for record
            in partition_records[partition_name]
        })
        if summary.get("group_ids") != observed_group_ids:
            raise EvaluationReportingError(
                f"partitions.{partition_name}.group_ids "
                "do not match records."
            )
        if summary.get("group_count") != len(
            observed_group_ids
        ):
            raise EvaluationReportingError(
                f"partitions.{partition_name}.group_count "
                "does not match records."
            )

        expected_metrics = build_metrics_summary(
            partition_records[partition_name],
            class_order_value,
        )
        if summary.get("metrics") != expected_metrics:
            raise EvaluationReportingError(
                f"partitions.{partition_name}.metrics "
                "do not match records."
            )

    overall = require_mapping(
        result.get("overall"),
        "overall",
    )
    if overall.get("use") != "descriptive_only":
        raise EvaluationReportingError(
            "overall.use must be descriptive_only."
        )
    if overall.get("row_count") != len(records_value):
        raise EvaluationReportingError(
            "overall.row_count does not match records."
        )
    if overall.get("metrics") != build_metrics_summary(
        records_value,
        class_order_value,
    ):
        raise EvaluationReportingError(
            "overall.metrics do not match records."
        )

    dataset_binding = require_mapping(
        result.get("dataset_binding"),
        "dataset_binding",
    )
    merged_dataset = require_mapping(
        dataset_binding.get("merged_dataset"),
        "dataset_binding.merged_dataset",
    )
    if merged_dataset.get("row_count") != len(records_value):
        raise EvaluationReportingError(
            "Merged dataset row_count does not match records."
        )
    split_binding = require_mapping(
        dataset_binding.get("split"),
        "dataset_binding.split",
    )
    if split_binding.get("no_cross_partition_group") is not True:
        raise EvaluationReportingError(
            "Dataset binding must confirm no group leakage."
        )
    partition_bindings = require_mapping(
        split_binding.get("partitions"),
        "dataset_binding.split.partitions",
    )
    if set(partition_bindings) != set(PARTITION_NAMES):
        raise EvaluationReportingError(
            "Dataset binding must contain all partitions."
        )
    for partition_name in PARTITION_NAMES:
        partition_binding = require_mapping(
            partition_bindings[partition_name],
            "dataset_binding.split.partitions."
            f"{partition_name}",
        )
        summary = require_mapping(
            partitions[partition_name],
            f"partitions.{partition_name}",
        )
        for key in (
            "row_count",
            "group_count",
            "group_ids",
        ):
            if partition_binding.get(key) != summary.get(key):
                raise EvaluationReportingError(
                    "Dataset and evaluation partition "
                    f"bindings disagree for {partition_name}.{key}."
                )

    provenance = require_mapping(
        result.get("provenance"),
        "provenance",
    )
    if method_id == "rule_based":
        require_mapping(
            provenance.get("rule_audit"),
            "provenance.rule_audit",
        )
    elif (
        method_id == "machine_learning"
        and provenance.get("rule_audit") is None
    ):
        for artifact_name in (
            "feature_matrix",
            "selection_result",
            "model_artifact",
        ):
            require_mapping(
                provenance.get(artifact_name),
                f"provenance.{artifact_name}",
            )
    if provenance.get("input_record_count") != len(
        records_value
    ):
        raise EvaluationReportingError(
            "provenance.input_record_count does not match records."
        )
    if provenance.get("artifact_reference_count") != (
        len(records_value) * 5
    ):
        raise EvaluationReportingError(
            "provenance.artifact_reference_count must be five "
            "per record."
        )


def validate_against_schema(
    result: Mapping[str, Any],
    schema_path: Path,
) -> None:
    schema = read_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(result),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        first = errors[0]
        location = ".".join(
            str(item)
            for item in first.absolute_path
        ) or "<root>"
        raise EvaluationReportingError(
            "Method evaluation result fails JSON Schema at "
            f"{location}: {first.message}"
        )


def build_partition_summary(
    partition_name: str,
    records: Sequence[Mapping[str, Any]],
    group_ids: Sequence[str],
    class_order: Sequence[str],
) -> dict[str, Any]:
    return {
        "use": PARTITION_USES[partition_name],
        "row_count": len(records),
        "group_count": len(group_ids),
        "group_ids": sorted(group_ids),
        "metrics": build_metrics_summary(
            records,
            class_order,
        ),
    }


def build_method_evaluation_result(
    *,
    result_id: str,
    method: Mapping[str, Any],
    dataset_binding: Mapping[str, Any],
    provenance: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    partition_group_ids: Mapping[str, Sequence[str]],
    class_order: Sequence[str] = DEFAULT_CLASS_ORDER,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    require_non_empty_string(result_id, "result_id")
    method_id = method.get("method_id")
    if method_id not in SUPPORTED_METHODS:
        raise EvaluationReportingError(
            "method.method_id is unsupported."
        )

    copied_records = [dict(record) for record in records]
    partition_records = {
        name: [
            record
            for record in copied_records
            if record.get("partition") == name
        ]
        for name in PARTITION_NAMES
    }

    partitions = {
        name: build_partition_summary(
            name,
            partition_records[name],
            partition_group_ids[name],
            class_order,
        )
        for name in PARTITION_NAMES
    }

    result = {
        "schema_version": (
            METHOD_EVALUATION_RESULT_SCHEMA_VERSION
        ),
        "result_id": result_id,
        "generated_at_utc": generated_at_utc or utc_now(),
        "status": "COMPLETED",
        "method": dict(method),
        "dataset_binding": dict(dataset_binding),
        "provenance": dict(provenance),
        "evaluation_policy": {
            "target": "fault_type",
            "class_order": list(class_order),
            "primary_metric": "macro_f1",
            "reported_classification_metrics": [
                "accuracy",
                "macro_precision",
                "macro_recall",
                "macro_f1",
                "per_class_precision",
                "per_class_recall",
                "per_class_f1",
                "confusion_matrix",
            ],
            "zero_division_policy": 0.0,
            "selection_partitions": [
                "train",
                "validation",
            ],
            "held_out_partition": "test",
            "test_use": "report_only",
            "overall_use": "descriptive_only",
        },
        "partitions": partitions,
        "overall": {
            "use": "descriptive_only",
            "row_count": len(copied_records),
            "metrics": build_metrics_summary(
                copied_records,
                class_order,
            ),
        },
        "records": copied_records,
        "limitations": [
            "The accepted dataset has only 30 rows, three "
            "classes, and five controlled deterministic "
            "laboratory contexts.",
            "Validation and test each contain one context "
            "with two repetitions per class; row-level "
            "repetitions are not independent topology samples.",
            "The test partition is report-only and cannot be "
            "used for feature, rule, threshold, or model "
            "selection.",
            "These results establish an internal controlled "
            "baseline, not real-world generalization or "
            "method superiority.",
        ],
    }

    validate_method_evaluation_result(result)
    return result


def validate_artifact_path(
    path: Path,
    experiment_directory: Path,
    relative_path: Path,
) -> Path:
    expected = (
        experiment_directory / relative_path
    ).resolve()
    actual = path.resolve()

    if actual != expected:
        raise EvaluationReportingError(
            f"Unexpected artifact path: {actual}; "
            f"expected {expected}."
        )

    sha256_file(actual)
    return actual


def collect_partition_rows(
    split_manifest: Mapping[str, Any],
    split_directory: Path,
    class_order: Sequence[str],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[str]],
    dict[str, dict[str, Any]],
]:
    manifest_partitions = require_mapping(
        split_manifest.get("partitions"),
        "split_manifest.partitions",
    )
    outputs = require_mapping(
        split_manifest.get("outputs"),
        "split_manifest.outputs",
    )
    expected_class_set = set(class_order)
    sample_rows: dict[str, dict[str, Any]] = {}
    partition_group_ids: dict[str, list[str]] = {}
    partition_bindings: dict[str, dict[str, Any]] = {}
    all_group_ids: set[str] = set()

    for partition_name in PARTITION_NAMES:
        partition = require_mapping(
            manifest_partitions.get(partition_name),
            f"split_manifest.partitions.{partition_name}",
        )
        file_name = f"{partition_name}.jsonl"
        output = require_mapping(
            outputs.get(file_name),
            f"split_manifest.outputs.{file_name}",
        )
        output_path = split_directory / file_name
        output_sha256 = sha256_file(output_path)
        if output.get("sha256") != output_sha256:
            raise EvaluationReportingError(
                f"Split partition hash mismatch: {file_name}"
            )

        rows = read_jsonl(output_path)
        if partition.get("row_count") != len(rows):
            raise EvaluationReportingError(
                f"Split {partition_name} row_count mismatch."
            )

        group_ids_value = partition.get("group_ids")
        if (
            not isinstance(group_ids_value, list)
            or any(
                not isinstance(group_id, str)
                or not group_id
                for group_id in group_ids_value
            )
        ):
            raise EvaluationReportingError(
                f"Split {partition_name} group_ids are invalid."
            )
        group_ids = sorted(group_ids_value)
        if len(group_ids) != partition.get("group_count"):
            raise EvaluationReportingError(
                f"Split {partition_name} group_count mismatch."
            )
        overlap = all_group_ids & set(group_ids)
        if overlap:
            raise EvaluationReportingError(
                "A split_group_id crosses partitions: "
                + ", ".join(sorted(overlap))
            )
        all_group_ids.update(group_ids)

        observed_class_counts: Counter[str] = Counter()
        observed_groups: set[str] = set()

        for row_number, row in enumerate(rows, start=1):
            try:
                validate_dataset_row(row)
            except DatasetContractError as error:
                raise EvaluationReportingError(
                    f"Invalid Dataset Row in {file_name} "
                    f"at row {row_number}: {error}"
                ) from error

            sample_id = require_non_empty_string(
                row.get("sample_id"),
                f"{file_name} row {row_number} sample_id",
            )
            if sample_id in sample_rows:
                raise EvaluationReportingError(
                    f"Duplicate split sample_id: {sample_id}"
                )
            metadata = require_mapping(
                row.get("metadata"),
                f"{file_name} row {row_number} metadata",
            )
            labels = require_mapping(
                row.get("labels"),
                f"{file_name} row {row_number} labels",
            )
            group_id = require_non_empty_string(
                metadata.get("split_group_id"),
                f"{file_name} row {row_number} split_group_id",
            )
            fault_type = require_non_empty_string(
                labels.get("fault_type"),
                f"{file_name} row {row_number} fault_type",
            )
            if group_id not in group_ids:
                raise EvaluationReportingError(
                    f"{sample_id} has an unexpected split group."
                )
            if fault_type not in expected_class_set:
                raise EvaluationReportingError(
                    f"{sample_id} has an unsupported fault type."
                )

            observed_groups.add(group_id)
            observed_class_counts[fault_type] += 1
            sample_rows[sample_id] = {
                "partition": partition_name,
                "split_group_id": group_id,
                "fault_type": fault_type,
            }

        if observed_groups != set(group_ids):
            raise EvaluationReportingError(
                f"Split {partition_name} group coverage mismatch."
            )
        if partition.get("class_row_counts") != dict(
            sorted(observed_class_counts.items())
        ):
            raise EvaluationReportingError(
                f"Split {partition_name} class counts mismatch."
            )

        partition_group_ids[partition_name] = group_ids
        partition_bindings[partition_name] = {
            "path": str(output_path),
            "sha256": output_sha256,
            "row_count": len(rows),
            "group_count": len(group_ids),
            "group_ids": group_ids,
        }

    return (
        sample_rows,
        partition_group_ids,
        partition_bindings,
    )


def build_rule_based_baseline_report(
    *,
    campaign_result_path: Path,
    output_path: Path,
    schema_path: Path,
    result_id: str = "p3_r0_rule_based_baseline_v1",
    expected_campaign_run_id: str | None = None,
    expected_dataset_sha256: str | None = None,
) -> dict[str, Any]:
    if output_path.exists():
        raise EvaluationReportingError(
            f"Output already exists: {output_path}"
        )

    campaign_result_path = campaign_result_path.resolve()
    campaign = read_json(campaign_result_path)
    if campaign.get("status") != "COMPLETED":
        raise EvaluationReportingError(
            "Campaign result must be COMPLETED."
        )

    campaign_run_id = require_non_empty_string(
        campaign.get("campaign_run_id"),
        "campaign_result.campaign_run_id",
    )
    if (
        expected_campaign_run_id is not None
        and campaign_run_id != expected_campaign_run_id
    ):
        raise EvaluationReportingError(
            "Campaign run does not match the accepted binding."
        )

    campaign_id = require_non_empty_string(
        campaign.get("campaign_id"),
        "campaign_result.campaign_id",
    )
    merged = require_mapping(
        campaign.get("merged_dataset"),
        "campaign_result.merged_dataset",
    )
    merged_path = Path(require_non_empty_string(
        merged.get("path"),
        "campaign_result.merged_dataset.path",
    )).resolve()
    merged_sha256 = sha256_file(merged_path)
    if merged.get("sha256") != merged_sha256:
        raise EvaluationReportingError(
            "Merged dataset hash does not match the campaign."
        )
    if (
        expected_dataset_sha256 is not None
        and merged_sha256 != expected_dataset_sha256
    ):
        raise EvaluationReportingError(
            "Merged dataset does not match the accepted binding."
        )

    rule_summary = require_mapping(
        campaign.get("rule_audit"),
        "campaign_result.rule_audit",
    )
    rule_audit_path = Path(require_non_empty_string(
        rule_summary.get("path"),
        "campaign_result.rule_audit.path",
    )).resolve()
    rule_audit = read_json(rule_audit_path)
    if rule_audit.get("method") != "rule_based":
        raise EvaluationReportingError(
            "P2 rule audit method must be rule_based."
        )
    if rule_audit.get("campaign_run_id") != campaign_run_id:
        raise EvaluationReportingError(
            "Rule audit campaign_run_id mismatch."
        )
    if rule_audit.get("campaign_id") != campaign_id:
        raise EvaluationReportingError(
            "Rule audit campaign_id mismatch."
        )

    split_summary = require_mapping(
        campaign.get("split"),
        "campaign_result.split",
    )
    split_manifest_path = Path(require_non_empty_string(
        split_summary.get("manifest_path"),
        "campaign_result.split.manifest_path",
    )).resolve()
    split_manifest = read_json(split_manifest_path)
    source = require_mapping(
        split_manifest.get("source"),
        "split_manifest.source",
    )
    if source.get("sha256") != merged_sha256:
        raise EvaluationReportingError(
            "Split source does not match the merged dataset."
        )

    required_fault_types = split_manifest.get(
        "required_fault_types"
    )
    if (
        not isinstance(required_fault_types, list)
        or set(required_fault_types)
        != set(DEFAULT_CLASS_ORDER)
    ):
        raise EvaluationReportingError(
            "Split fault-type coverage is not the frozen "
            "three-class set."
        )

    (
        sample_rows,
        partition_group_ids,
        partition_bindings,
    ) = collect_partition_rows(
        split_manifest,
        split_manifest_path.parent,
        DEFAULT_CLASS_ORDER,
    )

    audit_records = rule_audit.get("records")
    if not isinstance(audit_records, list):
        raise EvaluationReportingError(
            "Rule audit records must be an array."
        )
    if rule_audit.get("record_count") != len(audit_records):
        raise EvaluationReportingError(
            "Rule audit record_count mismatch."
        )

    report_records: list[dict[str, Any]] = []
    observed_sample_ids: set[str] = set()

    for index, value in enumerate(audit_records, start=1):
        audit_record = require_mapping(
            value,
            f"rule_audit.records[{index}]",
        )
        sample_id = require_non_empty_string(
            audit_record.get("sample_id"),
            f"rule_audit.records[{index}].sample_id",
        )
        if sample_id in observed_sample_ids:
            raise EvaluationReportingError(
                f"Duplicate rule-audit sample_id: {sample_id}"
            )
        observed_sample_ids.add(sample_id)
        if sample_id not in sample_rows:
            raise EvaluationReportingError(
                f"Rule-audit sample is absent from split: {sample_id}"
            )
        row_binding = sample_rows[sample_id]

        if audit_record.get("fault_type") != (
            row_binding["fault_type"]
        ):
            raise EvaluationReportingError(
                f"Rule-audit label mismatch for {sample_id}."
            )
        if audit_record.get("split_group_id") != (
            row_binding["split_group_id"]
        ):
            raise EvaluationReportingError(
                f"Rule-audit split group mismatch for {sample_id}."
            )

        evaluation_path = Path(require_non_empty_string(
            audit_record.get("evaluation_path"),
            f"rule_audit.records[{index}].evaluation_path",
        )).resolve()
        experiment_directory = evaluation_path.parent.parent
        validate_artifact_path(
            evaluation_path,
            experiment_directory,
            Path("evaluation/rule_based.json"),
        )
        evaluation = read_json(evaluation_path)
        if evaluation.get("method") != "rule_based":
            raise EvaluationReportingError(
                f"Evaluation method mismatch for {sample_id}."
            )
        expected = require_mapping(
            evaluation.get("expected"),
            f"evaluation.expected for {sample_id}",
        )
        if expected.get("fault_type") != row_binding["fault_type"]:
            raise EvaluationReportingError(
                f"Evaluation label mismatch for {sample_id}."
            )
        predicted_fault_type = normalize_predicted_fault_type(
            evaluation
        )
        if predicted_fault_type not in DEFAULT_CLASS_ORDER:
            raise EvaluationReportingError(
                f"Unsupported predicted class for {sample_id}."
            )

        evaluation_metrics = require_mapping(
            evaluation.get("metrics"),
            f"evaluation.metrics for {sample_id}",
        )
        exact_match = require_boolean(
            evaluation_metrics.get("exact_match"),
            f"evaluation.metrics.exact_match for {sample_id}",
        )
        affected_prefix_correct = require_boolean(
            evaluation_metrics.get("affected_prefix_correct"),
            "evaluation.metrics.affected_prefix_correct "
            f"for {sample_id}",
        )
        if audit_record.get("exact_match") is not exact_match:
            raise EvaluationReportingError(
                f"Rule-audit exact_match mismatch for {sample_id}."
            )
        if audit_record.get(
            "affected_prefix_correct"
        ) is not affected_prefix_correct:
            raise EvaluationReportingError(
                "Rule-audit affected-prefix mismatch for "
                f"{sample_id}."
            )

        artifact_paths = {
            "experiment_manifest": validate_artifact_path(
                experiment_directory / "manifest.json",
                experiment_directory,
                Path("manifest.json"),
            ),
            "ground_truth": validate_artifact_path(
                experiment_directory / "ground_truth.json",
                experiment_directory,
                Path("ground_truth.json"),
            ),
            "evidence": validate_artifact_path(
                experiment_directory / "parsed/evidence.json",
                experiment_directory,
                Path("parsed/evidence.json"),
            ),
            "prediction": validate_artifact_path(
                experiment_directory
                / "diagnosis/rule_based.json",
                experiment_directory,
                Path("diagnosis/rule_based.json"),
            ),
            "evaluation": evaluation_path,
        }

        report_records.append({
            "sample_id": sample_id,
            "partition": row_binding["partition"],
            "split_group_id": row_binding["split_group_id"],
            "expected_fault_type": row_binding["fault_type"],
            "predicted_fault_type": predicted_fault_type,
            "classification_correct": (
                predicted_fault_type
                == row_binding["fault_type"]
            ),
            "exact_match": exact_match,
            "affected_prefix_correct": (
                affected_prefix_correct
            ),
            "artifacts": {
                name: artifact_reference(path)
                for name, path in artifact_paths.items()
            },
        })

    if observed_sample_ids != set(sample_rows):
        missing = sorted(set(sample_rows) - observed_sample_ids)
        raise EvaluationReportingError(
            "Split samples are missing from the rule audit: "
            + ", ".join(missing)
        )

    partition_order = {
        name: index
        for index, name in enumerate(PARTITION_NAMES)
    }
    report_records.sort(
        key=lambda record: (
            partition_order[record["partition"]],
            record["sample_id"],
        )
    )

    dataset_binding = {
        "campaign_id": campaign_id,
        "campaign_run_id": campaign_run_id,
        "dataset_row_schema_version": campaign.get(
            "dataset_row_schema_version"
        ),
        "merged_dataset": {
            "path": str(merged_path),
            "sha256": merged_sha256,
            "row_count": len(sample_rows),
        },
        "split": {
            "algorithm": split_manifest.get("algorithm"),
            "seed": split_manifest.get("seed"),
            "ratios": split_manifest.get("ratios"),
            "manifest_path": str(split_manifest_path),
            "manifest_sha256": sha256_file(
                split_manifest_path
            ),
            "partitions": partition_bindings,
            "no_cross_partition_group": True,
        },
    }
    provenance = {
        "campaign_result": artifact_reference(
            campaign_result_path
        ),
        "rule_audit": artifact_reference(
            rule_audit_path
        ),
        "split_manifest": artifact_reference(
            split_manifest_path
        ),
        "input_record_count": len(report_records),
        "artifact_reference_count": (
            len(report_records) * 5
        ),
    }
    result = build_method_evaluation_result(
        result_id=result_id,
        method={
            "method_id": "rule_based",
            "family": "traditional",
            "implementation_id": (
                "deterministic_rule_engine_v1"
            ),
            "trained": False,
            "selection_statement": (
                "The rule engine predates the frozen P2 split; "
                "P3-R0 performs reporting only and changes no "
                "rule, threshold, feature, or prediction."
            ),
        },
        dataset_binding=dataset_binding,
        provenance=provenance,
        records=report_records,
        partition_group_ids=partition_group_ids,
    )
    validate_against_schema(result, schema_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f".{output_path.name}.{uuid4().hex}.tmp"
    )
    try:
        temporary_path.write_text(
            json.dumps(
                result,
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        written = read_json(temporary_path)
        validate_method_evaluation_result(written)
        validate_against_schema(written, schema_path)
        temporary_path.replace(output_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build the partition-aware P3-R0 rule-based "
            "baseline report from accepted P2-R10 artifacts."
        )
    )
    parser.add_argument(
        "--campaign-result",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(
            "schemas/method_evaluation_result_v1.schema.json"
        ),
    )
    parser.add_argument(
        "--result-id",
        default="p3_r0_rule_based_baseline_v1",
    )
    parser.add_argument(
        "--expected-campaign-run-id",
    )
    parser.add_argument(
        "--expected-dataset-sha256",
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        result = build_rule_based_baseline_report(
            campaign_result_path=(
                arguments.campaign_result
            ),
            output_path=arguments.output,
            schema_path=arguments.schema,
            result_id=arguments.result_id,
            expected_campaign_run_id=(
                arguments.expected_campaign_run_id
            ),
            expected_dataset_sha256=(
                arguments.expected_dataset_sha256
            ),
        )
    except (
        EvaluationReportingError,
        OSError,
        TypeError,
        KeyError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1

    summary = {
        "status": result["status"],
        "result_id": result["result_id"],
        "report_path": str(arguments.output),
        "report_sha256": sha256_file(arguments.output),
        "rows": result["overall"]["row_count"],
        "partitions": {
            name: {
                "rows": result["partitions"][name][
                    "row_count"
                ],
                "groups": result["partitions"][name][
                    "group_count"
                ],
                "accuracy": result["partitions"][name][
                    "metrics"
                ]["classification"]["accuracy"],
                "macro_f1": result["partitions"][name][
                    "metrics"
                ]["classification"]["macro"]["f1"],
                "exact_match_rate": result[
                    "partitions"
                ][name]["metrics"]["diagnostic_checks"][
                    "exact_diagnosis_match"
                ]["rate"],
            }
            for name in PARTITION_NAMES
        },
        "test_use": result["evaluation_policy"][
            "test_use"
        ],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
