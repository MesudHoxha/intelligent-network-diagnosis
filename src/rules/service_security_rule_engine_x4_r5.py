from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from src.contracts.expansion import validate_diagnosis_result_v2, validate_feature_vector_v2
from src.rules.service_security_rule_engine_x4_r1 import FEATURE_IDS, SIGNATURE as D1_SIGNATURE
from src.rules.service_security_rule_engine_x4_r2 import D2_SIGNATURE
from src.rules.service_security_rule_engine_x4_r3 import D3_SIGNATURE
from src.rules.service_security_rule_engine_x4_r4 import D4_SIGNATURE


ROOT = Path(__file__).resolve().parents[2]
D5_SIGNATURE = {"dhcp_server_reachable": True, "dhcp_lease_obtained": True, "dhcp_lease_matches_expected_scope": True, "dns_server_reachable": True, "dns_query_succeeds": True, "dns_answer_matches_expected": True, "service_process_running": True, "service_port_reachable": False, "service_flow_blocked_by_policy": True}


def diagnose_dhcp_dns_service_security_v2_r5(vector: Mapping[str, object], *, repository_root: Path = ROOT) -> dict[str, object]:
    catalog = json.loads((repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text(encoding="utf-8")); validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    values = vector.get("values"); assert isinstance(values, Mapping)
    unavailable = [name for name in FEATURE_IDS if not isinstance(values.get(name), Mapping) or values[name].get("availability") != "observed"]
    observed = {name: values[name].get("value") for name in FEATURE_IDS if isinstance(values.get(name), Mapping)}
    if unavailable:
        status, prediction, candidates, refs = "insufficient_evidence", None, [], ["missing:" + name for name in unavailable]
    elif observed == D1_SIGNATURE:
        prediction = {"fault_type": "dhcp_server_unavailable", "score": 1.0, "location": "dhcp_server", "affected_resource": "dhcp_service_endpoint_udp_67"}; status, candidates, refs = "diagnosed", [prediction], ["rule:R_X4_SERVICE_SECURITY_001"]
    elif observed == D2_SIGNATURE:
        prediction = {"fault_type": "dhcp_pool_misconfiguration", "score": 1.0, "location": "dhcp_server", "affected_resource": "dhcp_pool_scope"}; status, candidates, refs = "diagnosed", [prediction], ["rule:R_X4_SERVICE_SECURITY_002"]
    elif observed == D3_SIGNATURE:
        prediction = {"fault_type": "dns_service_down", "score": 1.0, "location": "dns_server", "affected_resource": "dns_service_endpoint_udp_53"}; status, candidates, refs = "diagnosed", [prediction], ["rule:R_X4_SERVICE_SECURITY_003"]
    elif observed == D4_SIGNATURE:
        prediction = {"fault_type": "wrong_dns_record", "score": 1.0, "location": "dns_server", "affected_resource": "dns_record_app_x4_test"}; status, candidates, refs = "diagnosed", [prediction], ["rule:R_X4_SERVICE_SECURITY_004"]
    elif observed == D5_SIGNATURE:
        prediction = {"fault_type": "firewall_service_block", "score": 1.0, "location": "app_server", "affected_resource": "app_server_tcp_8080_policy"}; status, candidates, refs = "diagnosed", [prediction], ["rule:R_X4_SERVICE_SECURITY_005"]
    else:
        status, prediction, candidates, refs = "abstained", None, [], ["conflict:x4_r1_r2_r3_r4_r5_signatures_not_exact"]
    result = {"schema_version": 2, "result_id": str(vector["vector_id"]) + ":rule_based_v2", "input_vector_id": vector["vector_id"], "method": "rule_based_v2", "truth_model": "single_fault", "status": status, "prediction": prediction, "ranked_candidates": candidates, "evidence_assessment": {"completeness_ratio": (len(FEATURE_IDS) - len(unavailable)) / len(FEATURE_IDS), "conflict_detected": status == "abstained", "missing_domains": ["services"] if unavailable else []}, "explanation_refs": refs}
    validate_diagnosis_result_v2(result, repository_root=repository_root)
    return result
