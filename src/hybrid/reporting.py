from __future__ import annotations

import argparse
import copy
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from jsonschema import Draft202012Validator

from src.evaluation.evaluator import evaluate_prediction
from src.evaluation.reporting import (
    EvaluationReportingError,
    build_method_evaluation_result,
    validate_against_schema as validate_method_schema,
    validate_method_evaluation_result,
)
from src.hybrid.engine import (
    DEFAULT_PREDICTION_SCHEMA_PATH,
    DEFAULT_SELECTION_SCHEMA_PATH,
    EXPECTED_IMPLEMENTATION_ID,
    EXPECTED_POLICY_SHA256,
    HybridEngineError,
    artifact_reference,
    build_hybrid_prediction,
    hybrid_predicted_class,
    load_verified_policy,
    read_json,
    require_mapping,
    require_non_empty_string,
    sha256_file,
    validate_artifact_reference,
    validate_hybrid_prediction,
    verify_baseline_bindings,
    verify_hybrid_selection,
    write_json,
)
from src.hybrid.policy import (
    DEFAULT_POLICY_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_POLICY_SCHEMA_PATH,
    EXPECTED_CLASS_ORDER,
    HybridPolicyError,
)


DEFAULT_METHOD_SCHEMA_PATH = Path(
    "schemas/method_evaluation_result_v1.schema.json"
)
DEFAULT_COMPARISON_SCHEMA_PATH = Path(
    "schemas/cross_method_comparison_v1.schema.json"
)
DEFAULT_SELECTION_PATH = Path(
    "models/p5_r1_hybrid_policy_v1/selection.json"
)
DEFAULT_OUTPUT_DIRECTORY = Path(
    "reports/experiments/p5_r2_hybrid_baseline_v1"
)
REPORT_FILE_NAME = "method_evaluation_result.json"
COMPARISON_FILE_NAME = "cross_method_comparison.json"
EXPECTED_RESULT_ID = "p5_r2_hybrid_baseline_v1"
EXPECTED_COMPARISON_ID = "p5_r2_rules_ml_hybrid_comparison_v1"
EXPECTED_SELECTION_SHA256 = (
    "59abc80339658a30ab82019c847dbb7a1c9348bc4ca82ad7e1378f2f339a9507"
)
EXPECTED_SELECTED_CANDIDATE = "consensus_abstain_v1"
EXPECTED_PARTITION_ROWS = {"train": 18, "validation": 6, "test": 6}
EXPECTED_TEST_GROUP = "CTX_G02_TOP02_CHAIN_3R"
PARTITION_ORDER = ("train", "validation", "test")
METHOD_ORDER = ("rule_based", "machine_learning", "hybrid")


class HybridReportingError(ValueError):
    """Raised when the frozen P5-R2 report boundary is violated."""


@dataclass(frozen=True)
class SourceSample:
    sample_id: str
    partition: str
    split_group_id: str
    experiment_manifest_reference: Mapping[str, str]
    ground_truth_reference: Mapping[str, str]
    evidence_reference: Mapping[str, str]
    rule_prediction_reference: Mapping[str, str]
    ml_prediction_reference: Mapping[str, str]


def _schema_validate(
    value: Mapping[str, Any],
    schema_path: Path,
    contract_name: str,
) -> None:
    schema = read_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path)
        prefix = f"{location}: " if location else ""
        raise HybridReportingError(
            f"{contract_name} JSON Schema violation: {prefix}{first.message}"
        )


def _report_index(
    report: Mapping[str, Any],
    expected_method_id: str,
) -> dict[tuple[str, str], Mapping[str, Any]]:
    method = require_mapping(report.get("method"), "report.method")
    if method.get("method_id") != expected_method_id:
        raise HybridReportingError(
            f"Expected {expected_method_id} source report."
        )
    records = report.get("records")
    if not isinstance(records, list) or len(records) != 30:
        raise HybridReportingError("A source report must contain 30 records.")
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    counts = {name: 0 for name in PARTITION_ORDER}
    for position, value in enumerate(records, start=1):
        record = require_mapping(value, f"report.records[{position}]")
        partition = require_non_empty_string(
            record.get("partition"),
            f"report.records[{position}].partition",
        )
        if partition not in counts:
            raise HybridReportingError("Source report partition changed.")
        sample_id = require_non_empty_string(
            record.get("sample_id"),
            f"report.records[{position}].sample_id",
        )
        key = (partition, sample_id)
        if key in indexed:
            raise HybridReportingError(f"Duplicate source sample: {sample_id}")
        indexed[key] = record
        counts[partition] += 1
    if counts != EXPECTED_PARTITION_ROWS:
        raise HybridReportingError("Source report partition counts changed.")
    return indexed


def _deferred_reference(
    value: object,
    reference: str,
    sample_id: str,
) -> dict[str, str]:
    normalized, _ = validate_artifact_reference(
        value,
        reference,
        sample_id=sample_id,
        verify_hash=False,
    )
    return normalized


def collect_source_samples(
    rule_report_path: Path,
    ml_report_path: Path,
    *,
    partitions: Sequence[str] = PARTITION_ORDER,
) -> list[SourceSample]:
    requested = tuple(partitions)
    if not requested or any(name not in PARTITION_ORDER for name in requested):
        raise HybridReportingError("Requested source partitions are invalid.")
    if len(set(requested)) != len(requested):
        raise HybridReportingError("Requested source partitions are duplicated.")

    rule_index = _report_index(read_json(rule_report_path), "rule_based")
    ml_index = _report_index(read_json(ml_report_path), "machine_learning")
    if set(rule_index) != set(ml_index):
        raise HybridReportingError("Rule and ML source sample sets differ.")

    samples: list[SourceSample] = []
    for partition in requested:
        keys = sorted(key for key in rule_index if key[0] == partition)
        if len(keys) != EXPECTED_PARTITION_ROWS[partition]:
            raise HybridReportingError(
                f"Unexpected {partition} source sample count."
            )
        for _, sample_id in keys:
            rule_record = rule_index[(partition, sample_id)]
            ml_record = ml_index[(partition, sample_id)]
            rule_group = require_non_empty_string(
                rule_record.get("split_group_id"),
                f"rule record {sample_id}.split_group_id",
            )
            ml_group = require_non_empty_string(
                ml_record.get("split_group_id"),
                f"ML record {sample_id}.split_group_id",
            )
            if rule_group != ml_group:
                raise HybridReportingError(
                    f"Source split-group mismatch for {sample_id}."
                )
            if partition == "test" and rule_group != EXPECTED_TEST_GROUP:
                raise HybridReportingError("Held-out G02 group binding changed.")

            rule_artifacts = require_mapping(
                rule_record.get("artifacts"),
                f"rule record {sample_id}.artifacts",
            )
            ml_artifacts = require_mapping(
                ml_record.get("artifacts"),
                f"ML record {sample_id}.artifacts",
            )
            evidence, _ = validate_artifact_reference(
                rule_artifacts.get("evidence"),
                f"rule record {sample_id}.evidence",
                sample_id=sample_id,
            )
            ml_evidence, _ = validate_artifact_reference(
                ml_artifacts.get("evidence"),
                f"ML record {sample_id}.evidence",
                sample_id=sample_id,
            )
            if evidence != ml_evidence:
                raise HybridReportingError(
                    f"Evidence reference mismatch for {sample_id}."
                )
            rule_prediction, _ = validate_artifact_reference(
                rule_artifacts.get("prediction"),
                f"rule record {sample_id}.prediction",
                sample_id=sample_id,
            )
            ml_prediction, _ = validate_artifact_reference(
                ml_artifacts.get("prediction"),
                f"ML record {sample_id}.prediction",
                sample_id=sample_id,
            )
            experiment_manifest = _deferred_reference(
                rule_artifacts.get("experiment_manifest"),
                f"rule record {sample_id}.experiment_manifest",
                sample_id,
            )
            ground_truth = _deferred_reference(
                rule_artifacts.get("ground_truth"),
                f"rule record {sample_id}.ground_truth",
                sample_id,
            )
            for name, rule_reference in (
                ("experiment_manifest", experiment_manifest),
                ("ground_truth", ground_truth),
                ("evidence", evidence),
            ):
                ml_reference = _deferred_reference(
                    ml_artifacts.get(name),
                    f"ML record {sample_id}.{name}",
                    sample_id,
                )
                if ml_reference != rule_reference:
                    raise HybridReportingError(
                        f"{name} reference mismatch for {sample_id}."
                    )
            samples.append(
                SourceSample(
                    sample_id=sample_id,
                    partition=partition,
                    split_group_id=rule_group,
                    experiment_manifest_reference=experiment_manifest,
                    ground_truth_reference=ground_truth,
                    evidence_reference=evidence,
                    rule_prediction_reference=rule_prediction,
                    ml_prediction_reference=ml_prediction,
                )
            )
    return samples


def _reference_with_final_path(
    temporary_path: Path,
    final_path: Path,
) -> dict[str, str]:
    return {
        "path": str(final_path.resolve()),
        "sha256": sha256_file(temporary_path),
    }


def _verify_freeze_gate(
    *,
    selection_path: Path,
    policy_path: Path,
    policy_schema_path: Path,
    prediction_schema_path: Path,
    selection_schema_path: Path,
    source_paths: Mapping[str, Path],
    expected_policy_sha256: str,
    expected_selection_sha256: str,
) -> dict[str, Any]:
    verified = verify_hybrid_selection(
        selection_path=selection_path,
        policy_path=policy_path,
        policy_schema_path=policy_schema_path,
        prediction_schema_path=prediction_schema_path,
        selection_schema_path=selection_schema_path,
        source_paths=source_paths,
        expected_policy_sha256=expected_policy_sha256,
        expected_selection_sha256=expected_selection_sha256,
    )
    if verified.get("selected_candidate") != EXPECTED_SELECTED_CANDIDATE:
        raise HybridReportingError("Frozen selected hybrid candidate changed.")
    if verified.get("test_predictions_or_metrics") != "ABSENT":
        raise HybridReportingError("P5-R1 freeze gate contains test output.")
    return verified


def _selected_development_records(
    selection: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    selected = require_mapping(
        selection.get("selected_candidate"),
        "selection.selected_candidate",
    )
    selected_id = require_non_empty_string(
        selected.get("candidate_id"),
        "selection.selected_candidate.candidate_id",
    )
    if selected_id != EXPECTED_SELECTED_CANDIDATE:
        raise HybridReportingError("Unexpected selected candidate.")
    results = selection.get("candidate_results")
    if not isinstance(results, list):
        raise HybridReportingError("Hybrid selection candidate results are invalid.")
    selected_result = next(
        (
            require_mapping(value, "candidate_result")
            for value in results
            if isinstance(value, Mapping)
            and value.get("candidate_id") == selected_id
        ),
        None,
    )
    if selected_result is None:
        raise HybridReportingError("Selected candidate manifest is absent.")
    _, manifest_path = validate_artifact_reference(
        selected_result.get("candidate_manifest"),
        "selected candidate manifest",
    )
    manifest = read_json(manifest_path)
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 24:
        raise HybridReportingError(
            "Selected candidate manifest must contain 24 development records."
        )
    indexed: dict[str, Mapping[str, Any]] = {}
    for value in records:
        record = require_mapping(value, "selected candidate record")
        sample_id = require_non_empty_string(
            record.get("sample_id"),
            "selected candidate record.sample_id",
        )
        if record.get("partition") not in {"train", "validation"}:
            raise HybridReportingError(
                "Selected candidate manifest contains held-out output."
            )
        if sample_id in indexed:
            raise HybridReportingError("Duplicate selected development sample.")
        indexed[sample_id] = record
    return indexed


def _record_from_artifacts(
    *,
    sample: SourceSample,
    prediction_reference: Mapping[str, str],
    evaluation_reference: Mapping[str, str],
    prediction_schema_path: Path,
    expected_policy_sha256: str,
) -> dict[str, Any]:
    _, prediction_path = validate_artifact_reference(
        prediction_reference,
        f"hybrid prediction {sample.sample_id}",
        sample_id=sample.sample_id,
    )
    _, evaluation_path = validate_artifact_reference(
        evaluation_reference,
        f"hybrid evaluation {sample.sample_id}",
        sample_id=sample.sample_id,
    )
    prediction = read_json(prediction_path)
    validate_hybrid_prediction(
        prediction,
        prediction_schema_path,
        expected_policy_sha256=expected_policy_sha256,
    )
    if (
        prediction.get("sample_id") != sample.sample_id
        or prediction.get("candidate_id") != EXPECTED_SELECTED_CANDIDATE
    ):
        raise HybridReportingError("Hybrid prediction identity changed.")
    evaluation = read_json(evaluation_path)
    if (
        evaluation.get("sample_id") != sample.sample_id
        or evaluation.get("method") != "hybrid"
    ):
        raise HybridReportingError("Hybrid evaluation identity changed.")
    expected = require_mapping(
        evaluation.get("expected"),
        f"evaluation {sample.sample_id}.expected",
    )
    metrics = require_mapping(
        evaluation.get("metrics"),
        f"evaluation {sample.sample_id}.metrics",
    )
    predicted_class = hybrid_predicted_class(prediction)
    manifest, _ = validate_artifact_reference(
        sample.experiment_manifest_reference,
        f"experiment manifest {sample.sample_id}",
        sample_id=sample.sample_id,
    )
    ground_truth, _ = validate_artifact_reference(
        sample.ground_truth_reference,
        f"ground truth {sample.sample_id}",
        sample_id=sample.sample_id,
    )
    return {
        "sample_id": sample.sample_id,
        "partition": sample.partition,
        "split_group_id": sample.split_group_id,
        "expected_fault_type": expected["fault_type"],
        "predicted_fault_type": predicted_class,
        "abstained": predicted_class is None,
        "classification_correct": (
            predicted_class is not None
            and predicted_class == expected["fault_type"]
        ),
        "exact_match": bool(metrics["exact_match"]),
        "affected_prefix_correct": bool(metrics["affected_prefix_correct"]),
        "artifacts": {
            "experiment_manifest": manifest,
            "ground_truth": ground_truth,
            "evidence": dict(sample.evidence_reference),
            "rule_prediction": dict(sample.rule_prediction_reference),
            "ml_prediction": dict(sample.ml_prediction_reference),
            "hybrid_prediction": dict(prediction_reference),
            "evaluation": dict(evaluation_reference),
        },
    }


def _source_reports_after_prediction_gate(
    rule_report_path: Path,
    ml_report_path: Path,
    method_schema_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rule_report = read_json(rule_report_path)
    ml_report = read_json(ml_report_path)
    for report, expected_method in (
        (rule_report, "rule_based"),
        (ml_report, "machine_learning"),
    ):
        validate_method_evaluation_result(report)
        validate_method_schema(report, method_schema_path)
        method = require_mapping(report.get("method"), "source report.method")
        if method.get("method_id") != expected_method:
            raise HybridReportingError("Source report method binding changed.")
    if rule_report.get("dataset_binding") != ml_report.get("dataset_binding"):
        raise HybridReportingError("Source report dataset bindings differ.")
    for name in ("campaign_result", "split_manifest"):
        rule_reference = require_mapping(
            require_mapping(rule_report.get("provenance"), "rule provenance").get(
                name
            ),
            f"rule provenance.{name}",
        )
        ml_reference = require_mapping(
            require_mapping(ml_report.get("provenance"), "ML provenance").get(
                name
            ),
            f"ML provenance.{name}",
        )
        if dict(rule_reference) != dict(ml_reference):
            raise HybridReportingError(f"Source {name} bindings differ.")
        validate_artifact_reference(rule_reference, f"source {name}")
    return rule_report, ml_report


def _metric_view(
    report: Mapping[str, Any],
    scope: str,
) -> dict[str, Any]:
    if scope == "overall":
        summary = require_mapping(report.get("overall"), "report.overall")
    else:
        summary = require_mapping(
            require_mapping(report.get("partitions"), "report.partitions").get(
                scope
            ),
            f"report.partitions.{scope}",
        )
    metrics = require_mapping(summary.get("metrics"), f"{scope}.metrics")
    classification = require_mapping(
        metrics.get("classification"),
        f"{scope}.classification",
    )
    macro = require_mapping(classification.get("macro"), f"{scope}.macro")
    checks = require_mapping(
        metrics.get("diagnostic_checks"),
        f"{scope}.diagnostic_checks",
    )
    exact = require_mapping(
        checks.get("exact_diagnosis_match"),
        f"{scope}.exact_diagnosis_match",
    )
    prefix = require_mapping(
        checks.get("affected_prefix_fault_only"),
        f"{scope}.affected_prefix_fault_only",
    )
    abstention = metrics.get("abstention")
    if isinstance(abstention, Mapping):
        coverage = abstention.get("coverage")
        abstention_count = abstention.get("abstention_count")
        abstention_rate = abstention.get("abstention_rate")
    else:
        coverage = 1.0
        abstention_count = 0
        abstention_rate = 0.0
    return {
        "accuracy": classification["accuracy"],
        "macro_precision": macro["precision"],
        "macro_recall": macro["recall"],
        "macro_f1": macro["f1"],
        "exact_diagnosis_rate": exact["rate"],
        "affected_prefix_fault_only_rate": prefix["rate"],
        "coverage": coverage,
        "abstention_count": abstention_count,
        "abstention_rate": abstention_rate,
    }


def build_cross_method_comparison(
    *,
    rule_report: Mapping[str, Any],
    ml_report: Mapping[str, Any],
    hybrid_report: Mapping[str, Any],
    report_references: Mapping[str, Mapping[str, str]],
    hybrid_selection_reference: Mapping[str, str],
    generated_at_utc: str,
) -> dict[str, Any]:
    reports = {
        "rule_based": rule_report,
        "machine_learning": ml_report,
        "hybrid": hybrid_report,
    }
    if tuple(reports) != METHOD_ORDER:
        raise HybridReportingError("Cross-method order changed.")
    dataset_binding = rule_report.get("dataset_binding")
    if any(
        report.get("dataset_binding") != dataset_binding
        for report in reports.values()
    ):
        raise HybridReportingError("Cross-method dataset bindings differ.")

    partition_comparison: dict[str, Any] = {}
    for partition in PARTITION_ORDER:
        source_summary = require_mapping(
            require_mapping(rule_report.get("partitions"), "rule partitions").get(
                partition
            ),
            f"rule partitions.{partition}",
        )
        for method_id, report in reports.items():
            summary = require_mapping(
                require_mapping(report.get("partitions"), "report partitions").get(
                    partition
                ),
                f"{method_id} partitions.{partition}",
            )
            for key in ("use", "row_count", "group_count", "group_ids"):
                if summary.get(key) != source_summary.get(key):
                    raise HybridReportingError(
                        f"Cross-method {partition}.{key} differs."
                    )
        partition_comparison[partition] = {
            "use": source_summary["use"],
            "row_count": source_summary["row_count"],
            "group_count": source_summary["group_count"],
            "group_ids": list(source_summary["group_ids"]),
            "methods": [
                {
                    "method_id": method_id,
                    "metrics": _metric_view(report, partition),
                }
                for method_id, report in reports.items()
            ],
        }

    comparison = {
        "schema_version": 1,
        "comparison_id": EXPECTED_COMPARISON_ID,
        "generated_at_utc": generated_at_utc,
        "status": "COMPLETED",
        "method_order": list(METHOD_ORDER),
        "dataset_binding": copy.deepcopy(dataset_binding),
        "report_references": {
            method_id: dict(report_references[method_id])
            for method_id in METHOD_ORDER
        },
        "hybrid_selection": dict(hybrid_selection_reference),
        "comparison_policy": {
            "target": "fault_type",
            "class_order": list(EXPECTED_CLASS_ORDER),
            "primary_metric": "macro_f1",
            "selection_partitions": ["train", "validation"],
            "held_out_partition": "test",
            "held_out_group_id": EXPECTED_TEST_GROUP,
            "test_use": "report_only",
            "overall_use": "descriptive_only",
            "test_influenced_policy_or_selection": False,
            "statistical_superiority_test_performed": False,
        },
        "partitions": partition_comparison,
        "overall": {
            "use": "descriptive_only",
            "row_count": require_mapping(
                rule_report.get("overall"),
                "rule report.overall",
            )["row_count"],
            "methods": [
                {
                    "method_id": method_id,
                    "metrics": _metric_view(report, "overall"),
                }
                for method_id, report in reports.items()
            ],
        },
        "limitations": [
            "The comparison is descriptive for one frozen 30-row controlled campaign.",
            "Validation and test each contain one topology context.",
            "No statistical superiority or real-world generalization claim is made.",
            "The ML method is class-only; rule and hybrid localization "
            "metrics are not equivalent model outputs.",
        ],
    }
    return comparison


def validate_cross_method_comparison(
    *,
    comparison: Mapping[str, Any],
    comparison_schema_path: Path,
    rule_report: Mapping[str, Any],
    ml_report: Mapping[str, Any],
    hybrid_report: Mapping[str, Any],
    report_references: Mapping[str, Mapping[str, str]],
    hybrid_selection_reference: Mapping[str, str],
) -> None:
    _schema_validate(
        comparison,
        comparison_schema_path,
        "Cross-Method Comparison v1",
    )
    if comparison.get("method_order") != list(METHOD_ORDER):
        raise HybridReportingError("Cross-method comparison order changed.")
    expected = build_cross_method_comparison(
        rule_report=rule_report,
        ml_report=ml_report,
        hybrid_report=hybrid_report,
        report_references=report_references,
        hybrid_selection_reference=hybrid_selection_reference,
        generated_at_utc=require_non_empty_string(
            comparison.get("generated_at_utc"),
            "comparison.generated_at_utc",
        ),
    )
    if dict(comparison) != expected:
        raise HybridReportingError("Cross-method comparison semantics drifted.")
    for name, reference in comparison["report_references"].items():
        validate_artifact_reference(reference, f"comparison report {name}")
    validate_artifact_reference(
        comparison["hybrid_selection"],
        "comparison hybrid selection",
    )


def _report_summary(
    report: Mapping[str, Any],
    report_path: Path,
    comparison_path: Path,
) -> dict[str, Any]:
    partitions = require_mapping(report.get("partitions"), "report.partitions")
    return {
        "status": "P5_R2_REPORT_AND_COMPARISON_VERIFIED",
        "result_id": report["result_id"],
        "selected_candidate": EXPECTED_SELECTED_CANDIDATE,
        "rows": report["overall"]["row_count"],
        "test_rows": partitions["test"]["row_count"],
        "test_group": partitions["test"]["group_ids"][0],
        "test_macro_f1": partitions["test"]["metrics"]["classification"][
            "macro"
        ]["f1"],
        "test_exact_diagnosis_rate": partitions["test"]["metrics"][
            "diagnostic_checks"
        ]["exact_diagnosis_match"]["rate"],
        "test_coverage": partitions["test"]["metrics"]["abstention"][
            "coverage"
        ],
        "test_abstentions": partitions["test"]["metrics"]["abstention"][
            "abstention_count"
        ],
        "test_use": report["evaluation_policy"]["test_use"],
        "report_path": str(report_path.resolve()),
        "report_sha256": sha256_file(report_path),
        "comparison_path": str(comparison_path.resolve()),
        "comparison_sha256": sha256_file(comparison_path),
        "test_influenced_policy_or_selection": False,
    }


def build_p5_r2_bundle(
    *,
    selection_path: Path,
    policy_path: Path,
    policy_schema_path: Path,
    prediction_schema_path: Path,
    selection_schema_path: Path,
    method_schema_path: Path,
    comparison_schema_path: Path,
    source_paths: Mapping[str, Path],
    output_directory: Path,
    expected_policy_sha256: str = EXPECTED_POLICY_SHA256,
    expected_selection_sha256: str = EXPECTED_SELECTION_SHA256,
) -> dict[str, Any]:
    selection_path = selection_path.resolve()
    policy_path = policy_path.resolve()
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise HybridReportingError(
            f"P5-R2 output already exists: {output_directory}"
        )

    # This independent P5-R1 verification is the one-way G02 gate.
    _verify_freeze_gate(
        selection_path=selection_path,
        policy_path=policy_path,
        policy_schema_path=policy_schema_path,
        prediction_schema_path=prediction_schema_path,
        selection_schema_path=selection_schema_path,
        source_paths=source_paths,
        expected_policy_sha256=expected_policy_sha256,
        expected_selection_sha256=expected_selection_sha256,
    )
    policy = load_verified_policy(
        policy_path,
        policy_schema_path,
        expected_policy_sha256=expected_policy_sha256,
    )
    baseline_references = verify_baseline_bindings(policy, source_paths)
    selection = read_json(selection_path)
    development_records = _selected_development_records(selection)

    # Only source identity and the three permitted prediction inputs are
    # bound here. Ground-truth content and test metrics are not read.
    test_samples = collect_source_samples(
        source_paths["rule_baseline"],
        source_paths["ml_report"],
        partitions=("test",),
    )

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = output_directory.parent / (
        f".{output_directory.name}.{uuid4().hex}.tmp"
    )
    try:
        temporary_directory.mkdir()
        test_prediction_references: dict[str, dict[str, str]] = {}
        for sample in test_samples:
            prediction = build_hybrid_prediction(
                sample_id=sample.sample_id,
                evidence_reference=sample.evidence_reference,
                rule_prediction_reference=sample.rule_prediction_reference,
                ml_prediction_reference=sample.ml_prediction_reference,
                policy=policy,
                policy_path=policy_path,
                candidate_id=EXPECTED_SELECTED_CANDIDATE,
                prediction_schema_path=prediction_schema_path,
                expected_policy_sha256=expected_policy_sha256,
            )
            temporary_prediction_path = (
                temporary_directory
                / "samples"
                / sample.sample_id
                / "prediction.json"
            )
            final_prediction_path = (
                output_directory / "samples" / sample.sample_id / "prediction.json"
            )
            write_json(temporary_prediction_path, prediction)
            test_prediction_references[sample.sample_id] = (
                _reference_with_final_path(
                    temporary_prediction_path,
                    final_prediction_path,
                )
            )

        if len(test_prediction_references) != 6 or len(
            list(temporary_directory.rglob("prediction.json"))
        ) != 6:
            raise HybridReportingError(
                "All six G02 predictions must exist before evaluation."
            )

        # The evaluator may read ground truth only after all six predictions
        # have been produced and frozen in the temporary output.
        test_evaluation_references: dict[str, dict[str, str]] = {}
        for sample in test_samples:
            prediction_path = Path(
                test_prediction_references[sample.sample_id]["path"]
            )
            temporary_prediction_path = (
                temporary_directory
                / "samples"
                / sample.sample_id
                / "prediction.json"
            )
            prediction = read_json(temporary_prediction_path)
            _, ground_truth_path = validate_artifact_reference(
                sample.ground_truth_reference,
                f"ground truth {sample.sample_id}",
                sample_id=sample.sample_id,
            )
            evaluation = evaluate_prediction(read_json(ground_truth_path), prediction)
            evaluation["sample_id"] = sample.sample_id
            evaluation["partition_use"] = "report_only"
            temporary_evaluation_path = (
                temporary_directory
                / "samples"
                / sample.sample_id
                / "evaluation.json"
            )
            final_evaluation_path = (
                output_directory / "samples" / sample.sample_id / "evaluation.json"
            )
            write_json(temporary_evaluation_path, evaluation)
            if prediction_path != (
                output_directory / "samples" / sample.sample_id / "prediction.json"
            ).resolve():
                raise HybridReportingError("Test prediction final path changed.")
            test_evaluation_references[sample.sample_id] = (
                _reference_with_final_path(
                    temporary_evaluation_path,
                    final_evaluation_path,
                )
            )

        # Labels and existing metrics may be traversed only after prediction
        # generation is complete.
        rule_report, ml_report = _source_reports_after_prediction_gate(
            source_paths["rule_baseline"],
            source_paths["ml_report"],
            method_schema_path,
        )
        all_samples = collect_source_samples(
            source_paths["rule_baseline"],
            source_paths["ml_report"],
        )
        report_records: list[dict[str, Any]] = []
        for sample in all_samples:
            if sample.partition == "test":
                prediction_reference = test_prediction_references[sample.sample_id]
                evaluation_reference = test_evaluation_references[sample.sample_id]
                temporary_prediction = (
                    temporary_directory
                    / "samples"
                    / sample.sample_id
                    / "prediction.json"
                )
                temporary_evaluation = (
                    temporary_directory
                    / "samples"
                    / sample.sample_id
                    / "evaluation.json"
                )
                # The final paths do not exist until the atomic rename; use
                # temporary paths for content validation while preserving
                # final references in the report record.
                prediction_for_record = {
                    "path": str(temporary_prediction.resolve()),
                    "sha256": prediction_reference["sha256"],
                }
                evaluation_for_record = {
                    "path": str(temporary_evaluation.resolve()),
                    "sha256": evaluation_reference["sha256"],
                }
                record = _record_from_artifacts(
                    sample=sample,
                    prediction_reference=prediction_for_record,
                    evaluation_reference=evaluation_for_record,
                    prediction_schema_path=prediction_schema_path,
                    expected_policy_sha256=expected_policy_sha256,
                )
                record["artifacts"]["hybrid_prediction"] = prediction_reference
                record["artifacts"]["evaluation"] = evaluation_reference
            else:
                development = development_records.get(sample.sample_id)
                if development is None:
                    raise HybridReportingError(
                        f"Selected development output missing: {sample.sample_id}"
                    )
                if (
                    development.get("partition") != sample.partition
                    or development.get("split_group_id") != sample.split_group_id
                ):
                    raise HybridReportingError(
                        "Selected development binding changed."
                    )
                record = _record_from_artifacts(
                    sample=sample,
                    prediction_reference=require_mapping(
                        development.get("prediction"),
                        "development prediction",
                    ),
                    evaluation_reference=require_mapping(
                        development.get("evaluation"),
                        "development evaluation",
                    ),
                    prediction_schema_path=prediction_schema_path,
                    expected_policy_sha256=expected_policy_sha256,
                )
            report_records.append(record)

        report_records.sort(
            key=lambda record: (
                PARTITION_ORDER.index(str(record["partition"])),
                str(record["sample_id"]),
            )
        )
        partition_group_ids = {
            partition: sorted(
                {
                    sample.split_group_id
                    for sample in all_samples
                    if sample.partition == partition
                }
            )
            for partition in PARTITION_ORDER
        }
        rule_provenance = require_mapping(
            rule_report.get("provenance"),
            "rule report.provenance",
        )
        report = build_method_evaluation_result(
            result_id=EXPECTED_RESULT_ID,
            method={
                "method_id": "hybrid",
                "family": "hybrid",
                "implementation_id": EXPECTED_IMPLEMENTATION_ID,
                "trained": False,
                "selection_statement": (
                    "consensus_abstain_v1 was selected only on G01 validation "
                    "by the frozen P5-R1 order; G02 was opened once for "
                    "report-only evaluation after policy, baseline, and "
                    "selection hash verification."
                ),
            },
            dataset_binding=copy.deepcopy(
                require_mapping(
                    rule_report.get("dataset_binding"),
                    "rule report.dataset_binding",
                )
            ),
            provenance={
                "campaign_result": copy.deepcopy(
                    require_mapping(
                        rule_provenance.get("campaign_result"),
                        "rule provenance.campaign_result",
                    )
                ),
                "split_manifest": copy.deepcopy(
                    require_mapping(
                        rule_provenance.get("split_manifest"),
                        "rule provenance.split_manifest",
                    )
                ),
                "rule_baseline": baseline_references["rule_baseline"],
                "feature_matrix": baseline_references["ml_feature_matrix"],
                "selection_result": baseline_references["ml_selection"],
                "model_artifact": baseline_references["ml_model"],
                "ml_baseline": baseline_references["ml_report"],
                "hybrid_policy": artifact_reference(policy_path),
                "hybrid_selection": artifact_reference(selection_path),
                "input_record_count": 30,
                "artifact_reference_count": 210,
            },
            records=report_records,
            partition_group_ids=partition_group_ids,
        )
        temporary_report_path = temporary_directory / REPORT_FILE_NAME
        final_report_path = output_directory / REPORT_FILE_NAME
        write_json(temporary_report_path, report)
        validate_method_evaluation_result(report)
        validate_method_schema(report, method_schema_path)

        report_references = {
            "rule_based": baseline_references["rule_baseline"],
            "machine_learning": baseline_references["ml_report"],
            "hybrid": _reference_with_final_path(
                temporary_report_path,
                final_report_path,
            ),
        }
        comparison = build_cross_method_comparison(
            rule_report=rule_report,
            ml_report=ml_report,
            hybrid_report=report,
            report_references=report_references,
            hybrid_selection_reference=artifact_reference(selection_path),
            generated_at_utc=report["generated_at_utc"],
        )
        temporary_comparison_path = temporary_directory / COMPARISON_FILE_NAME
        write_json(temporary_comparison_path, comparison)
        _schema_validate(
            comparison,
            comparison_schema_path,
            "Cross-Method Comparison v1",
        )
        temporary_directory.replace(output_directory)
    except Exception:
        if temporary_directory.exists():
            shutil.rmtree(temporary_directory)
        raise

    return verify_p5_r2_bundle(
        selection_path=selection_path,
        policy_path=policy_path,
        policy_schema_path=policy_schema_path,
        prediction_schema_path=prediction_schema_path,
        selection_schema_path=selection_schema_path,
        method_schema_path=method_schema_path,
        comparison_schema_path=comparison_schema_path,
        source_paths=source_paths,
        output_directory=output_directory,
        expected_policy_sha256=expected_policy_sha256,
        expected_selection_sha256=expected_selection_sha256,
        expected_report_sha256=sha256_file(output_directory / REPORT_FILE_NAME),
        expected_comparison_sha256=sha256_file(
            output_directory / COMPARISON_FILE_NAME
        ),
    )


def verify_p5_r2_bundle(
    *,
    selection_path: Path,
    policy_path: Path,
    policy_schema_path: Path,
    prediction_schema_path: Path,
    selection_schema_path: Path,
    method_schema_path: Path,
    comparison_schema_path: Path,
    source_paths: Mapping[str, Path],
    output_directory: Path,
    expected_policy_sha256: str = EXPECTED_POLICY_SHA256,
    expected_selection_sha256: str = EXPECTED_SELECTION_SHA256,
    expected_report_sha256: str | None = None,
    expected_comparison_sha256: str | None = None,
) -> dict[str, Any]:
    selection_path = selection_path.resolve()
    policy_path = policy_path.resolve()
    output_directory = output_directory.resolve()
    _verify_freeze_gate(
        selection_path=selection_path,
        policy_path=policy_path,
        policy_schema_path=policy_schema_path,
        prediction_schema_path=prediction_schema_path,
        selection_schema_path=selection_schema_path,
        source_paths=source_paths,
        expected_policy_sha256=expected_policy_sha256,
        expected_selection_sha256=expected_selection_sha256,
    )
    policy = load_verified_policy(
        policy_path,
        policy_schema_path,
        expected_policy_sha256=expected_policy_sha256,
    )
    baseline_references = verify_baseline_bindings(policy, source_paths)
    report_path = output_directory / REPORT_FILE_NAME
    comparison_path = output_directory / COMPARISON_FILE_NAME
    report_hash = sha256_file(report_path)
    comparison_hash = sha256_file(comparison_path)
    if expected_report_sha256 is not None and report_hash != expected_report_sha256:
        raise HybridReportingError("Hybrid report SHA-256 drift detected.")
    if (
        expected_comparison_sha256 is not None
        and comparison_hash != expected_comparison_sha256
    ):
        raise HybridReportingError("Cross-method comparison SHA-256 drift detected.")

    report = read_json(report_path)
    validate_method_evaluation_result(report)
    validate_method_schema(report, method_schema_path)
    method = require_mapping(report.get("method"), "hybrid report.method")
    if (
        report.get("result_id") != EXPECTED_RESULT_ID
        or method.get("method_id") != "hybrid"
        or method.get("implementation_id") != EXPECTED_IMPLEMENTATION_ID
        or method.get("trained") is not False
    ):
        raise HybridReportingError("Hybrid report identity changed.")
    provenance = require_mapping(report.get("provenance"), "report.provenance")
    expected_provenance = {
        "rule_baseline": baseline_references["rule_baseline"],
        "feature_matrix": baseline_references["ml_feature_matrix"],
        "selection_result": baseline_references["ml_selection"],
        "model_artifact": baseline_references["ml_model"],
        "ml_baseline": baseline_references["ml_report"],
        "hybrid_policy": artifact_reference(policy_path),
        "hybrid_selection": artifact_reference(selection_path),
    }
    for name, expected_reference in expected_provenance.items():
        if provenance.get(name) != expected_reference:
            raise HybridReportingError(f"Hybrid report {name} binding changed.")

    rule_report, ml_report = _source_reports_after_prediction_gate(
        source_paths["rule_baseline"],
        source_paths["ml_report"],
        method_schema_path,
    )
    samples = collect_source_samples(
        source_paths["rule_baseline"],
        source_paths["ml_report"],
    )
    sample_index = {sample.sample_id: sample for sample in samples}
    records = report.get("records")
    if not isinstance(records, list) or len(records) != 30:
        raise HybridReportingError("Hybrid report must contain 30 records.")
    artifact_count = 0
    observed_test_samples: set[str] = set()
    for value in records:
        record = require_mapping(value, "hybrid report record")
        sample_id = require_non_empty_string(
            record.get("sample_id"),
            "hybrid report record.sample_id",
        )
        sample = sample_index.get(sample_id)
        if sample is None:
            raise HybridReportingError("Hybrid report sample set changed.")
        if (
            record.get("partition") != sample.partition
            or record.get("split_group_id") != sample.split_group_id
        ):
            raise HybridReportingError("Hybrid report partition binding changed.")
        artifacts = require_mapping(record.get("artifacts"), "record.artifacts")
        expected_sources = {
            "experiment_manifest": sample.experiment_manifest_reference,
            "ground_truth": sample.ground_truth_reference,
            "evidence": sample.evidence_reference,
            "rule_prediction": sample.rule_prediction_reference,
            "ml_prediction": sample.ml_prediction_reference,
        }
        for name, expected_reference in expected_sources.items():
            if artifacts.get(name) != expected_reference:
                raise HybridReportingError(
                    f"Hybrid sample {sample_id} {name} binding changed."
                )
        resolved: dict[str, Path] = {}
        for name in (
            "experiment_manifest",
            "ground_truth",
            "evidence",
            "rule_prediction",
            "ml_prediction",
            "hybrid_prediction",
            "evaluation",
        ):
            _, path = validate_artifact_reference(
                artifacts.get(name),
                f"hybrid sample {sample_id}.{name}",
                sample_id=sample_id,
            )
            resolved[name] = path
            artifact_count += 1
        prediction = read_json(resolved["hybrid_prediction"])
        validate_hybrid_prediction(
            prediction,
            prediction_schema_path,
            expected_policy_sha256=expected_policy_sha256,
        )
        if (
            prediction.get("sample_id") != sample_id
            or prediction.get("candidate_id") != EXPECTED_SELECTED_CANDIDATE
        ):
            raise HybridReportingError("Hybrid report prediction changed.")
        source_references = require_mapping(
            prediction.get("source_references"),
            "hybrid prediction.source_references",
        )
        if source_references != {
            "evidence": dict(sample.evidence_reference),
            "rule_prediction": dict(sample.rule_prediction_reference),
            "ml_prediction": dict(sample.ml_prediction_reference),
        }:
            raise HybridReportingError("Hybrid prediction source binding changed.")
        evaluation = read_json(resolved["evaluation"])
        if (
            evaluation.get("sample_id") != sample_id
            or evaluation.get("method") != "hybrid"
        ):
            raise HybridReportingError("Hybrid evaluation binding changed.")
        expected = require_mapping(evaluation.get("expected"), "evaluation.expected")
        metrics = require_mapping(evaluation.get("metrics"), "evaluation.metrics")
        predicted_class = hybrid_predicted_class(prediction)
        if (
            record.get("expected_fault_type") != expected.get("fault_type")
            or record.get("predicted_fault_type") != predicted_class
            or record.get("abstained") is not (predicted_class is None)
            or record.get("exact_match") is not bool(metrics["exact_match"])
            or record.get("affected_prefix_correct")
            is not bool(metrics["affected_prefix_correct"])
        ):
            raise HybridReportingError("Hybrid report record metrics changed.")
        if sample.partition == "test":
            observed_test_samples.add(sample_id)
            expected_sample_directory = output_directory / "samples" / sample_id
            if (
                resolved["hybrid_prediction"].parent != expected_sample_directory
                or resolved["evaluation"].parent != expected_sample_directory
                or evaluation.get("partition_use") != "report_only"
            ):
                raise HybridReportingError("G02 output boundary changed.")
        else:
            if selection_path.parent not in resolved["hybrid_prediction"].parents:
                raise HybridReportingError(
                    "Development prediction is outside the frozen P5-R1 output."
                )
            if selection_path.parent not in resolved["evaluation"].parents:
                raise HybridReportingError(
                    "Development evaluation is outside the frozen P5-R1 output."
                )
    if artifact_count != 210 or len(observed_test_samples) != 6:
        raise HybridReportingError("Hybrid artifact count changed.")

    expected_json_paths = {
        report_path,
        comparison_path,
        *{
            output_directory / "samples" / sample_id / file_name
            for sample_id in observed_test_samples
            for file_name in ("prediction.json", "evaluation.json")
        },
    }
    observed_json_paths = set(output_directory.rglob("*.json"))
    if observed_json_paths != expected_json_paths:
        raise HybridReportingError("P5-R2 runtime JSON file set changed.")

    comparison = read_json(comparison_path)
    report_references = {
        "rule_based": baseline_references["rule_baseline"],
        "machine_learning": baseline_references["ml_report"],
        "hybrid": artifact_reference(report_path),
    }
    validate_cross_method_comparison(
        comparison=comparison,
        comparison_schema_path=comparison_schema_path,
        rule_report=rule_report,
        ml_report=ml_report,
        hybrid_report=report,
        report_references=report_references,
        hybrid_selection_reference=artifact_reference(selection_path),
    )
    return _report_summary(report, report_path, comparison_path)


def source_path_arguments(arguments: argparse.Namespace) -> dict[str, Path]:
    return {
        "rule_baseline": arguments.rule_report,
        "ml_feature_matrix": arguments.matrix,
        "ml_selection": arguments.ml_selection,
        "ml_model": arguments.ml_model,
        "ml_report": arguments.ml_report,
    }


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION_PATH)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument(
        "--policy-schema",
        type=Path,
        default=DEFAULT_POLICY_SCHEMA_PATH,
    )
    parser.add_argument(
        "--prediction-schema",
        type=Path,
        default=DEFAULT_PREDICTION_SCHEMA_PATH,
    )
    parser.add_argument(
        "--selection-schema",
        type=Path,
        default=DEFAULT_SELECTION_SCHEMA_PATH,
    )
    parser.add_argument(
        "--method-schema",
        type=Path,
        default=DEFAULT_METHOD_SCHEMA_PATH,
    )
    parser.add_argument(
        "--comparison-schema",
        type=Path,
        default=DEFAULT_COMPARISON_SCHEMA_PATH,
    )
    parser.add_argument(
        "--expected-selection-sha256",
        default=EXPECTED_SELECTION_SHA256,
    )
    parser.add_argument("--rule-report", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--ml-selection", type=Path, required=True)
    parser.add_argument("--ml-model", type=Path, required=True)
    parser.add_argument("--ml-report", type=Path, required=True)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run or independently verify the frozen P5-R2 report-only "
            "G02 evaluation and three-method comparison."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run-report")
    _add_common_arguments(run_parser)
    verify_parser = subparsers.add_parser("verify-report")
    _add_common_arguments(verify_parser)
    verify_parser.add_argument("--expected-report-sha256", required=True)
    verify_parser.add_argument("--expected-comparison-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    common = {
        "selection_path": arguments.selection,
        "policy_path": arguments.policy,
        "policy_schema_path": arguments.policy_schema,
        "prediction_schema_path": arguments.prediction_schema,
        "selection_schema_path": arguments.selection_schema,
        "method_schema_path": arguments.method_schema,
        "comparison_schema_path": arguments.comparison_schema,
        "source_paths": source_path_arguments(arguments),
        "output_directory": arguments.output_directory,
        "expected_selection_sha256": arguments.expected_selection_sha256,
    }
    try:
        if arguments.command == "run-report":
            result = build_p5_r2_bundle(**common)
        else:
            result = verify_p5_r2_bundle(
                **common,
                expected_report_sha256=arguments.expected_report_sha256,
                expected_comparison_sha256=(
                    arguments.expected_comparison_sha256
                ),
            )
            result["independent_verification"] = "PASS"
    except (
        EvaluationReportingError,
        HybridEngineError,
        HybridPolicyError,
        HybridReportingError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
