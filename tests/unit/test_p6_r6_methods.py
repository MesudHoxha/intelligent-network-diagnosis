from __future__ import annotations

import pytest

from src.campaign.phase6_plan import CLASS_ORDER
from src.phase6.contracts import MASK_ORDER, apply_method_input_mask
from src.phase6.methods import (
    ENCODED_FEATURE_NAMES,
    build_method_predictions,
    compute_metrics,
    encode_features,
    hybrid_prediction,
    instantiate_candidate,
    ml_prediction,
    policy_candidates,
    rule_prediction,
    scoped_metrics,
    select_hybrid_policy,
    select_ml_candidate,
)
from tests.unit.p6_r6_fixtures import (
    method_input,
    six_class_inputs,
    target_for,
)


@pytest.mark.parametrize("fault_type", CLASS_ORDER)
def test_rule_resolves_each_clean_signature(fault_type: str) -> None:
    value = method_input(fault_type)
    prediction = rule_prediction(value)

    assert prediction["status"] == "RESOLVED"
    assert prediction["predicted_fault_type"] == fault_type
    assert prediction["diagnosis"] == target_for(value, fault_type)["labels"]


@pytest.mark.parametrize("mask_id", MASK_ORDER)
def test_rule_reports_insufficient_evidence_for_each_mask(mask_id: str) -> None:
    value = apply_method_input_mask(method_input("acl_block"), mask_id)
    prediction = rule_prediction(value)

    assert prediction["status"] == "INSUFFICIENT_EVIDENCE"
    assert prediction["predicted_fault_type"] is None


def test_encoding_is_exact_twenty_binary_columns() -> None:
    vector = encode_features(method_input("wrong_next_hop"))

    assert len(vector) == len(ENCODED_FEATURE_NAMES) == 20
    assert set(vector) <= {0, 1}


def test_structural_and_masked_unavailable_share_predictor_encoding() -> None:
    structural = method_input("missing_static_route")
    masked = apply_method_input_mask(structural, "mask_route_family")

    assert encode_features(masked)[6:12] == [0, 0, 0, 0, 0, 0]
    assert "mask_id" not in ENCODED_FEATURE_NAMES


def test_ml_candidate_fit_uses_clean_train_and_validation_only() -> None:
    train_inputs, train_targets = six_class_inputs(partition="train", repetitions=2)
    validation_clean, validation_targets_clean = six_class_inputs(
        partition="validation", repetitions=1
    )
    validation_inputs = list(validation_clean)
    validation_targets = list(validation_targets_clean)
    for value, target in zip(validation_clean, validation_targets_clean, strict=True):
        for mask_id in MASK_ORDER:
            masked = apply_method_input_mask(value, mask_id)
            validation_inputs.append(masked)
            validation_targets.append({**target, "input_id": masked["input_id"]})

    estimator, selection = select_ml_candidate(
        train_inputs=train_inputs,
        train_targets=train_targets,
        validation_inputs=validation_inputs,
        validation_targets=validation_targets,
    )

    assert selection["fit_partition"] == "train"
    assert selection["fit_masked_inputs"] == 0
    assert selection["selection_partition"] == "validation"
    assert selection["test_predictions_or_metrics"] == "ABSENT"
    assert len(selection["candidate_results"]) == 6
    assert set(str(value) for value in estimator.classes_) == set(CLASS_ORDER)


def test_ml_prediction_uses_argmax_and_role_based_localization() -> None:
    inputs, targets = six_class_inputs(partition="train", repetitions=2)
    candidate = {
        "family": "decision_tree",
        "parameters": {"max_depth": 4, "min_samples_leaf": 1},
    }
    estimator = instantiate_candidate(candidate)
    estimator.fit([encode_features(item) for item in inputs], [
        target["labels"]["fault_type"] for target in targets
    ])
    value = method_input("wrong_default_gateway")

    prediction = ml_prediction(value, estimator)

    assert prediction["status"] == "RESOLVED"
    assert prediction["diagnosis"]["fault_location"] in {"hosta", "r1"}
    assert 0.0 <= prediction["confidence"] <= 1.0


@pytest.mark.parametrize("policy", policy_candidates())
def test_every_hybrid_policy_is_bounded(policy: dict[str, object]) -> None:
    value = method_input("acl_block")
    rule = rule_prediction(value)
    inputs, targets = six_class_inputs(partition="train", repetitions=2)
    estimator = instantiate_candidate(
        {
            "family": "decision_tree",
            "parameters": {"max_depth": 4, "min_samples_leaf": 1},
        }
    )
    estimator.fit([encode_features(item) for item in inputs], [
        target["labels"]["fault_type"] for target in targets
    ])
    ml = ml_prediction(value, estimator)

    result = hybrid_prediction(value, rule, ml, policy)

    assert result["method_id"] == "hybrid_p6_v1"
    assert result["status"] in {"RESOLVED", "ABSTAINED"}


def test_hybrid_selection_uses_validation_masks_without_test() -> None:
    train_inputs, train_targets = six_class_inputs(partition="train", repetitions=2)
    validation_clean, validation_targets_clean = six_class_inputs(
        partition="validation", repetitions=1
    )
    validation_inputs = list(validation_clean)
    validation_targets = list(validation_targets_clean)
    for value, target in zip(validation_clean, validation_targets_clean, strict=True):
        for mask_id in MASK_ORDER:
            masked = apply_method_input_mask(value, mask_id)
            validation_inputs.append(masked)
            validation_targets.append({**target, "input_id": masked["input_id"]})
    estimator, _ = select_ml_candidate(
        train_inputs=train_inputs,
        train_targets=train_targets,
        validation_inputs=validation_inputs,
        validation_targets=validation_targets,
    )

    selection = select_hybrid_policy(
        validation_inputs=validation_inputs,
        validation_targets=validation_targets,
        estimator=estimator,
    )

    assert len(selection["candidate_results"]) == 5
    assert selection["selection_partition"] == "validation"
    assert selection["test_predictions_or_metrics"] == "ABSENT"


def test_metrics_keep_insufficient_outputs_in_denominator() -> None:
    clean = method_input("acl_block")
    masked = apply_method_input_mask(clean, "mask_policy_state")
    target = target_for(clean, "acl_block")
    masked_target = {**target, "input_id": masked["input_id"]}
    predictions = [rule_prediction(clean), rule_prediction(masked)]

    metrics = compute_metrics(
        [clean, masked], [target, masked_target], predictions
    )

    assert metrics["sample_count"] == 2
    assert metrics["resolved_count"] == 1
    assert metrics["coverage"] == 0.5
    assert metrics["accuracy"] == 0.5
    assert metrics["insufficient_evidence_rate"] == 0.5


def test_scoped_metrics_cover_masks_contexts_and_classes() -> None:
    clean_inputs, clean_targets = six_class_inputs(partition="validation")
    inputs = list(clean_inputs)
    targets = list(clean_targets)
    for value, target in zip(clean_inputs, clean_targets, strict=True):
        masked = apply_method_input_mask(value, "mask_policy_state")
        inputs.append(masked)
        targets.append({**target, "input_id": masked["input_id"]})
    train_inputs, train_targets = six_class_inputs(partition="train", repetitions=2)
    estimator = instantiate_candidate(
        {
            "family": "decision_tree",
            "parameters": {"max_depth": 4, "min_samples_leaf": 1},
        }
    )
    estimator.fit([encode_features(item) for item in train_inputs], [
        target["labels"]["fault_type"] for target in train_targets
    ])
    predictions = build_method_predictions(
        inputs,
        estimator=estimator,
        hybrid_policy=policy_candidates()[0],
    )["hybrid_p6_v1"]

    metrics = scoped_metrics(inputs, targets, predictions)

    assert metrics["overall"]["sample_count"] == 12
    assert metrics["clean"]["sample_count"] == 6
    assert metrics["by_mask"]["mask_policy_state"]["sample_count"] == 6
    assert set(metrics["by_class"]) == set(CLASS_ORDER)
