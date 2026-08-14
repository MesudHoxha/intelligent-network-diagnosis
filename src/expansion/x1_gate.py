from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.collection.modular_registry import build_x1_registry
from src.contracts.expansion import (
    SCHEMA_PATHS,
    ExpansionContractError,
    validate_evidence_mask_plan_v2,
    validate_feature_catalog_v1,
)
from src.expansion.scope_gate import verify_scope_gate


MANIFEST_PATH = Path(
    "plans/expansion/X1_EXTENDED_CONTRACTS_MODULAR_COLLECTION_V1.json"
)
MANIFEST_SCHEMA_PATH = Path(
    "schemas/x1_extended_contracts_modular_collection_v1.schema.json"
)
FEATURE_CATALOG_PATH = Path("plans/expansion/X1_FEATURE_CATALOG_V1.json")
MASK_PLAN_PATH = Path("plans/expansion/X1_EVIDENCE_MASK_PLAN_V2.json")

EXPECTED_BASELINE_CLASS_ORDER = (
    "no_fault",
    "missing_static_route",
    "wrong_next_hop",
    "wrong_default_gateway",
    "interface_down",
    "acl_block",
)

EXPECTED_CONTRACTS = (
    "topology_context_v1",
    "collector_run_v1",
    "evidence_v4",
    "feature_catalog_v1",
    "feature_vector_v2",
    "dataset_row_v4",
    "diagnosis_result_v2",
    "evidence_mask_plan_v2",
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

EXPECTED_DOMAIN_COUNTS = {
    "connectivity": 2,
    "addressing": 7,
    "l2_vlan": 6,
    "routing": 8,
    "services": 8,
    "security": 2,
    "performance": 6,
}


class X1GateError(ValueError):
    """Raised when the X1 contract-only acceptance boundary drifts."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X1GateError(message)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"Expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_x1_manifest(
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
            raise X1GateError(
                "X1 manifest schema validation failed: " + errors[0].message
            )

    _require(
        manifest.get("gate_id")
        == "x1_extended_contracts_modular_collection_v1",
        "X1 gate identity drifted.",
    )
    _require(
        manifest.get("status") == "ACCEPTED_CONTRACT_ONLY",
        "X1 must remain contract-only.",
    )
    track = manifest.get("track")
    _require(isinstance(track, Mapping), "X1 track section is missing.")
    _require(
        track.get("phase9_status") == "P9_R1_PAUSED_BY_USER",
        "X1 cannot resume P9-R1.",
    )
    _require(
        track.get("next_milestone") == "X2_ADDRESSING_VERTICAL_SLICES",
        "X1 next milestone drifted.",
    )

    compatibility = manifest.get("compatibility")
    _require(
        isinstance(compatibility, Mapping),
        "X1 compatibility section is missing.",
    )
    _require(
        tuple(compatibility.get("frozen_class_order", ()))
        == EXPECTED_BASELINE_CLASS_ORDER,
        "The frozen Phase 6 class order drifted.",
    )
    _require(
        compatibility.get("extension_policy") == "APPEND_ONLY"
        and compatibility.get("api_v1_status") == "FROZEN_BASELINE"
        and compatibility.get("future_extended_api") == "/api/v2",
        "The append-only API compatibility boundary drifted.",
    )

    contracts = manifest.get("contracts")
    _require(isinstance(contracts, list), "X1 contracts are missing.")
    _require(
        tuple(row.get("contract_id") for row in contracts)
        == EXPECTED_CONTRACTS,
        "The ordered X1 contract family drifted.",
    )
    _require(
        all(row.get("schema_path") == SCHEMA_PATHS[row["contract_id"]] for row in contracts),
        "An X1 schema path drifted.",
    )

    catalog = manifest.get("feature_catalog")
    _require(isinstance(catalog, Mapping), "X1 feature catalog summary is missing.")
    _require(
        catalog.get("feature_count") == 39
        and catalog.get("frozen_baseline_count") == 10
        and catalog.get("planned_extension_count") == 29
        and catalog.get("domain_counts") == EXPECTED_DOMAIN_COUNTS,
        "X1 feature catalog summary drifted.",
    )

    collection = manifest.get("modular_collection")
    _require(isinstance(collection, Mapping), "Modular collection is missing.")
    _require(
        collection.get("executor_registered") is False
        and collection.get("runtime_authorized") is False
        and collection.get("catalog_coverage_required") is True
        and collection.get("collector_count") == 7,
        "X1 modular collection must remain design-only and fully catalogued.",
    )

    adapter = manifest.get("compatibility_adapter")
    _require(isinstance(adapter, Mapping), "The v3 adapter boundary is missing.")
    _require(
        adapter.get("read_only") is True
        and adapter.get("source_write_authorized") is False
        and adapter.get("source_hash_required") is True
        and adapter.get("preserved_feature_count") == 10,
        "The read-only Evidence v3 adapter boundary drifted.",
    )

    truth = manifest.get("truth_boundaries")
    _require(isinstance(truth, Mapping), "X1 truth boundaries are missing.")
    _require(
        truth.get("dataset_row_v4") == "SINGLE_FAULT_ONLY"
        and truth.get("diagnosis_result_v2") == "SINGLE_FAULT_ONLY"
        and truth.get("multiple_fault_dataset_contract")
        == "DEFERRED_TO_DATASET_ROW_V5"
        and truth.get("multiple_fault_diagnosis_contract")
        == "DEFERRED_TO_DIAGNOSIS_RESULT_V3",
        "Single-fault and future multiple-fault truth were conflated.",
    )

    authorization = manifest.get("runtime_authorization")
    _require(isinstance(authorization, Mapping), "Runtime authorization is missing.")
    _require(
        tuple(authorization) == EXPECTED_RUNTIME_FLAGS
        and not any(authorization.values()),
        "X1 cannot authorize runtime or scientific execution.",
    )


def verify_x1_gate(repository_root: Path) -> dict[str, Any]:
    repository_root = Path(repository_root)
    manifest = _load_json(repository_root / MANIFEST_PATH)
    schema = _load_json(repository_root / MANIFEST_SCHEMA_PATH)
    validate_x1_manifest(manifest, schema)
    verify_scope_gate(repository_root)

    compatibility = manifest["compatibility"]
    assert isinstance(compatibility, Mapping)
    protected_files = compatibility["protected_files"]
    assert isinstance(protected_files, list)
    for row in protected_files:
        path = repository_root / row["path"]
        _require(path.is_file(), f"Protected file is missing: {row['path']}")
        _require(
            _sha256(path) == row["sha256"],
            f"Protected file drifted: {row['path']}",
        )

    contracts = manifest["contracts"]
    assert isinstance(contracts, list)
    for row in contracts:
        schema_path = repository_root / row["schema_path"]
        _require(schema_path.is_file(), f"X1 schema is missing: {row['schema_path']}")
        Draft202012Validator.check_schema(_load_json(schema_path))
        artifact_path = row["artifact_path"]
        if artifact_path is not None:
            _require(
                (repository_root / artifact_path).is_file(),
                f"X1 normative artifact is missing: {artifact_path}",
            )

    feature_catalog = _load_json(repository_root / FEATURE_CATALOG_PATH)
    mask_plan = _load_json(repository_root / MASK_PLAN_PATH)
    try:
        feature_index = validate_feature_catalog_v1(
            feature_catalog, repository_root=repository_root
        )
        validate_evidence_mask_plan_v2(
            mask_plan,
            feature_catalog,
            repository_root=repository_root,
        )
    except ExpansionContractError as error:
        raise X1GateError(str(error)) from error

    domain_counts = Counter(row["domain"] for row in feature_index.values())
    lifecycle_counts = Counter(
        row["lifecycle"] for row in feature_index.values()
    )
    _require(dict(domain_counts) == EXPECTED_DOMAIN_COUNTS, "Catalog domain counts drifted.")
    _require(
        lifecycle_counts == {
            "FROZEN_BASELINE": 10,
            "PLANNED_EXTENSION": 29,
        },
        "Catalog lifecycle counts drifted.",
    )
    registry = build_x1_registry(feature_index)
    _require(not registry.uncovered_features, "Collector catalog coverage drifted.")
    _require(
        len(registry.specs) == 7
        and not any(spec.runtime_authorized for spec in registry.specs),
        "X1 registry runtime boundary drifted.",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the X1 contract gate.")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    manifest = verify_x1_gate(arguments.repository_root)
    print("x1_contract_gate=VERIFIED")
    print("contract_family=8_PASS")
    print("feature_catalog=39_TOTAL_10_BASELINE_29_PLANNED_PASS")
    print("collector_registry=7_DESIGN_ONLY_FULL_COVERAGE_PASS")
    print("evidence_v3_adapter=READ_ONLY_HASH_BOUND_PASS")
    print("runtime_authorization=10/10_FALSE_PASS")
    print(f"next_milestone={manifest['track']['next_milestone']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
