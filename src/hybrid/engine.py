from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from jsonschema import Draft202012Validator

from src.evaluation.evaluator import evaluate_prediction
from src.evaluation.reporting import (
    EvaluationReportingError,
    compute_abstention_aware_metrics,
)
from src.hybrid.policy import (
    DEFAULT_POLICY_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_POLICY_SCHEMA_PATH,
    EXPECTED_BASELINE_HASHES,
    EXPECTED_CANDIDATE_ORDER,
    EXPECTED_CLASS_ORDER,
    HybridPolicyError,
    verify_frozen_policy,
)


DEFAULT_PREDICTION_SCHEMA_PATH = Path(
    "schemas/hybrid_prediction_v1.schema.json"
)
DEFAULT_SELECTION_SCHEMA_PATH = Path(
    "schemas/hybrid_selection_v1.schema.json"
)
DEFAULT_OUTPUT_DIRECTORY = Path("models/p5_r1_hybrid_policy_v1")
DEFAULT_SELECTION_FILE_NAME = "selection.json"
EXPECTED_POLICY_SHA256 = (
    "a25467e9cfd8bb52cc67b0c3886eb439466ee51a27b22d292ee468d060bdecc7"
)
EXPECTED_SELECTION_ID = "p5_r1_hybrid_selection_v1"
EXPECTED_IMPLEMENTATION_ID = "deterministic_hybrid_engine_v1"
DEVELOPMENT_PARTITIONS = ("train", "validation")
HELD_OUT_PARTITION = "test"
EXPECTED_PARTITION_ROWS = {"train": 18, "validation": 6}
EXPECTED_PARTITION_GROUPS = {
    "train": [
        "CTX_G03_TOP02_BRANCH_MID",
        "CTX_G04_TOP02_DUAL_TRANSIT",
        "CTX_G05_TOP03_ASYMMETRIC_RETURN",
    ],
    "validation": ["CTX_G01_TOP01_LINEAR_2R"],
}
KNOWN_RULES = {
    "no_fault": "R_BASELINE_001",
    "missing_static_route": "R_ROUTING_001",
    "wrong_next_hop": "R_ROUTING_002",
}
GUARD_IDS = (
    "rule_status_is_final",
    "exactly_one_known_rule_matches_normalized_class",
    "rule_support_score_equals_one_but_is_not_a_probability",
    "contradicting_evidence_is_empty",
    "fault_location_and_affected_prefix_are_non_empty_for_faults",
)


class HybridEngineError(ValueError):
    """Raised when P5-R1 fusion or selection violates its freeze."""


@dataclass(frozen=True)
class DevelopmentSample:
    sample_id: str
    partition: str
    split_group_id: str
    evidence_reference: Mapping[str, str]
    rule_prediction_reference: Mapping[str, str]
    ml_prediction_reference: Mapping[str, str]
    ground_truth_reference: Mapping[str, str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise HybridEngineError(f"Required JSON artifact does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise HybridEngineError(f"Invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise HybridEngineError(f"JSON artifact must be an object: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise HybridEngineError(f"Required artifact does not exist: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_mapping(value: object, reference: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HybridEngineError(f"{reference} must be an object.")
    return value


def require_non_empty_string(value: object, reference: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HybridEngineError(f"{reference} must be a non-empty string.")
    return value


def require_string_list(value: object, reference: str) -> list[str]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise HybridEngineError(f"{reference} must be an array of strings.")
    return list(value)


def artifact_reference(path: Path) -> dict[str, str]:
    resolved = path.resolve()
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def validate_artifact_reference(
    value: object,
    reference: str,
    *,
    sample_id: str | None = None,
    verify_hash: bool = True,
) -> tuple[dict[str, str], Path]:
    mapping = require_mapping(value, reference)
    path = Path(require_non_empty_string(mapping.get("path"), f"{reference}.path"))
    expected_hash = require_non_empty_string(
        mapping.get("sha256"),
        f"{reference}.sha256",
    )
    if len(expected_hash) != 64 or any(
        character not in "0123456789abcdef" for character in expected_hash
    ):
        raise HybridEngineError(f"{reference}.sha256 is not SHA-256.")
    resolved = path.resolve()
    if sample_id is not None and sample_id not in resolved.parts:
        raise HybridEngineError(
            f"{reference} is not path-bound to sample {sample_id}."
        )
    if not resolved.is_file():
        raise HybridEngineError(f"Required artifact does not exist: {resolved}")
    if verify_hash and sha256_file(resolved) != expected_hash:
        raise HybridEngineError(f"{reference} SHA-256 drift detected.")
    return {"path": str(resolved), "sha256": expected_hash}, resolved


def validate_json_schema(
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
        raise HybridEngineError(
            f"{contract_name} JSON Schema violation: {prefix}{first.message}"
        )


def load_verified_policy(
    policy_path: Path,
    policy_schema_path: Path,
    *,
    expected_policy_sha256: str = EXPECTED_POLICY_SHA256,
) -> dict[str, Any]:
    result = verify_frozen_policy(policy_path, policy_schema_path)
    if result["policy_sha256"] != expected_policy_sha256:
        raise HybridEngineError("Frozen Hybrid Policy v1 SHA-256 changed.")
    return read_json(policy_path)


def verify_baseline_bindings(
    policy: Mapping[str, Any],
    source_paths: Mapping[str, Path],
) -> dict[str, dict[str, str]]:
    bindings = require_mapping(policy.get("baseline_bindings"), "baseline_bindings")
    if set(source_paths) != set(EXPECTED_BASELINE_HASHES):
        raise HybridEngineError("Exactly five accepted baseline sources are required.")
    verified: dict[str, dict[str, str]] = {}
    for name in sorted(source_paths):
        binding = require_mapping(bindings.get(name), f"baseline_bindings.{name}")
        expected_hash = require_non_empty_string(
            binding.get("sha256"),
            f"baseline_bindings.{name}.sha256",
        )
        if expected_hash != EXPECTED_BASELINE_HASHES[name]:
            raise HybridEngineError(f"Accepted {name} hash binding changed.")
        path = source_paths[name].resolve()
        expected_path = Path(
            require_non_empty_string(
                binding.get("path"),
                f"baseline_bindings.{name}.path",
            )
        ).resolve()
        if path != expected_path:
            raise HybridEngineError(f"Accepted {name} path binding changed.")
        if sha256_file(path) != expected_hash:
            raise HybridEngineError(f"Accepted {name} artifact drift detected.")
        verified[name] = {"path": str(path), "sha256": expected_hash}
    return verified


def _report_record_index(
    report: Mapping[str, Any],
    expected_method_id: str,
) -> dict[tuple[str, str], Mapping[str, Any]]:
    method = require_mapping(report.get("method"), "report.method")
    if method.get("method_id") != expected_method_id:
        raise HybridEngineError(f"Unexpected {expected_method_id} report method.")
    records = report.get("records")
    if not isinstance(records, list) or len(records) != 30:
        raise HybridEngineError("Accepted source report must contain 30 records.")
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    observed_partition_counts = {
        name: 0
        for name in (*DEVELOPMENT_PARTITIONS, HELD_OUT_PARTITION)
    }
    for position, value in enumerate(records, start=1):
        record = require_mapping(value, f"report.records[{position}]")
        partition = require_non_empty_string(
            record.get("partition"),
            f"report.records[{position}].partition",
        )
        if partition not in observed_partition_counts:
            raise HybridEngineError("Source report contains an invalid partition.")
        observed_partition_counts[partition] += 1
        if partition == HELD_OUT_PARTITION:
            # P5-R1 deliberately does not inspect any G02 artifact reference.
            continue
        sample_id = require_non_empty_string(
            record.get("sample_id"),
            f"report.records[{position}].sample_id",
        )
        key = (partition, sample_id)
        if key in indexed:
            raise HybridEngineError(f"Duplicate source report sample: {sample_id}")
        indexed[key] = record
    if observed_partition_counts != {"train": 18, "validation": 6, "test": 6}:
        raise HybridEngineError("Accepted source report partition counts changed.")
    return indexed


def collect_development_samples(
    rule_report_path: Path,
    ml_report_path: Path,
) -> list[DevelopmentSample]:
    rule_index = _report_record_index(read_json(rule_report_path), "rule_based")
    ml_index = _report_record_index(read_json(ml_report_path), "machine_learning")
    if set(rule_index) != set(ml_index):
        raise HybridEngineError("Rule and ML development sample sets differ.")

    samples: list[DevelopmentSample] = []
    for partition, sample_id in sorted(rule_index):
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
            raise HybridEngineError(f"Source group mismatch for {sample_id}.")

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
            raise HybridEngineError(f"Evidence reference mismatch for {sample_id}.")
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
        ground_truth, _ = validate_artifact_reference(
            rule_artifacts.get("ground_truth"),
            f"rule record {sample_id}.ground_truth",
            sample_id=sample_id,
            verify_hash=False,
        )
        samples.append(
            DevelopmentSample(
                sample_id=sample_id,
                partition=partition,
                split_group_id=rule_group,
                evidence_reference=evidence,
                rule_prediction_reference=rule_prediction,
                ml_prediction_reference=ml_prediction,
                ground_truth_reference=ground_truth,
            )
        )

    for partition in DEVELOPMENT_PARTITIONS:
        partition_samples = [
            sample
            for sample in samples
            if sample.partition == partition
        ]
        if len(partition_samples) != EXPECTED_PARTITION_ROWS[partition]:
            raise HybridEngineError(f"Unexpected {partition} sample count.")
        groups = sorted({sample.split_group_id for sample in partition_samples})
        if groups != EXPECTED_PARTITION_GROUPS[partition]:
            raise HybridEngineError(f"Unexpected {partition} group binding.")
    return samples


def normalize_rule_prediction(
    prediction: Mapping[str, Any],
) -> tuple[bool, str | None, Mapping[str, Any] | None]:
    if prediction.get("method") != "rule_based":
        raise HybridEngineError("Rule prediction method is invalid.")
    status = prediction.get("status")
    diagnosis_value = prediction.get("diagnosis")
    if status == "NO_FAULT_DETECTED":
        if diagnosis_value not in (None, {}):
            raise HybridEngineError("NO_FAULT_DETECTED has a diagnosis.")
        return True, "no_fault", None
    if status == "DIAGNOSIS_PRODUCED":
        diagnosis = require_mapping(diagnosis_value, "rule prediction diagnosis")
        fault_type = require_non_empty_string(
            diagnosis.get("fault_type"),
            "rule prediction diagnosis.fault_type",
        )
        if fault_type not in EXPECTED_CLASS_ORDER or fault_type == "no_fault":
            raise HybridEngineError("Rule prediction class is invalid.")
        return True, fault_type, diagnosis
    if status in {"INSUFFICIENT_EVIDENCE", "UNDETERMINED"}:
        return False, None, None
    raise HybridEngineError("Unsupported rule prediction status.")


def normalize_ml_prediction(
    prediction: Mapping[str, Any],
    sample_id: str,
) -> tuple[str, Mapping[str, Any] | None]:
    if prediction.get("method") != "machine_learning":
        raise HybridEngineError("ML prediction method is invalid.")
    if prediction.get("sample_id") != sample_id:
        raise HybridEngineError("ML prediction sample identity mismatch.")
    status = prediction.get("status")
    diagnosis_value = prediction.get("diagnosis")
    if status == "NO_FAULT_DETECTED":
        if diagnosis_value not in (None, {}):
            raise HybridEngineError("ML NO_FAULT_DETECTED has a diagnosis.")
        return "no_fault", None
    if status == "DIAGNOSIS_PRODUCED":
        diagnosis = require_mapping(diagnosis_value, "ML prediction diagnosis")
        fault_type = require_non_empty_string(
            diagnosis.get("fault_type"),
            "ML prediction diagnosis.fault_type",
        )
        if fault_type not in EXPECTED_CLASS_ORDER or fault_type == "no_fault":
            raise HybridEngineError("ML prediction class is invalid.")
        return fault_type, diagnosis
    raise HybridEngineError("Unsupported ML prediction status.")


def rule_guard_results(
    prediction: Mapping[str, Any],
    rule_class: str,
    rule_diagnosis: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    matched_rules = prediction.get("matched_rules")
    known_rule_pass = (
        isinstance(matched_rules, list)
        and matched_rules == [KNOWN_RULES[rule_class]]
    )
    support_score = prediction.get("rule_support_score")
    score_pass = (
        not isinstance(support_score, bool)
        and isinstance(support_score, (int, float))
        and float(support_score) == 1.0
    )
    contradicting = prediction.get("contradicting_evidence")
    contradiction_pass = isinstance(contradicting, list) and not contradicting
    localization_pass = True
    if rule_class != "no_fault":
        localization_pass = (
            isinstance(rule_diagnosis, Mapping)
            and isinstance(rule_diagnosis.get("location"), str)
            and bool(str(rule_diagnosis["location"]).strip())
            and isinstance(rule_diagnosis.get("affected_prefix"), str)
            and bool(str(rule_diagnosis["affected_prefix"]).strip())
        )
    values = (
        True,
        known_rule_pass,
        score_pass,
        contradiction_pass,
        localization_pass,
    )
    return [
        {"guard_id": guard_id, "passed": passed}
        for guard_id, passed in zip(GUARD_IDS, values)
    ]


def diagnosis_for_class(
    selected_class: str,
    rule_diagnosis: Mapping[str, Any] | None,
) -> tuple[str, dict[str, Any] | None]:
    if selected_class == "no_fault":
        return "NO_FAULT_DETECTED", None
    diagnosis = require_mapping(rule_diagnosis, "accepted rule diagnosis")
    location = require_non_empty_string(
        diagnosis.get("location"),
        "accepted rule diagnosis.location",
    )
    affected_prefix = require_non_empty_string(
        diagnosis.get("affected_prefix"),
        "accepted rule diagnosis.affected_prefix",
    )
    result = {
        "category": "routing",
        "fault_type": selected_class,
        "location": location,
        "affected_prefix": affected_prefix,
    }
    if selected_class == "wrong_next_hop" and isinstance(
        diagnosis.get("observed_next_hop"), str
    ):
        result["observed_next_hop"] = diagnosis["observed_next_hop"]
    return "DIAGNOSIS_PRODUCED", result


def build_hybrid_prediction(
    *,
    sample_id: str,
    evidence_reference: Mapping[str, str],
    rule_prediction_reference: Mapping[str, str],
    ml_prediction_reference: Mapping[str, str],
    policy: Mapping[str, Any],
    policy_path: Path,
    candidate_id: str,
    prediction_schema_path: Path = DEFAULT_PREDICTION_SCHEMA_PATH,
    expected_policy_sha256: str = EXPECTED_POLICY_SHA256,
) -> dict[str, Any]:
    if not sample_id or "/" in sample_id or "\\" in sample_id:
        raise HybridEngineError("sample_id is invalid.")
    evidence_reference, _ = validate_artifact_reference(
        evidence_reference,
        "evidence_reference",
        sample_id=sample_id,
    )
    rule_prediction_reference, rule_path = validate_artifact_reference(
        rule_prediction_reference,
        "rule_prediction_reference",
        sample_id=sample_id,
    )
    ml_prediction_reference, ml_path = validate_artifact_reference(
        ml_prediction_reference,
        "ml_prediction_reference",
        sample_id=sample_id,
    )
    policy_hash = sha256_file(policy_path.resolve())
    if policy_hash != expected_policy_sha256:
        raise HybridEngineError("Hybrid policy hash drift detected.")
    candidates = policy.get("candidate_policies")
    if not isinstance(candidates, list):
        raise HybridEngineError("Hybrid candidates are invalid.")
    candidate = next(
        (
            require_mapping(value, "candidate")
            for value in candidates
            if isinstance(value, Mapping) and value.get("candidate_id") == candidate_id
        ),
        None,
    )
    if candidate is None or candidate_id not in EXPECTED_CANDIDATE_ORDER:
        raise HybridEngineError("Unknown hybrid candidate.")

    rule_prediction = read_json(rule_path)
    ml_prediction = read_json(ml_path)
    rule_final, rule_class, rule_diagnosis = normalize_rule_prediction(
        rule_prediction
    )
    ml_class, _ = normalize_ml_prediction(ml_prediction, sample_id)

    guard_results: list[dict[str, Any]] = []
    selected_class: str | None = None
    if not rule_final:
        reason = "NON_FINAL_INPUT"
    else:
        assert rule_class is not None
        if rule_class == ml_class:
            selected_class = rule_class
            reason = "CLASS_AGREEMENT"
        elif candidate_id == "consensus_abstain_v1":
            reason = "CLASS_DISAGREEMENT_ABSTAIN"
        else:
            guard_results = rule_guard_results(
                rule_prediction,
                rule_class,
                rule_diagnosis,
            )
            if all(result["passed"] for result in guard_results):
                selected_class = rule_class
                reason = "RULE_GUARDED_FALLBACK"
            else:
                reason = "RULE_GUARDS_FAILED"

    if selected_class is None:
        status = "ABSTAINED"
        diagnosis = None
    else:
        status, diagnosis = diagnosis_for_class(selected_class, rule_diagnosis)

    matched_rules = require_string_list(
        rule_prediction.get("matched_rules", []),
        "rule prediction matched_rules",
    )
    supporting_evidence = require_string_list(
        rule_prediction.get("supporting_evidence", []),
        "rule prediction supporting_evidence",
    )
    contradicting_evidence = require_string_list(
        rule_prediction.get("contradicting_evidence", []),
        "rule prediction contradicting_evidence",
    )
    ml_explanation = require_mapping(
        ml_prediction.get("model_explanation"),
        "ML prediction model_explanation",
    )
    model_binding = require_mapping(
        ml_prediction.get("model_binding"),
        "ML prediction model_binding",
    )
    expected_model_hash = require_mapping(
        require_mapping(policy.get("baseline_bindings"), "baseline_bindings").get(
            "ml_model"
        ),
        "baseline_bindings.ml_model",
    ).get("sha256")
    if model_binding.get("model_sha256") != expected_model_hash:
        raise HybridEngineError("ML prediction model binding drift detected.")

    prediction = {
        "schema_version": 1,
        "sample_id": sample_id,
        "method": "hybrid",
        "implementation_id": EXPECTED_IMPLEMENTATION_ID,
        "candidate_id": candidate_id,
        "status": status,
        "diagnosis": diagnosis,
        "decision": {
            "reason": reason,
            "rule_class": rule_class,
            "ml_class": ml_class,
            "selected_class": selected_class,
            "guards": guard_results,
        },
        "source_references": {
            "evidence": evidence_reference,
            "rule_prediction": rule_prediction_reference,
            "ml_prediction": ml_prediction_reference,
        },
        "explanation": {
            "rule": {
                "matched_rules": matched_rules,
                "rule_support_score": rule_prediction.get("rule_support_score"),
                "score_interpretation": rule_prediction.get(
                    "score_interpretation"
                ),
                "supporting_evidence": supporting_evidence,
                "contradicting_evidence": contradicting_evidence,
            },
            "ml_model_explanation": copy.deepcopy(dict(ml_explanation)),
        },
        "policy_binding": {
            "policy_id": policy["policy_id"],
            "policy_sha256": policy_hash,
            "candidate_id": candidate_id,
            "complexity_rank": candidate["complexity_rank"],
        },
        "model_binding": copy.deepcopy(dict(model_binding)),
        "limitations": [
            "The decision combines only the frozen rule and ML outputs.",
            "Rule support is deterministic evidence support, not probability.",
        ],
    }
    validate_hybrid_prediction(
        prediction,
        prediction_schema_path,
        expected_policy_sha256=expected_policy_sha256,
    )
    return prediction


def validate_hybrid_prediction(
    prediction: Mapping[str, Any],
    schema_path: Path = DEFAULT_PREDICTION_SCHEMA_PATH,
    *,
    expected_policy_sha256: str = EXPECTED_POLICY_SHA256,
) -> None:
    validate_json_schema(prediction, schema_path, "Hybrid Prediction v1")
    candidate_id = prediction.get("candidate_id")
    if candidate_id not in EXPECTED_CANDIDATE_ORDER:
        raise HybridEngineError("Hybrid prediction candidate changed.")
    policy_binding = require_mapping(
        prediction.get("policy_binding"),
        "prediction.policy_binding",
    )
    if (
        policy_binding.get("policy_sha256") != expected_policy_sha256
        or policy_binding.get("candidate_id") != candidate_id
    ):
        raise HybridEngineError("Hybrid prediction policy binding is invalid.")
    decision = require_mapping(prediction.get("decision"), "prediction.decision")
    status = prediction.get("status")
    selected_class = decision.get("selected_class")
    diagnosis = prediction.get("diagnosis")
    if status == "ABSTAINED":
        if selected_class is not None or diagnosis is not None:
            raise HybridEngineError("An abstention cannot contain a diagnosis.")
    elif status == "NO_FAULT_DETECTED":
        if selected_class != "no_fault" or diagnosis is not None:
            raise HybridEngineError("NO_FAULT_DETECTED semantics are invalid.")
    elif status == "DIAGNOSIS_PRODUCED":
        diagnosis_mapping = require_mapping(diagnosis, "prediction.diagnosis")
        if diagnosis_mapping.get("fault_type") != selected_class:
            raise HybridEngineError("Hybrid diagnosis class mismatch.")
        require_non_empty_string(
            diagnosis_mapping.get("location"),
            "diagnosis.location",
        )
        require_non_empty_string(
            diagnosis_mapping.get("affected_prefix"),
            "diagnosis.affected_prefix",
        )
    else:
        raise HybridEngineError("Hybrid prediction status is invalid.")


def hybrid_predicted_class(prediction: Mapping[str, Any]) -> str | None:
    status = prediction.get("status")
    if status == "ABSTAINED":
        return None
    if status == "NO_FAULT_DETECTED":
        return "no_fault"
    diagnosis = require_mapping(prediction.get("diagnosis"), "prediction.diagnosis")
    return require_non_empty_string(
        diagnosis.get("fault_type"),
        "prediction.diagnosis.fault_type",
    )


def selection_sort_key(result: Mapping[str, Any]) -> tuple[Any, ...]:
    metrics = require_mapping(
        result.get("validation_metrics"),
        "candidate.validation_metrics",
    )
    return (
        -float(metrics["macro_f1_full_denominator"]),
        -float(metrics["exact_diagnosis_rate_full_denominator"]),
        -float(metrics["coverage"]),
        int(result["complexity_rank"]),
        str(result["candidate_id"]),
    )


def compact_selection_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    classification = require_mapping(metrics.get("classification"), "classification")
    macro = require_mapping(classification.get("macro"), "classification.macro")
    checks = require_mapping(metrics.get("diagnostic_checks"), "diagnostic_checks")
    exact = require_mapping(checks.get("exact_diagnosis_match"), "exact check")
    abstention = require_mapping(metrics.get("abstention"), "abstention")
    return {
        "row_count": classification["sample_count"],
        "macro_f1_full_denominator": macro["f1"],
        "accuracy_full_denominator": classification["accuracy"],
        "exact_diagnosis_rate_full_denominator": exact["rate"],
        "coverage": abstention["coverage"],
        "abstention_count": abstention["abstention_count"],
        "abstention_rate": abstention["abstention_rate"],
        "per_class_abstention_count": abstention[
            "per_class_abstention_count"
        ],
    }


def _final_reference(temporary_path: Path, final_path: Path) -> dict[str, str]:
    return {"path": str(final_path.resolve()), "sha256": sha256_file(temporary_path)}


def _candidate_manifest_and_result(
    *,
    candidate: Mapping[str, Any],
    samples: Sequence[DevelopmentSample],
    temporary_directory: Path,
    final_directory: Path,
    policy: Mapping[str, Any],
    policy_path: Path,
    prediction_schema_path: Path,
    expected_policy_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate_id = require_non_empty_string(
        candidate.get("candidate_id"),
        "candidate.candidate_id",
    )
    candidate_temp = temporary_directory / "candidates" / candidate_id
    candidate_final = final_directory / "candidates" / candidate_id
    prediction_records: list[dict[str, Any]] = []

    # Prediction generation finishes for every development sample before the
    # evaluator reads any ground truth.
    generated: list[tuple[DevelopmentSample, Path, Path]] = []
    for sample in samples:
        temporary_prediction_path = (
            candidate_temp / "samples" / sample.sample_id / "prediction.json"
        )
        final_prediction_path = (
            candidate_final / "samples" / sample.sample_id / "prediction.json"
        )
        if not temporary_prediction_path.is_file():
            raise HybridEngineError(
                "Candidate prediction batch was not completed before evaluation."
            )
        prediction = read_json(temporary_prediction_path)
        validate_hybrid_prediction(
            prediction,
            prediction_schema_path,
            expected_policy_sha256=expected_policy_sha256,
        )
        if (
            prediction.get("sample_id") != sample.sample_id
            or prediction.get("candidate_id") != candidate_id
        ):
            raise HybridEngineError("Pre-evaluation prediction identity mismatch.")
        generated.append((sample, temporary_prediction_path, final_prediction_path))

    for sample, temporary_prediction_path, final_prediction_path in generated:
        prediction = read_json(temporary_prediction_path)
        ground_truth_reference, ground_truth_path = validate_artifact_reference(
            sample.ground_truth_reference,
            f"ground truth {sample.sample_id}",
            sample_id=sample.sample_id,
        )
        evaluation = evaluate_prediction(read_json(ground_truth_path), prediction)
        evaluation["sample_id"] = sample.sample_id
        evaluation["partition_use"] = (
            "development" if sample.partition == "train" else "selection"
        )
        temporary_evaluation_path = (
            candidate_temp / "samples" / sample.sample_id / "evaluation.json"
        )
        final_evaluation_path = (
            candidate_final / "samples" / sample.sample_id / "evaluation.json"
        )
        write_json(temporary_evaluation_path, evaluation)
        evaluation_metrics = require_mapping(
            evaluation.get("metrics"),
            f"evaluation {sample.sample_id}.metrics",
        )
        predicted_class = hybrid_predicted_class(prediction)
        expected = require_mapping(
            evaluation.get("expected"),
            f"evaluation {sample.sample_id}.expected",
        )
        prediction_records.append(
            {
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
                "exact_match": bool(evaluation_metrics["exact_match"]),
                "affected_prefix_correct": bool(
                    evaluation_metrics["affected_prefix_correct"]
                ),
                "ground_truth_reference": ground_truth_reference,
                "prediction_reference": _final_reference(
                    temporary_prediction_path,
                    final_prediction_path,
                ),
                "evaluation_reference": _final_reference(
                    temporary_evaluation_path,
                    final_evaluation_path,
                ),
            }
        )

    partition_metrics: dict[str, dict[str, Any]] = {}
    manifest_records: list[dict[str, Any]] = []
    for partition in DEVELOPMENT_PARTITIONS:
        records = [
            record for record in prediction_records if record["partition"] == partition
        ]
        metrics = compute_abstention_aware_metrics(records, EXPECTED_CLASS_ORDER)
        partition_metrics[partition] = metrics
        for record in records:
            manifest_records.append(
                {
                    "sample_id": record["sample_id"],
                    "partition": record["partition"],
                    "split_group_id": record["split_group_id"],
                    "prediction": record["prediction_reference"],
                    "evaluation": record["evaluation_reference"],
                }
            )

    manifest = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "status": "CANDIDATE_EVALUATED_ON_TRAIN_AND_VALIDATION",
        "partitions": {
            partition: {
                "row_count": EXPECTED_PARTITION_ROWS[partition],
                "group_count": len(EXPECTED_PARTITION_GROUPS[partition]),
                "group_ids": EXPECTED_PARTITION_GROUPS[partition],
                "metrics": partition_metrics[partition],
            }
            for partition in DEVELOPMENT_PARTITIONS
        },
        "records": manifest_records,
        "held_out_partition": "test",
        "test_predictions_or_metrics": "ABSENT",
    }
    temporary_manifest_path = candidate_temp / "candidate_manifest.json"
    final_manifest_path = candidate_final / "candidate_manifest.json"
    write_json(temporary_manifest_path, manifest)
    result = {
        "candidate_id": candidate_id,
        "complexity_rank": candidate["complexity_rank"],
        "train_metrics": compact_selection_metrics(partition_metrics["train"]),
        "validation_metrics": compact_selection_metrics(
            partition_metrics["validation"]
        ),
        "candidate_manifest": _final_reference(
            temporary_manifest_path,
            final_manifest_path,
        ),
    }
    return manifest, result


def _generate_all_candidate_predictions(
    *,
    candidates: Sequence[Mapping[str, Any]],
    samples: Sequence[DevelopmentSample],
    temporary_directory: Path,
    policy: Mapping[str, Any],
    policy_path: Path,
    prediction_schema_path: Path,
    expected_policy_sha256: str,
) -> None:
    for candidate in candidates:
        candidate_id = require_non_empty_string(
            candidate.get("candidate_id"),
            "candidate.candidate_id",
        )
        for sample in samples:
            prediction = build_hybrid_prediction(
                sample_id=sample.sample_id,
                evidence_reference=sample.evidence_reference,
                rule_prediction_reference=sample.rule_prediction_reference,
                ml_prediction_reference=sample.ml_prediction_reference,
                policy=policy,
                policy_path=policy_path,
                candidate_id=candidate_id,
                prediction_schema_path=prediction_schema_path,
                expected_policy_sha256=expected_policy_sha256,
            )
            write_json(
                temporary_directory
                / "candidates"
                / candidate_id
                / "samples"
                / sample.sample_id
                / "prediction.json",
                prediction,
            )


def run_hybrid_selection(
    *,
    policy_path: Path,
    policy_schema_path: Path,
    prediction_schema_path: Path,
    selection_schema_path: Path,
    source_paths: Mapping[str, Path],
    output_directory: Path,
    expected_policy_sha256: str = EXPECTED_POLICY_SHA256,
) -> dict[str, Any]:
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise HybridEngineError(f"P5-R1 output already exists: {output_directory}")
    policy_path = policy_path.resolve()
    policy = load_verified_policy(
        policy_path,
        policy_schema_path,
        expected_policy_sha256=expected_policy_sha256,
    )
    baseline_references = verify_baseline_bindings(policy, source_paths)
    samples = collect_development_samples(
        source_paths["rule_baseline"],
        source_paths["ml_report"],
    )
    candidates = policy.get("candidate_policies")
    if not isinstance(candidates, list) or [
        candidate.get("candidate_id")
        for candidate in candidates
        if isinstance(candidate, Mapping)
    ] != EXPECTED_CANDIDATE_ORDER:
        raise HybridEngineError("Frozen hybrid candidate order changed.")

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = output_directory.parent / (
        f".{output_directory.name}.{uuid4().hex}.tmp"
    )
    try:
        temporary_directory.mkdir()
        candidate_mappings = [
            require_mapping(value, "candidate")
            for value in candidates
        ]
        _generate_all_candidate_predictions(
            candidates=candidate_mappings,
            samples=samples,
            temporary_directory=temporary_directory,
            policy=policy,
            policy_path=policy_path,
            prediction_schema_path=prediction_schema_path,
            expected_policy_sha256=expected_policy_sha256,
        )
        candidate_results: list[dict[str, Any]] = []
        for candidate in candidate_mappings:
            _, result = _candidate_manifest_and_result(
                candidate=candidate,
                samples=samples,
                temporary_directory=temporary_directory,
                final_directory=output_directory,
                policy=policy,
                policy_path=policy_path,
                prediction_schema_path=prediction_schema_path,
                expected_policy_sha256=expected_policy_sha256,
            )
            candidate_results.append(result)

        ranked = sorted(candidate_results, key=selection_sort_key)
        selected_result = ranked[0]
        selected_candidate = {
            "candidate_id": selected_result["candidate_id"],
            "complexity_rank": selected_result["complexity_rank"],
            "selection_rank": 1,
            "selection_key": {
                "macro_f1_full_denominator": selected_result[
                    "validation_metrics"
                ]["macro_f1_full_denominator"],
                "exact_diagnosis_rate_full_denominator": selected_result[
                    "validation_metrics"
                ]["exact_diagnosis_rate_full_denominator"],
                "coverage": selected_result["validation_metrics"]["coverage"],
            },
        }
        selection = {
            "schema_version": 1,
            "selection_id": EXPECTED_SELECTION_ID,
            "generated_at_utc": utc_now(),
            "status": "SELECTED_POLICY_FROZEN",
            "implementation_id": EXPECTED_IMPLEMENTATION_ID,
            "campaign_id": require_mapping(
                require_mapping(policy["baseline_bindings"], "baseline_bindings").get(
                    "campaign"
                ),
                "baseline_bindings.campaign",
            )["campaign_id"],
            "policy": {
                "path": str(policy_path),
                "sha256": expected_policy_sha256,
                "policy_id": policy["policy_id"],
            },
            "baseline_bindings": baseline_references,
            "partition_policy": {
                "prediction_partitions": ["train", "validation"],
                "selection_partition": "validation",
                "held_out_partition": "test",
                "test_use": "report_only_after_selected_policy_freeze",
            },
            "candidate_order": list(EXPECTED_CANDIDATE_ORDER),
            "metric_order": list(policy["selection_protocol"]["metric_order"]),
            "candidate_results": candidate_results,
            "selected_candidate": selected_candidate,
            "leakage_audit": {
                "ground_truth_reader": "evaluator_only",
                "ground_truth_read_after_all_candidate_predictions": True,
                "test_prediction_artifacts_read": False,
                "test_ground_truth_read": False,
                "test_predictions_generated": False,
                "test_metrics_generated": False,
                "test_influenced_selection": False,
                "rule_or_ml_output_overwritten": False,
                "model_refit_performed": False,
            },
            "limitations": [
                "Selection uses one controlled validation context with six rows.",
                "P5-R1 establishes a deterministic freeze, not test performance.",
                "G02 remains closed until P5-R2 independently verifies this artifact.",
            ],
        }
        temporary_selection_path = temporary_directory / DEFAULT_SELECTION_FILE_NAME
        write_json(temporary_selection_path, selection)
        validate_json_schema(
            selection,
            selection_schema_path,
            "Hybrid Selection v1",
        )
        temporary_directory.replace(output_directory)
    except Exception:
        if temporary_directory.exists():
            shutil.rmtree(temporary_directory)
        raise

    selection_path = output_directory / DEFAULT_SELECTION_FILE_NAME
    verify_hybrid_selection(
        selection_path=selection_path,
        policy_path=policy_path,
        policy_schema_path=policy_schema_path,
        prediction_schema_path=prediction_schema_path,
        selection_schema_path=selection_schema_path,
        source_paths=source_paths,
        expected_policy_sha256=expected_policy_sha256,
        expected_selection_sha256=sha256_file(selection_path),
    )
    return read_json(selection_path)


def _record_from_evaluation(
    sample_record: Mapping[str, Any],
    prediction: Mapping[str, Any],
    evaluation: Mapping[str, Any],
) -> dict[str, Any]:
    expected = require_mapping(evaluation.get("expected"), "evaluation.expected")
    metrics = require_mapping(evaluation.get("metrics"), "evaluation.metrics")
    predicted_class = hybrid_predicted_class(prediction)
    return {
        "sample_id": sample_record["sample_id"],
        "partition": sample_record["partition"],
        "split_group_id": sample_record["split_group_id"],
        "expected_fault_type": expected["fault_type"],
        "predicted_fault_type": predicted_class,
        "abstained": predicted_class is None,
        "classification_correct": (
            predicted_class is not None and predicted_class == expected["fault_type"]
        ),
        "exact_match": bool(metrics["exact_match"]),
        "affected_prefix_correct": bool(metrics["affected_prefix_correct"]),
    }


def verify_hybrid_selection(
    *,
    selection_path: Path,
    policy_path: Path,
    policy_schema_path: Path,
    prediction_schema_path: Path,
    selection_schema_path: Path,
    source_paths: Mapping[str, Path],
    expected_policy_sha256: str = EXPECTED_POLICY_SHA256,
    expected_selection_sha256: str | None = None,
) -> dict[str, Any]:
    selection_path = selection_path.resolve()
    selection_hash = sha256_file(selection_path)
    if (
        expected_selection_sha256 is not None
        and selection_hash != expected_selection_sha256
    ):
        raise HybridEngineError("Hybrid selection SHA-256 drift detected.")
    policy = load_verified_policy(
        policy_path,
        policy_schema_path,
        expected_policy_sha256=expected_policy_sha256,
    )
    baseline_references = verify_baseline_bindings(policy, source_paths)
    selection = read_json(selection_path)
    validate_json_schema(selection, selection_schema_path, "Hybrid Selection v1")
    if selection.get("selection_id") != EXPECTED_SELECTION_ID:
        raise HybridEngineError("Unexpected hybrid selection_id.")
    if selection.get("status") != "SELECTED_POLICY_FROZEN":
        raise HybridEngineError("Hybrid selection is not frozen.")
    if selection.get("candidate_order") != EXPECTED_CANDIDATE_ORDER:
        raise HybridEngineError("Hybrid selection candidate order changed.")
    policy_binding = require_mapping(selection.get("policy"), "selection.policy")
    if policy_binding != {
        "path": str(policy_path.resolve()),
        "sha256": expected_policy_sha256,
        "policy_id": policy["policy_id"],
    }:
        raise HybridEngineError("Hybrid selection policy binding drift detected.")
    if selection.get("metric_order") != policy["selection_protocol"][
        "metric_order"
    ]:
        raise HybridEngineError("Hybrid selection metric order changed.")
    if selection.get("baseline_bindings") != baseline_references:
        raise HybridEngineError("Hybrid selection baseline binding drift detected.")
    leakage = require_mapping(selection.get("leakage_audit"), "leakage_audit")
    required_false = (
        "test_prediction_artifacts_read",
        "test_ground_truth_read",
        "test_predictions_generated",
        "test_metrics_generated",
        "test_influenced_selection",
        "rule_or_ml_output_overwritten",
        "model_refit_performed",
    )
    if any(leakage.get(field) is not False for field in required_false):
        raise HybridEngineError("Hybrid selection leakage audit failed.")

    output_directory = selection_path.parent
    candidate_results_value = selection.get("candidate_results")
    if (
        not isinstance(candidate_results_value, list)
        or len(candidate_results_value) != 2
    ):
        raise HybridEngineError("Hybrid selection must contain two candidates.")
    observed_candidate_ids = [
        require_mapping(value, "candidate_result").get("candidate_id")
        for value in candidate_results_value
    ]
    if observed_candidate_ids != EXPECTED_CANDIDATE_ORDER:
        raise HybridEngineError("Hybrid candidate result order changed.")
    expected_complexity_ranks = {
        candidate["candidate_id"]: candidate["complexity_rank"]
        for candidate in policy["candidate_policies"]
    }
    recomputed_results: list[dict[str, Any]] = []
    candidate_sample_sets: list[set[str]] = []
    for candidate_value in candidate_results_value:
        candidate_result = require_mapping(candidate_value, "candidate_result")
        candidate_id = require_non_empty_string(
            candidate_result.get("candidate_id"),
            "candidate_result.candidate_id",
        )
        if candidate_result.get("complexity_rank") != expected_complexity_ranks[
            candidate_id
        ]:
            raise HybridEngineError("Hybrid candidate complexity rank changed.")
        manifest_reference, manifest_path = validate_artifact_reference(
            candidate_result.get("candidate_manifest"),
            f"candidate {candidate_id}.manifest",
        )
        if output_directory not in manifest_path.parents:
            raise HybridEngineError(
                "Candidate manifest is outside the frozen output."
            )
        manifest = read_json(manifest_path)
        if (
            manifest.get("candidate_id") != candidate_id
            or manifest.get("held_out_partition") != "test"
            or manifest.get("test_predictions_or_metrics") != "ABSENT"
        ):
            raise HybridEngineError("Candidate manifest freeze is invalid.")
        manifest_partitions = require_mapping(
            manifest.get("partitions"),
            "manifest.partitions",
        )
        if set(manifest_partitions) != set(DEVELOPMENT_PARTITIONS):
            raise HybridEngineError(
                "Candidate manifest contains a forbidden partition."
            )
        records = manifest.get("records")
        if not isinstance(records, list) or len(records) != 24:
            raise HybridEngineError("Candidate manifest must contain 24 records.")
        metric_records: list[dict[str, Any]] = []
        sample_ids: set[str] = set()
        for position, value in enumerate(records, start=1):
            sample_record = require_mapping(
                value,
                f"manifest.records[{position}]",
            )
            sample_id = require_non_empty_string(
                sample_record.get("sample_id"),
                f"manifest.records[{position}].sample_id",
            )
            partition = sample_record.get("partition")
            if partition not in DEVELOPMENT_PARTITIONS:
                raise HybridEngineError("Candidate record contains test partition.")
            if sample_id in sample_ids:
                raise HybridEngineError("Duplicate candidate sample_id.")
            sample_ids.add(sample_id)
            _, prediction_path = validate_artifact_reference(
                sample_record.get("prediction"),
                f"candidate prediction {sample_id}",
                sample_id=sample_id,
            )
            _, evaluation_path = validate_artifact_reference(
                sample_record.get("evaluation"),
                f"candidate evaluation {sample_id}",
                sample_id=sample_id,
            )
            if (
                output_directory not in prediction_path.parents
                or output_directory not in evaluation_path.parents
            ):
                raise HybridEngineError(
                    "Candidate sample artifact escaped output directory."
                )
            prediction = read_json(prediction_path)
            validate_hybrid_prediction(
                prediction,
                prediction_schema_path,
                expected_policy_sha256=expected_policy_sha256,
            )
            if (
                prediction.get("sample_id") != sample_id
                or prediction.get("candidate_id") != candidate_id
            ):
                raise HybridEngineError("Candidate prediction identity mismatch.")
            evaluation = read_json(evaluation_path)
            if (
                evaluation.get("sample_id") != sample_id
                or evaluation.get("method") != "hybrid"
            ):
                raise HybridEngineError("Candidate evaluation identity mismatch.")
            metric_records.append(
                _record_from_evaluation(sample_record, prediction, evaluation)
            )
        candidate_sample_sets.append(sample_ids)
        recomputed_metrics = {
            partition: compute_abstention_aware_metrics(
                [
                    record
                    for record in metric_records
                    if record["partition"] == partition
                ],
                EXPECTED_CLASS_ORDER,
            )
            for partition in DEVELOPMENT_PARTITIONS
        }
        partitions = require_mapping(
            manifest.get("partitions"),
            "manifest.partitions",
        )
        for partition in DEVELOPMENT_PARTITIONS:
            summary = require_mapping(
                partitions.get(partition),
                f"partitions.{partition}",
            )
            if summary.get("metrics") != recomputed_metrics[partition]:
                raise HybridEngineError(f"{candidate_id} {partition} metrics drift.")
        recomputed_result = {
            "candidate_id": candidate_id,
            "complexity_rank": candidate_result["complexity_rank"],
            "train_metrics": compact_selection_metrics(recomputed_metrics["train"]),
            "validation_metrics": compact_selection_metrics(
                recomputed_metrics["validation"]
            ),
            "candidate_manifest": manifest_reference,
        }
        if dict(candidate_result) != recomputed_result:
            raise HybridEngineError(f"{candidate_id} selection summary drift.")
        recomputed_results.append(recomputed_result)

    if candidate_sample_sets[0] != candidate_sample_sets[1] or len(
        candidate_sample_sets[0]
    ) != 24:
        raise HybridEngineError("Candidate development sample sets differ.")
    ranked = sorted(recomputed_results, key=selection_sort_key)
    selected = require_mapping(
        selection.get("selected_candidate"),
        "selected_candidate",
    )
    winner = ranked[0]
    expected_selected = {
        "candidate_id": winner["candidate_id"],
        "complexity_rank": winner["complexity_rank"],
        "selection_rank": 1,
        "selection_key": {
            "macro_f1_full_denominator": winner["validation_metrics"][
                "macro_f1_full_denominator"
            ],
            "exact_diagnosis_rate_full_denominator": winner[
                "validation_metrics"
            ]["exact_diagnosis_rate_full_denominator"],
            "coverage": winner["validation_metrics"]["coverage"],
        },
    }
    if dict(selected) != expected_selected:
        raise HybridEngineError("Selected hybrid candidate is not the frozen winner.")
    if any(
        path.name == "test" and path.is_dir()
        for path in output_directory.rglob("test")
    ):
        raise HybridEngineError("Unexpected test output directory exists.")
    return {
        "selection_id": selection["selection_id"],
        "selection_sha256": selection_hash,
        "status": "SELECTED_POLICY_FROZEN_VERIFIED",
        "selected_candidate": selected["candidate_id"],
        "candidate_count": len(recomputed_results),
        "development_rows": 24,
        "selection_partition": "validation",
        "test_predictions_or_metrics": "ABSENT",
    }


def source_path_arguments(arguments: argparse.Namespace) -> dict[str, Path]:
    return {
        "rule_baseline": arguments.rule_report,
        "ml_feature_matrix": arguments.matrix,
        "ml_selection": arguments.ml_selection,
        "ml_model": arguments.ml_model,
        "ml_report": arguments.ml_report,
    }


def add_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--rule-report", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--ml-selection", type=Path, required=True)
    parser.add_argument("--ml-model", type=Path, required=True)
    parser.add_argument("--ml-report", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or verify frozen P5-R1 hybrid selection."
    )
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
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-selection")
    add_source_arguments(run_parser)
    run_parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
    )

    verify_parser = subparsers.add_parser("verify-selection")
    add_source_arguments(verify_parser)
    verify_parser.add_argument("--selection", type=Path, required=True)
    verify_parser.add_argument("--expected-selection-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "run-selection":
            selection = run_hybrid_selection(
                policy_path=arguments.policy,
                policy_schema_path=arguments.policy_schema,
                prediction_schema_path=arguments.prediction_schema,
                selection_schema_path=arguments.selection_schema,
                source_paths=source_path_arguments(arguments),
                output_directory=arguments.output_directory,
            )
            selected = selection["selected_candidate"]
            result = {
                "selection_id": selection["selection_id"],
                "status": selection["status"],
                "selected_candidate": selected["candidate_id"],
                "selection_path": str(
                    (arguments.output_directory / DEFAULT_SELECTION_FILE_NAME).resolve()
                ),
                "selection_sha256": sha256_file(
                    arguments.output_directory / DEFAULT_SELECTION_FILE_NAME
                ),
                "candidate_count": len(selection["candidate_results"]),
                "development_rows": 24,
                "test_predictions_or_metrics": "ABSENT",
            }
        else:
            result = verify_hybrid_selection(
                selection_path=arguments.selection,
                policy_path=arguments.policy,
                policy_schema_path=arguments.policy_schema,
                prediction_schema_path=arguments.prediction_schema,
                selection_schema_path=arguments.selection_schema,
                source_paths=source_path_arguments(arguments),
                expected_selection_sha256=arguments.expected_selection_sha256,
            )
    except (
        EvaluationReportingError,
        HybridEngineError,
        HybridPolicyError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
