from __future__ import annotations

from pathlib import Path
from typing import Mapping

from src.collection.l2_vlan_state_collector_v3 import _load_object
from src.contracts.expansion import validate_diagnosis_result_v2, validate_feature_vector_v2
from src.expansion.x3_native_vlan_mismatch import X3NativeVlanMismatchError
from src.rules.l2_vlan_rule_engine_x3_r3 import REQUIRED_FEATURES, RULES as R3_RULES


ROOT = Path(__file__).resolve().parents[2]
RULES = (*R3_RULES, ("R_X3_L2_VLAN_004", "native_vlan_mismatch", {
    "access_vlan_matches_expected": True,
    "vlan_exists_on_target": True,
    "vlan_allowed_on_trunk": True,
    "native_vlan_matches_peer": False,
    "fdb_location_matches_expected": True,
}))


def diagnose_l2_vlan_x3_r4_v2(vector: Mapping[str, object], *, location_node: str, affected_resource: str, repository_root: Path = ROOT) -> dict[str, object]:
    catalog = _load_object(repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json")
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    values = vector.get("values")
    if not isinstance(values, Mapping):
        raise X3NativeVlanMismatchError("X3-R4 Feature Vector v2 has no values.")
    unavailable = [name for name in REQUIRED_FEATURES if not isinstance(values.get(name), Mapping) or values[name].get("availability") != "observed"]
    observed = {name: values[name].get("value") for name in REQUIRED_FEATURES if isinstance(values.get(name), Mapping)}
    matched = next(((rule_id, fault_type) for rule_id, fault_type, signature in RULES if observed == signature), None)
    completeness = (len(REQUIRED_FEATURES) - len(unavailable)) / len(REQUIRED_FEATURES)
    if unavailable:
        status, prediction, candidates, missing, refs = "insufficient_evidence", None, [], ["l2_vlan"], [f"missing:{name}" for name in unavailable]
    elif matched is not None:
        rule_id, fault_type = matched
        prediction = {"fault_type": fault_type, "score": 1.0, "location": location_node, "affected_resource": affected_resource}
        status, candidates, missing, refs = "diagnosed", [prediction], [], [f"rule:{rule_id}"]
    else:
        status, prediction, candidates, missing, refs = "abstained", None, [], [], ["conflict:x3_r4_signature_not_exact"]
    result = {"schema_version": 2, "result_id": f"{vector['vector_id']}:rule_based_v2", "input_vector_id": vector["vector_id"], "method": "rule_based_v2", "truth_model": "single_fault", "status": status, "prediction": prediction, "ranked_candidates": candidates, "evidence_assessment": {"completeness_ratio": completeness, "conflict_detected": status == "abstained", "missing_domains": missing}, "explanation_refs": refs}
    validate_diagnosis_result_v2(result, repository_root=repository_root)
    return result
