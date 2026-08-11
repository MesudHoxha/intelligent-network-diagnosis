from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

import joblib
from jsonschema import Draft202012Validator

from src.campaign.phase6_plan import CLASS_ORDER, load_phase6_campaign_plan
from src.phase6.contracts import (
    MASK_ORDER,
    Phase6MethodContractError,
    build_partition_inputs,
    read_json,
    sha256_file,
    write_json,
    write_jsonl,
)
from src.phase6.methods import (
    ENCODED_FEATURE_NAMES,
    FEATURE_ORDER,
    MODEL_RANDOM_SEED,
    build_method_predictions,
    ml_prediction,
    rule_prediction,
    scoped_metrics,
    select_hybrid_policy,
    select_ml_candidate,
)


ACCEPTED_CAMPAIGN_RUN_ID = "p6_r5_clean_campaign_recovery-20260811T070536Z"
ACCEPTED_CAMPAIGN_RESULT_SHA256 = (
    "c4c45e19e8b98d00a3fa2ed3b4d4a8ad2ba6debd04baae05c2d7d7377f9df4d2"
)
ACCEPTED_MERGED_DATASET_SHA256 = (
    "50dd030e51e4873eac7665980e033a0236e4ddf26e446b66bd3d11613c4a0a9d"
)
ACCEPTED_SPLIT_MANIFEST_SHA256 = (
    "adf70942a740be43e085aca67f9acb4085dd118827ceba8482913dbc6adb5f9f"
)
ACCEPTED_PARTITION_SHA256 = {
    "train": "128e3b6316a2f9065db0d8478b9571cd0474c39f3cec1c0e766e8f489884fec7",
    "validation": "8ae10a384f318e4e01a18da386585300547456ed32004eacd39054899176e60b",
    "test": "4757ba82cbe939fadb2491b1907f0f13cc70be9d3f0117758896931484bcfee7",
}
EXPECTED_ROWS = {"train": 36, "validation": 12, "test": 24}
DEFAULT_PLAN_PATH = Path("plans/campaigns/P6_EXTENDED_6CLASS_6CTX_V1.yml")
DEFAULT_PROTOCOL_PATH = Path("plans/phase6/P6_R6_METHOD_PROTOCOL_V1.json")
DEFAULT_CAMPAIGN_RESULT_PATH = Path(
    f"data/metadata/{ACCEPTED_CAMPAIGN_RUN_ID}.phase6-campaign.json"
)
DEFAULT_RAW_ROOT = Path(f"data/raw/{ACCEPTED_CAMPAIGN_RUN_ID}")
DEFAULT_SPLIT_ROOT = Path(
    f"data/processed/{ACCEPTED_CAMPAIGN_RUN_ID}-split"
)
DEFAULT_FREEZE_DIRECTORY = Path("models/p6_r6_six_class_v1")
DEFAULT_REPORT_DIRECTORY = Path("reports/experiments/p6_r6_six_class_v1")
DEFAULT_GATE_RESULT_PATH = Path(
    "data/metadata/p6_r6_six_class_method_gate_v1.json"
)
FREEZE_MANIFEST_NAME = "freeze_manifest.json"
FREEZE_RECEIPT_NAME = "freeze_receipt.json"
ESTIMATOR_NAME = "selected_estimator.joblib"
ML_SELECTION_NAME = "ml_selection.json"
HYBRID_SELECTION_NAME = "hybrid_selection.json"

IMPLEMENTATION_FILES = (
    "plans/phase6/P6_R6_METHOD_PROTOCOL_V1.json",
    "plans/campaigns/P6_EXTENDED_6CLASS_6CTX_V1.yml",
    "plans/taxonomies/P6_EXTENDED_FAULT_TAXONOMY_V1.json",
    "schemas/phase6_method_input_v1.schema.json",
    "schemas/phase6_method_prediction_v1.schema.json",
    "schemas/phase6_method_freeze_v1.schema.json",
    "schemas/phase6_method_report_v1.schema.json",
    "src/phase6/contracts.py",
    "src/phase6/methods.py",
    "src/phase6/coordinator.py",
    "src/dataset/contract_v3.py",
    "src/contracts/evidence_v3.py",
    "src/planning/fault_taxonomy.py",
)


class Phase6CoordinatorError(RuntimeError):
    """Raised when the P6-R6 freeze/report-only gate is violated."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise Phase6CoordinatorError(f"Path escaped repository root: {path}") from error


def _artifact(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": _relative(path, root),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _artifact_at_final_path(
    temporary_path: Path, final_path: Path, root: Path
) -> dict[str, Any]:
    """Bind bytes already written in a temp tree to their atomic final path."""
    return {
        "path": _relative(final_path, root),
        "sha256": sha256_file(temporary_path),
        "size_bytes": temporary_path.stat().st_size,
    }


def _software_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "scikit_learn": version("scikit-learn"),
        "numpy": version("numpy"),
        "joblib": version("joblib"),
    }


def _validate_schema(value: Mapping[str, Any], schema_path: Path, label: str) -> None:
    schema = read_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise Phase6CoordinatorError(
            f"{label} schema violation at {location}: {first.message}"
        )


def _require_absent(path: Path, label: str) -> None:
    if path.exists():
        raise Phase6CoordinatorError(f"{label} already exists: {path}")


def _load_protocol(path: Path) -> dict[str, Any]:
    protocol = read_json(path)
    expected = {
        "schema_version": 1,
        "protocol_id": "p6_r6_six_class_method_protocol_v1",
        "class_order": list(CLASS_ORDER),
        "feature_count": 10,
        "encoded_feature_count": 20,
        "fit_partition": "train",
        "fit_clean_rows": 36,
        "fit_masked_rows": 0,
        "selection_partition": "validation",
        "selection_clean_rows": 12,
        "selection_masked_rows": 48,
        "report_only_partition": "test",
        "report_only_clean_rows": 24,
        "report_only_masked_rows": 96,
        "missing_evidence_masks": list(MASK_ORDER),
        "ml_candidate_count": 6,
        "hybrid_policy_candidate_count": 5,
        "model_random_seed": MODEL_RANDOM_SEED,
        "test_use": "one_report_only_after_independent_freeze_verification",
        "statistical_superiority_test": "PROHIBITED",
        "refit_after_test": "PROHIBITED",
        "test_guided_revision": "PROHIBITED",
        "multiple_faults": "OUT_OF_SCOPE",
    }
    for name, value in expected.items():
        if protocol.get(name) != value:
            raise Phase6CoordinatorError(f"Protocol field drifted: {name}")
    return protocol


def _campaign_bindings(
    *, repository_root: Path, campaign_result_path: Path, split_root: Path
) -> tuple[dict[str, Any], dict[str, str]]:
    if sha256_file(campaign_result_path) != ACCEPTED_CAMPAIGN_RESULT_SHA256:
        raise Phase6CoordinatorError("Accepted P6-R5 campaign result hash drifted.")
    campaign = read_json(campaign_result_path)
    expected = {
        "campaign_run_id": ACCEPTED_CAMPAIGN_RUN_ID,
        "status": "COMPLETED",
        "completed_context_count": 6,
        "completed_experiment_count": 72,
        "dataset_row_count": 72,
        "diagnosis_count": 0,
        "prediction_count": 0,
        "metric_count": 0,
        "masked_row_count": 0,
        "test_partition_status": "SEALED_FOR_P6_R6_REPORT_ONLY",
    }
    for name, value in expected.items():
        if campaign.get(name) != value:
            raise Phase6CoordinatorError(f"P6-R5 campaign field drifted: {name}")
    merged = campaign.get("merged_dataset")
    if not isinstance(merged, Mapping) or merged.get("sha256") != (
        ACCEPTED_MERGED_DATASET_SHA256
    ):
        raise Phase6CoordinatorError("Accepted merged-dataset binding drifted.")
    split = campaign.get("split")
    if not isinstance(split, Mapping) or split.get("test_partition_status") != (
        "SEALED_FOR_P6_R6_REPORT_ONLY"
    ):
        raise Phase6CoordinatorError("P6-R5 test partition is not sealed.")
    split_manifest = split_root / "split_manifest.json"
    if sha256_file(split_manifest) != ACCEPTED_SPLIT_MANIFEST_SHA256:
        raise Phase6CoordinatorError("Accepted split-manifest hash drifted.")
    # Development may validate only train/validation bytes. The test hash is
    # carried from the sealed P6-R5 manifest and is not opened here.
    for partition in ("train", "validation"):
        path = split_root / f"{partition}.jsonl"
        if sha256_file(path) != ACCEPTED_PARTITION_SHA256[partition]:
            raise Phase6CoordinatorError(f"Accepted {partition} hash drifted.")
    test_path = split_root / "test.jsonl"
    if not test_path.is_file():
        raise Phase6CoordinatorError("Sealed test partition is absent.")
    plan = load_phase6_campaign_plan(
        repository_root / DEFAULT_PLAN_PATH, repository_root=repository_root
    )
    group_to_slot = {
        context.split_group_id: context.group_slot for context in plan.contexts
    }
    return campaign, group_to_slot


def _implementation_bindings(repository_root: Path) -> dict[str, dict[str, Any]]:
    return {
        relative: _artifact(repository_root / relative, repository_root)
        for relative in IMPLEMENTATION_FILES
    }


def _development_artifacts(
    directory: Path, repository_root: Path
) -> dict[str, dict[str, Any]]:
    names = (
        "train_inputs.jsonl",
        "train_targets.jsonl",
        "validation_inputs.jsonl",
        "validation_targets.jsonl",
        "validation_rule_predictions.jsonl",
        "validation_ml_predictions.jsonl",
        "validation_hybrid_predictions.jsonl",
        "development_summary.json",
        ML_SELECTION_NAME,
        HYBRID_SELECTION_NAME,
        ESTIMATOR_NAME,
    )
    return {name: _artifact(directory / name, repository_root) for name in names}


def create_development_freeze(
    *,
    repository_root: Path,
    freeze_directory: Path,
    report_directory: Path,
    gate_result_path: Path,
) -> dict[str, Any]:
    root = repository_root.resolve()
    freeze = (root / freeze_directory).resolve()
    report = (root / report_directory).resolve()
    gate = (root / gate_result_path).resolve()
    _require_absent(freeze, "P6-R6 freeze directory")
    _require_absent(report, "P6-R6 report directory")
    _require_absent(gate, "P6-R6 gate result")
    protocol_path = root / DEFAULT_PROTOCOL_PATH
    protocol = _load_protocol(protocol_path)
    campaign_result_path = root / DEFAULT_CAMPAIGN_RESULT_PATH
    split_root = root / DEFAULT_SPLIT_ROOT
    _, group_to_slot = _campaign_bindings(
        repository_root=root,
        campaign_result_path=campaign_result_path,
        split_root=split_root,
    )
    raw_root = root / DEFAULT_RAW_ROOT
    temporary = freeze.with_name(f".{freeze.name}.{uuid4().hex}.tmp")
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        train_inputs, train_targets, train_summary = build_partition_inputs(
            partition_path=split_root / "train.jsonl",
            partition="train",
            repository_root=root,
            raw_campaign_root=raw_root,
            group_to_slot=group_to_slot,
            include_masks=False,
            expected_clean_rows=EXPECTED_ROWS["train"],
        )
        validation_inputs, validation_targets, validation_summary = (
            build_partition_inputs(
                partition_path=split_root / "validation.jsonl",
                partition="validation",
                repository_root=root,
                raw_campaign_root=raw_root,
                group_to_slot=group_to_slot,
                include_masks=True,
                expected_clean_rows=EXPECTED_ROWS["validation"],
            )
        )
        if len(train_inputs) != 36 or len(validation_inputs) != 60:
            raise Phase6CoordinatorError("Development input counts drifted.")
        write_jsonl(temporary / "train_inputs.jsonl", train_inputs)
        write_jsonl(temporary / "train_targets.jsonl", train_targets)
        write_jsonl(temporary / "validation_inputs.jsonl", validation_inputs)
        write_jsonl(temporary / "validation_targets.jsonl", validation_targets)

        estimator, ml_selection = select_ml_candidate(
            train_inputs=train_inputs,
            train_targets=train_targets,
            validation_inputs=validation_inputs,
            validation_targets=validation_targets,
        )
        hybrid_selection = select_hybrid_policy(
            validation_inputs=validation_inputs,
            validation_targets=validation_targets,
            estimator=estimator,
        )
        selected_policy = hybrid_selection["selected_policy"]
        predictions = build_method_predictions(
            validation_inputs,
            estimator=estimator,
            hybrid_policy=selected_policy,
        )
        write_jsonl(
            temporary / "validation_rule_predictions.jsonl",
            predictions["rule_based_p6_v1"],
        )
        write_jsonl(
            temporary / "validation_ml_predictions.jsonl",
            predictions["machine_learning_p6_v1"],
        )
        write_jsonl(
            temporary / "validation_hybrid_predictions.jsonl",
            predictions["hybrid_p6_v1"],
        )
        write_json(temporary / ML_SELECTION_NAME, ml_selection)
        write_json(temporary / HYBRID_SELECTION_NAME, hybrid_selection)
        joblib.dump(estimator, temporary / ESTIMATOR_NAME)
        development_summary = {
            "schema_version": 1,
            "status": "DEVELOPMENT_ONLY",
            "train": train_summary,
            "validation": validation_summary,
            "selected_ml_candidate": ml_selection["selected_candidate"][
                "candidate_id"
            ],
            "selected_hybrid_policy": selected_policy["candidate_id"],
            "validation_metrics": {
                method_id: scoped_metrics(
                    validation_inputs, validation_targets, method_predictions
                )
                for method_id, method_predictions in predictions.items()
            },
            "test_inputs_read": 0,
            "test_predictions_or_metrics": "ABSENT",
        }
        write_json(temporary / "development_summary.json", development_summary)

        # Build the manifest after every development artifact is immutable.
        temporary.replace(freeze)
        artifacts = _development_artifacts(freeze, root)
        manifest = {
            "schema_version": 1,
            "freeze_id": "p6_r6_six_class_method_freeze_v1",
            "created_at_utc": utc_now(),
            "protocol": _artifact(protocol_path, root),
            "accepted_p6_r5": {
                "campaign_run_id": ACCEPTED_CAMPAIGN_RUN_ID,
                "campaign_result": _artifact(campaign_result_path, root),
                "merged_dataset_sha256": ACCEPTED_MERGED_DATASET_SHA256,
                "split_manifest": _artifact(
                    split_root / "split_manifest.json", root
                ),
                "train_sha256": ACCEPTED_PARTITION_SHA256["train"],
                "validation_sha256": ACCEPTED_PARTITION_SHA256["validation"],
                "sealed_test_sha256": ACCEPTED_PARTITION_SHA256["test"],
                "test_status": "SEALED_NOT_READ_BY_DEVELOPMENT",
            },
            "implementation": _implementation_bindings(root),
            "development_artifacts": artifacts,
            "selected_ml_candidate": ml_selection["selected_candidate"][
                "candidate_id"
            ],
            "selected_hybrid_policy": selected_policy["candidate_id"],
            "software": _software_versions(),
            "test_inputs_read": 0,
            "test_predictions_or_metrics": "ABSENT",
            "refit_after_test": "PROHIBITED",
        }
        _validate_schema(
            manifest,
            root / "schemas/phase6_method_freeze_v1.schema.json",
            "Method freeze",
        )
        write_json(freeze / FREEZE_MANIFEST_NAME, manifest)
        return manifest
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def verify_development_freeze(
    *,
    repository_root: Path,
    freeze_directory: Path,
    report_directory: Path,
    gate_result_path: Path,
    write_receipt: bool,
    allow_gate_result: bool = False,
) -> dict[str, Any]:
    root = repository_root.resolve()
    freeze = (root / freeze_directory).resolve()
    report = (root / report_directory).resolve()
    gate = (root / gate_result_path).resolve()
    manifest_path = freeze / FREEZE_MANIFEST_NAME
    manifest = read_json(manifest_path)
    if manifest.get("freeze_id") != "p6_r6_six_class_method_freeze_v1":
        raise Phase6CoordinatorError("Freeze identity drifted.")
    if manifest.get("test_inputs_read") != 0 or manifest.get(
        "test_predictions_or_metrics"
    ) != "ABSENT":
        raise Phase6CoordinatorError("Freeze contains test-derived output.")
    accepted = manifest.get("accepted_p6_r5")
    if not isinstance(accepted, Mapping) or accepted.get("test_status") != (
        "SEALED_NOT_READ_BY_DEVELOPMENT"
    ):
        raise Phase6CoordinatorError("Freeze test boundary drifted.")
    if accepted.get("sealed_test_sha256") != ACCEPTED_PARTITION_SHA256["test"]:
        raise Phase6CoordinatorError("Frozen sealed-test binding drifted.")
    protocol = manifest.get("protocol")
    if not isinstance(protocol, Mapping) or protocol.get("sha256") != sha256_file(
        root / DEFAULT_PROTOCOL_PATH
    ):
        raise Phase6CoordinatorError("Freeze protocol binding drifted.")
    _load_protocol(root / DEFAULT_PROTOCOL_PATH)
    implementation = manifest.get("implementation")
    if not isinstance(implementation, Mapping) or set(implementation) != set(
        IMPLEMENTATION_FILES
    ):
        raise Phase6CoordinatorError("Freeze implementation set drifted.")
    for relative in IMPLEMENTATION_FILES:
        reference = implementation[relative]
        if not isinstance(reference, Mapping) or reference.get("sha256") != (
            sha256_file(root / relative)
        ):
            raise Phase6CoordinatorError(
                f"Freeze implementation hash drifted: {relative}"
            )
    artifacts = manifest.get("development_artifacts")
    if not isinstance(artifacts, Mapping):
        raise Phase6CoordinatorError("Freeze development artifacts are invalid.")
    expected_artifacts = _development_artifacts(freeze, root)
    if set(artifacts) != set(expected_artifacts):
        raise Phase6CoordinatorError("Freeze development artifact set drifted.")
    for name, expected in expected_artifacts.items():
        reference = artifacts[name]
        if not isinstance(reference, Mapping) or reference.get("sha256") != expected[
            "sha256"
        ]:
            raise Phase6CoordinatorError(f"Freeze artifact hash drifted: {name}")
    ml_selection = read_json(freeze / ML_SELECTION_NAME)
    hybrid_selection = read_json(freeze / HYBRID_SELECTION_NAME)
    if ml_selection.get("test_predictions_or_metrics") != "ABSENT":
        raise Phase6CoordinatorError("ML selection contains test output.")
    if hybrid_selection.get("test_predictions_or_metrics") != "ABSENT":
        raise Phase6CoordinatorError("Hybrid selection contains test output.")
    if ml_selection.get("selected_candidate", {}).get("candidate_id") != manifest.get(
        "selected_ml_candidate"
    ):
        raise Phase6CoordinatorError("Selected ML candidate binding drifted.")
    if hybrid_selection.get("selected_policy", {}).get("candidate_id") != manifest.get(
        "selected_hybrid_policy"
    ):
        raise Phase6CoordinatorError("Selected Hybrid policy binding drifted.")
    estimator = joblib.load(freeze / ESTIMATOR_NAME)
    if set(str(value) for value in estimator.classes_) != set(CLASS_ORDER):
        raise Phase6CoordinatorError("Frozen estimator class universe drifted.")
    if len(getattr(estimator, "feature_names_in_", ())) not in (0, len(ENCODED_FEATURE_NAMES)):
        raise Phase6CoordinatorError("Frozen estimator feature width drifted.")
    if report.exists():
        raise Phase6CoordinatorError("Report-only output exists before authorization.")
    if gate.exists() and not allow_gate_result:
        raise Phase6CoordinatorError("Gate result exists before freeze receipt.")
    receipt_path = freeze / FREEZE_RECEIPT_NAME
    if write_receipt:
        _require_absent(receipt_path, "Independent freeze receipt")
        receipt = {
            "schema_version": 1,
            "receipt_id": "p6_r6_independent_freeze_verification_v1",
            "verified_at_utc": utc_now(),
            "freeze_manifest": _artifact(manifest_path, root),
            "selected_estimator": _artifact(freeze / ESTIMATOR_NAME, root),
            "ml_selection": _artifact(freeze / ML_SELECTION_NAME, root),
            "hybrid_selection": _artifact(freeze / HYBRID_SELECTION_NAME, root),
            "implementation_file_count": len(IMPLEMENTATION_FILES),
            "development_artifact_count": len(expected_artifacts),
            "test_inputs_read": 0,
            "test_predictions_or_metrics": "ABSENT",
            "authorization": "ONE_REPORT_ONLY_TEST_EVALUATION",
        }
        write_json(receipt_path, receipt)
        return receipt
    return {
        "freeze_manifest_sha256": sha256_file(manifest_path),
        "selected_ml_candidate": manifest["selected_ml_candidate"],
        "selected_hybrid_policy": manifest["selected_hybrid_policy"],
    }


def _verify_receipt(
    *, repository_root: Path, freeze_directory: Path
) -> dict[str, Any]:
    root = repository_root.resolve()
    freeze = (root / freeze_directory).resolve()
    receipt = read_json(freeze / FREEZE_RECEIPT_NAME)
    if receipt.get("authorization") != "ONE_REPORT_ONLY_TEST_EVALUATION":
        raise Phase6CoordinatorError("Independent freeze receipt is not authorized.")
    manifest_ref = receipt.get("freeze_manifest")
    if not isinstance(manifest_ref, Mapping) or manifest_ref.get("sha256") != (
        sha256_file(freeze / FREEZE_MANIFEST_NAME)
    ):
        raise Phase6CoordinatorError("Freeze receipt manifest binding drifted.")
    for key, name in (
        ("selected_estimator", ESTIMATOR_NAME),
        ("ml_selection", ML_SELECTION_NAME),
        ("hybrid_selection", HYBRID_SELECTION_NAME),
    ):
        reference = receipt.get(key)
        if not isinstance(reference, Mapping) or reference.get("sha256") != (
            sha256_file(freeze / name)
        ):
            raise Phase6CoordinatorError(f"Freeze receipt binding drifted: {key}")
    return receipt


def _compact_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metrics.items() if key != "records"}


def _build_method_report(
    *,
    method_id: str,
    inputs: Sequence[Mapping[str, Any]],
    targets: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, Any]],
    input_reference: Mapping[str, Any],
    target_reference: Mapping[str, Any],
    prediction_reference: Mapping[str, Any],
    schema_path: Path,
) -> dict[str, Any]:
    scoped = scoped_metrics(inputs, targets, predictions)
    records = scoped["overall"].pop("records")
    compact: dict[str, Any] = {}
    for key in ("overall", "clean", "masked_overall"):
        compact[key] = _compact_metrics(scoped[key]) if scoped[key] else None
    compact["by_mask"] = {
        name: _compact_metrics(value) if value else None
        for name, value in scoped["by_mask"].items()
    }
    compact["by_context"] = {
        name: _compact_metrics(value)
        for name, value in scoped["by_context"].items()
    }
    compact["by_class"] = {
        name: _compact_metrics(value) for name, value in scoped["by_class"].items()
    }
    report = {
        "schema_version": 1,
        "report_id": f"p6_r6_{method_id}_report_v1",
        "method_id": method_id,
        "evaluation_role": "TEST_REPORT_ONLY",
        "class_order": list(CLASS_ORDER),
        "input_count": len(inputs),
        "clean_input_count": sum(item["mask_id"] is None for item in inputs),
        "masked_input_count": sum(item["mask_id"] is not None for item in inputs),
        "sources": {
            "inputs": dict(input_reference),
            "targets": dict(target_reference),
            "predictions": dict(prediction_reference),
        },
        "scopes": compact,
        "records": records,
        "test_influenced_fitting_or_selection": False,
        "statistical_superiority_claim": False,
    }
    _validate_schema(
        report,
        schema_path,
        "Method report",
    )
    return report


def _build_comparison(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "comparison_id": "p6_r6_rules_ml_hybrid_report_only_comparison_v1",
        "comparison_type": "DESCRIPTIVE_ONLY",
        "test_role": "REPORT_ONLY",
        "method_order": [
            "rule_based_p6_v1",
            "machine_learning_p6_v1",
            "hybrid_p6_v1",
        ],
        "primary_metrics": [
            "accuracy",
            "macro_f1",
            "exact_diagnosis_rate",
            "affected_prefix_rate",
            "coverage",
            "abstention_rate",
            "insufficient_evidence_rate",
        ],
        "methods": {
            method_id: {
                scope: {
                    "sample_count": report["scopes"][scope]["sample_count"],
                    "accuracy": report["scopes"][scope]["accuracy"],
                    "macro_f1": report["scopes"][scope]["macro"]["f1"],
                    "exact_diagnosis_rate": report["scopes"][scope][
                        "exact_diagnosis"
                    ]["rate"],
                    "affected_prefix_rate": report["scopes"][scope][
                        "affected_prefix_fault_only"
                    ]["rate"],
                    "coverage": report["scopes"][scope]["coverage"],
                    "abstention_rate": report["scopes"][scope][
                        "abstention_rate"
                    ],
                    "insufficient_evidence_rate": report["scopes"][scope][
                        "insufficient_evidence_rate"
                    ],
                }
                for scope in ("clean", "masked_overall", "overall")
            }
            for method_id, report in reports.items()
        },
        "statistical_superiority_test": "NOT_PERFORMED",
        "test_guided_revision": "PROHIBITED",
    }


def run_report_only_evaluation(
    *,
    repository_root: Path,
    freeze_directory: Path,
    report_directory: Path,
    gate_result_path: Path,
) -> dict[str, Any]:
    root = repository_root.resolve()
    freeze = (root / freeze_directory).resolve()
    report = (root / report_directory).resolve()
    gate_path = (root / gate_result_path).resolve()
    _require_absent(report, "P6-R6 report-only directory")
    _require_absent(gate_path, "P6-R6 gate result")
    _verify_receipt(repository_root=root, freeze_directory=freeze_directory)
    verify_development_freeze(
        repository_root=root,
        freeze_directory=freeze_directory,
        report_directory=report_directory,
        gate_result_path=gate_result_path,
        write_receipt=False,
        allow_gate_result=False,
    )
    gate = {
        "schema_version": 1,
        "gate_id": "p6_r6_six_class_method_gate_v1",
        "status": "REPORT_ONLY_OPENING",
        "started_at_utc": utc_now(),
        "completed_at_utc": None,
        "development_freeze_verified": True,
        "test_opened": True,
        "test_opened_at_utc": utc_now(),
        "test_evaluation_attempt_count": 1,
        "test_source_sha256": None,
        "report_directory": _relative(report, root),
        "error": None,
        "artifacts": None,
    }
    write_json(gate_path, gate)
    temporary = report.with_name(f".{report.name}.{uuid4().hex}.tmp")
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        split_root = root / DEFAULT_SPLIT_ROOT
        test_path = split_root / "test.jsonl"
        observed_test_hash = sha256_file(test_path)
        gate["test_source_sha256"] = observed_test_hash
        write_json(gate_path, gate)
        if observed_test_hash != ACCEPTED_PARTITION_SHA256["test"]:
            raise Phase6CoordinatorError("Sealed test partition hash drifted.")
        _, group_to_slot = _campaign_bindings(
            repository_root=root,
            campaign_result_path=root / DEFAULT_CAMPAIGN_RESULT_PATH,
            split_root=split_root,
        )
        test_inputs, test_targets, test_summary = build_partition_inputs(
            partition_path=test_path,
            partition="test",
            repository_root=root,
            raw_campaign_root=root / DEFAULT_RAW_ROOT,
            group_to_slot=group_to_slot,
            include_masks=True,
            expected_clean_rows=EXPECTED_ROWS["test"],
        )
        if len(test_inputs) != 120:
            raise Phase6CoordinatorError("Report-only input count must be 120.")
        write_jsonl(temporary / "test_inputs.jsonl", test_inputs)
        write_jsonl(temporary / "test_targets.jsonl", test_targets)
        estimator = joblib.load(freeze / ESTIMATOR_NAME)
        hybrid_selection = read_json(freeze / HYBRID_SELECTION_NAME)
        policy = hybrid_selection["selected_policy"]
        predictions = build_method_predictions(
            test_inputs, estimator=estimator, hybrid_policy=policy
        )
        prediction_files = {
            "rule_based_p6_v1": "rule_predictions.jsonl",
            "machine_learning_p6_v1": "ml_predictions.jsonl",
            "hybrid_p6_v1": "hybrid_predictions.jsonl",
        }
        for method_id, file_name in prediction_files.items():
            write_jsonl(temporary / file_name, predictions[method_id])
        input_ref = _artifact_at_final_path(
            temporary / "test_inputs.jsonl", report / "test_inputs.jsonl", root
        )
        target_ref = _artifact_at_final_path(
            temporary / "test_targets.jsonl", report / "test_targets.jsonl", root
        )
        reports: dict[str, dict[str, Any]] = {}
        report_files = {
            "rule_based_p6_v1": "rule_report.json",
            "machine_learning_p6_v1": "ml_report.json",
            "hybrid_p6_v1": "hybrid_report.json",
        }
        for method_id, file_name in report_files.items():
            prediction_ref = _artifact_at_final_path(
                temporary / prediction_files[method_id],
                report / prediction_files[method_id],
                root,
            )
            report_value = _build_method_report(
                method_id=method_id,
                inputs=test_inputs,
                targets=test_targets,
                predictions=predictions[method_id],
                input_reference=input_ref,
                target_reference=target_ref,
                prediction_reference=prediction_ref,
                schema_path=root / "schemas/phase6_method_report_v1.schema.json",
            )
            reports[method_id] = report_value
            write_json(temporary / file_name, report_value)
        write_json(temporary / "cross_method_comparison.json", _build_comparison(reports))
        run_manifest = {
            "schema_version": 1,
            "run_id": "p6_r6_six_class_report_only_v1",
            "status": "COMPLETED",
            "test_use": "ONE_REPORT_ONLY_EVALUATION",
            "freeze_manifest": _artifact(freeze / FREEZE_MANIFEST_NAME, root),
            "freeze_receipt": _artifact(freeze / FREEZE_RECEIPT_NAME, root),
            "selected_estimator": _artifact(freeze / ESTIMATOR_NAME, root),
            "ml_selection": _artifact(freeze / ML_SELECTION_NAME, root),
            "hybrid_selection": _artifact(freeze / HYBRID_SELECTION_NAME, root),
            "test_summary": test_summary,
            "method_ids": list(reports),
            "test_clean_inputs": 24,
            "test_masked_inputs": 96,
            "test_total_inputs": 120,
            "model_refit_after_freeze": False,
            "policy_reselection_after_freeze": False,
            "test_guided_revision": False,
            "statistical_superiority_test": "NOT_PERFORMED",
        }
        write_json(temporary / "run_manifest.json", run_manifest)
        temporary.replace(report)
        artifact_names = (
            "test_inputs.jsonl",
            "test_targets.jsonl",
            "rule_predictions.jsonl",
            "ml_predictions.jsonl",
            "hybrid_predictions.jsonl",
            "rule_report.json",
            "ml_report.json",
            "hybrid_report.json",
            "cross_method_comparison.json",
            "run_manifest.json",
        )
        artifacts = {name: _artifact(report / name, root) for name in artifact_names}
        gate.update(
            {
                "status": "COMPLETED",
                "completed_at_utc": utc_now(),
                "artifacts": artifacts,
            }
        )
        write_json(gate_path, gate)
        return {
            "gate": gate,
            "reports": reports,
            "comparison": read_json(report / "cross_method_comparison.json"),
        }
    except Exception as error:
        if temporary.exists():
            shutil.rmtree(temporary)
        gate.update(
            {
                "status": "FAILED_AFTER_REPORT_ONLY_OPEN",
                "completed_at_utc": utc_now(),
                "error": {
                    "type": type(error).__name__,
                    "message": str(error),
                },
            }
        )
        write_json(gate_path, gate)
        raise


def run_full_gate(
    *,
    repository_root: Path,
    freeze_directory: Path = DEFAULT_FREEZE_DIRECTORY,
    report_directory: Path = DEFAULT_REPORT_DIRECTORY,
    gate_result_path: Path = DEFAULT_GATE_RESULT_PATH,
) -> dict[str, Any]:
    print("[1/4] verify P6-R5 sealed development boundary")
    manifest = create_development_freeze(
        repository_root=repository_root,
        freeze_directory=freeze_directory,
        report_directory=report_directory,
        gate_result_path=gate_result_path,
    )
    print(
        "[2/4] development freeze created: "
        f"ML={manifest['selected_ml_candidate']} "
        f"Hybrid={manifest['selected_hybrid_policy']}"
    )
    receipt = verify_development_freeze(
        repository_root=repository_root,
        freeze_directory=freeze_directory,
        report_directory=report_directory,
        gate_result_path=gate_result_path,
        write_receipt=True,
    )
    print(
        "[3/4] independent freeze verification passed: "
        f"{receipt['authorization']}"
    )
    result = run_report_only_evaluation(
        repository_root=repository_root,
        freeze_directory=freeze_directory,
        report_directory=report_directory,
        gate_result_path=gate_result_path,
    )
    print("[4/4] one report-only clean/missing-evidence evaluation completed")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the P6-R6 development freeze and one report-only gate."
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument(
        "command", choices=("run", "freeze", "verify", "report")
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    root = arguments.repository_root.resolve()
    try:
        if arguments.command == "run":
            result = run_full_gate(repository_root=root)
            freeze = root / DEFAULT_FREEZE_DIRECTORY
            report = root / DEFAULT_REPORT_DIRECTORY
            manifest = read_json(freeze / FREEZE_MANIFEST_NAME)
            comparison = result["comparison"]
            result = {
                "status": result["gate"]["status"],
                "test_evaluation_attempt_count": result["gate"][
                    "test_evaluation_attempt_count"
                ],
                "selected_ml_candidate": manifest["selected_ml_candidate"],
                "selected_hybrid_policy": manifest["selected_hybrid_policy"],
                "freeze_manifest_sha256": sha256_file(
                    freeze / FREEZE_MANIFEST_NAME
                ),
                "freeze_receipt_sha256": sha256_file(
                    freeze / FREEZE_RECEIPT_NAME
                ),
                "run_manifest_sha256": sha256_file(
                    report / "run_manifest.json"
                ),
                "cross_method_comparison_sha256": sha256_file(
                    report / "cross_method_comparison.json"
                ),
                "test_clean_inputs": 24,
                "test_masked_inputs": 96,
                "test_total_inputs": 120,
                "method_summaries": comparison["methods"],
                "comparison_type": "DESCRIPTIVE_ONLY",
                "statistical_superiority_test": "NOT_PERFORMED",
                "model_refit_after_freeze": False,
                "policy_reselection_after_freeze": False,
            }
        elif arguments.command == "freeze":
            result = create_development_freeze(
                repository_root=root,
                freeze_directory=DEFAULT_FREEZE_DIRECTORY,
                report_directory=DEFAULT_REPORT_DIRECTORY,
                gate_result_path=DEFAULT_GATE_RESULT_PATH,
            )
        elif arguments.command == "verify":
            result = verify_development_freeze(
                repository_root=root,
                freeze_directory=DEFAULT_FREEZE_DIRECTORY,
                report_directory=DEFAULT_REPORT_DIRECTORY,
                gate_result_path=DEFAULT_GATE_RESULT_PATH,
                write_receipt=True,
            )
        else:
            result = run_report_only_evaluation(
                repository_root=root,
                freeze_directory=DEFAULT_FREEZE_DIRECTORY,
                report_directory=DEFAULT_REPORT_DIRECTORY,
                gate_result_path=DEFAULT_GATE_RESULT_PATH,
            )
    except (
        Phase6CoordinatorError,
        Phase6MethodContractError,
        OSError,
        ValueError,
    ) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
