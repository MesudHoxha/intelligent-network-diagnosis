from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from jsonschema import Draft202012Validator

from src.dataset.contract import (
    FEATURE_NAMES_V2,
    DatasetContractError,
    validate_dataset_row_v2,
)
from src.dataset.splitter import PARTITION_NAMES


ML_FEATURE_MATRIX_SCHEMA_VERSION = 1
DEFAULT_MATRIX_ID = "p4_r0_ml_feature_matrix_v1"
PROTOCOL_ID = "leakage_safe_ml_baseline_v1"
EXPECTED_CAMPAIGN_ID = "P2_ROUTING_5CTX_V1"
EXPECTED_SPLIT_ALGORITHM = "complete_context_group_hash_v2"
EXPECTED_SPLIT_SEED = 20260730
EXPECTED_SPLIT_RATIOS = {
    "train": 0.6,
    "validation": 0.2,
    "test": 0.2,
}
CLASS_ORDER = (
    "no_fault",
    "missing_static_route",
    "wrong_next_hop",
)
PARTITION_USES = {
    "train": "fit",
    "validation": "selection",
    "test": "report_only",
}
EXPECTED_PARTITION_ROWS = {
    "train": 18,
    "validation": 6,
    "test": 6,
}
EXPECTED_PARTITION_GROUPS = {
    "train": 3,
    "validation": 1,
    "test": 1,
}
RAW_FEATURE_NAMES = FEATURE_NAMES_V2
ENCODED_FEATURE_NAMES = tuple(
    output_name
    for raw_name in RAW_FEATURE_NAMES
    for output_name in (
        f"{raw_name}__available",
        f"{raw_name}__true",
    )
)
TRISTATE_ENCODING = {
    "true": (1, 1),
    "false": (1, 0),
    "unavailable": (0, 0),
}
MODEL_RANDOM_SEED = 20260730


class MLFeatureMatrixError(ValueError):
    """Raised when the frozen ML feature-matrix contract is invalid."""


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise MLFeatureMatrixError(
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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MLFeatureMatrixError(
            f"Required JSON artifact does not exist: {path}"
        )

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MLFeatureMatrixError(
            f"Invalid JSON in {path}: {error.msg}"
        ) from error

    if not isinstance(value, dict):
        raise MLFeatureMatrixError(
            f"Expected a JSON object in: {path}"
        )
    return value


def read_jsonl_with_hashes(
    path: Path,
) -> list[tuple[dict[str, Any], str]]:
    if not path.is_file():
        raise MLFeatureMatrixError(
            f"Required JSONL artifact does not exist: {path}"
        )

    rows: list[tuple[dict[str, Any], str]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise MLFeatureMatrixError(
                f"Invalid JSON on line {line_number} of "
                f"{path}: {error.msg}"
            ) from error
        if not isinstance(value, dict):
            raise MLFeatureMatrixError(
                f"Line {line_number} of {path} is not an object."
            )
        rows.append((value, sha256_text(line)))
    return rows


def require_mapping(
    value: object,
    reference: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MLFeatureMatrixError(
            f"{reference} must be an object."
        )
    return value


def require_non_empty_string(
    value: object,
    reference: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MLFeatureMatrixError(
            f"{reference} must be a non-empty string."
        )
    return value


def artifact_reference(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path.resolve()),
    }


def encode_tristate_features(
    features: Mapping[str, Any],
) -> list[int]:
    if set(features) != set(RAW_FEATURE_NAMES):
        raise MLFeatureMatrixError(
            "Predictor input does not match the seven-feature "
            "Dataset Row v2 whitelist."
        )

    vector: list[int] = []
    for feature_name in RAW_FEATURE_NAMES:
        value = features[feature_name]
        if value not in TRISTATE_ENCODING:
            raise MLFeatureMatrixError(
                f"Unsupported tri-state value for {feature_name}: "
                f"{value!r}"
            )
        vector.extend(TRISTATE_ENCODING[value])
    return vector


def candidate_models() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "logreg_l2_c0_1",
            "family": "multinomial_logistic_regression",
            "complexity_rank": 1,
            "parameters": {
                "C": 0.1,
                "class_weight": None,
                "max_iter": 1000,
                "penalty": "l2",
                "solver": "lbfgs",
            },
        },
        {
            "candidate_id": "logreg_l2_c1",
            "family": "multinomial_logistic_regression",
            "complexity_rank": 2,
            "parameters": {
                "C": 1.0,
                "class_weight": None,
                "max_iter": 1000,
                "penalty": "l2",
                "solver": "lbfgs",
            },
        },
        {
            "candidate_id": "logreg_l2_c10",
            "family": "multinomial_logistic_regression",
            "complexity_rank": 3,
            "parameters": {
                "C": 10.0,
                "class_weight": None,
                "max_iter": 1000,
                "penalty": "l2",
                "solver": "lbfgs",
            },
        },
        {
            "candidate_id": "tree_depth1_leaf1",
            "family": "decision_tree",
            "complexity_rank": 4,
            "parameters": {
                "criterion": "gini",
                "max_depth": 1,
                "min_samples_leaf": 1,
                "splitter": "best",
            },
        },
        {
            "candidate_id": "tree_depth2_leaf1",
            "family": "decision_tree",
            "complexity_rank": 5,
            "parameters": {
                "criterion": "gini",
                "max_depth": 2,
                "min_samples_leaf": 1,
                "splitter": "best",
            },
        },
        {
            "candidate_id": "tree_depth3_leaf2",
            "family": "decision_tree",
            "complexity_rank": 6,
            "parameters": {
                "criterion": "gini",
                "max_depth": 3,
                "min_samples_leaf": 2,
                "splitter": "best",
            },
        },
    ]


def frozen_protocol() -> dict[str, Any]:
    return {
        "protocol_id": PROTOCOL_ID,
        "target_field": "labels.fault_type",
        "class_order": list(CLASS_ORDER),
        "raw_feature_names": list(RAW_FEATURE_NAMES),
        "encoded_feature_names": list(ENCODED_FEATURE_NAMES),
        "encoding": {
            "encoding_id": "tristate_available_true_pair_v1",
            "fit_required": False,
            "output_dtype": "int8_binary",
            "mapping": {
                key: list(value)
                for key, value in TRISTATE_ENCODING.items()
            },
            "invalid_pair": [0, 1],
        },
        "excluded_predictor_sources": [
            "labels",
            "metadata",
            "quality",
            "ground_truth",
            "rule_predictions",
            "evaluation_results",
            "identifiers",
            "paths",
            "hashes",
            "explanation_text",
        ],
        "partition_policy": {
            "fit_partition": "train",
            "selection_partition": "validation",
            "held_out_partition": "test",
            "test_use": "report_only_once_after_pipeline_freeze",
            "refit_on_train_plus_validation": False,
        },
        "selection_policy": {
            "primary_metric": "validation_macro_f1",
            "tie_breakers": [
                "validation_accuracy_desc",
                "complexity_rank_asc",
                "candidate_id_asc",
            ],
            "decision_threshold": "argmax",
            "test_metrics_allowed": False,
        },
        "model_random_seed": MODEL_RANDOM_SEED,
        "candidate_models": candidate_models(),
    }


def validate_against_schema(
    value: Mapping[str, Any],
    schema_path: Path,
) -> None:
    schema = read_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path)
        raise MLFeatureMatrixError(
            "ML Feature Matrix v1 schema validation failed at "
            f"{location or '<root>'}: {first.message}"
        )


def validate_ml_feature_matrix(
    matrix: Mapping[str, Any],
) -> None:
    if matrix.get("schema_version") != (
        ML_FEATURE_MATRIX_SCHEMA_VERSION
    ):
        raise MLFeatureMatrixError(
            "ML feature matrix schema_version must be 1."
        )
    if matrix.get("status") != "COMPLETED":
        raise MLFeatureMatrixError(
            "ML feature matrix status must be COMPLETED."
        )
    if matrix.get("protocol") != frozen_protocol():
        raise MLFeatureMatrixError(
            "The frozen ML protocol does not match P4-R0."
        )

    partitions = require_mapping(
        matrix.get("partitions"),
        "partitions",
    )
    if set(partitions) != set(PARTITION_NAMES):
        raise MLFeatureMatrixError(
            "partitions must contain train, validation, and test."
        )

    all_samples: set[str] = set()
    all_groups: set[str] = set()
    total_rows = 0
    total_unavailable = 0
    for partition_name in PARTITION_NAMES:
        partition = require_mapping(
            partitions[partition_name],
            f"partitions.{partition_name}",
        )
        if partition.get("use") != PARTITION_USES[partition_name]:
            raise MLFeatureMatrixError(
                f"Invalid use for {partition_name}."
            )
        records = partition.get("records")
        if not isinstance(records, list):
            raise MLFeatureMatrixError(
                f"partitions.{partition_name}.records must be an array."
            )
        if len(records) != EXPECTED_PARTITION_ROWS[partition_name]:
            raise MLFeatureMatrixError(
                f"Unexpected row count for {partition_name}."
            )
        if partition.get("row_count") != len(records):
            raise MLFeatureMatrixError(
                f"row_count mismatch for {partition_name}."
            )

        groups = partition.get("group_ids")
        if (
            not isinstance(groups, list)
            or len(groups) != EXPECTED_PARTITION_GROUPS[partition_name]
            or len(groups) != partition.get("group_count")
            or any(not isinstance(group, str) or not group for group in groups)
        ):
            raise MLFeatureMatrixError(
                f"Invalid group binding for {partition_name}."
            )
        overlap = all_groups & set(groups)
        if overlap:
            raise MLFeatureMatrixError(
                "A split group crosses matrix partitions: "
                + ", ".join(sorted(overlap))
            )
        all_groups.update(groups)

        classes: Counter[str] = Counter()
        partition_unavailable = 0
        ordered_ids: list[str] = []
        for index, value in enumerate(records, start=1):
            record = require_mapping(
                value,
                f"partitions.{partition_name}.records[{index}]",
            )
            sample_id = require_non_empty_string(
                record.get("sample_id"),
                f"{partition_name} record sample_id",
            )
            if sample_id in all_samples:
                raise MLFeatureMatrixError(
                    f"Duplicate matrix sample_id: {sample_id}"
                )
            all_samples.add(sample_id)
            ordered_ids.append(sample_id)
            group_id = require_non_empty_string(
                record.get("split_group_id"),
                f"{sample_id}.split_group_id",
            )
            if group_id not in groups:
                raise MLFeatureMatrixError(
                    f"{sample_id} has an unexpected split group."
                )
            target = record.get("target_class")
            if target not in CLASS_ORDER:
                raise MLFeatureMatrixError(
                    f"{sample_id} has an unsupported target class."
                )
            classes[target] += 1
            vector = record.get("feature_vector")
            if (
                not isinstance(vector, list)
                or len(vector) != len(ENCODED_FEATURE_NAMES)
                or any(value not in (0, 1) for value in vector)
            ):
                raise MLFeatureMatrixError(
                    f"{sample_id} has an invalid feature vector."
                )
            for offset in range(0, len(vector), 2):
                pair = vector[offset:offset + 2]
                if pair == [0, 1]:
                    raise MLFeatureMatrixError(
                        f"{sample_id} contains the invalid pair [0, 1]."
                    )
                partition_unavailable += pair == [0, 0]
            row_sha256 = record.get("source_row_sha256")
            if (
                not isinstance(row_sha256, str)
                or len(row_sha256) != 64
            ):
                raise MLFeatureMatrixError(
                    f"{sample_id} has an invalid source-row hash."
                )

        if ordered_ids != sorted(ordered_ids):
            raise MLFeatureMatrixError(
                f"{partition_name} records are not sample-id ordered."
            )
        if partition.get("class_row_counts") != dict(sorted(classes.items())):
            raise MLFeatureMatrixError(
                f"Class counts disagree for {partition_name}."
            )
        if partition.get("unavailable_value_count") != partition_unavailable:
            raise MLFeatureMatrixError(
                f"Unavailable-value count disagrees for {partition_name}."
            )
        total_rows += len(records)
        total_unavailable += partition_unavailable

    if total_rows != 30 or matrix.get("row_count") != total_rows:
        raise MLFeatureMatrixError(
            "The frozen matrix must contain exactly 30 rows."
        )
    if matrix.get("raw_feature_count") != len(RAW_FEATURE_NAMES):
        raise MLFeatureMatrixError("raw_feature_count mismatch.")
    if matrix.get("encoded_feature_count") != len(ENCODED_FEATURE_NAMES):
        raise MLFeatureMatrixError("encoded_feature_count mismatch.")
    audit = require_mapping(matrix.get("leakage_audit"), "leakage_audit")
    expected_audit = {
        "predictor_source": "features_only",
        "transformation_fit_required": False,
        "no_cross_partition_group": True,
        "test_used_for_fit": False,
        "test_used_for_selection": False,
        "unexpected_predictor_fields": [],
        "unavailable_value_count": total_unavailable,
    }
    if audit != expected_audit:
        raise MLFeatureMatrixError("Leakage audit does not match P4-R0.")


def build_ml_feature_matrix(
    *,
    campaign_result_path: Path,
    output_path: Path,
    schema_path: Path,
    matrix_id: str = DEFAULT_MATRIX_ID,
    expected_campaign_run_id: str,
    expected_dataset_sha256: str,
) -> dict[str, Any]:
    if output_path.exists():
        raise MLFeatureMatrixError(
            f"Output already exists: {output_path}"
        )

    campaign_path = campaign_result_path.resolve()
    campaign = read_json(campaign_path)
    if campaign.get("schema_version") != 1:
        raise MLFeatureMatrixError("Campaign Result schema_version must be 1.")
    if campaign.get("status") != "COMPLETED":
        raise MLFeatureMatrixError("Campaign Result must be COMPLETED.")
    if campaign.get("campaign_id") != EXPECTED_CAMPAIGN_ID:
        raise MLFeatureMatrixError("Unexpected campaign_id.")
    if campaign.get("campaign_run_id") != expected_campaign_run_id:
        raise MLFeatureMatrixError("Unexpected campaign_run_id.")
    if campaign.get("dataset_row_schema_version") != 2:
        raise MLFeatureMatrixError("Dataset Row v2 is required.")

    merged = require_mapping(campaign.get("merged_dataset"), "merged_dataset")
    merged_path = Path(require_non_empty_string(
        merged.get("path"),
        "merged_dataset.path",
    )).resolve()
    merged_hash = sha256_file(merged_path)
    if (
        merged_hash != expected_dataset_sha256
        or merged.get("sha256") != expected_dataset_sha256
    ):
        raise MLFeatureMatrixError(
            "Merged dataset hash does not match D-067."
        )

    split_summary = require_mapping(campaign.get("split"), "split")
    split_manifest_path = Path(require_non_empty_string(
        split_summary.get("manifest_path"),
        "split.manifest_path",
    )).resolve()
    split_manifest = read_json(split_manifest_path)
    if split_manifest.get("schema_version") != 2:
        raise MLFeatureMatrixError("Split manifest schema_version must be 2.")
    if split_manifest.get("algorithm") != EXPECTED_SPLIT_ALGORITHM:
        raise MLFeatureMatrixError("Unexpected split algorithm.")
    if split_manifest.get("seed") != EXPECTED_SPLIT_SEED:
        raise MLFeatureMatrixError("Unexpected split seed.")
    if split_manifest.get("ratios") != EXPECTED_SPLIT_RATIOS:
        raise MLFeatureMatrixError("Unexpected split ratios.")
    if split_manifest.get("source_dataset_schema_version") != 2:
        raise MLFeatureMatrixError("Split source must use Dataset Row v2.")
    if split_manifest.get("required_fault_types") != sorted(CLASS_ORDER):
        raise MLFeatureMatrixError("Unexpected split class coverage.")
    source = require_mapping(split_manifest.get("source"), "split.source")
    if source.get("sha256") != merged_hash:
        raise MLFeatureMatrixError("Split source hash mismatch.")

    manifest_partitions = require_mapping(
        split_manifest.get("partitions"),
        "split.partitions",
    )
    outputs = require_mapping(split_manifest.get("outputs"), "split.outputs")
    matrix_partitions: dict[str, Any] = {}
    partition_bindings: dict[str, Any] = {}
    all_samples: set[str] = set()
    all_groups: set[str] = set()
    unavailable_total = 0

    for partition_name in PARTITION_NAMES:
        partition = require_mapping(
            manifest_partitions.get(partition_name),
            f"split.partitions.{partition_name}",
        )
        file_name = f"{partition_name}.jsonl"
        output = require_mapping(
            outputs.get(file_name),
            f"split.outputs.{file_name}",
        )
        partition_path = split_manifest_path.parent / file_name
        partition_hash = sha256_file(partition_path)
        if output.get("sha256") != partition_hash:
            raise MLFeatureMatrixError(
                f"Split partition hash mismatch: {file_name}"
            )
        rows_with_hashes = read_jsonl_with_hashes(partition_path)
        if len(rows_with_hashes) != EXPECTED_PARTITION_ROWS[partition_name]:
            raise MLFeatureMatrixError(
                f"Unexpected D-067 row count for {partition_name}."
            )
        if partition.get("row_count") != len(rows_with_hashes):
            raise MLFeatureMatrixError(
                f"Split row_count mismatch for {partition_name}."
            )
        group_ids_value = partition.get("group_ids")
        if (
            not isinstance(group_ids_value, list)
            or len(group_ids_value) != EXPECTED_PARTITION_GROUPS[partition_name]
        ):
            raise MLFeatureMatrixError(
                f"Unexpected D-067 groups for {partition_name}."
            )
        group_ids = sorted(group_ids_value)
        if set(group_ids) & all_groups:
            raise MLFeatureMatrixError("A split group crosses partitions.")
        all_groups.update(group_ids)

        records: list[dict[str, Any]] = []
        class_counts: Counter[str] = Counter()
        partition_unavailable = 0
        for row_number, (row, row_hash) in enumerate(
            rows_with_hashes,
            start=1,
        ):
            try:
                validate_dataset_row_v2(row)
            except DatasetContractError as error:
                raise MLFeatureMatrixError(
                    f"Invalid Dataset Row v2 in {file_name} at row "
                    f"{row_number}: {error}"
                ) from error
            sample_id = require_non_empty_string(
                row.get("sample_id"),
                f"{file_name} row {row_number} sample_id",
            )
            if sample_id in all_samples:
                raise MLFeatureMatrixError(
                    f"Duplicate split sample_id: {sample_id}"
                )
            all_samples.add(sample_id)
            metadata = require_mapping(row.get("metadata"), f"{sample_id}.metadata")
            labels = require_mapping(row.get("labels"), f"{sample_id}.labels")
            group_id = require_non_empty_string(
                metadata.get("split_group_id"),
                f"{sample_id}.split_group_id",
            )
            if group_id not in group_ids:
                raise MLFeatureMatrixError(
                    f"{sample_id} has an unexpected split group."
                )
            target = labels.get("fault_type")
            if target not in CLASS_ORDER:
                raise MLFeatureMatrixError(
                    f"{sample_id} has an unsupported target class."
                )
            features = require_mapping(
                row.get("features"),
                f"{sample_id}.features",
            )
            vector = encode_tristate_features(features)
            partition_unavailable += sum(
                vector[offset:offset + 2] == [0, 0]
                for offset in range(0, len(vector), 2)
            )
            class_counts[target] += 1
            records.append({
                "sample_id": sample_id,
                "split_group_id": group_id,
                "target_class": target,
                "feature_vector": vector,
                "source_row_sha256": row_hash,
            })
        records.sort(key=lambda record: record["sample_id"])
        expected_class_counts = {
            label: EXPECTED_PARTITION_GROUPS[partition_name] * 2
            for label in sorted(CLASS_ORDER)
        }
        if dict(sorted(class_counts.items())) != expected_class_counts:
            raise MLFeatureMatrixError(
                f"Unexpected class counts for {partition_name}."
            )
        if partition.get("class_row_counts") != expected_class_counts:
            raise MLFeatureMatrixError(
                f"Split class counts disagree for {partition_name}."
            )
        matrix_partitions[partition_name] = {
            "use": PARTITION_USES[partition_name],
            "row_count": len(records),
            "group_count": len(group_ids),
            "group_ids": group_ids,
            "class_row_counts": expected_class_counts,
            "unavailable_value_count": partition_unavailable,
            "records": records,
        }
        partition_bindings[partition_name] = {
            "path": str(partition_path.resolve()),
            "sha256": partition_hash,
            "row_count": len(records),
            "group_count": len(group_ids),
            "group_ids": group_ids,
        }
        unavailable_total += partition_unavailable

    result = {
        "schema_version": ML_FEATURE_MATRIX_SCHEMA_VERSION,
        "matrix_id": matrix_id,
        "status": "COMPLETED",
        "row_count": len(all_samples),
        "raw_feature_count": len(RAW_FEATURE_NAMES),
        "encoded_feature_count": len(ENCODED_FEATURE_NAMES),
        "protocol": frozen_protocol(),
        "dataset_binding": {
            "campaign_id": EXPECTED_CAMPAIGN_ID,
            "campaign_run_id": expected_campaign_run_id,
            "dataset_row_schema_version": 2,
            "merged_dataset": {
                "path": str(merged_path),
                "sha256": merged_hash,
                "row_count": len(all_samples),
            },
            "split": {
                "algorithm": EXPECTED_SPLIT_ALGORITHM,
                "seed": EXPECTED_SPLIT_SEED,
                "ratios": EXPECTED_SPLIT_RATIOS,
                "manifest_path": str(split_manifest_path),
                "manifest_sha256": sha256_file(split_manifest_path),
                "partitions": partition_bindings,
                "no_cross_partition_group": True,
            },
        },
        "partitions": matrix_partitions,
        "leakage_audit": {
            "predictor_source": "features_only",
            "transformation_fit_required": False,
            "no_cross_partition_group": True,
            "test_used_for_fit": False,
            "test_used_for_selection": False,
            "unexpected_predictor_fields": [],
            "unavailable_value_count": unavailable_total,
        },
        "provenance": {
            "campaign_result": artifact_reference(campaign_path),
            "merged_dataset": artifact_reference(merged_path),
            "split_manifest": artifact_reference(split_manifest_path),
            "partition_artifact_count": len(PARTITION_NAMES),
            "source_row_reference_count": len(all_samples),
        },
    }
    validate_ml_feature_matrix(result)
    validate_against_schema(result, schema_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f".{output_path.name}.{uuid4().hex}.tmp"
    )
    try:
        temporary_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written = read_json(temporary_path)
        validate_ml_feature_matrix(written)
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
            "Build the frozen P4-R0 leakage-safe ML feature matrix."
        )
    )
    parser.add_argument("--campaign-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--matrix-id", default=DEFAULT_MATRIX_ID)
    parser.add_argument("--expected-campaign-run-id", required=True)
    parser.add_argument("--expected-dataset-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    result = build_ml_feature_matrix(
        campaign_result_path=arguments.campaign_result,
        output_path=arguments.output,
        schema_path=arguments.schema,
        matrix_id=arguments.matrix_id,
        expected_campaign_run_id=arguments.expected_campaign_run_id,
        expected_dataset_sha256=arguments.expected_dataset_sha256,
    )
    print(json.dumps({
        "matrix_id": result["matrix_id"],
        "status": result["status"],
        "rows": result["row_count"],
        "raw_features": result["raw_feature_count"],
        "encoded_features": result["encoded_feature_count"],
        "partition_rows": {
            name: result["partitions"][name]["row_count"]
            for name in PARTITION_NAMES
        },
        "partition_groups": {
            name: result["partitions"][name]["group_count"]
            for name in PARTITION_NAMES
        },
        "unavailable_values": result["leakage_audit"][
            "unavailable_value_count"
        ],
        "test_use": result["partitions"]["test"]["use"],
        "output_path": str(arguments.output.resolve()),
        "output_sha256": sha256_file(arguments.output.resolve()),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
