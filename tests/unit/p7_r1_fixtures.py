from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.campaign.phase6_plan import CLASS_ORDER
from src.phase6.contracts import MASK_ORDER, apply_method_input_mask
from src.phase6.methods import rule_prediction, scoped_metrics
from src.phase7.catalog import (
    ARTIFACT_SPECS,
    DEFAULT_CATALOG_MANIFEST_PATH,
    DEFAULT_INTERFACE_PLAN_PATH,
    FREEZE_ROOT,
    GATE_PATH,
    METHOD_ORDER,
    PREDICTION_FILES,
    REPORT_ARTIFACT_NAMES,
    REPORT_FILES,
    REPORT_ROOT,
    ROOT_IDS,
    build_catalog_manifest,
)
from tests.unit.p6_r6_fixtures import six_class_inputs


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
            for value in values
        ),
        encoding="utf-8",
    )


def _digest(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative,
        "sha256": _digest(path),
        "size_bytes": path.stat().st_size,
    }


def _estimator_reference() -> dict[str, Any]:
    return {
        "path": f"{FREEZE_ROOT}/selected_estimator.joblib",
        "sha256": "e" * 64,
        "size_bytes": 123,
    }


def _compact(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(item) for key, item in value.items() if key != "records"}


def _method_report(
    *,
    root: Path,
    method_id: str,
    inputs: Sequence[Mapping[str, Any]],
    targets: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    metrics = scoped_metrics(inputs, targets, predictions)
    records = metrics["overall"].pop("records")
    scopes = {
        scope: _compact(metrics[scope]) for scope in ("overall", "clean", "masked_overall")
    }
    scopes["by_mask"] = {
        name: _compact(value) for name, value in metrics["by_mask"].items()
    }
    scopes["by_context"] = {
        name: _compact(value) for name, value in metrics["by_context"].items()
    }
    scopes["by_class"] = {
        name: _compact(value) for name, value in metrics["by_class"].items()
    }
    return {
        "schema_version": 1,
        "report_id": f"p6_r6_{method_id}_report_v1",
        "method_id": method_id,
        "evaluation_role": "TEST_REPORT_ONLY",
        "class_order": list(CLASS_ORDER),
        "input_count": 120,
        "clean_input_count": 24,
        "masked_input_count": 96,
        "sources": {
            "inputs": _reference(root, f"{REPORT_ROOT}/test_inputs.jsonl"),
            "targets": _reference(root, f"{REPORT_ROOT}/test_targets.jsonl"),
            "predictions": _reference(
                root, f"{REPORT_ROOT}/{PREDICTION_FILES[method_id]}"
            ),
        },
        "scopes": scopes,
        "records": records,
        "test_influenced_fitting_or_selection": False,
        "statistical_superiority_claim": False,
    }


def _comparison(reports: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "comparison_id": "p6_r6_rules_ml_hybrid_report_only_comparison_v1",
        "comparison_type": "DESCRIPTIVE_ONLY",
        "test_role": "REPORT_ONLY",
        "method_order": list(METHOD_ORDER),
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
                    "abstention_rate": report["scopes"][scope]["abstention_rate"],
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


def build_p7_fixture_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    clean_inputs, clean_targets = six_class_inputs(partition="test", repetitions=4)
    inputs: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for method_input, target in zip(clean_inputs, clean_targets, strict=True):
        inputs.append(deepcopy(method_input))
        targets.append(deepcopy(target))
        for mask_id in MASK_ORDER:
            masked = apply_method_input_mask(method_input, mask_id)
            inputs.append(masked)
            targets.append({**deepcopy(target), "input_id": masked["input_id"]})

    input_path = root / REPORT_ROOT / "test_inputs.jsonl"
    target_path = root / REPORT_ROOT / "test_targets.jsonl"
    _write_jsonl(input_path, inputs)
    _write_jsonl(target_path, targets)

    predictions: dict[str, list[dict[str, Any]]] = {
        method_id: [] for method_id in METHOD_ORDER
    }
    for method_input, target in zip(inputs, targets, strict=True):
        predictions["rule_based_p6_v1"].append(rule_prediction(method_input))
        for method_id in ("machine_learning_p6_v1", "hybrid_p6_v1"):
            predictions[method_id].append(
                {
                    "schema_version": 1,
                    "input_id": method_input["input_id"],
                    "sample_id": method_input["sample_id"],
                    "method_id": method_id,
                    "status": "RESOLVED",
                    "predicted_fault_type": target["labels"]["fault_type"],
                    "confidence": 0.75,
                    "diagnosis": deepcopy(target["labels"]),
                    "reason": "Frozen fixture prediction.",
                }
            )
    for method_id, file_name in PREDICTION_FILES.items():
        _write_jsonl(root / REPORT_ROOT / file_name, predictions[method_id])

    ml_selection = {
        "schema_version": 1,
        "selection_id": "p6_r6_ml_selection_v1",
        "selected_candidate": {"candidate_id": "logreg_l2_c1"},
        "test_predictions_or_metrics": "ABSENT",
    }
    hybrid_selection = {
        "schema_version": 1,
        "selection_id": "p6_r6_hybrid_selection_v1",
        "selected_policy": {"candidate_id": "rule_then_ml_fallback_v1"},
        "test_predictions_or_metrics": "ABSENT",
    }
    _write_json(root / FREEZE_ROOT / "ml_selection.json", ml_selection)
    _write_json(root / FREEZE_ROOT / "hybrid_selection.json", hybrid_selection)
    manifest = {
        "schema_version": 1,
        "freeze_id": "p6_r6_six_class_method_freeze_v1",
        "selected_ml_candidate": "logreg_l2_c1",
        "selected_hybrid_policy": "rule_then_ml_fallback_v1",
        "test_inputs_read": 0,
        "test_predictions_or_metrics": "ABSENT",
    }
    _write_json(root / FREEZE_ROOT / "freeze_manifest.json", manifest)
    receipt = {
        "schema_version": 1,
        "receipt_id": "p6_r6_independent_freeze_verification_v1",
        "freeze_manifest": _reference(root, f"{FREEZE_ROOT}/freeze_manifest.json"),
        "selected_estimator": _estimator_reference(),
        "ml_selection": _reference(root, f"{FREEZE_ROOT}/ml_selection.json"),
        "hybrid_selection": _reference(root, f"{FREEZE_ROOT}/hybrid_selection.json"),
        "authorization": "ONE_REPORT_ONLY_TEST_EVALUATION",
    }
    _write_json(root / FREEZE_ROOT / "freeze_receipt.json", receipt)

    reports: dict[str, dict[str, Any]] = {}
    for method_id, report_name in REPORT_FILES.items():
        report = _method_report(
            root=root,
            method_id=method_id,
            inputs=inputs,
            targets=targets,
            predictions=predictions[method_id],
        )
        reports[method_id] = report
        _write_json(root / REPORT_ROOT / report_name, report)
    _write_json(root / REPORT_ROOT / "cross_method_comparison.json", _comparison(reports))
    run = {
        "schema_version": 1,
        "run_id": "p6_r6_six_class_report_only_v1",
        "status": "COMPLETED",
        "test_use": "ONE_REPORT_ONLY_EVALUATION",
        "freeze_manifest": _reference(root, f"{FREEZE_ROOT}/freeze_manifest.json"),
        "freeze_receipt": _reference(root, f"{FREEZE_ROOT}/freeze_receipt.json"),
        "selected_estimator": _estimator_reference(),
        "ml_selection": _reference(root, f"{FREEZE_ROOT}/ml_selection.json"),
        "hybrid_selection": _reference(root, f"{FREEZE_ROOT}/hybrid_selection.json"),
        "method_ids": list(METHOD_ORDER),
        "test_clean_inputs": 24,
        "test_masked_inputs": 96,
        "test_total_inputs": 120,
        "model_refit_after_freeze": False,
        "policy_reselection_after_freeze": False,
        "test_guided_revision": False,
        "statistical_superiority_test": "NOT_PERFORMED",
    }
    _write_json(root / REPORT_ROOT / "run_manifest.json", run)
    gate = {
        "schema_version": 1,
        "gate_id": "p6_r6_six_class_method_gate_v1",
        "status": "COMPLETED",
        "development_freeze_verified": True,
        "test_opened": True,
        "test_evaluation_attempt_count": 1,
        "error": None,
        "artifacts": {
            name: _reference(root, f"{REPORT_ROOT}/{name}")
            for name in REPORT_ARTIFACT_NAMES
        },
    }
    _write_json(root / GATE_PATH, gate)

    root_artifacts = {
        "freeze_manifest": f"{FREEZE_ROOT}/freeze_manifest.json",
        "freeze_receipt": f"{FREEZE_ROOT}/freeze_receipt.json",
        "run_manifest": f"{REPORT_ROOT}/run_manifest.json",
        "cross_method_comparison": f"{REPORT_ROOT}/cross_method_comparison.json",
    }
    plan = {
        "schema_version": 1,
        "contract_id": "p7_readonly_dashboard_api_v1",
        "status": "FROZEN_FOR_IMPLEMENTATION",
        "mode": "READ_ONLY_ACCEPTED_ARTIFACT_PROJECTION",
        "accepted_root_bindings": [
            {
                "artifact_id": artifact_id,
                "path": root_artifacts[artifact_id],
                "sha256": _digest(root / root_artifacts[artifact_id]),
            }
            for artifact_id in ROOT_IDS
        ],
        "projection_source_allowlist": [spec.path for spec in ARTIFACT_SPECS],
    }
    _write_json(root / DEFAULT_INTERFACE_PLAN_PATH, plan)
    catalog = build_catalog_manifest(repository_root=root)
    _write_json(root / DEFAULT_CATALOG_MANIFEST_PATH, catalog)
    return root
