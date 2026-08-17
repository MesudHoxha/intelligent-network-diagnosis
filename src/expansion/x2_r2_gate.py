from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from src.contracts.expansion import validate_topology_context_v1
from src.expansion.x2_r1_gate import verify_x2_r1_gate
from src.expansion.x2_subnet_mask import load_wrong_subnet_mask_scenario


MANIFEST_PATH = "plans/expansion/X2_R2_WRONG_SUBNET_MASK_V1.json"
SCHEMA_PATH = "schemas/x2_r2_wrong_subnet_mask_gate_v1.schema.json"
EXPECTED_RUNTIME = {
    "containerlab_execution": True,
    "network_mutation": True,
    "new_evidence_collection": True,
    "dataset_generation": False,
    "model_fit_or_selection": False,
    "estimator_deserialization": False,
    "method_prediction": True,
    "metric_calculation": False,
    "report_only_test_access": False,
    "multiple_fault_execution": False,
}
EXPECTED_SIGNATURE = {
    "source_address_matches_expected": True,
    "source_prefix_matches_expected": False,
    "source_default_route_present": True,
    "duplicate_address_detected": False,
}
EXPECTED_PREVIOUS_SIGNATURE = {
    "fault_type": "wrong_ip_address",
    "rule_id": "R_X2_ADDRESSING_001",
    "source_address_matches_expected": False,
    "source_prefix_matches_expected": True,
    "source_default_route_present": True,
    "duplicate_address_detected": False,
}
EXPECTED_SAFETY = (
    "DURABLE_RECOVERY_INTENT_BEFORE_MUTATION",
    "ATOMIC_MUTATION_JOURNAL",
    "BEST_EFFORT_RESTORATION_ON_PARTIAL_FAILURE",
    "IDEMPOTENT_CONFIRMED_RESTORATION",
    "FINAL_HEALTHY_STATE_VERIFIED",
    "BASELINE_BEFORE_AND_AFTER",
    "REAL_CONTAINERLAB_LIFECYCLE",
    "CLEANUP_ZERO_CONTAINERS",
)


class X2R2GateError(ValueError):
    """Raised when the X2-R2 release boundary drifts."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X2R2GateError(message)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X2R2GateError(f"Cannot read X2-R2 JSON object: {path}") from error
    _require(isinstance(value, dict), f"X2-R2 JSON artifact is not an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe(root: Path, relative: str) -> Path:
    path = root / relative
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise X2R2GateError(f"X2-R2 source binding is unavailable: {relative}") from error
    _require(
        resolved.is_relative_to(root.resolve()) and path.is_file() and not path.is_symlink(),
        f"X2-R2 source binding is unsafe: {relative}",
    )
    return path


def validate_x2_r2_manifest(
    manifest: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> None:
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(manifest),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].path)
        raise X2R2GateError(
            f"X2-R2 schema validation failed at {path or '<root>'}: "
            f"{errors[0].message}"
        )
    _require(
        manifest.get("runtime_authorization") == EXPECTED_RUNTIME,
        "X2-R2 runtime authorization drifted outside the scoped slice.",
    )
    compatibility = manifest.get("compatibility")
    _require(isinstance(compatibility, Mapping), "X2-R2 compatibility is missing.")
    _require(
        compatibility.get("phase6_evidence_v3") == "UNCHANGED"
        and compatibility.get("phase6_dataset_row_v3") == "UNCHANGED"
        and compatibility.get("accepted_results") == "UNCHANGED"
        and compatibility.get("api_v1") == "UNCHANGED"
        and compatibility.get("x2_r1_gate") == "UNCHANGED_AND_VERIFIED"
        and compatibility.get("extended_api") == "NOT_CREATED"
        and compatibility.get("p9_r1") == "PAUSED",
        "X2-R2 frozen compatibility boundary drifted.",
    )
    slice_definition = manifest.get("slice")
    _require(isinstance(slice_definition, Mapping), "X2-R2 slice is missing.")
    _require(
        slice_definition.get("fault_type") == "wrong_subnet_mask"
        and slice_definition.get("rule_id") == "R_X2_ADDRESSING_002"
        and slice_definition.get("truth_model") == "single_fault"
        and slice_definition.get("signature") == EXPECTED_SIGNATURE
        and slice_definition.get("preserved_signature")
        == EXPECTED_PREVIOUS_SIGNATURE
        and slice_definition.get("excluded_confounders")
        == ["wrong_ip_address", "missing_default_route", "duplicate_ip"],
        "X2-R2 signature, preserved rule, or confounder boundary drifted.",
    )
    collector = manifest.get("collector_activation")
    _require(isinstance(collector, Mapping), "X2-R2 collector activation is missing.")
    _require(
        collector.get("collector_id") == "addressing_state_collector"
        and collector.get("collector_version") == 2
        and collector.get("evidence_contract") == "Evidence v4"
        and collector.get("raw_artifact_hash_required") is True
        and collector.get("active_duplicate_check_required") is True
        and collector.get("duplicate_address_mac_churn_detected")
        == "NOT_REQUESTED_UNTIL_X2_R4",
        "X2-R2 collector activation drifted.",
    )
    safety = manifest.get("safety")
    _require(
        isinstance(safety, Mapping)
        and tuple(safety.get("invariants", ())) == EXPECTED_SAFETY
        and safety.get("verified_topology_reused") is True,
        "X2-R2 safety invariants drifted.",
    )
    acceptance = manifest.get("acceptance")
    _require(isinstance(acceptance, Mapping), "X2-R2 acceptance is missing.")
    _require(
        acceptance.get("real_evidence_required") is True
        and acceptance.get("real_infrastructure_e2e_required") is True
        and acceptance.get("x2_r1_regression_required") is True
        and acceptance.get("dataset_row_created") is False
        and acceptance.get("model_operation_performed") is False
        and acceptance.get("metric_created") is False
        and acceptance.get("frozen_artifacts_unchanged") is True,
        "X2-R2 acceptance or scientific boundary drifted.",
    )


def verify_x2_r2_gate(repository_root: Path) -> dict[str, Any]:
    root = Path(repository_root)
    manifest = _load(root / MANIFEST_PATH)
    schema = _load(root / SCHEMA_PATH)
    validate_x2_r2_manifest(manifest, schema)
    parent = verify_x2_r1_gate(root)
    _require(
        parent["status"] == "IMPLEMENTED_RUNTIME_SLICE"
        and parent["track"]["next_release"] == "X2_R2_WRONG_SUBNET_MASK",
        "X2-R2 parent runtime gate is not accepted at the expected boundary.",
    )
    bindings = manifest["source_bindings"]
    assert isinstance(bindings, list)
    _require(
        len({row["binding_id"] for row in bindings}) == len(bindings),
        "X2-R2 source binding IDs must be unique.",
    )
    for row in bindings:
        path = _safe(root, str(row["path"]))
        _require(
            _sha256(path) == row["sha256"],
            f"X2-R2 source binding drifted: {row['path']}",
        )
    scenario_path = root / str(manifest["slice"]["scenario_path"])
    binding = load_wrong_subnet_mask_scenario(scenario_path)
    _require(
        binding.scenario_id == "X2_R2_WRONG_SUBNET_MASK"
        and binding.expected_interface == "10.20.1.10/24"
        and binding.wrong_interface == "10.20.1.10/25",
        "X2-R2 scenario identity drifted.",
    )
    context_path = root / str(manifest["slice"]["topology_context_path"])
    context = _load(context_path)
    validate_topology_context_v1(context, repository_root=root)
    _require(
        context["context_id"] == binding.topology_context_id,
        "X2-R2 topology context does not match the scenario.",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the X2-R2 Wrong Subnet Mask runtime gate."
    )
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    manifest = verify_x2_r2_gate(arguments.repository_root)
    print("x2_r1_gate=VERIFIED_UNCHANGED")
    print("x2_r2_gate=VERIFIED")
    print("wrong_mask_signature=ADDRESS_TRUE_PREFIX_FALSE_DEFAULT_TRUE_DUPLICATE_FALSE_PASS")
    print("wrong_ip_signature=R_X2_ADDRESSING_001_PRESERVED_PASS")
    print("runtime_scope=4/10_AUTHORIZED_PASS")
    print("evidence_contract=NATIVE_V4_HASH_BOUND_PASS")
    print("dataset_model_metric=ABSENT_PASS")
    print(f"next_release={manifest['track']['next_release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
