from __future__ import annotations

from pathlib import Path
from typing import Mapping

from src.collection.l2_vlan_state_collector_v3 import _load_object
from src.contracts.expansion import validate_diagnosis_result_v2, validate_feature_vector_v2
from src.expansion.x3_vlan_not_allowed_on_trunk import X3VlanNotAllowedOnTrunkError


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FEATURES = (
    "access_vlan_matches_expected",
    "vlan_exists_on_target",
    "vlan_allowed_on_trunk",
    "native_vlan_matches_peer",
    "fdb_location_matches_expected",
)
RULES = (
    (
        "R_X3_L2_VLAN_001",
        "wrong_access_vlan",
        {
            "access_vlan_matches_expected": False,
            "vlan_exists_on_target": True,
            "vlan_allowed_on_trunk": True,
            "native_vlan_matches_peer": True,
            "fdb_location_matches_expected": False,
        },
    ),
    (
        "R_X3_L2_VLAN_002",
        "vlan_missing",
        {
            "access_vlan_matches_expected": False,
            "vlan_exists_on_target": False,
            "vlan_allowed_on_trunk": False,
            "native_vlan_matches_peer": True,
            "fdb_location_matches_expected": False,
        },
    ),
    (
        "R_X3_L2_VLAN_003",
        "vlan_not_allowed_on_trunk",
        {
            "access_vlan_matches_expected": True,
            "vlan_exists_on_target": True,
            "vlan_allowed_on_trunk": False,
            "native_vlan_matches_peer": True,
            "fdb_location_matches_expected": True,
        },
    ),
)


def diagnose_l2_vlan_x3_r3_v2(
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
        raise X3VlanNotAllowedOnTrunkError("X3-R3 Feature Vector v2 has no values.")

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
    matched = next(
        (
            (rule_id, fault_type)
            for rule_id, fault_type, signature in RULES
            if observed == signature
        ),
        None,
    )

    if unavailable:
        status = "insufficient_evidence"
        prediction = None
        candidates: list[dict[str, object]] = []
        missing_domains = ["l2_vlan"]
        explanation_refs = [f"missing:{name}" for name in unavailable]
    elif matched is not None:
        rule_id, fault_type = matched
        candidate = {
            "fault_type": fault_type,
            "score": 1.0,
            "location": location_node,
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
        explanation_refs = ["conflict:x3_r3_signature_not_exact"]

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
