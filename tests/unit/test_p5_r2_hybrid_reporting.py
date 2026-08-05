from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import src.hybrid.engine as engine
import src.hybrid.policy as policy_module
import src.hybrid.reporting as reporting
from src.evaluation.evaluator import evaluate_prediction
from src.evaluation.reporting import build_method_evaluation_result
from src.hybrid.engine import HybridEngineError, run_hybrid_selection, sha256_file
from src.hybrid.reporting import (
    HybridReportingError,
    build_cross_method_comparison,
    build_p5_r2_bundle,
    verify_p5_r2_bundle,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_TEMPLATE = ROOT / "policies/hybrid/P5_HYBRID_POLICY_V1.json"
POLICY_SCHEMA = ROOT / "schemas/hybrid_policy_v1.schema.json"
PREDICTION_SCHEMA = ROOT / "schemas/hybrid_prediction_v1.schema.json"
SELECTION_SCHEMA = ROOT / "schemas/hybrid_selection_v1.schema.json"
METHOD_SCHEMA = ROOT / "schemas/method_evaluation_result_v1.schema.json"
COMPARISON_SCHEMA = ROOT / "schemas/cross_method_comparison_v1.schema.json"
CLASSES = ("no_fault", "missing_static_route", "wrong_next_hop")
GROUPS = {
    "train": (
        "CTX_G03_TOP02_BRANCH_MID",
        "CTX_G04_TOP02_DUAL_TRANSIT",
        "CTX_G05_TOP03_ASYMMETRIC_RETURN",
    ),
    "validation": ("CTX_G01_TOP01_LINEAR_2R",),
    "test": ("CTX_G02_TOP02_CHAIN_3R",),
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def reference(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def rule_prediction(fault_type: str) -> dict[str, Any]:
    rule_id = {
        "no_fault": "R_BASELINE_001",
        "missing_static_route": "R_ROUTING_001",
        "wrong_next_hop": "R_ROUTING_002",
    }[fault_type]
    diagnosis = None
    if fault_type != "no_fault":
        diagnosis = {
            "category": "routing",
            "fault_type": fault_type,
            "location": "r1",
            "affected_prefix": "10.10.2.0/24",
        }
        if fault_type == "wrong_next_hop":
            diagnosis["observed_next_hop"] = "10.10.12.254"
    return {
        "schema_version": 1,
        "method": "rule_based",
        "status": (
            "NO_FAULT_DETECTED"
            if fault_type == "no_fault"
            else "DIAGNOSIS_PRODUCED"
        ),
        "diagnosis": diagnosis,
        "matched_rules": [rule_id],
        "rule_support_score": 1.0,
        "score_interpretation": (
            "Deterministic rule support, not a calibrated probability."
        ),
        "supporting_evidence": ["Synthetic evidence support."],
        "contradicting_evidence": [],
    }


def ml_prediction(
    sample_id: str,
    fault_type: str,
    model_sha256: str,
) -> dict[str, Any]:
    diagnosis = None
    if fault_type != "no_fault":
        diagnosis = {
            "category": "routing",
            "fault_type": fault_type,
            "location": None,
            "affected_prefix": None,
        }
    return {
        "schema_version": 1,
        "sample_id": sample_id,
        "method": "machine_learning",
        "status": (
            "NO_FAULT_DETECTED"
            if fault_type == "no_fault"
            else "DIAGNOSIS_PRODUCED"
        ),
        "diagnosis": {} if fault_type == "no_fault" else diagnosis,
        "supporting_evidence": {
            "source": "ml_feature_matrix_v1",
            "observations": [],
        },
        "model_explanation": {
            "predicted_class": fault_type,
            "predicted_class_probability": 1.0,
            "class_probabilities": {fault_type: 1.0},
        },
        "model_binding": {
            "pipeline_id": "p4_r1_ml_pipeline_v1",
            "candidate_id": "logreg_l2_c0_1",
            "model_sha256": model_sha256,
        },
        "limitations": ["Synthetic ML prediction."],
    }


def ground_truth(fault_type: str) -> dict[str, Any]:
    return {
        "fault_category": None if fault_type == "no_fault" else "routing",
        "fault_type": fault_type,
        "fault_location": None if fault_type == "no_fault" else "r1",
        "affected_prefix": (
            None if fault_type == "no_fault" else "10.10.2.0/24"
        ),
    }


def make_runtime_sources(
    base: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    project = base / "project"
    source_paths = {
        "rule_baseline": project / "reports/rule.json",
        "ml_feature_matrix": project / "reports/matrix.json",
        "ml_selection": project / "models/ml/selection.json",
        "ml_model": project / "models/ml/estimator.joblib",
        "ml_report": project / "reports/ml/method_evaluation_result.json",
    }
    write_json(source_paths["ml_feature_matrix"], {"matrix_id": "synthetic"})
    write_json(source_paths["ml_selection"], {"selection_id": "synthetic"})
    source_paths["ml_model"].parent.mkdir(parents=True, exist_ok=True)
    source_paths["ml_model"].write_bytes(b"synthetic-model")
    model_hash = sha256_file(source_paths["ml_model"])

    campaign_path = project / "data/metadata/campaign_result.json"
    split_manifest_path = project / "data/processed/split_manifest.json"
    merged_path = project / "data/processed/merged.jsonl"
    rule_audit_path = project / "reports/rule_audit.json"
    write_json(campaign_path, {"campaign_id": "P2_ROUTING_5CTX_V1"})
    write_json(split_manifest_path, {"split_id": "synthetic"})
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path.write_text("synthetic\n", encoding="utf-8")
    write_json(rule_audit_path, {"status": "PASS"})

    partition_files: dict[str, Path] = {}
    for partition in reporting.PARTITION_ORDER:
        path = project / "data/processed/splits" / f"{partition}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{partition}\n", encoding="utf-8")
        partition_files[partition] = path

    dataset_binding = {
        "campaign_id": "P2_ROUTING_5CTX_V1",
        "campaign_run_id": "synthetic-run-v1",
        "dataset_row_schema_version": 2,
        "merged_dataset": {
            "path": str(merged_path.resolve()),
            "sha256": sha256_file(merged_path),
            "row_count": 30,
        },
        "split": {
            "algorithm": "complete_context_group_hash_v2",
            "seed": 20260730,
            "ratios": {"train": 0.6, "validation": 0.2, "test": 0.2},
            "manifest_path": str(split_manifest_path.resolve()),
            "manifest_sha256": sha256_file(split_manifest_path),
            "partitions": {
                partition: {
                    "path": str(partition_files[partition].resolve()),
                    "sha256": sha256_file(partition_files[partition]),
                    "row_count": reporting.EXPECTED_PARTITION_ROWS[partition],
                    "group_count": len(GROUPS[partition]),
                    "group_ids": list(GROUPS[partition]),
                }
                for partition in reporting.PARTITION_ORDER
            },
            "no_cross_partition_group": True,
        },
    }

    rule_records: list[dict[str, Any]] = []
    ml_records: list[dict[str, Any]] = []
    sequence = 0
    for partition in reporting.PARTITION_ORDER:
        for group_id in GROUPS[partition]:
            for fault_type in CLASSES:
                for repetition in (1, 2):
                    sequence += 1
                    sample_id = (
                        f"sample-{partition}-{sequence}-{fault_type}-{repetition}"
                    )
                    raw = project / "data/raw" / sample_id
                    ml_sample = project / "reports/ml/samples" / sample_id
                    manifest_path = raw / "experiment_manifest.json"
                    ground_truth_path = raw / "ground_truth.json"
                    evidence_path = raw / "parsed/evidence.json"
                    rule_path = raw / "diagnosis/rule_based.json"
                    rule_evaluation_path = raw / "evaluation/rule_based.json"
                    ml_path = ml_sample / "prediction.json"
                    ml_evaluation_path = ml_sample / "evaluation.json"
                    write_json(manifest_path, {"experiment_id": sample_id})
                    write_json(ground_truth_path, ground_truth(fault_type))
                    write_json(evidence_path, {"schema_version": 2})
                    rule_document = rule_prediction(fault_type)
                    ml_document = ml_prediction(sample_id, fault_type, model_hash)
                    write_json(rule_path, rule_document)
                    write_json(ml_path, ml_document)
                    rule_evaluation = evaluate_prediction(
                        ground_truth(fault_type),
                        rule_document,
                    )
                    rule_evaluation["sample_id"] = sample_id
                    ml_evaluation = evaluate_prediction(
                        ground_truth(fault_type),
                        ml_document,
                    )
                    ml_evaluation["sample_id"] = sample_id
                    write_json(rule_evaluation_path, rule_evaluation)
                    write_json(ml_evaluation_path, ml_evaluation)
                    shared = {
                        "experiment_manifest": reference(manifest_path),
                        "ground_truth": reference(ground_truth_path),
                        "evidence": reference(evidence_path),
                    }
                    rule_metrics = rule_evaluation["metrics"]
                    ml_metrics = ml_evaluation["metrics"]
                    rule_records.append(
                        {
                            "sample_id": sample_id,
                            "partition": partition,
                            "split_group_id": group_id,
                            "expected_fault_type": fault_type,
                            "predicted_fault_type": fault_type,
                            "classification_correct": True,
                            "exact_match": bool(rule_metrics["exact_match"]),
                            "affected_prefix_correct": bool(
                                rule_metrics["affected_prefix_correct"]
                            ),
                            "artifacts": {
                                **shared,
                                "prediction": reference(rule_path),
                                "evaluation": reference(rule_evaluation_path),
                            },
                        }
                    )
                    ml_records.append(
                        {
                            "sample_id": sample_id,
                            "partition": partition,
                            "split_group_id": group_id,
                            "expected_fault_type": fault_type,
                            "predicted_fault_type": fault_type,
                            "classification_correct": True,
                            "exact_match": bool(ml_metrics["exact_match"]),
                            "affected_prefix_correct": bool(
                                ml_metrics["affected_prefix_correct"]
                            ),
                            "artifacts": {
                                **shared,
                                "prediction": reference(ml_path),
                                "evaluation": reference(ml_evaluation_path),
                            },
                        }
                    )

    partition_group_ids = {
        name: list(GROUPS[name]) for name in reporting.PARTITION_ORDER
    }
    rule_report = build_method_evaluation_result(
        result_id="p3_r0_rule_based_baseline_v1",
        method={
            "method_id": "rule_based",
            "family": "traditional",
            "implementation_id": "deterministic_rule_engine_v1",
            "trained": False,
            "selection_statement": "Frozen deterministic rule baseline.",
        },
        dataset_binding=dataset_binding,
        provenance={
            "campaign_result": reference(campaign_path),
            "split_manifest": reference(split_manifest_path),
            "rule_audit": reference(rule_audit_path),
            "input_record_count": 30,
            "artifact_reference_count": 150,
        },
        records=rule_records,
        partition_group_ids=partition_group_ids,
    )
    ml_report = build_method_evaluation_result(
        result_id="p4_r1_ml_baseline_v1",
        method={
            "method_id": "machine_learning",
            "family": "machine_learning",
            "implementation_id": "p4_r1_ml_pipeline_v1",
            "trained": True,
            "selection_statement": "Synthetic train/validation freeze.",
        },
        dataset_binding=dataset_binding,
        provenance={
            "campaign_result": reference(campaign_path),
            "split_manifest": reference(split_manifest_path),
            "feature_matrix": reference(source_paths["ml_feature_matrix"]),
            "selection_result": reference(source_paths["ml_selection"]),
            "model_artifact": reference(source_paths["ml_model"]),
            "input_record_count": 30,
            "artifact_reference_count": 150,
        },
        records=ml_records,
        partition_group_ids=partition_group_ids,
    )
    write_json(source_paths["rule_baseline"], rule_report)
    write_json(source_paths["ml_report"], ml_report)

    baseline_hashes = {
        name: sha256_file(path) for name, path in source_paths.items()
    }
    policy = json.loads(POLICY_TEMPLATE.read_text(encoding="utf-8"))
    for name, path in source_paths.items():
        policy["baseline_bindings"][name]["path"] = str(path.resolve())
        policy["baseline_bindings"][name]["sha256"] = baseline_hashes[name]
    policy_path = project / "policies/P5_HYBRID_POLICY_V1.json"
    write_json(policy_path, policy)
    monkeypatch.setattr(engine, "EXPECTED_BASELINE_HASHES", baseline_hashes)
    monkeypatch.setattr(policy_module, "EXPECTED_BASELINE_HASHES", baseline_hashes)

    selection_directory = project / "models/p5_r1_hybrid_policy_v1"
    run_hybrid_selection(
        policy_path=policy_path,
        policy_schema_path=POLICY_SCHEMA,
        prediction_schema_path=PREDICTION_SCHEMA,
        selection_schema_path=SELECTION_SCHEMA,
        source_paths=source_paths,
        output_directory=selection_directory,
        expected_policy_sha256=sha256_file(policy_path),
    )
    selection_path = selection_directory / "selection.json"
    return {
        "project": project,
        "source_paths": source_paths,
        "policy_path": policy_path,
        "policy_sha256": sha256_file(policy_path),
        "selection_path": selection_path,
        "selection_sha256": sha256_file(selection_path),
    }


def build_bundle(artifacts: dict[str, Any], output: Path) -> dict[str, Any]:
    return build_p5_r2_bundle(
        selection_path=artifacts["selection_path"],
        policy_path=artifacts["policy_path"],
        policy_schema_path=POLICY_SCHEMA,
        prediction_schema_path=PREDICTION_SCHEMA,
        selection_schema_path=SELECTION_SCHEMA,
        method_schema_path=METHOD_SCHEMA,
        comparison_schema_path=COMPARISON_SCHEMA,
        source_paths=artifacts["source_paths"],
        output_directory=output,
        expected_policy_sha256=artifacts["policy_sha256"],
        expected_selection_sha256=artifacts["selection_sha256"],
    )


@pytest.fixture(scope="module")
def accepted_runtime(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    monkeypatch = pytest.MonkeyPatch()
    base = tmp_path_factory.mktemp("p5_r2_runtime")
    artifacts = make_runtime_sources(base, monkeypatch)
    output = artifacts["project"] / "reports/p5_r2_hybrid_baseline_v1"
    summary = build_bundle(artifacts, output)
    artifacts.update({"output": output, "summary": summary})
    yield artifacts
    monkeypatch.undo()


def verification_arguments(artifacts: dict[str, Any]) -> dict[str, Any]:
    output = artifacts["output"]
    return {
        "selection_path": artifacts["selection_path"],
        "policy_path": artifacts["policy_path"],
        "policy_schema_path": POLICY_SCHEMA,
        "prediction_schema_path": PREDICTION_SCHEMA,
        "selection_schema_path": SELECTION_SCHEMA,
        "method_schema_path": METHOD_SCHEMA,
        "comparison_schema_path": COMPARISON_SCHEMA,
        "source_paths": artifacts["source_paths"],
        "output_directory": output,
        "expected_policy_sha256": artifacts["policy_sha256"],
        "expected_selection_sha256": artifacts["selection_sha256"],
        "expected_report_sha256": sha256_file(
            output / reporting.REPORT_FILE_NAME
        ),
        "expected_comparison_sha256": sha256_file(
            output / reporting.COMPARISON_FILE_NAME
        ),
    }


def test_cross_method_schema_is_strict_draft_2020_12() -> None:
    schema = json.loads(COMPARISON_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["additionalProperties"] is False


def test_freeze_gate_runs_before_test_source_collection(
    accepted_runtime: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    called = False

    def forbidden_collection(*args: object, **kwargs: object) -> list[object]:
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(reporting, "collect_source_samples", forbidden_collection)
    with pytest.raises(HybridEngineError, match="selection SHA-256"):
        build_p5_r2_bundle(
            selection_path=accepted_runtime["selection_path"],
            policy_path=accepted_runtime["policy_path"],
            policy_schema_path=POLICY_SCHEMA,
            prediction_schema_path=PREDICTION_SCHEMA,
            selection_schema_path=SELECTION_SCHEMA,
            method_schema_path=METHOD_SCHEMA,
            comparison_schema_path=COMPARISON_SCHEMA,
            source_paths=accepted_runtime["source_paths"],
            output_directory=tmp_path / "must-not-exist",
            expected_policy_sha256=accepted_runtime["policy_sha256"],
            expected_selection_sha256="0" * 64,
        )
    assert called is False


def test_all_test_predictions_exist_before_ground_truth_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = make_runtime_sources(tmp_path / "isolated", monkeypatch)
    output = artifacts["project"] / "reports/held_out"
    original = reporting.evaluate_prediction
    observations: list[int] = []

    def guarded_evaluator(
        truth: dict[str, Any],
        prediction: dict[str, Any],
    ) -> dict[str, Any]:
        temporary_directories = list(
            output.parent.glob(f".{output.name}.*.tmp")
        )
        assert len(temporary_directories) == 1
        count = len(list(temporary_directories[0].rglob("prediction.json")))
        observations.append(count)
        assert count == 6
        return original(truth, prediction)

    monkeypatch.setattr(reporting, "evaluate_prediction", guarded_evaluator)
    build_bundle(artifacts, output)
    assert observations == [6] * 6


def test_p5_r2_runtime_has_only_six_test_prediction_evaluation_pairs(
    accepted_runtime: dict[str, Any],
) -> None:
    output = accepted_runtime["output"]
    assert len(list(output.rglob("prediction.json"))) == 6
    assert len(list(output.rglob("evaluation.json"))) == 6
    assert len(list(output.rglob("*.json"))) == 14


def test_hybrid_report_has_thirty_rows_and_210_references(
    accepted_runtime: dict[str, Any],
) -> None:
    report = json.loads(
        (accepted_runtime["output"] / reporting.REPORT_FILE_NAME).read_text()
    )
    assert len(report["records"]) == 30
    assert report["provenance"]["artifact_reference_count"] == 210
    assert all(len(record["artifacts"]) == 7 for record in report["records"])


def test_report_uses_only_frozen_selected_candidate(
    accepted_runtime: dict[str, Any],
) -> None:
    output = accepted_runtime["output"]
    predictions = [
        json.loads(path.read_text()) for path in output.rglob("prediction.json")
    ]
    assert {value["candidate_id"] for value in predictions} == {
        "consensus_abstain_v1"
    }
    assert all(
        value["policy_binding"]["complexity_rank"] == 0
        for value in predictions
    )


def test_g02_is_report_only_and_did_not_influence_selection(
    accepted_runtime: dict[str, Any],
) -> None:
    summary = accepted_runtime["summary"]
    assert summary["test_rows"] == 6
    assert summary["test_group"] == "CTX_G02_TOP02_CHAIN_3R"
    assert summary["test_use"] == "report_only"
    assert summary["test_influenced_policy_or_selection"] is False


def test_cross_method_comparison_contains_frozen_method_order(
    accepted_runtime: dict[str, Any],
) -> None:
    comparison = json.loads(
        (
            accepted_runtime["output"] / reporting.COMPARISON_FILE_NAME
        ).read_text()
    )
    assert comparison["method_order"] == [
        "rule_based",
        "machine_learning",
        "hybrid",
    ]
    for partition in reporting.PARTITION_ORDER:
        assert [
            item["method_id"]
            for item in comparison["partitions"][partition]["methods"]
        ] == comparison["method_order"]


def test_cross_method_comparison_is_descriptive_not_superiority_claim(
    accepted_runtime: dict[str, Any],
) -> None:
    comparison = json.loads(
        (
            accepted_runtime["output"] / reporting.COMPARISON_FILE_NAME
        ).read_text()
    )
    policy = comparison["comparison_policy"]
    assert policy["test_use"] == "report_only"
    assert policy["test_influenced_policy_or_selection"] is False
    assert policy["statistical_superiority_test_performed"] is False
    assert comparison["overall"]["use"] == "descriptive_only"


def test_comparison_builder_rejects_dataset_mismatch(
    accepted_runtime: dict[str, Any],
) -> None:
    output = accepted_runtime["output"]
    rule_report = json.loads(
        accepted_runtime["source_paths"]["rule_baseline"].read_text()
    )
    ml_report = json.loads(
        accepted_runtime["source_paths"]["ml_report"].read_text()
    )
    hybrid_report = json.loads((output / reporting.REPORT_FILE_NAME).read_text())
    changed = copy.deepcopy(ml_report)
    changed["dataset_binding"]["campaign_id"] = "DIFFERENT"
    with pytest.raises(HybridReportingError, match="dataset bindings"):
        build_cross_method_comparison(
            rule_report=rule_report,
            ml_report=changed,
            hybrid_report=hybrid_report,
            report_references={
                "rule_based": reference(
                    accepted_runtime["source_paths"]["rule_baseline"]
                ),
                "machine_learning": reference(
                    accepted_runtime["source_paths"]["ml_report"]
                ),
                "hybrid": reference(output / reporting.REPORT_FILE_NAME),
            },
            hybrid_selection_reference=reference(
                accepted_runtime["selection_path"]
            ),
            generated_at_utc=hybrid_report["generated_at_utc"],
        )


def test_independent_bundle_verification_passes(
    accepted_runtime: dict[str, Any],
) -> None:
    summary = verify_p5_r2_bundle(**verification_arguments(accepted_runtime))
    assert summary["status"] == "P5_R2_REPORT_AND_COMPARISON_VERIFIED"


def test_independent_verifier_rejects_report_hash_drift(
    accepted_runtime: dict[str, Any],
) -> None:
    arguments = verification_arguments(accepted_runtime)
    arguments["expected_report_sha256"] = "0" * 64
    with pytest.raises(HybridReportingError, match="report SHA-256"):
        verify_p5_r2_bundle(**arguments)


def test_independent_verifier_rejects_extra_runtime_json(
    accepted_runtime: dict[str, Any],
) -> None:
    extra = accepted_runtime["output"] / "unexpected.json"
    write_json(extra, {"unexpected": True})
    try:
        with pytest.raises(HybridReportingError, match="file set"):
            verify_p5_r2_bundle(**verification_arguments(accepted_runtime))
    finally:
        extra.unlink()


def test_report_generation_refuses_overwrite(
    accepted_runtime: dict[str, Any],
) -> None:
    with pytest.raises(HybridReportingError, match="already exists"):
        build_bundle(accepted_runtime, accepted_runtime["output"])
