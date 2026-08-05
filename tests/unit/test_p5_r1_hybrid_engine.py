from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import src.hybrid.engine as engine
import src.hybrid.policy as policy_module
from src.evaluation.reporting import (
    EvaluationReportingError,
    compute_abstention_aware_metrics,
)
from src.hybrid.engine import (
    HybridEngineError,
    build_hybrid_prediction,
    run_hybrid_selection,
    selection_sort_key,
    sha256_file,
    validate_hybrid_prediction,
    verify_hybrid_selection,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "policies/hybrid/P5_HYBRID_POLICY_V1.json"
POLICY_SCHEMA = ROOT / "schemas/hybrid_policy_v1.schema.json"
PREDICTION_SCHEMA = ROOT / "schemas/hybrid_prediction_v1.schema.json"
SELECTION_SCHEMA = ROOT / "schemas/hybrid_selection_v1.schema.json"
CLASSES = ("no_fault", "missing_static_route", "wrong_next_hop")
GROUPS = {
    "train": (
        "CTX_G03_TOP02_BRANCH_MID",
        "CTX_G04_TOP02_DUAL_TRANSIT",
        "CTX_G05_TOP03_ASYMMETRIC_RETURN",
    ),
    "validation": ("CTX_G01_TOP01_LINEAR_2R",),
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def reference(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def rule_prediction(
    fault_type: str,
    *,
    final: bool = True,
    complete_location: bool = True,
) -> dict[str, Any]:
    if not final:
        return {
            "schema_version": 1,
            "method": "rule_based",
            "status": "UNDETERMINED",
            "diagnosis": None,
            "matched_rules": [],
            "supporting_evidence": [],
            "contradicting_evidence": [],
        }
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
            "location": "r1" if complete_location else None,
            "affected_prefix": (
                "10.10.2.0/24" if complete_location else None
            ),
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
    diagnosis: dict[str, Any] | None = None
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


def make_engine_inputs(
    tmp_path: Path,
    *,
    rule_class: str = "missing_static_route",
    ml_class: str = "missing_static_route",
    final_rule: bool = True,
    complete_location: bool = True,
) -> dict[str, Any]:
    sample_id = "sample-g03-missing-1"
    sample_directory = tmp_path / sample_id
    evidence_path = sample_directory / "parsed/evidence.json"
    rule_path = sample_directory / "diagnosis/rule_based.json"
    ml_path = tmp_path / "ml-report/samples" / sample_id / "prediction.json"
    write_json(evidence_path, {"schema_version": 2})
    write_json(
        rule_path,
        rule_prediction(
            rule_class,
            final=final_rule,
            complete_location=complete_location,
        ),
    )
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    model_hash = policy["baseline_bindings"]["ml_model"]["sha256"]
    write_json(ml_path, ml_prediction(sample_id, ml_class, model_hash))
    return {
        "sample_id": sample_id,
        "evidence_reference": reference(evidence_path),
        "rule_prediction_reference": reference(rule_path),
        "ml_prediction_reference": reference(ml_path),
        "policy": policy,
        "policy_path": POLICY_PATH,
        "prediction_schema_path": PREDICTION_SCHEMA,
    }


def test_consensus_agreement_uses_only_rule_localization(
    tmp_path: Path,
) -> None:
    inputs = make_engine_inputs(tmp_path)
    result = build_hybrid_prediction(
        **inputs,
        candidate_id="consensus_abstain_v1",
    )
    assert result["status"] == "DIAGNOSIS_PRODUCED"
    assert result["diagnosis"]["location"] == "r1"
    assert result["diagnosis"]["affected_prefix"] == "10.10.2.0/24"
    ml_source = json.loads(
        Path(result["source_references"]["ml_prediction"]["path"]).read_text()
    )
    assert ml_source["diagnosis"]["location"] is None
    assert result["decision"]["reason"] == "CLASS_AGREEMENT"


def test_consensus_disagreement_abstains(tmp_path: Path) -> None:
    inputs = make_engine_inputs(tmp_path, ml_class="wrong_next_hop")
    result = build_hybrid_prediction(
        **inputs,
        candidate_id="consensus_abstain_v1",
    )
    assert result["status"] == "ABSTAINED"
    assert result["diagnosis"] is None
    assert result["decision"]["selected_class"] is None
    assert result["decision"]["guards"] == []


def test_guarded_disagreement_accepts_rule_when_all_guards_pass(
    tmp_path: Path,
) -> None:
    inputs = make_engine_inputs(tmp_path, ml_class="wrong_next_hop")
    result = build_hybrid_prediction(
        **inputs,
        candidate_id="rule_guarded_fallback_v1",
    )
    assert result["status"] == "DIAGNOSIS_PRODUCED"
    assert result["decision"]["reason"] == "RULE_GUARDED_FALLBACK"
    assert len(result["decision"]["guards"]) == 5
    assert all(guard["passed"] for guard in result["decision"]["guards"])


def test_guarded_disagreement_abstains_when_localization_guard_fails(
    tmp_path: Path,
) -> None:
    inputs = make_engine_inputs(
        tmp_path,
        ml_class="wrong_next_hop",
        complete_location=False,
    )
    result = build_hybrid_prediction(
        **inputs,
        candidate_id="rule_guarded_fallback_v1",
    )
    assert result["status"] == "ABSTAINED"
    assert result["decision"]["reason"] == "RULE_GUARDS_FAILED"
    assert result["decision"]["guards"][-1]["passed"] is False


def test_non_final_rule_input_abstains_for_both_candidates(
    tmp_path: Path,
) -> None:
    inputs = make_engine_inputs(tmp_path, final_rule=False)
    for candidate_id in engine.EXPECTED_CANDIDATE_ORDER:
        result = build_hybrid_prediction(
            **inputs,
            candidate_id=candidate_id,
        )
        assert result["status"] == "ABSTAINED"
        assert result["decision"]["reason"] == "NON_FINAL_INPUT"


def test_prediction_source_hash_drift_is_fail_stop(tmp_path: Path) -> None:
    inputs = make_engine_inputs(tmp_path)
    ml_path = Path(inputs["ml_prediction_reference"]["path"])
    with ml_path.open("a", encoding="utf-8") as stream:
        stream.write("drift")
    with pytest.raises(HybridEngineError, match="SHA-256 drift"):
        build_hybrid_prediction(
            **inputs,
            candidate_id="consensus_abstain_v1",
        )


def test_engine_api_excludes_ground_truth_and_partition() -> None:
    parameters = set(inspect.signature(build_hybrid_prediction).parameters)
    assert "ground_truth" not in parameters
    assert "target_class" not in parameters
    assert "partition" not in parameters
    assert "evaluation" not in parameters
    assert "method_metrics" not in parameters


def test_abstention_metrics_use_full_denominator() -> None:
    records = [
        {
            "expected_fault_type": "no_fault",
            "predicted_fault_type": "no_fault",
            "abstained": False,
            "exact_match": True,
            "affected_prefix_correct": True,
        },
        {
            "expected_fault_type": "missing_static_route",
            "predicted_fault_type": None,
            "abstained": True,
            "exact_match": False,
            "affected_prefix_correct": False,
        },
        {
            "expected_fault_type": "wrong_next_hop",
            "predicted_fault_type": "missing_static_route",
            "abstained": False,
            "exact_match": False,
            "affected_prefix_correct": False,
        },
    ]
    metrics = compute_abstention_aware_metrics(records, CLASSES)
    assert metrics["classification"]["accuracy"] == pytest.approx(1 / 3)
    assert metrics["abstention"]["coverage"] == pytest.approx(2 / 3)
    assert metrics["abstention"]["abstention_count"] == 1
    assert metrics["abstention"]["per_class_abstention_count"] == {
        "no_fault": 0,
        "missing_static_route": 1,
        "wrong_next_hop": 0,
    }
    assert sum(
        sum(row)
        for row in metrics["classification"]["confusion_matrix"]["values"]
    ) == 2
    assert metrics["diagnostic_checks"]["exact_diagnosis_match"]["rate"] == (
        pytest.approx(1 / 3)
    )


def test_abstention_cannot_claim_exact_or_prefix_correctness() -> None:
    record = {
        "expected_fault_type": "missing_static_route",
        "predicted_fault_type": None,
        "abstained": True,
        "exact_match": True,
        "affected_prefix_correct": True,
    }
    with pytest.raises(EvaluationReportingError, match="exact"):
        compute_abstention_aware_metrics([record], CLASSES)


def test_selection_sort_key_uses_frozen_tie_break_order() -> None:
    base = {
        "candidate_id": "rule_guarded_fallback_v1",
        "complexity_rank": 1,
        "validation_metrics": {
            "macro_f1_full_denominator": 1.0,
            "exact_diagnosis_rate_full_denominator": 1.0,
            "coverage": 1.0,
        },
    }
    simpler = copy.deepcopy(base)
    simpler["candidate_id"] = "consensus_abstain_v1"
    simpler["complexity_rank"] = 0
    assert selection_sort_key(simpler) < selection_sort_key(base)


def create_runtime_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    project = tmp_path / "project"
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

    rule_records: list[dict[str, Any]] = []
    ml_records: list[dict[str, Any]] = []
    sequence = 0
    for partition in ("train", "validation"):
        for group_id in GROUPS[partition]:
            for fault_type in CLASSES:
                for repetition in (1, 2):
                    sequence += 1
                    sample_id = (
                        f"sample-{partition}-{sequence}-{fault_type}-{repetition}"
                    )
                    raw = project / "data/raw" / sample_id
                    ml_sample = project / "reports/ml/samples" / sample_id
                    evidence_path = raw / "parsed/evidence.json"
                    rule_path = raw / "diagnosis/rule_based.json"
                    ground_truth_path = raw / "ground_truth.json"
                    ml_path = ml_sample / "prediction.json"
                    write_json(evidence_path, {"schema_version": 2})
                    write_json(rule_path, rule_prediction(fault_type))
                    write_json(
                        ground_truth_path,
                        {
                            "fault_category": (
                                None if fault_type == "no_fault" else "routing"
                            ),
                            "fault_type": fault_type,
                            "fault_location": (
                                None if fault_type == "no_fault" else "r1"
                            ),
                            "affected_prefix": (
                                None
                                if fault_type == "no_fault"
                                else "10.10.2.0/24"
                            ),
                        },
                    )
                    write_json(
                        ml_path,
                        ml_prediction(sample_id, fault_type, model_hash),
                    )
                    rule_records.append(
                        {
                            "sample_id": sample_id,
                            "partition": partition,
                            "split_group_id": group_id,
                            "artifacts": {
                                "evidence": reference(evidence_path),
                                "prediction": reference(rule_path),
                                "ground_truth": reference(ground_truth_path),
                            },
                        }
                    )
                    ml_records.append(
                        {
                            "sample_id": sample_id,
                            "partition": partition,
                            "split_group_id": group_id,
                            "artifacts": {
                                "evidence": reference(evidence_path),
                                "prediction": reference(ml_path),
                            },
                        }
                    )
    for index in range(6):
        rule_records.append({"partition": "test", "opaque": index})
        ml_records.append({"partition": "test", "opaque": index})
    write_json(
        source_paths["rule_baseline"],
        {
            "method": {"method_id": "rule_based"},
            "records": rule_records,
        },
    )
    write_json(
        source_paths["ml_report"],
        {
            "method": {"method_id": "machine_learning"},
            "records": ml_records,
        },
    )

    baseline_hashes = {
        name: sha256_file(path)
        for name, path in source_paths.items()
    }
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    for name, path in source_paths.items():
        policy["baseline_bindings"][name]["path"] = str(path.resolve())
        policy["baseline_bindings"][name]["sha256"] = baseline_hashes[name]
    policy_path = project / "policies/P5_HYBRID_POLICY_V1.json"
    write_json(policy_path, policy)
    monkeypatch.setattr(engine, "EXPECTED_BASELINE_HASHES", baseline_hashes)
    monkeypatch.setattr(
        policy_module,
        "EXPECTED_BASELINE_HASHES",
        baseline_hashes,
    )
    return {
        "project": project,
        "source_paths": source_paths,
        "policy": policy_path,
        "policy_sha256": sha256_file(policy_path),
    }


def test_end_to_end_selection_freezes_without_test_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = create_runtime_sources(tmp_path, monkeypatch)
    output = artifacts["project"] / "models/p5_r1_hybrid_policy_v1"
    selection = run_hybrid_selection(
        policy_path=artifacts["policy"],
        policy_schema_path=POLICY_SCHEMA,
        prediction_schema_path=PREDICTION_SCHEMA,
        selection_schema_path=SELECTION_SCHEMA,
        source_paths=artifacts["source_paths"],
        output_directory=output,
        expected_policy_sha256=artifacts["policy_sha256"],
    )
    assert selection["selected_candidate"]["candidate_id"] == (
        "consensus_abstain_v1"
    )
    assert all(
        result["validation_metrics"]["macro_f1_full_denominator"] == 1.0
        for result in selection["candidate_results"]
    )
    assert all(
        result["validation_metrics"]["exact_diagnosis_rate_full_denominator"]
        == 1.0
        for result in selection["candidate_results"]
    )
    assert len(list(output.rglob("prediction.json"))) == 48
    assert len(list(output.rglob("evaluation.json"))) == 48
    assert not any(path.name == "test" for path in output.rglob("test"))
    selection_path = output / "selection.json"
    verified = verify_hybrid_selection(
        selection_path=selection_path,
        policy_path=artifacts["policy"],
        policy_schema_path=POLICY_SCHEMA,
        prediction_schema_path=PREDICTION_SCHEMA,
        selection_schema_path=SELECTION_SCHEMA,
        source_paths=artifacts["source_paths"],
        expected_policy_sha256=artifacts["policy_sha256"],
        expected_selection_sha256=sha256_file(selection_path),
    )
    assert verified["status"] == "SELECTED_POLICY_FROZEN_VERIFIED"
    assert verified["test_predictions_or_metrics"] == "ABSENT"


def test_hybrid_schemas_are_strict_draft_2020_12() -> None:
    for path in (PREDICTION_SCHEMA, SELECTION_SCHEMA):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False


def test_prediction_semantics_reject_abstention_with_diagnosis(
    tmp_path: Path,
) -> None:
    inputs = make_engine_inputs(tmp_path, ml_class="wrong_next_hop")
    prediction = build_hybrid_prediction(
        **inputs,
        candidate_id="consensus_abstain_v1",
    )
    prediction["diagnosis"] = {
        "category": "routing",
        "fault_type": "missing_static_route",
        "location": "r1",
        "affected_prefix": "10.10.2.0/24",
    }
    with pytest.raises(HybridEngineError, match="abstention"):
        validate_hybrid_prediction(prediction, PREDICTION_SCHEMA)
