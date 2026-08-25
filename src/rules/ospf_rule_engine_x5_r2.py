from __future__ import annotations

from pathlib import Path

from src.contracts.expansion import validate_diagnosis_result_v2

SIGNATURE = {"ospf_adjacency_full": True, "ospf_route_advertised": False, "ospf_route_installed": False, "route_filter_allows_prefix": False}


def diagnose_x5_r2_route_suppression(vector: dict[str, object], *, repository_root: Path) -> dict[str, object]:
    values = vector["values"]
    observed = {key: values[key]["value"] for key in SIGNATURE}
    matched = observed == SIGNATURE
    prediction = {"fault_type": "route_filtering_or_advertisement_problem", "score": 1.0, "location": "r3:ospf", "affected_resource": "ospf_prefix_10.51.3.0_24"} if matched else None
    result = {"schema_version": 2, "result_id": vector["vector_id"] + ":rule_based_v2", "input_vector_id": vector["vector_id"], "method": "rule_based_v2", "truth_model": "single_fault", "status": "diagnosed" if matched else "abstained", "prediction": prediction, "ranked_candidates": [prediction] if prediction else [], "evidence_assessment": {"completeness_ratio": 1.0, "conflict_detected": not matched, "missing_domains": []}, "explanation_refs": ["rule:R_X5_OSPF_002"] if matched else ["conflict:x5_r2_signature_not_exact"]}
    validate_diagnosis_result_v2(result, repository_root=repository_root)
    return result
