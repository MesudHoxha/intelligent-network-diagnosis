from __future__ import annotations

from pathlib import Path
from typing import Mapping

from src.collection.subnet_mask_state_collector import _load_object
from src.contracts.expansion import (
    validate_diagnosis_result_v2,
    validate_feature_vector_v2,
)
from src.expansion.x2_addressing import X2AddressingError
from src.rules.addressing_rule_engine_v2 import WRONG_IP_SIGNATURE


ROOT = Path(__file__).resolve().parents[2]
WRONG_IP_RULE_ID = "R_X2_ADDRESSING_001"
WRONG_SUBNET_MASK_RULE_ID = "R_X2_ADDRESSING_002"
REQUIRED_FEATURES = (
    "source_address_matches_expected",
    "source_prefix_matches_expected",
    "source_default_route_present",
    "duplicate_address_detected",
)
WRONG_SUBNET_MASK_SIGNATURE = {
    "source_address_matches_expected": True,
    "source_prefix_matches_expected": False,
    "source_default_route_present": True,
    "duplicate_address_detected": False,
}
SIGNATURES = (
    (WRONG_IP_SIGNATURE, "wrong_ip_address", WRONG_IP_RULE_ID),
    (
        WRONG_SUBNET_MASK_SIGNATURE,
        "wrong_subnet_mask",
        WRONG_SUBNET_MASK_RULE_ID,
    ),
)


def diagnose_addressing_v2(
    vector: Mapping[str, object],
    *,
    source_node: str,
    affected_resource: str,
    repository_root: Path = ROOT,
) -> dict[str, object]:
    catalog = _load_object(
        repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"
    )
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    values = vector.get("values")
    if not isinstance(values, Mapping):
        raise X2AddressingError("X2-R2 Feature Vector v2 has no values.")

    unavailable = [
        name
        for name in REQUIRED_FEATURES
        if not isinstance(values.get(name), Mapping)
        or values[name].get("availability") != "observed"
    ]
    observed = {
        name: values[name].get("value")
        for name in REQUIRED_FEATURES
        if isinstance(values.get(name), Mapping)
    }
    completeness = (len(REQUIRED_FEATURES) - len(unavailable)) / len(
        REQUIRED_FEATURES
    )
    matches = [row for row in SIGNATURES if observed == row[0]]
    if unavailable:
        status = "insufficient_evidence"
        prediction = None
        candidates: list[dict[str, object]] = []
        missing_domains = ["addressing"]
        explanation_refs = [f"missing:{name}" for name in unavailable]
    elif len(matches) == 1:
        _, fault_type, rule_id = matches[0]
        candidate = {
            "fault_type": fault_type,
            "score": 1.0,
            "location": source_node,
            "affected_resource": affected_resource,
        }
        status = "diagnosed"
        prediction = candidate
        candidates = [candidate]
        missing_domains = []
        explanation_refs = [f"rule:{rule_id}"]
    else:
        status = "abstained"
        prediction = None
        candidates = []
        missing_domains = []
        explanation_refs = ["conflict:x2_r2_addressing_signature_not_exact"]

    result = {
        "schema_version": 2,
        "result_id": f"{vector['vector_id']}:rule_based_v2",
        "input_vector_id": vector["vector_id"],
        "method": "rule_based_v2",
        "truth_model": "single_fault",
        "status": status,
        "prediction": prediction,
        "ranked_candidates": candidates,
        "evidence_assessment": {
            "completeness_ratio": completeness,
            "conflict_detected": status == "abstained",
            "missing_domains": missing_domains,
        },
        "explanation_refs": explanation_refs,
    }
    validate_diagnosis_result_v2(result, repository_root=repository_root)
    return result
