from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from src.contracts.expansion import (
    validate_topology_context_v1,
)
from src.expansion.x2_addressing import load_wrong_ip_scenario
from src.expansion.x2_gate import verify_x2_gate


MANIFEST_PATH = "plans/expansion/X2_R1_WRONG_IP_ADDRESS_V1.json"
SCHEMA_PATH = "schemas/x2_r1_wrong_ip_gate_v1.schema.json"
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


class X2R1GateError(ValueError):
    """Raised when the X2-R1 release boundary drifts."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X2R1GateError(message)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X2R1GateError(f"Cannot read X2-R1 JSON object: {path}") from error
    _require(isinstance(value, dict), f"X2-R1 JSON artifact is not an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe(root: Path, relative: str) -> Path:
    path = root / relative
    resolved = path.resolve(strict=True)
    _require(
        resolved.is_relative_to(root.resolve()) and path.is_file() and not path.is_symlink(),
        f"X2-R1 source binding is unsafe: {relative}",
    )
    return path


def validate_x2_r1_manifest(
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
        raise X2R1GateError(
            f"X2-R1 schema validation failed at {path or '<root>'}: "
            f"{errors[0].message}"
        )
    _require(
        manifest.get("runtime_authorization") == EXPECTED_RUNTIME,
        "X2-R1 runtime authorization drifted outside the scoped slice.",
    )
    compatibility = manifest.get("compatibility")
    _require(isinstance(compatibility, Mapping), "X2-R1 compatibility is missing.")
    _require(
        compatibility.get("phase6_evidence_v3") == "UNCHANGED"
        and compatibility.get("phase6_dataset_row_v3") == "UNCHANGED"
        and compatibility.get("accepted_results") == "UNCHANGED"
        and compatibility.get("api_v1") == "UNCHANGED"
        and compatibility.get("extended_api") == "NOT_CREATED"
        and compatibility.get("p9_r1") == "PAUSED",
        "X2-R1 frozen compatibility boundary drifted.",
    )
    slice_definition = manifest.get("slice")
    _require(isinstance(slice_definition, Mapping), "X2-R1 slice is missing.")
    _require(
        slice_definition.get("fault_type") == "wrong_ip_address"
        and slice_definition.get("rule_id") == "R_X2_ADDRESSING_001"
        and slice_definition.get("truth_model") == "single_fault"
        and slice_definition.get("signature") == EXPECTED_SIGNATURE
        and slice_definition.get("excluded_confounders")
        == ["wrong_subnet_mask", "missing_default_route", "duplicate_ip"],
        "X2-R1 signature or confounder boundary drifted.",
    )
    collector = manifest.get("collector_activation")
    _require(isinstance(collector, Mapping), "X2-R1 collector activation is missing.")
    _require(
        collector.get("collector_id") == "addressing_state_collector"
        and collector.get("collector_version") == 1
        and collector.get("evidence_contract") == "Evidence v4"
        and collector.get("raw_artifact_hash_required") is True
        and collector.get("duplicate_address_mac_churn_detected")
        == "NOT_REQUESTED_UNTIL_X2_R4",
        "X2-R1 collector activation drifted.",
    )
    safety = manifest.get("safety")
    _require(
        isinstance(safety, Mapping)
        and tuple(safety.get("invariants", ())) == EXPECTED_SAFETY,
        "X2-R1 safety invariants drifted.",
    )
    acceptance = manifest.get("acceptance")
    _require(isinstance(acceptance, Mapping), "X2-R1 acceptance is missing.")
    _require(
        acceptance.get("real_evidence_required") is True
        and acceptance.get("real_infrastructure_e2e_required") is True
        and acceptance.get("dataset_row_created") is False
        and acceptance.get("model_operation_performed") is False
        and acceptance.get("metric_created") is False
        and acceptance.get("frozen_artifacts_unchanged") is True,
        "X2-R1 acceptance or scientific boundary drifted.",
    )


def verify_x2_r1_gate(repository_root: Path) -> dict[str, Any]:
    root = Path(repository_root)
    manifest = _load(root / MANIFEST_PATH)
    schema = _load(root / SCHEMA_PATH)
    validate_x2_r1_manifest(manifest, schema)
    parent = verify_x2_gate(root)
    _require(
        parent["status"] == "ACCEPTED_DESIGN_ONLY",
        "X2-R1 parent design gate is not accepted.",
    )
    bindings = manifest["source_bindings"]
    assert isinstance(bindings, list)
    _require(
        len({row["binding_id"] for row in bindings}) == len(bindings),
        "X2-R1 source binding IDs must be unique.",
    )
    for row in bindings:
        path = _safe(root, str(row["path"]))
        _require(
            _sha256(path) == row["sha256"],
            f"X2-R1 source binding drifted: {row['path']}",
        )
    scenario_path = root / str(manifest["slice"]["scenario_path"])
    binding = load_wrong_ip_scenario(scenario_path)
    _require(
        binding.scenario_id == "X2_R1_WRONG_IP_ADDRESS"
        and binding.expected_interface == "10.20.1.10/24"
        and binding.wrong_interface == "10.20.1.11/24",
        "X2-R1 scenario identity drifted.",
    )
    context_path = root / str(manifest["slice"]["topology_context_path"])
    context = _load(context_path)
    validate_topology_context_v1(context, repository_root=root)
    _require(
        context["context_id"] == binding.topology_context_id,
        "X2-R1 topology context does not match the scenario.",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the X2-R1 Wrong IP runtime gate.")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    manifest = verify_x2_r1_gate(arguments.repository_root)
    print("x2_r0_gate=VERIFIED")
    print("x2_r1_gate=VERIFIED")
    print("wrong_ip_signature=ADDRESS_FALSE_PREFIX_TRUE_DEFAULT_TRUE_DUPLICATE_FALSE_PASS")
    print("runtime_scope=4/10_AUTHORIZED_PASS")
    print("evidence_contract=NATIVE_V4_HASH_BOUND_PASS")
    print("dataset_model_metric=ABSENT_PASS")
    print(f"next_release={manifest['track']['next_release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

