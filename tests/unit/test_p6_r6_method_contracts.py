from __future__ import annotations

import pytest

from src.phase6.contracts import (
    MASK_ORDER,
    Phase6MethodContractError,
    apply_method_input_mask,
    validate_method_input,
    validate_prediction,
    validate_target,
)
from tests.unit.p6_r6_fixtures import clone, method_input, target_for


def test_clean_method_input_contract() -> None:
    validate_method_input(method_input())


@pytest.mark.parametrize("mask_id", MASK_ORDER)
def test_each_frozen_mask_is_non_destructive(mask_id: str) -> None:
    clean = method_input("wrong_next_hop")
    masked = apply_method_input_mask(clean, mask_id)

    assert clean["mask_id"] is None
    assert masked["mask_id"] == mask_id
    assert masked["sample_id"] == clean["sample_id"]
    assert masked["provenance"] == clean["provenance"]
    assert any(
        state == "masked_missing" for state in masked["availability"].values()
    )


def test_route_mask_preserves_structural_unavailability() -> None:
    clean = method_input("missing_static_route")
    masked = apply_method_input_mask(clean, "mask_route_family")

    assert masked["availability"]["route_to_destination_exists_on_observer"] == (
        "masked_missing"
    )
    assert masked["availability"]["route_next_hop_matches_expected"] == (
        "structurally_unavailable"
    )


def test_rejects_unknown_mask() -> None:
    with pytest.raises(Phase6MethodContractError, match="frozen ID"):
        apply_method_input_mask(method_input(), "mask_unknown")


def test_rejects_clean_input_with_mask_identity() -> None:
    value = method_input()
    value["mask_id"] = "mask_policy_state"

    with pytest.raises(Phase6MethodContractError, match="Masked input identity"):
        validate_method_input(value)


def test_rejects_value_under_masked_missing() -> None:
    value = method_input()
    value["availability"]["flow_blocked_by_policy"] = "masked_missing"

    with pytest.raises(Phase6MethodContractError, match="contains a value"):
        validate_method_input(value)


def test_target_contract_keeps_truth_separate() -> None:
    value = method_input("acl_block")
    target = target_for(value, "acl_block")

    validate_method_input(value)
    validate_target(target)
    assert "labels" not in value
    assert target["labels"]["fault_type"] == "acl_block"


def test_rejects_target_with_unknown_class() -> None:
    value = method_input()
    target = target_for(value, "no_fault")
    target["labels"]["fault_type"] = "ospf_failure"

    with pytest.raises(Phase6MethodContractError, match="not a Phase 6 class"):
        validate_target(target)


def test_prediction_contract_rejects_unresolved_class() -> None:
    prediction = {
        "schema_version": 1,
        "input_id": "sample",
        "sample_id": "sample",
        "method_id": "rule_based_p6_v1",
        "status": "INSUFFICIENT_EVIDENCE",
        "predicted_fault_type": "no_fault",
        "confidence": None,
        "diagnosis": None,
        "reason": "missing",
    }

    with pytest.raises(Phase6MethodContractError, match="Unresolved prediction"):
        validate_prediction(prediction)


def test_input_copy_drift_is_detected() -> None:
    value = clone(method_input())
    value["features"].pop("flow_blocked_by_policy")

    with pytest.raises(Phase6MethodContractError, match="whitelist"):
        validate_method_input(value)
