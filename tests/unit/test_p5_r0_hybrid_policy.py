from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.hybrid.policy import (
    DEFAULT_POLICY_PATH,
    DEFAULT_SCHEMA_PATH,
    HybridPolicyError,
    validate_against_schema,
    validate_frozen_semantics,
    verify_frozen_policy,
)


def load_policy() -> dict:
    return json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))


def test_canonical_policy_schema_and_semantics_are_frozen() -> None:
    result = verify_frozen_policy()

    assert result["policy_id"] == "p5_r0_hybrid_policy_v1"
    assert result["status"] == "HYBRID_POLICY_CANDIDATES_FROZEN_VERIFIED"
    assert result["candidate_ids"] == [
        "consensus_abstain_v1",
        "rule_guarded_fallback_v1",
    ]
    assert result["selection_partition"] == "validation"
    assert result["held_out_partition"] == "test"
    assert result["test_predictions_or_metrics"] == "ABSENT"
    assert len(result["policy_sha256"]) == 64


def test_schema_is_valid_draft_2020_12() -> None:
    schema = json.loads(DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(load_policy())


def test_policy_binds_all_five_accepted_baseline_hashes() -> None:
    result = verify_frozen_policy()

    assert result["baseline_hash_bindings"] == [
        "ml_feature_matrix",
        "ml_model",
        "ml_report",
        "ml_selection",
        "rule_baseline",
    ]


def test_schema_rejects_a_selected_candidate_in_p5_r0() -> None:
    policy = load_policy()
    policy["selection_protocol"]["selected_candidate"] = (
        "consensus_abstain_v1"
    )

    with pytest.raises(HybridPolicyError, match="Schema violation"):
        validate_against_schema(policy, DEFAULT_SCHEMA_PATH)


def test_semantics_reject_test_metrics_or_predictions() -> None:
    policy = load_policy()
    policy["test_predictions_or_metrics"] = "PRESENT"

    with pytest.raises(
        HybridPolicyError,
        match="must not contain test predictions or metrics",
    ):
        validate_frozen_semantics(policy)


def test_semantics_reject_changed_accepted_hash() -> None:
    policy = load_policy()
    policy["baseline_bindings"]["ml_model"]["sha256"] = "0" * 64

    with pytest.raises(
        HybridPolicyError,
        match="Accepted ml_model SHA-256 changed",
    ):
        validate_frozen_semantics(policy)


def test_semantics_reject_prediction_time_label_leakage() -> None:
    policy = load_policy()
    policy["prediction_time_contract"]["forbidden_inputs"].remove(
        "ground_truth"
    )

    with pytest.raises(
        HybridPolicyError,
        match="forbidden inputs changed",
    ):
        validate_frozen_semantics(policy)


def test_semantics_reject_candidate_reordering() -> None:
    policy = load_policy()
    policy["candidate_policies"].reverse()

    with pytest.raises(
        HybridPolicyError,
        match="candidate order changed",
    ):
        validate_frozen_semantics(policy)


def test_semantics_reject_test_as_selection_partition() -> None:
    policy = load_policy()
    policy["selection_protocol"]["selection_partition"] = "test"

    with pytest.raises(
        HybridPolicyError,
        match="must use validation only",
    ):
        validate_frozen_semantics(policy)


def test_semantics_reject_ml_localization_copying() -> None:
    policy = copy.deepcopy(load_policy())
    policy["output_contract"]["ml_location_or_prefix_copying"] = "ALLOWED"

    with pytest.raises(
        HybridPolicyError,
        match="localization copying must remain forbidden",
    ):
        validate_frozen_semantics(policy)


def test_p5_r0_module_has_no_prediction_or_metric_output_api() -> None:
    source = Path("src/hybrid/policy.py").read_text(encoding="utf-8")

    assert "def predict" not in source
    assert "def diagnose" not in source
    assert "def evaluate" not in source
    assert ".predict(" not in source
    assert "ground_truth.json" not in source
