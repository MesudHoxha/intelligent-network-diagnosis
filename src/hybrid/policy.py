from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


DEFAULT_POLICY_PATH = Path(
    "policies/hybrid/P5_HYBRID_POLICY_V1.json"
)
DEFAULT_SCHEMA_PATH = Path("schemas/hybrid_policy_v1.schema.json")

EXPECTED_POLICY_ID = "p5_r0_hybrid_policy_v1"
EXPECTED_CLASS_ORDER = [
    "no_fault",
    "missing_static_route",
    "wrong_next_hop",
]
EXPECTED_CANDIDATE_ORDER = [
    "consensus_abstain_v1",
    "rule_guarded_fallback_v1",
]
EXPECTED_METRIC_ORDER = [
    "macro_f1_full_denominator",
    "exact_diagnosis_rate_full_denominator",
    "coverage",
    "complexity_rank",
    "candidate_id",
]
EXPECTED_FORBIDDEN_INPUTS = {
    "ground_truth",
    "dataset_labels",
    "partition_name",
    "rule_correctness",
    "ml_correctness",
    "per_experiment_evaluation",
    "method_evaluation_metrics",
    "test_results",
}
EXPECTED_BASELINE_HASHES = {
    "rule_baseline": (
        "7158f1de31a892779bbce2eaad8f5c5e5bb7c2fc08e0766b49a55047ddc56424"
    ),
    "ml_feature_matrix": (
        "9193b4b8c676bf94ef9af05562d9d0047faef61bc94c9d81b0485b88bf599730"
    ),
    "ml_selection": (
        "a02536d6f2478d9fdc40510275dd3b48a2824ee7b1f0fa08c1aed472611fb6fb"
    ),
    "ml_model": (
        "90db38e625f4bcf6a234b6a0516371b76f98e01b4437f684ffea119cbc09cdb2"
    ),
    "ml_report": (
        "8fc6e77e5008cd7cc74e5ce130b901ed750afab9a35eb62652ff55f9205b0e92"
    ),
}


class HybridPolicyError(ValueError):
    """Raised when the frozen hybrid policy contract is invalid."""


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise HybridPolicyError(f"Required artifact does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise HybridPolicyError(f"Invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise HybridPolicyError(f"JSON artifact must be an object: {path}")
    return value


def sha256_file(path: Path) -> str:
    if not path.exists():
        raise HybridPolicyError(f"Required artifact does not exist: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HybridPolicyError(f"{field} must be an object.")
    return value


def validate_against_schema(
    policy: Mapping[str, Any],
    schema_path: Path,
) -> None:
    schema = read_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(policy),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path)
        prefix = f"{location}: " if location else ""
        raise HybridPolicyError(
            f"Hybrid Policy v1 JSON Schema violation: {prefix}{first.message}"
        )


def validate_frozen_semantics(policy: Mapping[str, Any]) -> None:
    if policy.get("policy_id") != EXPECTED_POLICY_ID:
        raise HybridPolicyError("Unexpected hybrid policy_id.")
    if policy.get("status") != "CANDIDATES_FROZEN_BEFORE_IMPLEMENTATION":
        raise HybridPolicyError("Hybrid candidate freeze status is invalid.")
    if policy.get("method_id") != "hybrid":
        raise HybridPolicyError("Hybrid policy method_id is invalid.")
    if policy.get("class_order") != EXPECTED_CLASS_ORDER:
        raise HybridPolicyError("Frozen class order changed.")
    if policy.get("test_predictions_or_metrics") != "ABSENT":
        raise HybridPolicyError(
            "P5-R0 must not contain test predictions or metrics."
        )

    bindings = require_mapping(
        policy.get("baseline_bindings"),
        "baseline_bindings",
    )
    for name, expected_hash in EXPECTED_BASELINE_HASHES.items():
        binding = require_mapping(bindings.get(name), f"baseline_bindings.{name}")
        if binding.get("sha256") != expected_hash:
            raise HybridPolicyError(f"Accepted {name} SHA-256 changed.")

    prediction_contract = require_mapping(
        policy.get("prediction_time_contract"),
        "prediction_time_contract",
    )
    forbidden = prediction_contract.get("forbidden_inputs")
    if not isinstance(forbidden, list) or set(forbidden) != EXPECTED_FORBIDDEN_INPUTS:
        raise HybridPolicyError("Prediction-time forbidden inputs changed.")
    if prediction_contract.get("ground_truth_reader") != "evaluator_only":
        raise HybridPolicyError("Only the evaluator may read ground truth.")
    if prediction_contract.get("raw_method_outputs_immutable") is not True:
        raise HybridPolicyError("Raw method outputs must remain immutable.")

    candidates = policy.get("candidate_policies")
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise HybridPolicyError("Exactly two hybrid candidates are required.")
    candidate_ids = [candidate.get("candidate_id") for candidate in candidates]
    if candidate_ids != EXPECTED_CANDIDATE_ORDER:
        raise HybridPolicyError("Hybrid candidate order changed.")
    if [candidate.get("complexity_rank") for candidate in candidates] != [0, 1]:
        raise HybridPolicyError("Hybrid complexity ranks changed.")
    if candidates[0].get("disagreement_action") != "ABSTAIN":
        raise HybridPolicyError("Consensus candidate must abstain on disagreement.")
    guarded = candidates[1]
    guards = guarded.get("rule_fallback_guards")
    if not isinstance(guards, list) or len(guards) != 5:
        raise HybridPolicyError("Rule fallback must retain exactly five guards.")

    selection = require_mapping(
        policy.get("selection_protocol"),
        "selection_protocol",
    )
    if selection.get("selection_partition") != "validation":
        raise HybridPolicyError("Hybrid selection must use validation only.")
    if selection.get("held_out_partition") != "test":
        raise HybridPolicyError("The held-out partition must remain test.")
    if selection.get("test_access_before_selection_freeze") is not False:
        raise HybridPolicyError("Test access before policy selection is forbidden.")
    if selection.get("candidate_order") != EXPECTED_CANDIDATE_ORDER:
        raise HybridPolicyError("Selection candidate order changed.")
    if selection.get("metric_order") != EXPECTED_METRIC_ORDER:
        raise HybridPolicyError("Validation selection order changed.")
    if selection.get("selected_candidate") is not None:
        raise HybridPolicyError("P5-R0 cannot select a hybrid candidate.")
    if selection.get("selection_status") != "NOT_RUN":
        raise HybridPolicyError("P5-R0 selection status must remain NOT_RUN.")

    output = require_mapping(policy.get("output_contract"), "output_contract")
    if output.get("ml_location_or_prefix_copying") != "FORBIDDEN":
        raise HybridPolicyError("ML localization copying must remain forbidden.")
    if output.get("ground_truth_copying") != "FORBIDDEN":
        raise HybridPolicyError("Ground-truth copying must remain forbidden.")
    if output.get("accepted_fault_requires_rule_location_and_prefix") is not True:
        raise HybridPolicyError(
            "Accepted hybrid faults require rule-derived location and prefix."
        )


def verify_frozen_policy(
    policy_path: Path = DEFAULT_POLICY_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    policy = read_json(policy_path)
    validate_against_schema(policy, schema_path)
    validate_frozen_semantics(policy)
    bindings = require_mapping(policy["baseline_bindings"], "baseline_bindings")
    selection = require_mapping(policy["selection_protocol"], "selection_protocol")
    candidates = policy["candidate_policies"]
    assert isinstance(candidates, list)
    return {
        "policy_id": policy["policy_id"],
        "policy_sha256": sha256_file(policy_path),
        "status": "HYBRID_POLICY_CANDIDATES_FROZEN_VERIFIED",
        "candidate_ids": [candidate["candidate_id"] for candidate in candidates],
        "selection_partition": selection["selection_partition"],
        "held_out_partition": selection["held_out_partition"],
        "baseline_hash_bindings": sorted(EXPECTED_BASELINE_HASHES),
        "campaign_id": require_mapping(
            bindings["campaign"], "baseline_bindings.campaign"
        )["campaign_id"],
        "test_predictions_or_metrics": policy["test_predictions_or_metrics"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the frozen P5-R0 hybrid policy without prediction."
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY_PATH,
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        result = verify_frozen_policy(arguments.policy, arguments.schema)
    except HybridPolicyError as error:
        print(f"[ERROR] {error}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
