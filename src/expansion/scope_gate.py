from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


MANIFEST_PATH = Path(
    "plans/expansion/X0_SCOPE_COMPATIBILITY_FREEZE_V1.json"
)
SCHEMA_PATH = Path(
    "schemas/x0_scope_compatibility_freeze_v1.schema.json"
)

EXPECTED_BASELINE_CLASS_ORDER = (
    "no_fault",
    "missing_static_route",
    "wrong_next_hop",
    "wrong_default_gateway",
    "interface_down",
    "acl_block",
)

EXPECTED_PROTECTED_CONTRACTS = (
    "plans/taxonomies/P6_EXTENDED_FAULT_TAXONOMY_V1.json",
    "plans/phase6/P6_R6_METHOD_PROTOCOL_V1.json",
    "schemas/evidence_v3.schema.json",
    "schemas/dataset_row_v3.schema.json",
    "schemas/phase6_method_input_v1.schema.json",
    "schemas/phase6_method_prediction_v1.schema.json",
    "schemas/phase6_method_report_v1.schema.json",
)

EXPECTED_FAULT_TYPES = (
    ("A1", "wrong_ip_address", "addressing", "MISSING", "X2"),
    ("A2", "wrong_subnet_mask", "addressing", "MISSING", "X2"),
    (
        "A3",
        "wrong_default_gateway",
        "addressing",
        "FROZEN_IMPLEMENTED",
        "BASELINE",
    ),
    ("A4", "duplicate_ip", "addressing", "MISSING", "X2"),
    (
        "B1",
        "interface_down",
        "l2_vlan",
        "FROZEN_IMPLEMENTED",
        "BASELINE",
    ),
    ("B2", "wrong_access_vlan", "l2_vlan", "MISSING", "X3"),
    ("B3", "vlan_missing", "l2_vlan", "MISSING", "X3"),
    (
        "B4",
        "vlan_not_allowed_on_trunk",
        "l2_vlan",
        "MISSING",
        "X3",
    ),
    ("B5", "native_vlan_mismatch", "l2_vlan", "MISSING", "X3"),
    (
        "C1",
        "missing_static_route",
        "routing",
        "FROZEN_IMPLEMENTED",
        "BASELINE",
    ),
    (
        "C2",
        "wrong_next_hop",
        "routing",
        "FROZEN_IMPLEMENTED",
        "BASELINE",
    ),
    ("C3", "missing_default_route", "routing", "MISSING", "X2"),
    (
        "C4",
        "dynamic_routing_adjacency_failure",
        "routing",
        "MISSING",
        "X5",
    ),
    (
        "C5",
        "route_filtering_or_advertisement_problem",
        "routing",
        "MISSING",
        "X5",
    ),
    (
        "D1",
        "dhcp_server_unavailable",
        "services",
        "MISSING",
        "X4",
    ),
    (
        "D2",
        "dhcp_pool_misconfiguration",
        "services",
        "MISSING",
        "X4",
    ),
    ("D3", "dns_service_down", "services", "MISSING", "X4"),
    ("D4", "wrong_dns_record", "services", "MISSING", "X4"),
    (
        "E1",
        "acl_block",
        "security",
        "FROZEN_IMPLEMENTED",
        "BASELINE",
    ),
    (
        "E2",
        "firewall_service_block",
        "security",
        "PARTIAL_MECHANISM_ONLY",
        "X4",
    ),
    ("F1", "packet_loss", "performance", "MISSING", "X6"),
    ("F2", "high_latency", "performance", "MISSING", "X6"),
    ("F3", "congestion", "performance", "MISSING", "X6"),
    (
        "F4",
        "bandwidth_rate_limiting",
        "performance",
        "MISSING",
        "X6",
    ),
)

EXPECTED_PHASES = (
    ("X0", "ACCEPTED_DESIGN_ONLY"),
    ("X1", "PLANNED"),
    ("X2", "PLANNED"),
    ("X3", "PLANNED"),
    ("X4", "PLANNED"),
    ("X5", "PLANNED"),
    ("X6", "PLANNED"),
    ("X7", "PLANNED"),
    ("X8", "PLANNED"),
    ("X9", "PLANNED"),
    ("X10", "PLANNED"),
)

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


class ExpansionScopeError(ValueError):
    """Raised when the X0 scope or compatibility boundary drifts."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExpansionScopeError(f"Expected a JSON object: {path}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExpansionScopeError(message)


def validate_scope_manifest(
    manifest: Mapping[str, Any],
    schema: Mapping[str, Any] | None = None,
) -> None:
    """Validate the machine-readable X0 design boundary fail closed."""

    if schema is not None:
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema).iter_errors(manifest),
            key=lambda error: tuple(str(part) for part in error.path),
        )
        if errors:
            raise ExpansionScopeError(
                "X0 JSON Schema validation failed: " + errors[0].message
            )

    _require(
        manifest.get("gate_id") == "x0_scope_compatibility_freeze_v1",
        "X0 gate identity drifted.",
    )
    _require(
        manifest.get("status") == "ACCEPTED_DESIGN_ONLY",
        "X0 must remain a design-only acceptance gate.",
    )

    track = manifest.get("track")
    _require(isinstance(track, Mapping), "X0 track section is missing.")
    _require(
        track.get("phase9_status") == "P9_R1_PAUSED_BY_USER",
        "X0 must not resume or rewrite P9-R1.",
    )
    _require(
        track.get("next_milestone")
        == "X1_EXTENDED_CONTRACTS_AND_MODULAR_COLLECTION",
        "X0 next milestone drifted.",
    )

    vision = manifest.get("vision_source")
    _require(isinstance(vision, Mapping), "X0 vision source is missing.")
    _require(
        vision.get("detailed_fault_type_count") == 24
        and vision.get("prioritization_claimed_count") == 23
        and vision.get("omitted_from_prioritization") == ["vlan_missing"]
        and vision.get("resolution")
        == "INCLUDE_ALL_24_DETAILED_FAULT_TYPES",
        "The documented 23/24 taxonomy discrepancy is not resolved safely.",
    )

    baseline = manifest.get("baseline_boundary")
    _require(
        isinstance(baseline, Mapping), "X0 baseline boundary is missing."
    )
    _require(
        tuple(baseline.get("immutable_class_order", ()))
        == EXPECTED_BASELINE_CLASS_ORDER,
        "The frozen Phase 6 class order drifted.",
    )
    _require(
        tuple(baseline.get("protected_contract_paths", ()))
        == EXPECTED_PROTECTED_CONTRACTS,
        "The protected baseline contract set drifted.",
    )
    _require(
        baseline.get("accepted_artifact_mutation_allowed") is False
        and baseline.get("consumed_test_reuse_for_selection_allowed") is False,
        "X0 weakened a frozen baseline protection.",
    )
    _require(
        baseline.get("historical_decisions") == ["D-085", "D-091", "D-097"],
        "The historical decision boundary drifted.",
    )

    taxonomy = manifest.get("taxonomy")
    _require(isinstance(taxonomy, Mapping), "X0 taxonomy is missing.")
    healthy = taxonomy.get("healthy_class")
    _require(
        healthy
        == {
            "fault_type": "no_fault",
            "category": None,
            "implementation_status": "FROZEN_IMPLEMENTED",
        },
        "The frozen healthy class drifted.",
    )
    rows = taxonomy.get("fault_types")
    _require(isinstance(rows, list), "X0 fault type list is missing.")
    actual_rows = tuple(
        (
            row.get("code"),
            row.get("fault_type"),
            row.get("category"),
            row.get("implementation_status"),
            row.get("target_phase"),
        )
        for row in rows
        if isinstance(row, Mapping)
    )
    _require(
        actual_rows == EXPECTED_FAULT_TYPES,
        "The canonical 24-fault taxonomy drifted.",
    )
    status_counts = Counter(row[3] for row in actual_rows)
    _require(
        status_counts
        == {
            "FROZEN_IMPLEMENTED": 5,
            "PARTIAL_MECHANISM_ONLY": 1,
            "MISSING": 18,
        },
        "The implementation gap counts drifted.",
    )
    category_counts = Counter(row[2] for row in actual_rows)
    _require(
        category_counts
        == {
            "addressing": 4,
            "l2_vlan": 5,
            "routing": 5,
            "services": 4,
            "security": 2,
            "performance": 4,
        },
        "The six-domain taxonomy coverage drifted.",
    )

    policy = manifest.get("architecture_policy")
    _require(
        isinstance(policy, Mapping), "X0 architecture policy is missing."
    )
    _require(
        policy.get("incremental_extension_only") is True
        and policy.get("rewrite_from_zero_authorized") is False
        and policy.get("automatic_remediation_authorized") is False,
        "X0 weakened an architecture or safety boundary.",
    )
    _require(
        policy.get("first_dynamic_routing_protocol") == "ospf"
        and policy.get("bgp_status") == "OPTIONAL_AFTER_OSPF_GATE",
        "The dynamic-routing protocol priority drifted.",
    )
    _require(
        policy.get("new_single_fault_contracts")
        == [
            "Topology Context v1",
            "Evidence v4",
            "Feature Catalog v1",
            "Feature Vector v2",
            "Dataset Row v4",
            "Diagnosis Result v2",
            "Evidence Mask Plan v2",
        ],
        "The planned single-fault contract family drifted.",
    )
    _require(
        policy.get("multiple_fault_contracts")
        == ["Dataset Row v5", "Diagnosis Result v3"],
        "The separate multiple-fault contract boundary drifted.",
    )

    roadmap = manifest.get("roadmap")
    _require(isinstance(roadmap, list), "X0 roadmap is missing.")
    actual_phases = tuple(
        (phase.get("phase_id"), phase.get("status"))
        for phase in roadmap
        if isinstance(phase, Mapping)
    )
    _require(actual_phases == EXPECTED_PHASES, "The X0-X10 roadmap drifted.")
    _require(
        all(phase.get("runtime_authorized_now") is False for phase in roadmap),
        "A future expansion phase was authorized prematurely.",
    )

    gates = manifest.get("release_gates")
    _require(isinstance(gates, Mapping), "X0 release gates are missing.")
    groups = gates.get("minimum_ml_ready_single_fault_groups")
    _require(
        groups
        == {
            "train": 3,
            "validation": 1,
            "report_only_test": 2,
            "repetitions_per_group": 2,
        },
        "The minimum grouped single-fault design drifted.",
    )
    pairs = gates.get("multiple_fault_pair_policy")
    _require(
        pairs
        == {
            "cartesian_product_allowed": False,
            "minimum_selected_pairs": 6,
            "maximum_selected_pairs": 10,
            "initial_pilot_pairs": 2,
            "identifiability_gate_required": True,
        },
        "The bounded multiple-fault pair policy drifted.",
    )

    authorization = manifest.get("runtime_authorization")
    _require(
        isinstance(authorization, Mapping),
        "X0 runtime authorization section is missing.",
    )
    _require(
        tuple(authorization) == EXPECTED_RUNTIME_FLAGS
        and all(authorization[name] is False for name in EXPECTED_RUNTIME_FLAGS),
        "X0 must authorize no empirical or network runtime.",
    )

    change_control = manifest.get("change_control")
    _require(
        isinstance(change_control, Mapping), "X0 change control is missing."
    )
    _require(
        change_control.get("future_technical_changes_allowed") is True
        and change_control.get("frozen_baseline_changes_allowed") is False
        and change_control.get("scientific_result_changes_allowed") is False,
        "X0 change control does not preserve the accepted baseline.",
    )


def verify_scope_gate(repository_root: Path) -> dict[str, Any]:
    """Verify schema, semantics, and protected tracked contract presence."""

    root = repository_root.resolve()
    manifest_path = root / MANIFEST_PATH
    schema_path = root / SCHEMA_PATH
    _require(
        manifest_path.is_file() and not manifest_path.is_symlink(),
        "The tracked X0 manifest is missing or unsafe.",
    )
    _require(
        schema_path.is_file() and not schema_path.is_symlink(),
        "The tracked X0 JSON Schema is missing or unsafe.",
    )
    manifest = _load_json(manifest_path)
    schema = _load_json(schema_path)
    validate_scope_manifest(manifest, schema)

    for relative in EXPECTED_PROTECTED_CONTRACTS:
        path = root / relative
        _require(
            path.is_file() and not path.is_symlink(),
            f"Protected baseline contract is missing or unsafe: {relative}",
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the X0 expansion scope and compatibility freeze."
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    args = parser.parse_args()
    manifest = verify_scope_gate(args.repository_root)
    print("x0_scope_gate=VERIFIED")
    print(f"canonical_fault_types={len(manifest['taxonomy']['fault_types'])}")
    print(f"next_milestone={manifest['track']['next_milestone']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
