from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.collection.modular_registry import build_x1_registry
from src.contracts.expansion import (
    ExpansionContractError,
    validate_feature_catalog_v1,
)
from src.expansion.x1_gate import verify_x1_gate


MANIFEST_PATH = Path(
    "plans/expansion/X2_R0_ADDRESSING_RUNTIME_GATE_V1.json"
)
MANIFEST_SCHEMA_PATH = Path(
    "schemas/x2_addressing_runtime_gate_v1.schema.json"
)
X0_MANIFEST_PATH = Path(
    "plans/expansion/X0_SCOPE_COMPATIBILITY_FREEZE_V1.json"
)
FEATURE_CATALOG_PATH = Path("plans/expansion/X1_FEATURE_CATALOG_V1.json")

EXPECTED_RUNTIME_FLAGS = (
    "containerlab_execution",
    "network_mutation",
    "new_evidence_collection",
    "dataset_generation",
    "model_fit_or_selection",
    "estimator_deserialization",
    "method_prediction",
    "metric_calculation",
    "report_only_test_access",
    "multiple_fault_execution",
)

EXPECTED_FEATURE_IDS = (
    "source_address_matches_expected",
    "source_prefix_matches_expected",
    "source_default_route_present",
    "duplicate_address_detected",
    "duplicate_address_mac_churn_detected",
)

EXPECTED_FAULTS = (
    ("A1", "wrong_ip_address", "addressing", "X2_R1_WRONG_IP_ADDRESS"),
    (
        "A2",
        "wrong_subnet_mask",
        "addressing",
        "X2_R2_WRONG_SUBNET_MASK",
    ),
    (
        "C3",
        "missing_default_route",
        "routing",
        "X2_R3_MISSING_DEFAULT_ROUTE",
    ),
    (
        "A4",
        "duplicate_ip",
        "addressing",
        "X2_R4_DUPLICATE_IP_TEMPORAL",
    ),
)

EXPECTED_SIGNATURES = {
    "wrong_ip_address": {
        "source_address_matches_expected": False,
        "source_prefix_matches_expected": True,
        "source_default_route_present": True,
        "duplicate_address_detected": False,
    },
    "wrong_subnet_mask": {
        "source_address_matches_expected": True,
        "source_prefix_matches_expected": False,
        "source_default_route_present": True,
        "duplicate_address_detected": False,
    },
    "missing_default_route": {
        "source_address_matches_expected": True,
        "source_prefix_matches_expected": True,
        "source_default_route_present": False,
        "duplicate_address_detected": False,
    },
    "duplicate_ip": {
        "source_address_matches_expected": True,
        "source_prefix_matches_expected": True,
        "source_default_route_present": True,
        "duplicate_address_detected": True,
        "duplicate_address_mac_churn_detected": True,
    },
}

EXPECTED_RELEASES = (
    "X2_R0_ADDRESSING_DESIGN_GATE",
    "X2_R1_WRONG_IP_ADDRESS",
    "X2_R2_WRONG_SUBNET_MASK",
    "X2_R3_MISSING_DEFAULT_ROUTE",
    "X2_R4_DUPLICATE_IP_TEMPORAL",
    "X2_R5_ADDRESSING_CLOSEOUT",
)

EXPECTED_SAFETY_INVARIANTS = (
    "DURABLE_RECOVERY_INTENT_BEFORE_MUTATION",
    "ATOMIC_MUTATION_JOURNAL",
    "BEST_EFFORT_RESTORATION",
    "IDEMPOTENT_CONFIRMED_RESTORATION",
    "FINAL_HEALTHY_STATE_VERIFIED",
    "SINGLE_FAULT_ISOLATION",
    "BASELINE_BEFORE_AND_AFTER",
    "CLEANUP_ZERO_CONTAINERS",
)


class X2GateError(ValueError):
    """Raised when the X2-R0 design or authorization boundary drifts."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X2GateError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X2GateError(f"Cannot read a valid JSON object: {path}") from error
    _require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_source_path(repository_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    _require(
        not candidate.is_absolute() and candidate.as_posix() == relative,
        "An X2 source binding is not a canonical relative path.",
    )
    root = repository_root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise X2GateError("An X2 source binding escaped the repository.") from error
    _require(
        resolved.is_file() and not (root / candidate).is_symlink(),
        f"An X2 source binding is unavailable: {relative}",
    )
    return resolved


def validate_x2_manifest(
    manifest: Mapping[str, Any],
    schema: Mapping[str, Any] | None = None,
) -> None:
    if schema is not None:
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(manifest),
            key=lambda error: tuple(str(part) for part in error.path),
        )
        if errors:
            raise X2GateError(
                "X2-R0 manifest schema validation failed: "
                + errors[0].message
            )

    _require(
        manifest.get("gate_id")
        == "x2_r0_addressing_design_runtime_gate_v1",
        "X2-R0 gate identity drifted.",
    )
    _require(
        manifest.get("status") == "ACCEPTED_DESIGN_ONLY",
        "X2-R0 must remain design-only.",
    )

    track = manifest.get("track")
    _require(isinstance(track, Mapping), "X2-R0 track section is missing.")
    _require(
        track.get("source_x1_gate")
        == "x1_extended_contracts_modular_collection_v1"
        and track.get("phase9_status") == "P9_R1_PAUSED_BY_USER"
        and track.get("current_release") == "X2_R0_ADDRESSING_DESIGN_GATE"
        and track.get("next_release") == "X2_R1_WRONG_IP_ADDRESS",
        "X2-R0 track boundary drifted.",
    )

    compatibility = manifest.get("compatibility")
    _require(
        isinstance(compatibility, Mapping),
        "X2-R0 compatibility section is missing.",
    )
    _require(
        compatibility.get("extension_policy") == "APPEND_ONLY"
        and compatibility.get("frozen_baseline_mutation_allowed") is False
        and compatibility.get("accepted_result_mutation_allowed") is False
        and compatibility.get("api_v1_status") == "FROZEN_BASELINE"
        and compatibility.get("future_extended_api") == "/api/v2"
        and compatibility.get("truth_model") == "SINGLE_FAULT_ONLY",
        "X2-R0 compatibility or truth boundary drifted.",
    )

    authorization = manifest.get("runtime_authorization")
    _require(
        isinstance(authorization, Mapping)
        and tuple(authorization) == EXPECTED_RUNTIME_FLAGS
        and not any(authorization.values()),
        "X2-R0 cannot authorize runtime or scientific execution.",
    )

    feature_boundary = manifest.get("feature_boundary")
    _require(
        isinstance(feature_boundary, Mapping)
        and feature_boundary.get("catalog_id") == "x1_feature_catalog_v1"
        and feature_boundary.get("collector_id")
        == "addressing_state_collector"
        and feature_boundary.get("collector_version") == 1
        and feature_boundary.get("collector_status") == "DESIGN_ONLY"
        and tuple(feature_boundary.get("required_feature_ids", ()))
        == EXPECTED_FEATURE_IDS,
        "The X2 addressing feature or collector boundary drifted.",
    )

    slices = manifest.get("addressing_scope")
    _require(isinstance(slices, list), "X2 addressing slices are missing.")
    observed_faults = tuple(
        (
            row.get("fault_code"),
            row.get("fault_type"),
            row.get("category"),
            row.get("implementation_release"),
        )
        for row in slices
        if isinstance(row, Mapping)
    )
    _require(observed_faults == EXPECTED_FAULTS, "X2 fault ordering drifted.")
    _require(
        tuple(row.get("order") for row in slices) == (1, 2, 3, 4),
        "X2 slice order drifted.",
    )

    signature_keys: set[tuple[tuple[str, bool], ...]] = set()
    for row in slices:
        assert isinstance(row, Mapping)
        fault_type = str(row["fault_type"])
        signature = row.get("fault_signature")
        _require(
            signature == EXPECTED_SIGNATURES[fault_type],
            f"The {fault_type} signature drifted.",
        )
        signature_key = tuple(sorted(signature.items()))
        _require(
            signature_key not in signature_keys,
            "Addressing fault signatures must remain disjoint.",
        )
        signature_keys.add(signature_key)
        required_features = tuple(row.get("required_feature_ids", ()))
        _require(
            set(required_features) == set(signature),
            f"The {fault_type} rule uses unbound evidence.",
        )
        _require(
            row.get("recovery_intent_required") is True
            and row.get("idempotent_restoration_required") is True
            and row.get("real_e2e_required") is True,
            f"The {fault_type} safety gate drifted.",
        )

    duplicate = slices[-1]
    _require(
        tuple(duplicate.get("required_evidence_modes", ()))
        == ("ACTIVE_DUPLICATE_CHECK", "TEMPORAL_NEIGHBOR_OBSERVATION")
        and duplicate["fault_signature"].get("duplicate_address_detected")
        is True
        and duplicate["fault_signature"].get(
            "duplicate_address_mac_churn_detected"
        )
        is True,
        "Duplicate IP requires active and temporal two-signal evidence.",
    )

    releases = manifest.get("release_sequence")
    _require(isinstance(releases, list), "X2 release sequence is missing.")
    _require(
        tuple(row.get("release_id") for row in releases) == EXPECTED_RELEASES
        and releases[0].get("status") == "ACCEPTED_DESIGN_ONLY"
        and all(row.get("status") == "PLANNED" for row in releases[1:])
        and not any(row.get("runtime_inherited") for row in releases),
        "X2 release order or non-inherited runtime boundary drifted.",
    )

    _require(
        tuple(manifest.get("safety_invariants", ()))
        == EXPECTED_SAFETY_INVARIANTS,
        "X2 safety invariants drifted.",
    )
    evidence = manifest.get("evidence_policy")
    acceptance = manifest.get("acceptance")
    _require(
        isinstance(evidence, Mapping)
        and evidence.get("evidence_contract") == "Evidence v4"
        and evidence.get("real_evidence_required_per_runtime_slice") is True
        and evidence.get("r0_creates_empirical_evidence") is False
        and evidence.get("report_only_test_access_allowed") is False,
        "X2-R0 evidence boundary drifted.",
    )
    _require(
        isinstance(acceptance, Mapping)
        and acceptance.get("new_runtime_executed") is False
        and acceptance.get("new_empirical_claim_created") is False
        and acceptance.get("frozen_artifacts_unchanged") is True
        and acceptance.get("explicit_gate_before_each_runtime_release")
        is True,
        "X2-R0 acceptance boundary drifted.",
    )


def verify_x2_gate(repository_root: Path) -> dict[str, Any]:
    root = Path(repository_root)
    manifest = _load_json(root / MANIFEST_PATH)
    schema = _load_json(root / MANIFEST_SCHEMA_PATH)
    validate_x2_manifest(manifest, schema)
    verify_x1_gate(root)

    bindings = manifest["source_bindings"]
    assert isinstance(bindings, list)
    _require(
        len({row["binding_id"] for row in bindings}) == len(bindings),
        "X2 source binding IDs must be unique.",
    )
    for row in bindings:
        path = _safe_source_path(root, str(row["path"]))
        _require(
            _sha256(path) == row["sha256"],
            f"X2 source binding drifted: {row['path']}",
        )

    x0 = _load_json(root / X0_MANIFEST_PATH)
    x0_rows = {
        row["fault_type"]: row
        for row in x0["taxonomy"]["fault_types"]
        if row["target_phase"] == "X2"
    }
    _require(
        set(x0_rows) == {fault for _, fault, _, _ in EXPECTED_FAULTS},
        "X2 scope drifted from the canonical X0 taxonomy.",
    )
    for code, fault_type, category, _ in EXPECTED_FAULTS:
        row = x0_rows[fault_type]
        _require(
            row["code"] == code
            and row["category"] == category
            and row["implementation_status"] == "MISSING",
            f"X2 taxonomy binding drifted: {fault_type}",
        )

    feature_catalog = _load_json(root / FEATURE_CATALOG_PATH)
    try:
        feature_index = validate_feature_catalog_v1(
            feature_catalog,
            repository_root=root,
        )
    except ExpansionContractError as error:
        raise X2GateError(str(error)) from error
    for feature_id in EXPECTED_FEATURE_IDS:
        row = feature_index[feature_id]
        _require(
            row["target_phase"] == "X2"
            and row["lifecycle"] == "PLANNED_EXTENSION",
            f"X2 feature lifecycle drifted: {feature_id}",
        )

    registry = build_x1_registry(feature_index)
    owner = next(
        spec
        for spec in registry.specs
        if spec.collector_id == "addressing_state_collector"
    )
    _require(
        owner.feature_ids == EXPECTED_FEATURE_IDS
        and owner.implementation_status == "DESIGN_ONLY"
        and owner.runtime_authorized is False,
        "The X1 addressing collector must remain design-only at X2-R0.",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the X2-R0 addressing design and runtime gate."
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    manifest = verify_x2_gate(arguments.repository_root)
    print("x2_r0_gate=VERIFIED")
    print("addressing_scope=4_DISJOINT_SINGLE_FAULT_SLICES_PASS")
    print("duplicate_ip_evidence=ACTIVE_PLUS_TEMPORAL_REQUIRED_PASS")
    print("release_sequence=X2_R0_THROUGH_X2_R5_PASS")
    print("runtime_authorization=10/10_FALSE_PASS")
    print("new_empirical_evidence=ABSENT_PASS")
    print(f"next_release={manifest['track']['next_release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
