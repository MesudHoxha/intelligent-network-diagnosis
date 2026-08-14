from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import shutil
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

import joblib
from jsonschema import Draft202012Validator
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from src.evaluation.evaluator import evaluate_prediction
from src.evaluation.reporting import (
    artifact_reference,
    build_method_evaluation_result,
    compute_classification_metrics,
    validate_against_schema as validate_method_schema,
    validate_method_evaluation_result,
)
from src.ml.feature_matrix import (
    CLASS_ORDER,
    ENCODED_FEATURE_NAMES,
    MODEL_RANDOM_SEED,
    RAW_FEATURE_NAMES,
    candidate_models,
    validate_ml_feature_matrix,
)


ML_PIPELINE_SELECTION_SCHEMA_VERSION = 1
DEFAULT_SELECTION_ID = "p4_r1_ml_selection_v1"
DEFAULT_PIPELINE_ID = "p4_r1_ml_pipeline_v1"
DEFAULT_RESULT_ID = "p4_r1_ml_baseline_v1"
EXPECTED_MATRIX_ID = "p4_r0_ml_feature_matrix_v1"
EXPECTED_MATRIX_SHA256 = (
    "9193b4b8c676bf94ef9af05562d9d0047faef61bc94c9d81"
    "b0485b88bf599730"
)
EXPECTED_CAMPAIGN_RUN_ID = (
    "p2_routing_5ctx_v1-20260804T073429388394Z-"
    "617194fea9954ed98ec120bdefea23d9"
)
EXPECTED_DATASET_SHA256 = (
    "be92cef4e78764e772909e15f43ab5cba98ef9610f4a446fc"
    "95e8afb5e830c80"
)
ACCEPTED_SELECTION_SHA256 = (
    "a02536d6f2478d9fdc40510275dd3b48a2824ee7b1f0fa08c"
    "1aed472611fb6fb"
)
ACCEPTED_MODEL_SHA256 = (
    "90db38e625f4bcf6a234b6a0516371b76f98e01b4437f684f"
    "fea119cbc09cdb2"
)
SELECTION_FILE_NAME = "selection.json"
MODEL_FILE_NAME = "estimator.joblib"
REPORT_FILE_NAME = "method_evaluation_result.json"


class MLBaselineError(ValueError):
    """Raised when the frozen P4-R1 ML baseline contract is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise MLBaselineError(f"Required artifact does not exist: {path}")

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MLBaselineError(f"Required JSON artifact does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise MLBaselineError(
            f"Invalid JSON in {path}: {error.msg}"
        ) from error
    if not isinstance(value, dict):
        raise MLBaselineError(f"Expected a JSON object in: {path}")
    return value


def require_mapping(value: object, reference: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MLBaselineError(f"{reference} must be an object.")
    return value


def require_non_empty_string(value: object, reference: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MLBaselineError(f"{reference} must be a non-empty string.")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_selection_schema(
    selection: Mapping[str, Any],
    schema_path: Path,
) -> None:
    schema = read_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(selection),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(
            str(part) for part in first.absolute_path
        ) or "<root>"
        raise MLBaselineError(
            "ML Pipeline Selection v1 schema validation failed at "
            f"{location}: {first.message}"
        )


def software_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "scikit_learn": version("scikit-learn"),
        "numpy": version("numpy"),
        "joblib": version("joblib"),
    }


def load_accepted_matrix(
    matrix_path: Path,
    expected_matrix_sha256: str,
) -> dict[str, Any]:
    resolved = matrix_path.resolve()
    observed_hash = sha256_file(resolved)
    if observed_hash != expected_matrix_sha256:
        raise MLBaselineError(
            "Feature-matrix SHA-256 does not match the accepted binding."
        )
    matrix = read_json(resolved)
    validate_ml_feature_matrix(matrix)
    if matrix.get("matrix_id") != EXPECTED_MATRIX_ID:
        raise MLBaselineError("Unexpected ML feature-matrix identity.")

    dataset_binding = require_mapping(
        matrix.get("dataset_binding"),
        "matrix.dataset_binding",
    )
    if dataset_binding.get("campaign_run_id") != EXPECTED_CAMPAIGN_RUN_ID:
        raise MLBaselineError("Feature matrix is not bound to D-067.")
    merged = require_mapping(
        dataset_binding.get("merged_dataset"),
        "matrix.dataset_binding.merged_dataset",
    )
    if merged.get("sha256") != EXPECTED_DATASET_SHA256:
        raise MLBaselineError("Feature matrix dataset hash is not D-067.")
    return matrix


def partition_records(
    matrix: Mapping[str, Any],
    partition_name: str,
) -> list[Mapping[str, Any]]:
    partitions = require_mapping(matrix.get("partitions"), "matrix.partitions")
    partition = require_mapping(
        partitions.get(partition_name),
        f"matrix.partitions.{partition_name}",
    )
    records = partition.get("records")
    if not isinstance(records, list):
        raise MLBaselineError(
            f"matrix.partitions.{partition_name}.records must be an array."
        )
    return [
        require_mapping(record, f"{partition_name}.record")
        for record in records
    ]


def predictor_arrays(
    records: Sequence[Mapping[str, Any]],
) -> tuple[list[list[int]], list[str]]:
    features: list[list[int]] = []
    targets: list[str] = []
    for record in records:
        vector = record.get("feature_vector")
        if (
            not isinstance(vector, list)
            or len(vector) != len(ENCODED_FEATURE_NAMES)
            or any(value not in (0, 1) for value in vector)
        ):
            raise MLBaselineError("Invalid predictor vector in feature matrix.")
        target = record.get("target_class")
        if target not in CLASS_ORDER:
            raise MLBaselineError("Invalid target class in feature matrix.")
        features.append(list(vector))
        targets.append(str(target))
    return features, targets


def instantiate_candidate(candidate: Mapping[str, Any]) -> object:
    family = candidate.get("family")
    parameters = copy.deepcopy(
        require_mapping(candidate.get("parameters"), "candidate.parameters")
    )
    if family == "multinomial_logistic_regression":
        return LogisticRegression(
            C=float(parameters["C"]),
            class_weight=parameters["class_weight"],
            max_iter=int(parameters["max_iter"]),
            penalty=str(parameters["penalty"]),
            solver=str(parameters["solver"]),
            random_state=MODEL_RANDOM_SEED,
        )
    if family == "decision_tree":
        return DecisionTreeClassifier(
            criterion=str(parameters["criterion"]),
            max_depth=int(parameters["max_depth"]),
            min_samples_leaf=int(parameters["min_samples_leaf"]),
            splitter=str(parameters["splitter"]),
            random_state=MODEL_RANDOM_SEED,
        )
    raise MLBaselineError(f"Unsupported candidate family: {family!r}")


def compact_metrics(
    expected: Sequence[str],
    predicted: Sequence[str],
) -> dict[str, Any]:
    if len(expected) != len(predicted):
        raise MLBaselineError("Prediction count does not match target count.")
    records = [
        {
            "expected_fault_type": expected_value,
            "predicted_fault_type": predicted_value,
        }
        for expected_value, predicted_value in zip(expected, predicted)
    ]
    metrics = compute_classification_metrics(records, CLASS_ORDER)
    return {
        "row_count": metrics["sample_count"],
        "correct_count": metrics["correct_count"],
        "accuracy": metrics["accuracy"],
        "macro_f1": metrics["macro"]["f1"],
    }


def candidate_sort_key(result: Mapping[str, Any]) -> tuple[Any, ...]:
    validation = require_mapping(
        result.get("validation_metrics"),
        "candidate_result.validation_metrics",
    )
    candidate = require_mapping(
        result.get("candidate"),
        "candidate_result.candidate",
    )
    return (
        -float(validation["macro_f1"]),
        -float(validation["accuracy"]),
        int(candidate["complexity_rank"]),
        str(candidate["candidate_id"]),
    )


def sample_ids_sha256(records: Sequence[Mapping[str, Any]]) -> str:
    sample_ids = sorted(
        require_non_empty_string(record.get("sample_id"), "record.sample_id")
        for record in records
    )
    return sha256_text("\n".join(sample_ids) + "\n")


def partition_fit_binding(
    matrix: Mapping[str, Any],
    partition_name: str,
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    partition = require_mapping(
        require_mapping(matrix.get("partitions"), "matrix.partitions").get(
            partition_name
        ),
        f"matrix.partitions.{partition_name}",
    )
    groups = partition.get("group_ids")
    if not isinstance(groups, list):
        raise MLBaselineError(f"Invalid {partition_name} group binding.")
    return {
        "partition": partition_name,
        "row_count": len(records),
        "group_ids": list(groups),
        "sample_ids_sha256": sample_ids_sha256(records),
    }


def model_bundle(
    *,
    estimator: object,
    matrix_path: Path,
    matrix_sha256: str,
    selected_candidate: Mapping[str, Any],
    train_records: Sequence[Mapping[str, Any]],
    software: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "artifact_version": 1,
        "pipeline_id": DEFAULT_PIPELINE_ID,
        "protocol_id": "leakage_safe_ml_baseline_v1",
        "matrix": {
            "matrix_id": EXPECTED_MATRIX_ID,
            "path": str(matrix_path.resolve()),
            "sha256": matrix_sha256,
        },
        "selected_candidate": copy.deepcopy(dict(selected_candidate)),
        "encoded_feature_names": list(ENCODED_FEATURE_NAMES),
        "class_order": list(CLASS_ORDER),
        "fit_partition": "train",
        "fit_row_count": len(train_records),
        "fit_sample_ids_sha256": sample_ids_sha256(train_records),
        "model_random_seed": MODEL_RANDOM_SEED,
        "software": dict(software),
        "estimator": estimator,
    }


def build_selection_result(
    *,
    matrix: Mapping[str, Any],
    matrix_path: Path,
    matrix_sha256: str,
    candidate_results: Sequence[Mapping[str, Any]],
    selected_candidate: Mapping[str, Any],
    model_path: Path,
    model_sha256: str,
    train_records: Sequence[Mapping[str, Any]],
    validation_records: Sequence[Mapping[str, Any]],
    software: Mapping[str, str],
) -> dict[str, Any]:
    selected_metrics = require_mapping(
        selected_candidate.get("validation_metrics"),
        "selected.validation_metrics",
    )
    selected_identity = require_mapping(
        selected_candidate.get("candidate"),
        "selected.candidate",
    )
    return {
        "schema_version": ML_PIPELINE_SELECTION_SCHEMA_VERSION,
        "selection_id": DEFAULT_SELECTION_ID,
        "pipeline_id": DEFAULT_PIPELINE_ID,
        "generated_at_utc": utc_now(),
        "status": "PIPELINE_FROZEN",
        "protocol_id": "leakage_safe_ml_baseline_v1",
        "matrix": {
            "matrix_id": matrix["matrix_id"],
            "path": str(matrix_path.resolve()),
            "sha256": matrix_sha256,
            "row_count": matrix["row_count"],
            "encoded_feature_count": matrix["encoded_feature_count"],
        },
        "partition_policy": {
            "fit_partition": "train",
            "selection_partition": "validation",
            "held_out_partition": "test",
            "test_use": "report_only_after_pipeline_freeze",
            "refit_on_train_plus_validation": False,
        },
        "selection_policy": {
            "ordered_criteria": [
                "validation_macro_f1_desc",
                "validation_accuracy_desc",
                "complexity_rank_asc",
                "candidate_id_asc",
            ],
            "decision_threshold": "argmax",
            "candidate_count": 6,
        },
        "candidate_results": [copy.deepcopy(dict(value)) for value in candidate_results],
        "selected_candidate": {
            "candidate": copy.deepcopy(dict(selected_identity)),
            "validation_macro_f1": selected_metrics["macro_f1"],
            "validation_accuracy": selected_metrics["accuracy"],
            "selection_rank": 1,
        },
        "fit_summary": {
            "class_order": list(CLASS_ORDER),
            "encoded_feature_names": list(ENCODED_FEATURE_NAMES),
            "train": partition_fit_binding(matrix, "train", train_records),
            "validation": partition_fit_binding(
                matrix,
                "validation",
                validation_records,
            ),
        },
        "software": dict(software),
        "model_artifact": {
            "path": str(model_path.resolve()),
            "sha256": model_sha256,
            "serialization": "joblib",
            "fitted_partition": "train",
            "refit_performed": False,
        },
        "leakage_audit": {
            "predictor_columns": len(ENCODED_FEATURE_NAMES),
            "fit_partitions": ["train"],
            "selection_partitions": ["validation"],
            "test_features_accessed_for_selection": False,
            "test_labels_accessed_for_selection": False,
            "test_predictions_generated": False,
            "test_metrics_generated": False,
            "validation_used_for_parameter_fit": False,
            "refit_on_train_plus_validation": False,
        },
        "limitations": [
            "Selection uses one six-row validation context.",
            "The fitted estimator uses only 18 controlled train rows.",
            "No test prediction or test metric exists in this freeze artifact.",
        ],
    }


def train_select_and_freeze(
    *,
    matrix_path: Path,
    pipeline_directory: Path,
    selection_schema_path: Path,
    expected_matrix_sha256: str = EXPECTED_MATRIX_SHA256,
) -> dict[str, Any]:
    if pipeline_directory.exists():
        raise MLBaselineError(
            f"Pipeline output already exists: {pipeline_directory}"
        )

    matrix_path = matrix_path.resolve()
    matrix = load_accepted_matrix(matrix_path, expected_matrix_sha256)
    if matrix["protocol"]["candidate_models"] != candidate_models():
        raise MLBaselineError("Candidate set drifted from D-070.")

    # Selection code intentionally never requests the held-out records.
    train_records = partition_records(matrix, "train")
    validation_records = partition_records(matrix, "validation")
    train_x, train_y = predictor_arrays(train_records)
    validation_x, validation_y = predictor_arrays(validation_records)

    results: list[dict[str, Any]] = []
    estimators: dict[str, object] = {}
    for candidate in candidate_models():
        estimator = instantiate_candidate(candidate)
        estimator.fit(train_x, train_y)
        train_predictions = [str(value) for value in estimator.predict(train_x)]
        validation_predictions = [
            str(value) for value in estimator.predict(validation_x)
        ]
        result = {
            "candidate": copy.deepcopy(candidate),
            "fit_partition": "train",
            "selection_partition": "validation",
            "train_metrics": compact_metrics(train_y, train_predictions),
            "validation_metrics": compact_metrics(
                validation_y,
                validation_predictions,
            ),
        }
        results.append(result)
        estimators[str(candidate["candidate_id"])] = estimator

    ranked = sorted(results, key=candidate_sort_key)
    winner = ranked[0]
    winner_identity = require_mapping(
        winner.get("candidate"),
        "winner.candidate",
    )
    selected_estimator = estimators[str(winner_identity["candidate_id"])]
    software = software_versions()

    parent = pipeline_directory.resolve().parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = parent / (
        f".{pipeline_directory.name}.{uuid4().hex}.tmp"
    )
    model_final_path = pipeline_directory.resolve() / MODEL_FILE_NAME
    selection_final_path = pipeline_directory.resolve() / SELECTION_FILE_NAME

    try:
        temporary_directory.mkdir()
        temporary_model_path = temporary_directory / MODEL_FILE_NAME
        bundle = model_bundle(
            estimator=selected_estimator,
            matrix_path=matrix_path,
            matrix_sha256=expected_matrix_sha256,
            selected_candidate=winner_identity,
            train_records=train_records,
            software=software,
        )
        joblib.dump(bundle, temporary_model_path, compress=3)
        model_hash = sha256_file(temporary_model_path)
        selection = build_selection_result(
            matrix=matrix,
            matrix_path=matrix_path,
            matrix_sha256=expected_matrix_sha256,
            candidate_results=results,
            selected_candidate=winner,
            model_path=model_final_path,
            model_sha256=model_hash,
            train_records=train_records,
            validation_records=validation_records,
            software=software,
        )
        temporary_selection_path = temporary_directory / SELECTION_FILE_NAME
        write_json(temporary_selection_path, selection)
        validate_frozen_pipeline(
            matrix_path=matrix_path,
            selection_path=temporary_selection_path,
            model_path=temporary_model_path,
            selection_schema_path=selection_schema_path,
            expected_matrix_sha256=expected_matrix_sha256,
            expected_model_path=model_final_path,
        )
        temporary_directory.replace(pipeline_directory.resolve())
    except Exception:
        if temporary_directory.exists():
            for child in temporary_directory.iterdir():
                if child.is_file():
                    child.unlink()
            temporary_directory.rmdir()
        raise

    return read_json(selection_final_path)


def validate_candidate_results(
    selection: Mapping[str, Any],
    matrix: Mapping[str, Any],
    estimator_bundle: Mapping[str, Any],
) -> None:
    results = selection.get("candidate_results")
    if not isinstance(results, list) or len(results) != 6:
        raise MLBaselineError("Exactly six candidate results are required.")
    observed_candidates = [
        require_mapping(result, "candidate_result").get("candidate")
        for result in results
    ]
    if observed_candidates != candidate_models():
        raise MLBaselineError("Candidate results do not match D-070 order.")

    winner = sorted(
        [require_mapping(result, "candidate_result") for result in results],
        key=candidate_sort_key,
    )[0]
    selected = require_mapping(
        selection.get("selected_candidate"),
        "selection.selected_candidate",
    )
    selected_identity = require_mapping(
        selected.get("candidate"),
        "selection.selected_candidate.candidate",
    )
    if selected_identity != winner.get("candidate"):
        raise MLBaselineError(
            "Selected candidate violates the frozen tie-break order."
        )
    validation = require_mapping(
        winner.get("validation_metrics"),
        "winner.validation_metrics",
    )
    if (
        selected.get("validation_macro_f1") != validation.get("macro_f1")
        or selected.get("validation_accuracy") != validation.get("accuracy")
    ):
        raise MLBaselineError("Selected-candidate metrics disagree.")

    bundle_identity = require_mapping(
        estimator_bundle.get("selected_candidate"),
        "model.selected_candidate",
    )
    if bundle_identity != selected_identity:
        raise MLBaselineError("Model and selection identities disagree.")

    train_records = partition_records(matrix, "train")
    validation_records = partition_records(matrix, "validation")
    train_x, train_y = predictor_arrays(train_records)
    validation_x, validation_y = predictor_arrays(validation_records)
    estimator = estimator_bundle.get("estimator")
    if not hasattr(estimator, "predict"):
        raise MLBaselineError("Frozen model does not provide predict().")
    train_predictions = [str(value) for value in estimator.predict(train_x)]
    validation_predictions = [
        str(value) for value in estimator.predict(validation_x)
    ]
    if winner.get("train_metrics") != compact_metrics(
        train_y,
        train_predictions,
    ):
        raise MLBaselineError("Frozen train metrics cannot be reproduced.")
    if winner.get("validation_metrics") != compact_metrics(
        validation_y,
        validation_predictions,
    ):
        raise MLBaselineError(
            "Frozen validation metrics cannot be reproduced."
        )


def validate_frozen_pipeline(
    *,
    matrix_path: Path,
    selection_path: Path,
    model_path: Path,
    selection_schema_path: Path,
    expected_matrix_sha256: str = EXPECTED_MATRIX_SHA256,
    expected_selection_sha256: str | None = None,
    expected_model_sha256: str | None = None,
    expected_model_path: Path | None = None,
) -> dict[str, Any]:
    matrix_path = matrix_path.resolve()
    selection_path = selection_path.resolve()
    model_path = model_path.resolve()
    matrix = load_accepted_matrix(matrix_path, expected_matrix_sha256)

    if expected_selection_sha256 is not None and sha256_file(
        selection_path
    ) != expected_selection_sha256:
        raise MLBaselineError("Selection-result SHA-256 drift detected.")
    observed_model_hash = sha256_file(model_path)
    if (
        expected_model_sha256 is not None
        and observed_model_hash != expected_model_sha256
    ):
        raise MLBaselineError("Model-artifact SHA-256 drift detected.")

    selection = read_json(selection_path)
    validate_selection_schema(selection, selection_schema_path)
    if selection.get("status") != "PIPELINE_FROZEN":
        raise MLBaselineError("Pipeline is not frozen.")
    if selection.get("candidate_results") is None:
        raise MLBaselineError("Candidate results are absent.")
    matrix_binding = require_mapping(
        selection.get("matrix"),
        "selection.matrix",
    )
    if (
        matrix_binding.get("path") != str(matrix_path)
        or matrix_binding.get("sha256") != expected_matrix_sha256
        or matrix_binding.get("matrix_id") != EXPECTED_MATRIX_ID
    ):
        raise MLBaselineError("Selection matrix binding is invalid.")
    leakage = require_mapping(
        selection.get("leakage_audit"),
        "selection.leakage_audit",
    )
    if leakage != {
        "predictor_columns": 14,
        "fit_partitions": ["train"],
        "selection_partitions": ["validation"],
        "test_features_accessed_for_selection": False,
        "test_labels_accessed_for_selection": False,
        "test_predictions_generated": False,
        "test_metrics_generated": False,
        "validation_used_for_parameter_fit": False,
        "refit_on_train_plus_validation": False,
    }:
        raise MLBaselineError("Selection leakage audit is invalid.")

    model_binding = require_mapping(
        selection.get("model_artifact"),
        "selection.model_artifact",
    )
    required_model_path = (
        expected_model_path.resolve()
        if expected_model_path is not None
        else model_path
    )
    if model_binding.get("path") != str(required_model_path):
        raise MLBaselineError("Selection model path is invalid.")
    if model_binding.get("sha256") != observed_model_hash:
        raise MLBaselineError("Selection model hash is invalid.")

    try:
        bundle = joblib.load(model_path)
    except Exception as error:
        raise MLBaselineError("Frozen model artifact cannot be loaded.") from error
    if not isinstance(bundle, Mapping):
        raise MLBaselineError("Frozen model artifact must contain a mapping.")
    if (
        bundle.get("artifact_version") != 1
        or bundle.get("pipeline_id") != DEFAULT_PIPELINE_ID
        or bundle.get("fit_partition") != "train"
        or bundle.get("fit_row_count") != 18
        or bundle.get("matrix", {}).get("sha256")
        != expected_matrix_sha256
        or bundle.get("encoded_feature_names")
        != list(ENCODED_FEATURE_NAMES)
        or bundle.get("class_order") != list(CLASS_ORDER)
    ):
        raise MLBaselineError("Frozen model metadata is invalid.")
    if bundle.get("fit_sample_ids_sha256") != sample_ids_sha256(
        partition_records(matrix, "train")
    ):
        raise MLBaselineError("Frozen model train-sample binding is invalid.")
    validate_candidate_results(selection, matrix, bundle)
    return {
        "selection": selection,
        "model_bundle": bundle,
        "selection_sha256": sha256_file(selection_path),
        "model_sha256": observed_model_hash,
    }


def decode_evidence(vector: Sequence[int]) -> list[dict[str, str]]:
    observations: list[dict[str, str]] = []
    for index, feature_name in enumerate(RAW_FEATURE_NAMES):
        pair = list(vector[index * 2:index * 2 + 2])
        if pair == [1, 1]:
            state = "true"
        elif pair == [1, 0]:
            state = "false"
        elif pair == [0, 0]:
            state = "unavailable"
        else:
            raise MLBaselineError(
                f"Invalid encoded pair for {feature_name}: {pair}"
            )
        observations.append({"feature": feature_name, "state": state})
    return observations


def explain_prediction(
    estimator: object,
    vector: Sequence[int],
    predicted_class: str,
) -> dict[str, Any]:
    if not hasattr(estimator, "predict_proba"):
        raise MLBaselineError("Frozen estimator does not expose predict_proba().")
    probabilities = estimator.predict_proba([list(vector)])[0]
    classes = [str(value) for value in estimator.classes_]
    class_probabilities = {
        label: float(probability)
        for label, probability in zip(classes, probabilities)
    }

    if isinstance(estimator, LogisticRegression):
        predicted_index = classes.index(predicted_class)
        coefficients = estimator.coef_[predicted_index]
        contributions = [
            {
                "feature": feature_name,
                "value": int(value),
                "coefficient": float(coefficient),
                "contribution": float(value * coefficient),
            }
            for feature_name, value, coefficient in zip(
                ENCODED_FEATURE_NAMES,
                vector,
                coefficients,
            )
        ]
        contributions.sort(
            key=lambda item: (
                -abs(item["contribution"]),
                item["feature"],
            )
        )
        detail = {
            "explanation_type": "linear_feature_contributions",
            "top_contributions": contributions[:5],
        }
    elif isinstance(estimator, DecisionTreeClassifier):
        decision_path = estimator.decision_path([list(vector)]).indices
        nodes: list[dict[str, Any]] = []
        for node_id in decision_path:
            feature_index = int(estimator.tree_.feature[node_id])
            if feature_index < 0:
                nodes.append({"node_id": int(node_id), "kind": "leaf"})
                continue
            threshold = float(estimator.tree_.threshold[node_id])
            observed_value = int(vector[feature_index])
            nodes.append({
                "node_id": int(node_id),
                "kind": "decision",
                "feature": ENCODED_FEATURE_NAMES[feature_index],
                "observed_value": observed_value,
                "threshold": threshold,
                "branch": "left" if observed_value <= threshold else "right",
            })
        detail = {
            "explanation_type": "decision_path",
            "nodes": nodes,
        }
    else:
        raise MLBaselineError("Unsupported fitted estimator family.")

    return {
        "predicted_class": predicted_class,
        "predicted_class_probability": class_probabilities[predicted_class],
        "class_probabilities": dict(sorted(class_probabilities.items())),
        **detail,
    }


def build_prediction_document(
    *,
    sample_id: str,
    vector: Sequence[int],
    predicted_class: str,
    estimator: object,
    candidate_id: str,
    model_sha256: str,
) -> dict[str, Any]:
    if predicted_class == "no_fault":
        status = "NO_FAULT_DETECTED"
        diagnosis: dict[str, Any] = {}
    else:
        status = "DIAGNOSIS_PRODUCED"
        diagnosis = {
            "category": "routing",
            "fault_type": predicted_class,
            "location": None,
            "affected_prefix": None,
        }
    return {
        "schema_version": 1,
        "sample_id": sample_id,
        "method": "machine_learning",
        "status": status,
        "diagnosis": diagnosis,
        "supporting_evidence": {
            "source": "ml_feature_matrix_v1",
            "observations": decode_evidence(vector),
        },
        "model_explanation": explain_prediction(
            estimator,
            vector,
            predicted_class,
        ),
        "model_binding": {
            "pipeline_id": DEFAULT_PIPELINE_ID,
            "candidate_id": candidate_id,
            "model_sha256": model_sha256,
        },
        "limitations": [
            "This independent ML baseline predicts fault_type only.",
            "It does not infer fault_location or affected_prefix.",
        ],
    }


def original_artifact_paths(
    experiments_root: Path,
    sample_id: str,
) -> dict[str, Path]:
    experiment_directory = (experiments_root / sample_id).resolve()
    paths = {
        "experiment_manifest": experiment_directory / "manifest.json",
        "ground_truth": experiment_directory / "ground_truth.json",
        "evidence": experiment_directory / "parsed" / "evidence.json",
    }
    for path in paths.values():
        sha256_file(path)
    manifest = read_json(paths["experiment_manifest"])
    if manifest.get("experiment_id") != sample_id:
        raise MLBaselineError(
            f"Experiment manifest identity mismatch for {sample_id}."
        )
    return paths


def reference_with_final_path(
    temporary_path: Path,
    final_path: Path,
) -> dict[str, str]:
    return {
        "path": str(final_path.resolve()),
        "sha256": sha256_file(temporary_path.resolve()),
    }


def dataset_binding_from_matrix(
    matrix: Mapping[str, Any],
) -> dict[str, Any]:
    binding = copy.deepcopy(
        dict(require_mapping(matrix.get("dataset_binding"), "matrix.dataset_binding"))
    )
    # The matrix contract already stores the exact Method Evaluation
    # Result v1 dataset binding shape.
    return binding


def build_ml_baseline_report(
    *,
    matrix_path: Path,
    selection_path: Path,
    model_path: Path,
    selection_schema_path: Path,
    method_schema_path: Path,
    experiments_root: Path,
    report_directory: Path,
    expected_matrix_sha256: str = EXPECTED_MATRIX_SHA256,
    expected_selection_sha256: str,
    expected_model_sha256: str,
) -> dict[str, Any]:
    if report_directory.exists():
        raise MLBaselineError(
            f"ML report output already exists: {report_directory}"
        )

    # This complete verification is the freeze gate. No test record is
    # requested or predicted before it succeeds.
    frozen = validate_frozen_pipeline(
        matrix_path=matrix_path,
        selection_path=selection_path,
        model_path=model_path,
        selection_schema_path=selection_schema_path,
        expected_matrix_sha256=expected_matrix_sha256,
        expected_selection_sha256=expected_selection_sha256,
        expected_model_sha256=expected_model_sha256,
    )
    matrix = load_accepted_matrix(matrix_path, expected_matrix_sha256)
    selection = require_mapping(frozen["selection"], "frozen.selection")
    bundle = require_mapping(frozen["model_bundle"], "frozen.model_bundle")
    estimator = bundle.get("estimator")
    selected = require_mapping(
        selection.get("selected_candidate"),
        "selection.selected_candidate",
    )
    selected_identity = require_mapping(
        selected.get("candidate"),
        "selection.selected_candidate.candidate",
    )
    candidate_id = require_non_empty_string(
        selected_identity.get("candidate_id"),
        "selected_candidate.candidate_id",
    )

    # Predictions are produced from feature vectors only. Targets and
    # ground truth are read later by the evaluation-only stage.
    ordered_records: list[tuple[str, Mapping[str, Any]]] = []
    predictions: dict[str, str] = {}
    for partition_name in ("train", "validation", "test"):
        for record in partition_records(matrix, partition_name):
            vector = record.get("feature_vector")
            if not isinstance(vector, list):
                raise MLBaselineError("Invalid report predictor vector.")
            sample_id = require_non_empty_string(
                record.get("sample_id"),
                "matrix.record.sample_id",
            )
            predictions[sample_id] = str(estimator.predict([vector])[0])
            ordered_records.append((partition_name, record))

    parent = report_directory.resolve().parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary_directory = parent / (
        f".{report_directory.name}.{uuid4().hex}.tmp"
    )
    final_report_path = report_directory.resolve() / REPORT_FILE_NAME

    try:
        temporary_directory.mkdir()
        report_records: list[dict[str, Any]] = []
        for partition_name, record in ordered_records:
            sample_id = require_non_empty_string(
                record.get("sample_id"),
                "matrix.record.sample_id",
            )
            vector = record.get("feature_vector")
            if not isinstance(vector, list):
                raise MLBaselineError("Invalid report predictor vector.")
            predicted_class = predictions[sample_id]
            if predicted_class not in CLASS_ORDER:
                raise MLBaselineError(
                    f"Unsupported model prediction for {sample_id}."
                )

            prediction = build_prediction_document(
                sample_id=sample_id,
                vector=vector,
                predicted_class=predicted_class,
                estimator=estimator,
                candidate_id=candidate_id,
                model_sha256=expected_model_sha256,
            )
            source_paths = original_artifact_paths(
                experiments_root.resolve(),
                sample_id,
            )
            ground_truth = read_json(source_paths["ground_truth"])
            if ground_truth.get("fault_type") != record.get("target_class"):
                raise MLBaselineError(
                    f"Ground-truth label mismatch for {sample_id}."
                )
            evaluation = evaluate_prediction(ground_truth, prediction)
            evaluation["sample_id"] = sample_id
            evaluation["experiment_directory"] = str(
                (experiments_root / sample_id).resolve()
            )

            temporary_sample_directory = temporary_directory / "samples" / sample_id
            temporary_prediction_path = (
                temporary_sample_directory / "prediction.json"
            )
            temporary_evaluation_path = (
                temporary_sample_directory / "evaluation.json"
            )
            write_json(temporary_prediction_path, prediction)
            write_json(temporary_evaluation_path, evaluation)
            final_sample_directory = (
                report_directory.resolve() / "samples" / sample_id
            )
            evaluation_metrics = require_mapping(
                evaluation.get("metrics"),
                f"evaluation.metrics for {sample_id}",
            )
            report_records.append({
                "sample_id": sample_id,
                "partition": partition_name,
                "split_group_id": record["split_group_id"],
                "expected_fault_type": record["target_class"],
                "predicted_fault_type": predicted_class,
                "classification_correct": (
                    predicted_class == record["target_class"]
                ),
                "exact_match": bool(evaluation_metrics["exact_match"]),
                "affected_prefix_correct": bool(
                    evaluation_metrics["affected_prefix_correct"]
                ),
                "artifacts": {
                    **{
                        name: artifact_reference(path)
                        for name, path in source_paths.items()
                    },
                    "prediction": reference_with_final_path(
                        temporary_prediction_path,
                        final_sample_directory / "prediction.json",
                    ),
                    "evaluation": reference_with_final_path(
                        temporary_evaluation_path,
                        final_sample_directory / "evaluation.json",
                    ),
                },
            })

        matrix_provenance = require_mapping(
            matrix.get("provenance"),
            "matrix.provenance",
        )
        campaign_reference = require_mapping(
            matrix_provenance.get("campaign_result"),
            "matrix.provenance.campaign_result",
        )
        campaign_path = Path(require_non_empty_string(
            campaign_reference.get("path"),
            "matrix.provenance.campaign_result.path",
        )).resolve()
        if sha256_file(campaign_path) != campaign_reference.get("sha256"):
            raise MLBaselineError("Campaign-result provenance drift detected.")
        split = require_mapping(
            require_mapping(
                matrix.get("dataset_binding"),
                "matrix.dataset_binding",
            ).get("split"),
            "matrix.dataset_binding.split",
        )
        split_manifest_path = Path(require_non_empty_string(
            split.get("manifest_path"),
            "matrix.dataset_binding.split.manifest_path",
        )).resolve()
        if sha256_file(split_manifest_path) != split.get("manifest_sha256"):
            raise MLBaselineError("Split-manifest provenance drift detected.")

        partition_group_ids = {
            name: list(
                require_mapping(
                    require_mapping(matrix.get("partitions"), "matrix.partitions").get(name),
                    f"matrix.partitions.{name}",
                )["group_ids"]
            )
            for name in ("train", "validation", "test")
        }
        result = build_method_evaluation_result(
            result_id=DEFAULT_RESULT_ID,
            method={
                "method_id": "machine_learning",
                "family": "machine_learning",
                "implementation_id": DEFAULT_PIPELINE_ID,
                "trained": True,
                "selection_statement": (
                    f"{candidate_id} was fitted on train only and selected "
                    "only by frozen validation macro F1, accuracy, "
                    "complexity rank, and candidate ID; G02 test was "
                    "opened only after pipeline hash verification."
                ),
            },
            dataset_binding=dataset_binding_from_matrix(matrix),
            provenance={
                "campaign_result": artifact_reference(campaign_path),
                "split_manifest": artifact_reference(split_manifest_path),
                "feature_matrix": artifact_reference(matrix_path.resolve()),
                "selection_result": artifact_reference(selection_path.resolve()),
                "model_artifact": artifact_reference(model_path.resolve()),
                "input_record_count": len(report_records),
                "artifact_reference_count": len(report_records) * 5,
            },
            records=report_records,
            partition_group_ids=partition_group_ids,
        )
        temporary_report_path = temporary_directory / REPORT_FILE_NAME
        write_json(temporary_report_path, result)
        validate_method_evaluation_result(result)
        validate_method_schema(result, method_schema_path)
        temporary_directory.replace(report_directory.resolve())
    except Exception:
        if temporary_directory.exists():
            shutil.rmtree(temporary_directory)
        raise

    validate_ml_baseline_report(
        report_path=final_report_path,
        matrix_path=matrix_path,
        selection_path=selection_path,
        model_path=model_path,
        method_schema_path=method_schema_path,
        expected_matrix_sha256=expected_matrix_sha256,
        expected_selection_sha256=expected_selection_sha256,
        expected_model_sha256=expected_model_sha256,
    )
    return read_json(final_report_path)


def validate_ml_baseline_report(
    *,
    report_path: Path,
    matrix_path: Path,
    selection_path: Path,
    model_path: Path,
    method_schema_path: Path,
    expected_matrix_sha256: str = EXPECTED_MATRIX_SHA256,
    expected_selection_sha256: str,
    expected_model_sha256: str,
) -> dict[str, Any]:
    if sha256_file(matrix_path.resolve()) != expected_matrix_sha256:
        raise MLBaselineError("Report matrix binding drift detected.")
    if sha256_file(selection_path.resolve()) != expected_selection_sha256:
        raise MLBaselineError("Report selection binding drift detected.")
    if sha256_file(model_path.resolve()) != expected_model_sha256:
        raise MLBaselineError("Report model binding drift detected.")

    result = read_json(report_path.resolve())
    validate_method_evaluation_result(result)
    validate_method_schema(result, method_schema_path)
    method = require_mapping(result.get("method"), "report.method")
    if (
        method.get("method_id") != "machine_learning"
        or method.get("implementation_id") != DEFAULT_PIPELINE_ID
        or method.get("trained") is not True
    ):
        raise MLBaselineError("ML Method Evaluation method binding is invalid.")
    provenance = require_mapping(result.get("provenance"), "report.provenance")
    expected_method_artifacts = {
        "feature_matrix": (matrix_path.resolve(), expected_matrix_sha256),
        "selection_result": (
            selection_path.resolve(),
            expected_selection_sha256,
        ),
        "model_artifact": (model_path.resolve(), expected_model_sha256),
    }
    for name, (path, digest) in expected_method_artifacts.items():
        reference = require_mapping(
            provenance.get(name),
            f"report.provenance.{name}",
        )
        if reference.get("path") != str(path) or reference.get("sha256") != digest:
            raise MLBaselineError(f"Invalid report provenance binding: {name}.")

    records = result.get("records")
    if not isinstance(records, list) or len(records) != 30:
        raise MLBaselineError("ML report must contain exactly 30 records.")
    artifact_count = 0
    for value in records:
        record = require_mapping(value, "report.record")
        artifacts = require_mapping(record.get("artifacts"), "report.record.artifacts")
        for artifact_name in (
            "experiment_manifest",
            "ground_truth",
            "evidence",
            "prediction",
            "evaluation",
        ):
            reference = require_mapping(
                artifacts.get(artifact_name),
                f"report.record.artifacts.{artifact_name}",
            )
            path = Path(require_non_empty_string(
                reference.get("path"),
                f"{artifact_name}.path",
            )).resolve()
            if sha256_file(path) != reference.get("sha256"):
                raise MLBaselineError(
                    f"Artifact-reference hash mismatch: {artifact_name}."
                )
            artifact_count += 1

        prediction = read_json(Path(artifacts["prediction"]["path"]))
        if prediction.get("sample_id") != record.get("sample_id"):
            raise MLBaselineError("Prediction sample identity mismatch.")
        evidence = require_mapping(
            prediction.get("supporting_evidence"),
            "prediction.supporting_evidence",
        )
        observations = evidence.get("observations")
        if not isinstance(observations, list) or len(observations) != 7:
            raise MLBaselineError("ML prediction lacks seven evidence states.")
        explanation = require_mapping(
            prediction.get("model_explanation"),
            "prediction.model_explanation",
        )
        if explanation.get("explanation_type") not in {
            "linear_feature_contributions",
            "decision_path",
        }:
            raise MLBaselineError("ML prediction explanation is invalid.")
        if record.get("expected_fault_type") != "no_fault" and record.get(
            "exact_match"
        ) is not False:
            raise MLBaselineError(
                "A class-only ML fault prediction cannot be a full exact match."
            )

    if artifact_count != 150:
        raise MLBaselineError("ML report must verify 150 artifact references.")
    partitions = require_mapping(result.get("partitions"), "report.partitions")
    expected_rows = {"train": 18, "validation": 6, "test": 6}
    for name, row_count in expected_rows.items():
        partition = require_mapping(partitions.get(name), f"report.partitions.{name}")
        if partition.get("row_count") != row_count:
            raise MLBaselineError(f"Unexpected report row count for {name}.")
    if require_mapping(
        result.get("evaluation_policy"),
        "report.evaluation_policy",
    ).get("test_use") != "report_only":
        raise MLBaselineError("G02 test is not report_only.")
    return result


def selection_summary(
    selection: Mapping[str, Any],
    pipeline_directory: Path,
) -> dict[str, Any]:
    selected = require_mapping(
        selection.get("selected_candidate"),
        "selection.selected_candidate",
    )
    identity = require_mapping(selected.get("candidate"), "selected.candidate")
    selection_path = pipeline_directory.resolve() / SELECTION_FILE_NAME
    model_path = pipeline_directory.resolve() / MODEL_FILE_NAME
    return {
        "status": selection["status"],
        "selection_id": selection["selection_id"],
        "pipeline_id": selection["pipeline_id"],
        "selected_candidate": identity["candidate_id"],
        "selected_family": identity["family"],
        "validation_macro_f1": selected["validation_macro_f1"],
        "validation_accuracy": selected["validation_accuracy"],
        "candidate_count": len(selection["candidate_results"]),
        "fit_partition": "train",
        "selection_partition": "validation",
        "test_predictions_or_metrics": "ABSENT",
        "selection_path": str(selection_path),
        "selection_sha256": sha256_file(selection_path),
        "model_path": str(model_path),
        "model_sha256": sha256_file(model_path),
    }


def report_summary(result: Mapping[str, Any], report_path: Path) -> dict[str, Any]:
    partitions = require_mapping(result.get("partitions"), "report.partitions")
    return {
        "status": result["status"],
        "result_id": result["result_id"],
        "rows": result["overall"]["row_count"],
        "partitions": {
            name: {
                "rows": partitions[name]["row_count"],
                "groups": partitions[name]["group_count"],
                "accuracy": partitions[name]["metrics"]["classification"]["accuracy"],
                "macro_f1": partitions[name]["metrics"]["classification"]["macro"]["f1"],
                "exact_match_rate": partitions[name]["metrics"]["diagnostic_checks"]["exact_diagnosis_match"]["rate"],
                "affected_prefix_rate": partitions[name]["metrics"]["diagnostic_checks"]["affected_prefix_fault_only"]["rate"],
            }
            for name in ("train", "validation", "test")
        },
        "test_use": result["evaluation_policy"]["test_use"],
        "report_path": str(report_path.resolve()),
        "report_sha256": sha256_file(report_path.resolve()),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train, freeze, and report the leakage-safe P4-R1 ML baseline."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--matrix", type=Path, required=True)
    common.add_argument(
        "--expected-matrix-sha256",
        default=EXPECTED_MATRIX_SHA256,
    )
    common.add_argument(
        "--selection-schema",
        type=Path,
        default=Path("schemas/ml_pipeline_selection_v1.schema.json"),
    )

    select_parser = subparsers.add_parser("select", parents=[common])
    select_parser.add_argument("--pipeline-directory", type=Path, required=True)

    verify_selection = subparsers.add_parser(
        "verify-selection",
        parents=[common],
    )
    verify_selection.add_argument("--selection", type=Path, required=True)
    verify_selection.add_argument("--model", type=Path, required=True)
    verify_selection.add_argument(
        "--expected-selection-sha256",
        required=True,
        choices=(ACCEPTED_SELECTION_SHA256,),
    )
    verify_selection.add_argument(
        "--expected-model-sha256",
        required=True,
        choices=(ACCEPTED_MODEL_SHA256,),
    )

    report_parser = subparsers.add_parser("report", parents=[common])
    report_parser.add_argument("--selection", type=Path, required=True)
    report_parser.add_argument("--model", type=Path, required=True)
    report_parser.add_argument(
        "--expected-selection-sha256",
        required=True,
        choices=(ACCEPTED_SELECTION_SHA256,),
    )
    report_parser.add_argument(
        "--expected-model-sha256",
        required=True,
        choices=(ACCEPTED_MODEL_SHA256,),
    )
    report_parser.add_argument("--experiments-root", type=Path, required=True)
    report_parser.add_argument("--report-directory", type=Path, required=True)
    report_parser.add_argument(
        "--method-schema",
        type=Path,
        default=Path("schemas/method_evaluation_result_v1.schema.json"),
    )

    verify_report = subparsers.add_parser("verify-report", parents=[common])
    verify_report.add_argument("--selection", type=Path, required=True)
    verify_report.add_argument("--model", type=Path, required=True)
    verify_report.add_argument("--expected-selection-sha256", required=True)
    verify_report.add_argument("--expected-model-sha256", required=True)
    verify_report.add_argument("--report", type=Path, required=True)
    verify_report.add_argument(
        "--method-schema",
        type=Path,
        default=Path("schemas/method_evaluation_result_v1.schema.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "select":
            selection = train_select_and_freeze(
                matrix_path=arguments.matrix,
                pipeline_directory=arguments.pipeline_directory,
                selection_schema_path=arguments.selection_schema,
                expected_matrix_sha256=arguments.expected_matrix_sha256,
            )
            summary = selection_summary(selection, arguments.pipeline_directory)
        elif arguments.command == "verify-selection":
            verified = validate_frozen_pipeline(
                matrix_path=arguments.matrix,
                selection_path=arguments.selection,
                model_path=arguments.model,
                selection_schema_path=arguments.selection_schema,
                expected_matrix_sha256=arguments.expected_matrix_sha256,
                expected_selection_sha256=arguments.expected_selection_sha256,
                expected_model_sha256=arguments.expected_model_sha256,
            )
            summary = {
                "status": "PIPELINE_FROZEN_VERIFIED",
                "selection_sha256": verified["selection_sha256"],
                "model_sha256": verified["model_sha256"],
                "test_predictions_or_metrics": "ABSENT",
            }
        elif arguments.command == "report":
            result = build_ml_baseline_report(
                matrix_path=arguments.matrix,
                selection_path=arguments.selection,
                model_path=arguments.model,
                selection_schema_path=arguments.selection_schema,
                method_schema_path=arguments.method_schema,
                experiments_root=arguments.experiments_root,
                report_directory=arguments.report_directory,
                expected_matrix_sha256=arguments.expected_matrix_sha256,
                expected_selection_sha256=arguments.expected_selection_sha256,
                expected_model_sha256=arguments.expected_model_sha256,
            )
            summary = report_summary(
                result,
                arguments.report_directory / REPORT_FILE_NAME,
            )
        else:
            result = validate_ml_baseline_report(
                report_path=arguments.report,
                matrix_path=arguments.matrix,
                selection_path=arguments.selection,
                model_path=arguments.model,
                method_schema_path=arguments.method_schema,
                expected_matrix_sha256=arguments.expected_matrix_sha256,
                expected_selection_sha256=arguments.expected_selection_sha256,
                expected_model_sha256=arguments.expected_model_sha256,
            )
            summary = report_summary(result, arguments.report)
            summary["verification"] = "PASS"
    except (MLBaselineError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"[ERROR] {error}")
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
