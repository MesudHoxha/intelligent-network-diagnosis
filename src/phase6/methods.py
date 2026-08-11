from __future__ import annotations

import copy
from collections import Counter
from typing import Any, Mapping, Sequence

from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from src.campaign.phase6_plan import CLASS_ORDER
from src.phase6.contracts import (
    FEATURE_ORDER,
    MASK_ORDER,
    Phase6MethodContractError,
    validate_method_input,
    validate_prediction,
    validate_target,
)
from src.planning.fault_taxonomy import EXPECTED_SIGNATURES


MODEL_RANDOM_SEED = 20260811
ENCODED_FEATURE_NAMES = tuple(
    output
    for feature in FEATURE_ORDER
    for output in (f"{feature}__available", f"{feature}__true")
)
TRISTATE_ENCODING = {
    "true": (1, 1),
    "false": (1, 0),
    "unavailable": (0, 0),
}
CATEGORIES = {
    "no_fault": None,
    "missing_static_route": "routing",
    "wrong_next_hop": "routing",
    "wrong_default_gateway": "routing",
    "interface_down": "link",
    "acl_block": "access_control",
}


def encode_features(method_input: Mapping[str, Any]) -> list[int]:
    validate_method_input(method_input)
    vector: list[int] = []
    for feature in FEATURE_ORDER:
        vector.extend(TRISTATE_ENCODING[method_input["features"][feature]])
    return vector


def _diagnosis(
    method_input: Mapping[str, Any], fault_type: str
) -> dict[str, Any]:
    if fault_type == "no_fault":
        return {
            "fault_type": "no_fault",
            "fault_category": None,
            "fault_location": None,
            "affected_prefix": None,
        }
    location = (
        method_input["source_node"]
        if fault_type == "wrong_default_gateway"
        else method_input["route_observer_node"]
    )
    return {
        "fault_type": fault_type,
        "fault_category": CATEGORIES[fault_type],
        "fault_location": location,
        "affected_prefix": method_input["destination_prefix"],
    }


def _resolved_prediction(
    method_input: Mapping[str, Any],
    *,
    method_id: str,
    fault_type: str,
    confidence: float,
    reason: str,
) -> dict[str, Any]:
    prediction = {
        "schema_version": 1,
        "input_id": method_input["input_id"],
        "sample_id": method_input["sample_id"],
        "method_id": method_id,
        "status": "RESOLVED",
        "predicted_fault_type": fault_type,
        "confidence": float(confidence),
        "diagnosis": _diagnosis(method_input, fault_type),
        "reason": reason,
    }
    validate_prediction(prediction)
    return prediction


def _unresolved_prediction(
    method_input: Mapping[str, Any],
    *,
    method_id: str,
    status: str,
    reason: str,
) -> dict[str, Any]:
    prediction = {
        "schema_version": 1,
        "input_id": method_input["input_id"],
        "sample_id": method_input["sample_id"],
        "method_id": method_id,
        "status": status,
        "predicted_fault_type": None,
        "confidence": None,
        "diagnosis": None,
        "reason": reason,
    }
    validate_prediction(prediction)
    return prediction


def rule_prediction(method_input: Mapping[str, Any]) -> dict[str, Any]:
    validate_method_input(method_input)
    unavailable = [
        name
        for name in FEATURE_ORDER
        if method_input["availability"][name]
        in {"collection_unavailable", "masked_missing"}
    ]
    if unavailable:
        return _unresolved_prediction(
            method_input,
            method_id="rule_based_p6_v1",
            status="INSUFFICIENT_EVIDENCE",
            reason=(
                "Definitive rule matching is blocked by unavailable features: "
                + ",".join(unavailable)
            ),
        )
    matches = [
        fault_type
        for fault_type in CLASS_ORDER
        if tuple(method_input["features"][name] for name in FEATURE_ORDER)
        == tuple(EXPECTED_SIGNATURES[fault_type])
    ]
    if len(matches) != 1:
        return _unresolved_prediction(
            method_input,
            method_id="rule_based_p6_v1",
            status="NO_RULE_MATCH",
            reason="The ten-feature vector matches no unique frozen signature.",
        )
    return _resolved_prediction(
        method_input,
        method_id="rule_based_p6_v1",
        fault_type=matches[0],
        confidence=1.0,
        reason="Exact deterministic Phase 6 signature match.",
    )


def ml_prediction(
    method_input: Mapping[str, Any], estimator: object
) -> dict[str, Any]:
    vector = [encode_features(method_input)]
    predicted_values = estimator.predict(vector)  # type: ignore[attr-defined]
    probabilities = estimator.predict_proba(vector)  # type: ignore[attr-defined]
    classes = list(estimator.classes_)  # type: ignore[attr-defined]
    fault_type = str(predicted_values[0])
    if fault_type not in CLASS_ORDER or fault_type not in classes:
        raise Phase6MethodContractError("Estimator returned an invalid class.")
    confidence = float(probabilities[0][classes.index(fault_type)])
    return _resolved_prediction(
        method_input,
        method_id="machine_learning_p6_v1",
        fault_type=fault_type,
        confidence=confidence,
        reason="Frozen six-class estimator argmax prediction.",
    )


def candidate_models() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "logreg_l2_c0_1",
            "family": "multinomial_logistic_regression",
            "complexity_rank": 1,
            "parameters": {"C": 0.1, "max_iter": 2000},
        },
        {
            "candidate_id": "logreg_l2_c1",
            "family": "multinomial_logistic_regression",
            "complexity_rank": 2,
            "parameters": {"C": 1.0, "max_iter": 2000},
        },
        {
            "candidate_id": "logreg_l2_c10",
            "family": "multinomial_logistic_regression",
            "complexity_rank": 3,
            "parameters": {"C": 10.0, "max_iter": 2000},
        },
        {
            "candidate_id": "tree_depth2_leaf1",
            "family": "decision_tree",
            "complexity_rank": 4,
            "parameters": {"max_depth": 2, "min_samples_leaf": 1},
        },
        {
            "candidate_id": "tree_depth3_leaf1",
            "family": "decision_tree",
            "complexity_rank": 5,
            "parameters": {"max_depth": 3, "min_samples_leaf": 1},
        },
        {
            "candidate_id": "tree_depth4_leaf2",
            "family": "decision_tree",
            "complexity_rank": 6,
            "parameters": {"max_depth": 4, "min_samples_leaf": 2},
        },
    ]


def instantiate_candidate(candidate: Mapping[str, Any]) -> object:
    family = candidate.get("family")
    parameters = candidate.get("parameters")
    if not isinstance(parameters, Mapping):
        raise Phase6MethodContractError("Candidate parameters are invalid.")
    if family == "multinomial_logistic_regression":
        return LogisticRegression(
            C=float(parameters["C"]),
            max_iter=int(parameters["max_iter"]),
            solver="lbfgs",
            random_state=MODEL_RANDOM_SEED,
        )
    if family == "decision_tree":
        return DecisionTreeClassifier(
            criterion="gini",
            max_depth=int(parameters["max_depth"]),
            min_samples_leaf=int(parameters["min_samples_leaf"]),
            splitter="best",
            random_state=MODEL_RANDOM_SEED,
        )
    raise Phase6MethodContractError(f"Unsupported ML family: {family!r}")


def _target_index(
    targets: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for target in targets:
        validate_target(target)
        input_id = str(target["input_id"])
        if input_id in indexed:
            raise Phase6MethodContractError(f"Duplicate target: {input_id}")
        indexed[input_id] = target
    return indexed


def predictor_arrays(
    inputs: Sequence[Mapping[str, Any]],
    targets: Sequence[Mapping[str, Any]],
) -> tuple[list[list[int]], list[str]]:
    target_by_id = _target_index(targets)
    if {str(item["input_id"]) for item in inputs} != set(target_by_id):
        raise Phase6MethodContractError("Predictor inputs and targets differ.")
    vectors: list[list[int]] = []
    labels: list[str] = []
    for method_input in inputs:
        vectors.append(encode_features(method_input))
        labels.append(str(target_by_id[str(method_input["input_id"])]["labels"]["fault_type"]))
    return vectors, labels


def _safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def compute_metrics(
    inputs: Sequence[Mapping[str, Any]],
    targets: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    input_by_id = {str(item["input_id"]): item for item in inputs}
    target_by_id = _target_index(targets)
    prediction_by_id: dict[str, Mapping[str, Any]] = {}
    for prediction in predictions:
        validate_prediction(prediction)
        input_id = str(prediction["input_id"])
        if input_id in prediction_by_id:
            raise Phase6MethodContractError(f"Duplicate prediction: {input_id}")
        prediction_by_id[input_id] = prediction
    if set(input_by_id) != set(target_by_id) or set(input_by_id) != set(
        prediction_by_id
    ):
        raise Phase6MethodContractError("Evaluation sample sets differ.")

    label_index = {label: index for index, label in enumerate(CLASS_ORDER)}
    matrix = [[0 for _ in CLASS_ORDER] for _ in CLASS_ORDER]
    unresolved_by_class = {label: 0 for label in CLASS_ORDER}
    statuses: Counter[str] = Counter()
    correct = 0
    exact = 0
    prefix_applicable = 0
    prefix_correct = 0
    records: list[dict[str, Any]] = []
    for input_id in sorted(input_by_id):
        method_input = input_by_id[input_id]
        target = target_by_id[input_id]
        prediction = prediction_by_id[input_id]
        expected = str(target["labels"]["fault_type"])
        predicted = prediction["predicted_fault_type"]
        status = str(prediction["status"])
        statuses[status] += 1
        resolved = status == "RESOLVED"
        class_correct = resolved and predicted == expected
        if class_correct:
            correct += 1
        if resolved:
            matrix[label_index[expected]][label_index[str(predicted)]] += 1
        else:
            unresolved_by_class[expected] += 1
        diagnosis = prediction["diagnosis"]
        exact_match = bool(resolved and diagnosis == target["labels"])
        if exact_match:
            exact += 1
        affected_prefix_correct = None
        if expected != "no_fault":
            prefix_applicable += 1
            affected_prefix_correct = bool(
                resolved
                and isinstance(diagnosis, Mapping)
                and diagnosis.get("affected_prefix")
                == target["labels"]["affected_prefix"]
            )
            if affected_prefix_correct:
                prefix_correct += 1
        records.append(
            {
                "input_id": input_id,
                "sample_id": method_input["sample_id"],
                "split_group_id": method_input["split_group_id"],
                "mask_id": method_input["mask_id"],
                "expected_fault_type": expected,
                "predicted_fault_type": predicted,
                "status": status,
                "class_correct": class_correct,
                "exact_match": exact_match,
                "affected_prefix_correct": affected_prefix_correct,
            }
        )

    per_class: dict[str, Any] = {}
    for index, label in enumerate(CLASS_ORDER):
        true_positive = matrix[index][index]
        false_positive = sum(
            matrix[row][index] for row in range(len(CLASS_ORDER)) if row != index
        )
        support = sum(matrix[index]) + unresolved_by_class[label]
        false_negative = support - true_positive
        precision = _safe_rate(true_positive, true_positive + false_positive)
        recall = _safe_rate(true_positive, true_positive + false_negative)
        f1 = _safe_rate(2 * precision * recall, precision + recall)
        per_class[label] = {
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    sample_count = len(records)
    resolved_count = statuses["RESOLVED"]
    macro = {
        metric: sum(per_class[label][metric] for label in CLASS_ORDER)
        / len(CLASS_ORDER)
        for metric in ("precision", "recall", "f1")
    }
    return {
        "sample_count": sample_count,
        "resolved_count": resolved_count,
        "coverage": _safe_rate(resolved_count, sample_count),
        "accuracy": _safe_rate(correct, sample_count),
        "macro": macro,
        "per_class": per_class,
        "confusion_matrix": {
            "actual_labels": list(CLASS_ORDER),
            "predicted_labels": list(CLASS_ORDER),
            "values": matrix,
            "unresolved_by_actual_class": unresolved_by_class,
        },
        "status_counts": dict(sorted(statuses.items())),
        "abstention_rate": _safe_rate(statuses["ABSTAINED"], sample_count),
        "insufficient_evidence_rate": _safe_rate(
            statuses["INSUFFICIENT_EVIDENCE"], sample_count
        ),
        "exact_diagnosis": {
            "correct_count": exact,
            "rate": _safe_rate(exact, sample_count),
        },
        "affected_prefix_fault_only": {
            "applicable_count": prefix_applicable,
            "correct_count": prefix_correct,
            "rate": _safe_rate(prefix_correct, prefix_applicable),
        },
        "records": records,
    }


def _subset(
    inputs: Sequence[Mapping[str, Any]],
    targets: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, Any]],
    *,
    predicate: Any,
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    ids = {str(item["input_id"]) for item in inputs if predicate(item)}
    return (
        [item for item in inputs if str(item["input_id"]) in ids],
        [item for item in targets if str(item["input_id"]) in ids],
        [item for item in predictions if str(item["input_id"]) in ids],
    )


def scoped_metrics(
    inputs: Sequence[Mapping[str, Any]],
    targets: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    scopes: dict[str, Any] = {
        "overall": compute_metrics(inputs, targets, predictions)
    }
    clean = _subset(
        inputs, targets, predictions, predicate=lambda item: item["mask_id"] is None
    )
    masked = _subset(
        inputs, targets, predictions, predicate=lambda item: item["mask_id"] is not None
    )
    scopes["clean"] = compute_metrics(*clean)
    scopes["masked_overall"] = compute_metrics(*masked) if masked[0] else None
    scopes["by_mask"] = {}
    for mask_id in MASK_ORDER:
        values = _subset(
            inputs,
            targets,
            predictions,
            predicate=lambda item, expected=mask_id: item["mask_id"] == expected,
        )
        scopes["by_mask"][mask_id] = compute_metrics(*values) if values[0] else None
    scopes["by_context"] = {}
    for group_id in sorted({str(item["split_group_id"]) for item in inputs}):
        values = _subset(
            inputs,
            targets,
            predictions,
            predicate=lambda item, expected=group_id: item["split_group_id"] == expected,
        )
        scopes["by_context"][group_id] = compute_metrics(*values)
    scopes["by_class"] = {}
    target_by_id = _target_index(targets)
    for fault_type in CLASS_ORDER:
        values = _subset(
            inputs,
            targets,
            predictions,
            predicate=lambda item, expected=fault_type: target_by_id[str(item["input_id"])][
                "labels"
            ]["fault_type"]
            == expected,
        )
        scopes["by_class"][fault_type] = compute_metrics(*values)
    return scopes


def select_ml_candidate(
    *,
    train_inputs: Sequence[Mapping[str, Any]],
    train_targets: Sequence[Mapping[str, Any]],
    validation_inputs: Sequence[Mapping[str, Any]],
    validation_targets: Sequence[Mapping[str, Any]],
) -> tuple[object, dict[str, Any]]:
    if any(item["mask_id"] is not None for item in train_inputs):
        raise Phase6MethodContractError("ML fitting cannot use masked train inputs.")
    x_train, y_train = predictor_arrays(train_inputs, train_targets)
    candidate_results: list[dict[str, Any]] = []
    estimators: dict[str, object] = {}
    for candidate in candidate_models():
        estimator = instantiate_candidate(candidate)
        estimator.fit(x_train, y_train)  # type: ignore[attr-defined]
        predictions = [ml_prediction(item, estimator) for item in validation_inputs]
        metrics = scoped_metrics(validation_inputs, validation_targets, predictions)
        result = {
            "candidate": copy.deepcopy(candidate),
            "validation_clean": metrics["clean"],
            "validation_masked": metrics["masked_overall"],
            "validation_overall": metrics["overall"],
        }
        candidate_results.append(result)
        estimators[str(candidate["candidate_id"])] = estimator

    def sort_key(result: Mapping[str, Any]) -> tuple[Any, ...]:
        candidate = result["candidate"]
        return (
            -float(result["validation_clean"]["macro"]["f1"]),
            -float(result["validation_masked"]["macro"]["f1"]),
            -float(result["validation_masked"]["accuracy"]),
            int(candidate["complexity_rank"]),
            str(candidate["candidate_id"]),
        )

    ranked = sorted(candidate_results, key=sort_key)
    selected = ranked[0]["candidate"]
    selection = {
        "schema_version": 1,
        "selection_id": "p6_r6_ml_selection_v1",
        "method_id": "machine_learning_p6_v1",
        "class_order": list(CLASS_ORDER),
        "raw_feature_names": list(FEATURE_ORDER),
        "encoded_feature_names": list(ENCODED_FEATURE_NAMES),
        "fit_partition": "train",
        "fit_masked_inputs": 0,
        "selection_partition": "validation",
        "selection_order": [
            "clean_macro_f1_desc",
            "masked_macro_f1_desc",
            "masked_accuracy_desc",
            "complexity_rank_asc",
            "candidate_id_asc",
        ],
        "model_random_seed": MODEL_RANDOM_SEED,
        "candidate_results": candidate_results,
        "selected_candidate": copy.deepcopy(selected),
        "test_predictions_or_metrics": "ABSENT",
    }
    return estimators[str(selected["candidate_id"])], selection


def policy_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "rule_then_ml_fallback_v1",
            "mode": "rule_then_ml",
            "confidence_threshold": None,
            "complexity_rank": 1,
        },
        {
            "candidate_id": "guarded_ml_fallback_p060_v1",
            "mode": "guarded_ml_fallback",
            "confidence_threshold": 0.60,
            "complexity_rank": 2,
        },
        {
            "candidate_id": "guarded_ml_fallback_p075_v1",
            "mode": "guarded_ml_fallback",
            "confidence_threshold": 0.75,
            "complexity_rank": 3,
        },
        {
            "candidate_id": "guarded_ml_fallback_p090_v1",
            "mode": "guarded_ml_fallback",
            "confidence_threshold": 0.90,
            "complexity_rank": 4,
        },
        {
            "candidate_id": "consensus_abstain_v1",
            "mode": "consensus_abstain",
            "confidence_threshold": None,
            "complexity_rank": 5,
        },
    ]


def hybrid_prediction(
    method_input: Mapping[str, Any],
    rule: Mapping[str, Any],
    ml: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    validate_method_input(method_input)
    validate_prediction(rule)
    validate_prediction(ml)
    if rule["input_id"] != method_input["input_id"] or ml["input_id"] != method_input[
        "input_id"
    ]:
        raise Phase6MethodContractError("Hybrid source prediction binding drifted.")
    if rule["method_id"] != "rule_based_p6_v1" or ml["method_id"] != (
        "machine_learning_p6_v1"
    ):
        raise Phase6MethodContractError("Hybrid source method identity drifted.")
    mode = policy.get("mode")
    if rule["status"] == "RESOLVED":
        if mode == "consensus_abstain" and rule["predicted_fault_type"] != ml[
            "predicted_fault_type"
        ]:
            return _unresolved_prediction(
                method_input,
                method_id="hybrid_p6_v1",
                status="ABSTAINED",
                reason="Rule and ML predictions disagree under consensus policy.",
            )
        return _resolved_prediction(
            method_input,
            method_id="hybrid_p6_v1",
            fault_type=str(rule["predicted_fault_type"]),
            confidence=float(rule["confidence"]),
            reason="Frozen Hybrid policy accepted the deterministic rule output.",
        )
    if mode == "rule_then_ml":
        return _resolved_prediction(
            method_input,
            method_id="hybrid_p6_v1",
            fault_type=str(ml["predicted_fault_type"]),
            confidence=float(ml["confidence"]),
            reason="Rule lacked evidence; frozen policy used the ML fallback.",
        )
    if mode == "guarded_ml_fallback":
        threshold = float(policy["confidence_threshold"])
        if float(ml["confidence"]) >= threshold:
            return _resolved_prediction(
                method_input,
                method_id="hybrid_p6_v1",
                fault_type=str(ml["predicted_fault_type"]),
                confidence=float(ml["confidence"]),
                reason=f"ML fallback met the frozen confidence threshold {threshold:.2f}.",
            )
        return _unresolved_prediction(
            method_input,
            method_id="hybrid_p6_v1",
            status="ABSTAINED",
            reason=f"ML fallback was below the frozen threshold {threshold:.2f}.",
        )
    if mode == "consensus_abstain":
        return _unresolved_prediction(
            method_input,
            method_id="hybrid_p6_v1",
            status="ABSTAINED",
            reason="Rule lacked evidence under the frozen consensus policy.",
        )
    raise Phase6MethodContractError("Unknown Hybrid policy mode.")


def select_hybrid_policy(
    *,
    validation_inputs: Sequence[Mapping[str, Any]],
    validation_targets: Sequence[Mapping[str, Any]],
    estimator: object,
) -> dict[str, Any]:
    rules = {item["input_id"]: rule_prediction(item) for item in validation_inputs}
    mls = {item["input_id"]: ml_prediction(item, estimator) for item in validation_inputs}
    candidate_results: list[dict[str, Any]] = []
    for candidate in policy_candidates():
        predictions = [
            hybrid_prediction(
                item,
                rules[item["input_id"]],
                mls[item["input_id"]],
                candidate,
            )
            for item in validation_inputs
        ]
        metrics = scoped_metrics(validation_inputs, validation_targets, predictions)
        candidate_results.append(
            {
                "candidate": copy.deepcopy(candidate),
                "validation_overall": metrics["overall"],
                "validation_clean": metrics["clean"],
                "validation_masked": metrics["masked_overall"],
            }
        )

    def sort_key(result: Mapping[str, Any]) -> tuple[Any, ...]:
        candidate = result["candidate"]
        return (
            -float(result["validation_overall"]["macro"]["f1"]),
            -float(result["validation_clean"]["macro"]["f1"]),
            -float(result["validation_overall"]["coverage"]),
            int(candidate["complexity_rank"]),
            str(candidate["candidate_id"]),
        )

    ranked = sorted(candidate_results, key=sort_key)
    return {
        "schema_version": 1,
        "selection_id": "p6_r6_hybrid_selection_v1",
        "method_id": "hybrid_p6_v1",
        "selection_partition": "validation",
        "selection_order": [
            "overall_macro_f1_desc",
            "clean_macro_f1_desc",
            "overall_coverage_desc",
            "complexity_rank_asc",
            "candidate_id_asc",
        ],
        "candidate_results": candidate_results,
        "selected_policy": copy.deepcopy(ranked[0]["candidate"]),
        "test_predictions_or_metrics": "ABSENT",
    }


def build_method_predictions(
    inputs: Sequence[Mapping[str, Any]],
    *,
    estimator: object,
    hybrid_policy: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    rules = [rule_prediction(item) for item in inputs]
    mls = [ml_prediction(item, estimator) for item in inputs]
    rule_by_id = {item["input_id"]: item for item in rules}
    ml_by_id = {item["input_id"]: item for item in mls}
    hybrids = [
        hybrid_prediction(
            item,
            rule_by_id[item["input_id"]],
            ml_by_id[item["input_id"]],
            hybrid_policy,
        )
        for item in inputs
    ]
    return {
        "rule_based_p6_v1": rules,
        "machine_learning_p6_v1": mls,
        "hybrid_p6_v1": hybrids,
    }
