from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


PLAN_SCHEMA_VERSION = 1
PLAN_ID = "p6_extended_fault_taxonomy_v1"
PLAN_STATUS = "FROZEN_DESIGN"

CLASS_ORDER = (
    "no_fault",
    "missing_static_route",
    "wrong_next_hop",
    "wrong_default_gateway",
    "interface_down",
    "acl_block",
)

FEATURE_ORDER = (
    "source_expected_gateway_reachable",
    "source_default_gateway_matches_expected",
    "destination_reachable",
    "route_to_destination_exists_on_observer",
    "route_next_hop_matches_expected",
    "route_next_hop_reachable_from_observer",
    "expected_next_hop_reachable_from_observer",
    "observer_egress_interface_oper_up",
    "destination_reachable_from_transit",
    "flow_blocked_by_policy",
)

MASK_ORDER = (
    "mask_source_gateway_family",
    "mask_route_family",
    "mask_interface_state",
    "mask_policy_state",
)

PARTITION_GROUP_COUNTS = {
    "train_groups": 3,
    "validation_groups": 1,
    "test_groups": 2,
}

EXPECTED_PARTITION_ROWS = {
    "train": 36,
    "validation": 12,
    "test": 24,
}

EXPECTED_SIGNATURE_DISCRIMINATORS = {
    "no_fault": {
        "destination_reachable": "true",
    },
    "missing_static_route": {
        "route_to_destination_exists_on_observer": "false",
        "route_next_hop_matches_expected": "unavailable",
    },
    "wrong_next_hop": {
        "route_next_hop_matches_expected": "false",
        "expected_next_hop_reachable_from_observer": "true",
    },
    "wrong_default_gateway": {
        "source_default_gateway_matches_expected": "false",
        "source_expected_gateway_reachable": "true",
    },
    "interface_down": {
        "route_next_hop_matches_expected": "true",
        "observer_egress_interface_oper_up": "false",
    },
    "acl_block": {
        "observer_egress_interface_oper_up": "true",
        "flow_blocked_by_policy": "true",
    },
}

EXPECTED_SIGNATURES = {
    "no_fault": (
        "true", "true", "true", "true", "true",
        "true", "true", "true", "true", "false",
    ),
    "missing_static_route": (
        "true", "true", "false", "false", "unavailable",
        "unavailable", "true", "true", "true", "false",
    ),
    "wrong_next_hop": (
        "true", "true", "false", "true", "false",
        "false", "true", "true", "true", "false",
    ),
    "wrong_default_gateway": (
        "true", "false", "false", "true", "true",
        "true", "true", "true", "true", "false",
    ),
    "interface_down": (
        "true", "true", "false", "true", "true",
        "false", "false", "false", "true", "false",
    ),
    "acl_block": (
        "true", "true", "false", "true", "true",
        "true", "true", "true", "true", "true",
    ),
}

EXPECTED_CONTEXTS = (
    (
        "E01",
        "CTX_P6_E01_TOP01_LINEAR_SOURCE_EDGE",
        "TOP_01",
    ),
    (
        "E02",
        "CTX_P6_E02_TOP02_CHAIN_OBSERVER_EDGE",
        "TOP_02_CHAIN",
    ),
    (
        "E03",
        "CTX_P6_E03_TOP02_BRANCH_TARGET_ARM",
        "TOP_02_BRANCH",
    ),
    (
        "E04",
        "CTX_P6_E04_TOP02_DUAL_TRANSIT_SELECTED_ARM",
        "TOP_02_DUAL_TRANSIT",
    ),
    (
        "E05",
        "CTX_P6_E05_TOP03_ASYMMETRIC_FORWARD",
        "TOP_03_ASYMMETRIC_RETURN",
    ),
    (
        "E06",
        "CTX_P6_E06_TOP04_FILTER_BOUNDARY",
        "NEW_TOP_04_REQUIRED",
    ),
)

EXPECTED_SPLIT_GROUPS = {
    "train_groups": (
        "CTX_P6_E01_TOP01_LINEAR_SOURCE_EDGE",
        "CTX_P6_E03_TOP02_BRANCH_TARGET_ARM",
        "CTX_P6_E05_TOP03_ASYMMETRIC_FORWARD",
    ),
    "validation_groups": (
        "CTX_P6_E04_TOP02_DUAL_TRANSIT_SELECTED_ARM",
    ),
    "test_groups": (
        "CTX_P6_E02_TOP02_CHAIN_OBSERVER_EDGE",
        "CTX_P6_E06_TOP04_FILTER_BOUNDARY",
    ),
}

EXPECTED_MASKS = {
    "mask_source_gateway_family": (
        "source_expected_gateway_reachable",
        "source_default_gateway_matches_expected",
    ),
    "mask_route_family": (
        "route_to_destination_exists_on_observer",
        "route_next_hop_matches_expected",
        "route_next_hop_reachable_from_observer",
    ),
    "mask_interface_state": (
        "observer_egress_interface_oper_up",
    ),
    "mask_policy_state": (
        "flow_blocked_by_policy",
    ),
}

PRIMARY_METRICS = (
    "macro_f1",
    "exact_diagnosis_rate",
    "affected_prefix_rate",
    "coverage",
    "abstention_rate",
    "insufficient_evidence_rate",
)

REQUIRED_SCOPES = (
    "overall",
    "per_partition",
    "per_class",
    "per_context",
    "per_missing_evidence_mask",
)

ACCEPTANCE_GATES = (
    "strict_schema_and_semantic_validation",
    "six_unique_complete_evidence_signatures",
    "six_complete_context_groups",
    "two_repetitions_per_class_context",
    "exact_36_12_24_row_split",
    "no_group_crosses_partitions",
    "all_phase6_rows_use_evidence_v3_and_dataset_row_v3",
    "no_p2_p5_row_rewrite_or_phase6_training_reuse",
    "injector_preconditions_postconditions_and_restoration_for_every_fault",
    "baseline_valid_before_and_after_every_experiment",
    "prediction_inputs_exclude_labels_ground_truth_partition_and_metrics",
    "selected_models_and_hybrid_policy_frozen_before_test",
    "missing_evidence_masks_preserve_source_hashes_and_do_not_impute",
    "test_outputs_generated_once_for_report_only_use",
)


class FaultTaxonomyPlanError(ValueError):
    """Raised when the frozen Phase 6 design is invalid."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FaultTaxonomyPlanError(
            f"Required JSON file does not exist: {path}"
        ) from error
    except json.JSONDecodeError as error:
        raise FaultTaxonomyPlanError(
            f"Invalid JSON in {path}: {error}"
        ) from error

    if not isinstance(document, dict):
        raise FaultTaxonomyPlanError(
            f"Expected a JSON object in {path}."
        )

    return document


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _validate_json_schema(
    plan: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    validator = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    )
    errors = sorted(
        validator.iter_errors(plan),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        first_error = errors[0]
        location = ".".join(
            str(part) for part in first_error.absolute_path
        )
        prefix = f" at {location}" if location else ""
        raise FaultTaxonomyPlanError(
            f"Fault taxonomy schema violation{prefix}: "
            f"{first_error.message}"
        )


def _require_equal(
    actual: object,
    expected: object,
    message: str,
) -> None:
    if actual != expected:
        raise FaultTaxonomyPlanError(message)


def _validate_taxonomy(plan: dict[str, Any]) -> None:
    taxonomy = plan["taxonomy"]
    class_order = tuple(taxonomy["class_order"])
    _require_equal(
        class_order,
        CLASS_ORDER,
        "The exact six-class order is frozen.",
    )

    classes = taxonomy["classes"]
    class_ids = tuple(item["fault_type"] for item in classes)
    _require_equal(
        class_ids,
        CLASS_ORDER,
        "taxonomy.classes must follow the frozen class order.",
    )

    signatures: set[tuple[str, ...]] = set()

    for item in classes:
        fault_type = item["fault_type"]
        signature = item["expected_signature"]
        _require_equal(
            tuple(signature),
            FEATURE_ORDER,
            f"{fault_type} signature must use the frozen feature order.",
        )

        signature_values = tuple(
            signature[feature] for feature in FEATURE_ORDER
        )
        if signature_values in signatures:
            raise FaultTaxonomyPlanError(
                "Complete-evidence class signatures must be unique."
            )
        signatures.add(signature_values)

        for feature, expected in (
            EXPECTED_SIGNATURE_DISCRIMINATORS[fault_type].items()
        ):
            _require_equal(
                signature[feature],
                expected,
                f"{fault_type} has an invalid {feature} discriminator.",
            )

        _require_equal(
            signature_values,
            EXPECTED_SIGNATURES[fault_type],
            f"{fault_type} must retain its full frozen signature.",
        )

        if fault_type == "no_fault":
            _require_equal(
                item["scenario_kind"],
                "normal",
                "no_fault must be a normal scenario.",
            )
            _require_equal(
                item["injection_mechanism"],
                "none",
                "no_fault cannot define an injector.",
            )
        else:
            _require_equal(
                item["scenario_kind"],
                "fault",
                f"{fault_type} must be a fault scenario.",
            )
            if (
                item["injection_mechanism"] == "none"
                or item["restoration_mechanism"] == "none"
            ):
                raise FaultTaxonomyPlanError(
                    f"{fault_type} requires injection and restoration."
                )


def _validate_campaign(plan: dict[str, Any]) -> None:
    campaign = plan["campaign"]
    contexts = campaign["contexts"]

    slots = [context["slot"] for context in contexts]
    _require_equal(
        slots,
        [f"E0{index}" for index in range(1, 7)],
        "Phase 6 context slots must be E01 through E06 in order.",
    )

    context_groups = [
        context["split_group_id"] for context in contexts
    ]
    if len(set(context_groups)) != 6:
        raise FaultTaxonomyPlanError(
            "All six Phase 6 split groups must be unique."
        )

    context_bindings = tuple(
        (
            context["slot"],
            context["split_group_id"],
            context["implementation_source"],
        )
        for context in contexts
    )
    _require_equal(
        context_bindings,
        EXPECTED_CONTEXTS,
        "The six Phase 6 context bindings are frozen.",
    )

    split = campaign["split"]
    partition_groups: list[str] = []

    for field_name, expected_count in (
        PARTITION_GROUP_COUNTS.items()
    ):
        groups = split[field_name]
        _require_equal(
            len(groups),
            expected_count,
            f"{field_name} must contain {expected_count} groups.",
        )
        partition_groups.extend(groups)

    if len(set(partition_groups)) != 6:
        raise FaultTaxonomyPlanError(
            "No Phase 6 split group may cross partitions."
        )

    _require_equal(
        set(partition_groups),
        set(context_groups),
        "The split must cover exactly the six frozen contexts.",
    )

    for field_name in PARTITION_GROUP_COUNTS:
        _require_equal(
            tuple(split[field_name]),
            EXPECTED_SPLIT_GROUPS[field_name],
            f"{field_name} does not match the frozen allocation.",
        )

    _require_equal(
        split["expected_rows"],
        EXPECTED_PARTITION_ROWS,
        "The Phase 6 split row counts are frozen at 36/12/24.",
    )

    expected_rows = (
        campaign["context_count"]
        * campaign["class_count"]
        * campaign["repetitions_per_class_context"]
    )
    _require_equal(
        campaign["expected_clean_rows"],
        expected_rows,
        "Campaign row arithmetic is inconsistent.",
    )
    _require_equal(
        sum(split["expected_rows"].values()),
        expected_rows,
        "Partition rows must sum to the clean campaign size.",
    )


def _validate_missing_evidence(plan: dict[str, Any]) -> None:
    track = plan["robustness_tracks"]["missing_evidence"]
    _require_equal(
        tuple(track["mask_order"]),
        MASK_ORDER,
        "The missing-evidence mask order is frozen.",
    )

    masks = track["masks"]
    mask_ids = tuple(mask["mask_id"] for mask in masks)
    _require_equal(
        mask_ids,
        MASK_ORDER,
        "Missing-evidence masks must follow mask_order.",
    )

    masked_features: set[str] = set()
    for mask in masks:
        features = mask["features"]
        unknown = set(features) - set(FEATURE_ORDER)
        if unknown:
            raise FaultTaxonomyPlanError(
                "Missing-evidence mask contains unknown features: "
                + ", ".join(sorted(unknown))
            )
        overlap = masked_features.intersection(features)
        if overlap:
            raise FaultTaxonomyPlanError(
                "Missing-evidence masks must not overlap: "
                + ", ".join(sorted(overlap))
            )
        _require_equal(
            tuple(features),
            EXPECTED_MASKS[mask["mask_id"]],
            f"{mask['mask_id']} does not match its frozen features.",
        )
        masked_features.update(features)


def _validate_boundaries(plan: dict[str, Any]) -> None:
    predecessor = plan["immutable_predecessors"]
    _require_equal(
        predecessor["phases"],
        ["P2", "P3", "P4", "P5"],
        "P2-P5 must remain immutable predecessors.",
    )

    evidence = plan["planned_evidence_contract"]
    _require_equal(
        tuple(evidence["feature_order"]),
        FEATURE_ORDER,
        "The planned Evidence/Dataset v3 feature order is frozen.",
    )

    boundaries = plan["implementation_boundaries"]
    forbidden_in_r0 = (
        "new_scenario_execution_in_p6_r0",
        "containerlab_execution_in_p6_r0",
        "model_training_in_p6_r0",
    )
    if any(boundaries[field] for field in forbidden_in_r0):
        raise FaultTaxonomyPlanError(
            "P6-R0 is design-only and cannot execute scenarios, "
            "Containerlab, or model training."
        )

    if plan["robustness_tracks"]["multiple_fault"][
        "enabled_in_first_campaign"
    ]:
        raise FaultTaxonomyPlanError(
            "Multiple faults require a later multi-label design gate."
        )

    evaluation = plan["evaluation"]
    _require_equal(
        tuple(evaluation["primary_metrics"]),
        PRIMARY_METRICS,
        "The Phase 6 primary metric order is frozen.",
    )
    _require_equal(
        tuple(evaluation["required_scopes"]),
        REQUIRED_SCOPES,
        "The Phase 6 report scopes are frozen.",
    )
    _require_equal(
        tuple(plan["acceptance_gates"]),
        ACCEPTANCE_GATES,
        "The Phase 6 acceptance gates are frozen.",
    )


def validate_fault_taxonomy_plan(
    plan: dict[str, Any],
    schema: dict[str, Any],
) -> None:
    _validate_json_schema(plan, schema)
    _require_equal(
        plan["schema_version"],
        PLAN_SCHEMA_VERSION,
        "Unsupported fault taxonomy plan schema version.",
    )
    _require_equal(
        plan["plan_id"],
        PLAN_ID,
        "Unexpected Phase 6 plan identifier.",
    )
    _require_equal(
        plan["status"],
        PLAN_STATUS,
        "The canonical Phase 6 plan must be frozen design.",
    )
    _validate_taxonomy(plan)
    _validate_campaign(plan)
    _validate_missing_evidence(plan)
    _validate_boundaries(plan)


def validate_plan_files(
    plan_path: Path,
    schema_path: Path,
) -> dict[str, Any]:
    plan = read_json(plan_path)
    schema = read_json(schema_path)
    validate_fault_taxonomy_plan(plan, schema)

    return {
        "status": "P6_R0_TAXONOMY_PLAN_FROZEN_VERIFIED",
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256_file(plan_path),
        "class_count": len(plan["taxonomy"]["classes"]),
        "feature_count": len(
            plan["planned_evidence_contract"]["feature_order"]
        ),
        "context_count": len(plan["campaign"]["contexts"]),
        "expected_clean_rows": plan["campaign"][
            "expected_clean_rows"
        ],
        "partition_rows": plan["campaign"]["split"][
            "expected_rows"
        ],
        "missing_evidence_masks": len(
            plan["robustness_tracks"]["missing_evidence"]["masks"]
        ),
        "runtime_experiments": "ABSENT",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the frozen Phase 6 fault-taxonomy design."
        )
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    result = validate_plan_files(
        arguments.plan,
        arguments.schema,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
