from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.planning.fault_taxonomy import (
    CLASS_ORDER,
    FEATURE_ORDER,
    FaultTaxonomyPlanError,
    sha256_file,
    validate_fault_taxonomy_plan,
    validate_plan_files,
)


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = (
    ROOT
    / "plans"
    / "taxonomies"
    / "P6_EXTENDED_FAULT_TAXONOMY_V1.json"
)
SCHEMA_PATH = (
    ROOT / "schemas" / "fault_taxonomy_plan_v1.schema.json"
)


def load_json(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


@pytest.fixture
def plan() -> dict[str, object]:
    return load_json(PLAN_PATH)


@pytest.fixture
def schema() -> dict[str, object]:
    return load_json(SCHEMA_PATH)


def test_schema_is_valid_draft_2020_12(
    schema: dict[str, object],
) -> None:
    Draft202012Validator.check_schema(schema)


def test_canonical_plan_passes_schema_and_semantics(
    plan: dict[str, object],
    schema: dict[str, object],
) -> None:
    validate_fault_taxonomy_plan(plan, schema)


def test_file_verification_reports_frozen_design() -> None:
    result = validate_plan_files(PLAN_PATH, SCHEMA_PATH)

    assert (
        result["status"]
        == "P6_R0_TAXONOMY_PLAN_FROZEN_VERIFIED"
    )
    assert result["class_count"] == 6
    assert result["feature_count"] == 10
    assert result["context_count"] == 6
    assert result["expected_clean_rows"] == 72
    assert result["partition_rows"] == {
        "train": 36,
        "validation": 12,
        "test": 24,
    }
    assert result["missing_evidence_masks"] == 4
    assert result["runtime_experiments"] == "ABSENT"
    assert result["plan_sha256"] == sha256_file(PLAN_PATH)


def test_exact_class_and_feature_orders_are_frozen(
    plan: dict[str, object],
) -> None:
    taxonomy = plan["taxonomy"]
    evidence = plan["planned_evidence_contract"]

    assert isinstance(taxonomy, dict)
    assert isinstance(evidence, dict)
    assert tuple(taxonomy["class_order"]) == CLASS_ORDER
    assert tuple(evidence["feature_order"]) == FEATURE_ORDER


def test_wrong_gateway_candidate_uses_precise_canonical_name(
    plan: dict[str, object],
) -> None:
    taxonomy = plan["taxonomy"]
    assert isinstance(taxonomy, dict)

    assert "wrong_default_gateway" in taxonomy["class_order"]
    assert "wrong_gateway" not in taxonomy["class_order"]


def test_duplicate_signature_is_rejected(
    plan: dict[str, object],
    schema: dict[str, object],
) -> None:
    invalid = copy.deepcopy(plan)
    taxonomy = invalid["taxonomy"]
    assert isinstance(taxonomy, dict)
    classes = taxonomy["classes"]
    assert isinstance(classes, list)

    classes[2]["expected_signature"] = copy.deepcopy(
        classes[1]["expected_signature"]
    )

    with pytest.raises(
        FaultTaxonomyPlanError,
        match="signatures must be unique",
    ):
        validate_fault_taxonomy_plan(invalid, schema)


def test_wrong_default_gateway_discriminator_is_rejected(
    plan: dict[str, object],
    schema: dict[str, object],
) -> None:
    invalid = copy.deepcopy(plan)
    taxonomy = invalid["taxonomy"]
    assert isinstance(taxonomy, dict)
    classes = taxonomy["classes"]
    assert isinstance(classes, list)

    classes[3]["expected_signature"][
        "source_default_gateway_matches_expected"
    ] = "true"

    with pytest.raises(
        FaultTaxonomyPlanError,
        match="wrong_default_gateway has an invalid",
    ):
        validate_fault_taxonomy_plan(invalid, schema)


def test_group_crossing_partitions_is_rejected(
    plan: dict[str, object],
    schema: dict[str, object],
) -> None:
    invalid = copy.deepcopy(plan)
    campaign = invalid["campaign"]
    assert isinstance(campaign, dict)
    split = campaign["split"]
    assert isinstance(split, dict)

    split["test_groups"][0] = split["train_groups"][0]

    with pytest.raises(
        FaultTaxonomyPlanError,
        match="cross partitions",
    ):
        validate_fault_taxonomy_plan(invalid, schema)


def test_campaign_row_arithmetic_is_schema_guarded(
    plan: dict[str, object],
    schema: dict[str, object],
) -> None:
    invalid = copy.deepcopy(plan)
    campaign = invalid["campaign"]
    assert isinstance(campaign, dict)
    campaign["expected_clean_rows"] = 71

    with pytest.raises(
        FaultTaxonomyPlanError,
        match="schema violation",
    ):
        validate_fault_taxonomy_plan(invalid, schema)


def test_unknown_mask_feature_is_rejected(
    plan: dict[str, object],
    schema: dict[str, object],
) -> None:
    invalid = copy.deepcopy(plan)
    tracks = invalid["robustness_tracks"]
    assert isinstance(tracks, dict)
    missing = tracks["missing_evidence"]
    assert isinstance(missing, dict)
    missing["masks"][0]["features"].append("ground_truth_label")

    with pytest.raises(
        FaultTaxonomyPlanError,
        match="unknown features",
    ):
        validate_fault_taxonomy_plan(invalid, schema)


def test_overlapping_mask_features_are_rejected(
    plan: dict[str, object],
    schema: dict[str, object],
) -> None:
    invalid = copy.deepcopy(plan)
    tracks = invalid["robustness_tracks"]
    assert isinstance(tracks, dict)
    missing = tracks["missing_evidence"]
    assert isinstance(missing, dict)
    missing["masks"][3]["features"].append(
        "observer_egress_interface_oper_up"
    )

    with pytest.raises(
        FaultTaxonomyPlanError,
        match="must not overlap",
    ):
        validate_fault_taxonomy_plan(invalid, schema)


@pytest.mark.parametrize(
    "boundary",
    [
        "new_scenario_execution_in_p6_r0",
        "containerlab_execution_in_p6_r0",
        "model_training_in_p6_r0",
    ],
)
def test_design_only_boundary_is_rejected_when_enabled(
    plan: dict[str, object],
    schema: dict[str, object],
    boundary: str,
) -> None:
    invalid = copy.deepcopy(plan)
    boundaries = invalid["implementation_boundaries"]
    assert isinstance(boundaries, dict)
    boundaries[boundary] = True

    with pytest.raises(
        FaultTaxonomyPlanError,
        match="schema violation",
    ):
        validate_fault_taxonomy_plan(invalid, schema)


def test_multiple_fault_execution_requires_later_design_gate(
    plan: dict[str, object],
    schema: dict[str, object],
) -> None:
    invalid = copy.deepcopy(plan)
    tracks = invalid["robustness_tracks"]
    assert isinstance(tracks, dict)
    multiple = tracks["multiple_fault"]
    assert isinstance(multiple, dict)
    multiple["enabled_in_first_campaign"] = True

    with pytest.raises(
        FaultTaxonomyPlanError,
        match="schema violation",
    ):
        validate_fault_taxonomy_plan(invalid, schema)


def test_unexpected_plan_property_is_rejected(
    plan: dict[str, object],
    schema: dict[str, object],
) -> None:
    invalid = copy.deepcopy(plan)
    invalid["runtime_results"] = {"accuracy": 1.0}

    with pytest.raises(
        FaultTaxonomyPlanError,
        match="schema violation",
    ):
        validate_fault_taxonomy_plan(invalid, schema)
