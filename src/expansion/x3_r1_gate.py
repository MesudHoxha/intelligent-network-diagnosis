from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from src.contracts.expansion import validate_topology_context_v1
from src.expansion.x3_gate import verify_x3_gate
from src.expansion.x3_wrong_access_vlan import load_wrong_access_vlan_scenario


MANIFEST_PATH = Path("plans/expansion/X3_R1_WRONG_ACCESS_VLAN_V1.json")
SCHEMA_PATH = Path("schemas/x3_r1_wrong_access_vlan_gate_v1.schema.json")
EXPECTED_PARENT = "f59af55caadea6591195fd09512b73f23d78135a"
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
    "access_vlan_matches_expected": False,
    "vlan_exists_on_target": True,
    "vlan_allowed_on_trunk": True,
    "native_vlan_matches_peer": True,
    "fdb_location_matches_expected": False,
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
    "EXACT_VLAN_MEMBERSHIP_RESTORATION",
    "NATIVE_FLOW_PRESERVED",
)


class X3R1GateError(ValueError):
    """Raised when the X3-R1 runtime boundary drifts."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X3R1GateError(message)


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X3R1GateError(f"Cannot read X3-R1 JSON object: {path}") from error
    _require(isinstance(value, dict), f"X3-R1 JSON artifact is not an object: {path}")
    return value


def _safe(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    _require(
        relative
        and not pure.is_absolute()
        and ".." not in pure.parts
        and pure.as_posix() == relative,
        "X3-R1 source binding path is not canonical.",
    )
    path = root / relative
    resolved = path.resolve(strict=True)
    _require(
        resolved.is_relative_to(root.resolve()) and path.is_file() and not path.is_symlink(),
        f"X3-R1 source binding is unsafe: {relative}",
    )
    return path


def validate_x3_r1_manifest(
    manifest: Mapping[str, Any], schema: Mapping[str, Any]
) -> None:
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(manifest),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].path)
        raise X3R1GateError(
            f"X3-R1 schema validation failed at {path or '<root>'}: {errors[0].message}"
        )
    _require(
        manifest.get("runtime_authorization") == EXPECTED_RUNTIME,
        "X3-R1 runtime authorization drifted outside the scoped slice.",
    )
    boundary = manifest.get("source_boundary")
    _require(
        isinstance(boundary, Mapping)
        and boundary.get("parent_commit") == EXPECTED_PARENT
        and boundary.get("extension_policy") == "APPEND_ONLY"
        and boundary.get("runtime_inherited") is False,
        "X3-R1 parent or append-only boundary drifted.",
    )
    slice_definition = manifest.get("slice")
    _require(isinstance(slice_definition, Mapping), "X3-R1 slice is missing.")
    _require(
        slice_definition.get("fault_type") == "wrong_access_vlan"
        and slice_definition.get("rule_id") == "R_X3_L2_VLAN_001"
        and slice_definition.get("signature") == EXPECTED_SIGNATURE,
        "X3-R1 signature drifted.",
    )
    safety = manifest.get("safety")
    _require(
        isinstance(safety, Mapping)
        and tuple(safety.get("invariants", ())) == EXPECTED_SAFETY,
        "X3-R1 safety boundary drifted.",
    )
    acceptance = manifest.get("acceptance")
    _require(
        isinstance(acceptance, Mapping)
        and acceptance.get("real_evidence_required") is True
        and acceptance.get("real_infrastructure_e2e_required") is True
        and acceptance.get("dataset_row_created") is False
        and acceptance.get("model_operation_performed") is False
        and acceptance.get("metric_created") is False,
        "X3-R1 acceptance or scientific boundary drifted.",
    )


def verify_x3_r1_gate(repository_root: Path) -> dict[str, Any]:
    root = Path(repository_root)
    manifest = _load(root / MANIFEST_PATH)
    schema = _load(root / SCHEMA_PATH)
    validate_x3_r1_manifest(manifest, schema)
    parent = verify_x3_gate(root)
    _require(parent["status"] == "ACCEPTED_DESIGN_ONLY", "X3-R0 parent is not accepted.")
    bindings = manifest["source_bindings"]
    assert isinstance(bindings, list)
    _require(
        len(bindings) == 14
        and len({row["binding_id"] for row in bindings}) == 14
        and len({row["path"] for row in bindings}) == 14,
        "X3-R1 requires exactly 14 unique source bindings.",
    )
    for row in bindings:
        path = _safe(root, str(row["path"]))
        _require(
            hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"],
            f"X3-R1 source binding drifted: {row['path']}",
        )
    scenario = load_wrong_access_vlan_scenario(
        root / str(manifest["slice"]["scenario_path"])
    )
    _require(
        scenario.scenario_id == "X3_R1_WRONG_ACCESS_VLAN"
        and scenario.topology_id == "X3_TOP_01_L2_VLAN"
        and (scenario.expected_vlan, scenario.wrong_vlan, scenario.native_vlan)
        == (10, 20, 99),
        "X3-R1 scenario identity drifted.",
    )
    context = _load(root / str(manifest["slice"]["topology_context_path"]))
    validate_topology_context_v1(context, repository_root=root)
    _require(
        context["context_id"] == scenario.topology_context_id
        and context["observation_roles"]
        == {"source": "hosta", "destination": "hostb", "observers": ["sw1", "sw2"]},
        "X3-R1 topology observation roles drifted.",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the X3-R1 Wrong Access VLAN gate.")
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    manifest = verify_x3_r1_gate(arguments.repository_root)
    print("x3_r0_gate=VERIFIED")
    print("x3_r1_gate=VERIFIED")
    print("wrong_access_vlan_signature=FALSE_TRUE_TRUE_TRUE_FALSE_PASS")
    print("runtime_scope=4/10_AUTHORIZED_PASS")
    print("tagged_fault_native_flow_preserved=PASS")
    print("dataset_model_metric=ABSENT_PASS")
    print(f"next_release={manifest['track']['next_release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
