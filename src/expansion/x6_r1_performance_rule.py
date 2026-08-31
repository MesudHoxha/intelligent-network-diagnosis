"""Exact conditional F1 rule, fail-closed on Feature Vector v2."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from src.collection.x6_performance_collector import FEATURES
from src.collection.x6_r0_3_pre_runtime_validation import validate_threshold_manifest
from src.contracts.expansion import validate_diagnosis_result_v2, validate_feature_vector_v2


def predicates_from_vector(vector: Mapping[str, object], threshold: Mapping[str, object], *, repository_root: Path) -> dict[str, bool] | None:
    catalog = json.loads((repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text())
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    validate_threshold_manifest(threshold, repository_root=repository_root)
    values = vector["values"]
    if any(values[name]["availability"] != "observed" for name in FEATURES):
        return None
    bounds = {row["feature_id"]: row for row in threshold["features"]}
    return {
        "loss_above_baseline": float(values["packet_loss_ratio"]["value"]) > float(bounds["packet_loss_ratio"]["upper_threshold"]),
        "latency_within_baseline": float(values["round_trip_latency_ms_p95"]["value"]) <= float(bounds["round_trip_latency_ms_p95"]["upper_threshold"]),
        "throughput_within_baseline": float(values["throughput_mbps"]["value"]) >= float(bounds["throughput_mbps"]["lower_threshold"]),
        "utilization_within_baseline": float(values["interface_utilization_ratio"]["value"]) <= float(bounds["interface_utilization_ratio"]["upper_threshold"]),
        "queue_delta_zero": values["queue_drop_count"]["value"] == 0,
        "rate_limit_false": values["rate_limit_detected"]["value"] is False,
    }


def diagnose_x6_r1(vector: dict[str, object], threshold: dict[str, object], *, repository_root: Path) -> dict[str, object]:
    predicates = predicates_from_vector(vector, threshold, repository_root=repository_root)
    missing = [] if predicates is not None else [name for name in FEATURES if vector["values"][name]["availability"] != "observed"]
    if predicates is None:
        status, prediction, candidates, refs = "insufficient_evidence", None, [], ["missing:" + name for name in missing]
    elif all(predicates.values()):
        prediction = {"fault_type": "packet_loss", "score": 1.0, "location": "r2:eth2", "affected_resource": "x6_top_01_r2_to_r3_egress"}
        status, candidates, refs = "diagnosed", [prediction], ["rule:R_X6_PERFORMANCE_001"]
    else:
        status, prediction, candidates, refs = "abstained", None, [], ["conflict:x6_f1_conditional_signature_not_exact"]
    result = {"schema_version": 2, "result_id": vector["vector_id"] + ":rule_based_v2", "input_vector_id": vector["vector_id"], "method": "rule_based_v2", "truth_model": "single_fault", "status": status, "prediction": prediction, "ranked_candidates": candidates, "evidence_assessment": {"completeness_ratio": (6 - len(missing)) / 6, "conflict_detected": status == "abstained", "missing_domains": ["performance"] if missing else []}, "explanation_refs": refs}
    validate_diagnosis_result_v2(result, repository_root=repository_root)
    return result
