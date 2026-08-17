from __future__ import annotations

from pathlib import Path
from typing import Mapping

from src.collection.l2_vlan_state_collector import _load_object
from src.contracts.expansion import validate_diagnosis_result_v2, validate_feature_vector_v2
from src.expansion.x3_wrong_access_vlan import X3WrongAccessVlanError


ROOT = Path(__file__).resolve().parents[2]
RULE_ID = "R_X3_L2_VLAN_001"
REQUIRED_FEATURES = (
    "access_vlan_matches_expected",
    "vlan_exists_on_target",
    "vlan_allowed_on_trunk",
    "native_vlan_matches_peer",
    "fdb_location_matches_expected",
)
WRONG_ACCESS_VLAN_SIGNATURE = {
    "access_vlan_matches_expected": False,
    "vlan_exists_on_target": True,
    "vlan_allowed_on_trunk": True,
    "native_vlan_matches_peer": True,
    "fdb_location_matches_expected": False,
}


def diagnose_wrong_access_vlan_v2(
    vector: Mapping[str, object],
    *,
    location_node: str,
    affected_resource: str,
    repository_root: Path = ROOT,
) -> dict[str, object]:
    catalog = _load_object(
        repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"
    )
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    values = vector.get("values")
    if not isinstance(values, Mapping):
        raise X3WrongAccessVlanError("X3-R1 Feature Vector v2 has no values.")

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
    completeness = (len(REQUIRED_FEATURES) - len(unavailable)) / len(REQUIRED_FEATURES)
    candidate = {
        "fault_type": "wrong_access_vlan",
        "score": 1.0,
        "location": location_node,
        "affected_resource": affected_resource,
    }
    if unavailable:
        status = "insufficient_evidence"
        prediction = None
        candidates: list[dict[str, object]] = []
        missing_domains = ["l2_vlan"]
        explanation_refs = [f"missing:{name}" for name in unavailable]
    elif observed == WRONG_ACCESS_VLAN_SIGNATURE:
        status = "diagnosed"
        prediction = candidate
        candidates = [candidate]
        missing_domains = []
        explanation_refs = [f"rule:{RULE_ID}"]
    else:
        status = "abstained"
        prediction = None
        candidates = []
        missing_domains = []
        explanation_refs = ["conflict:x3_r1_signature_not_exact"]
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
