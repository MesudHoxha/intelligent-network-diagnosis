from __future__ import annotations
from pathlib import Path
from src.contracts.expansion import validate_diagnosis_result_v2

FEATURES=("ospf_adjacency_full","ospf_route_advertised","ospf_route_installed","route_filter_allows_prefix")
SIGNATURE={"ospf_adjacency_full":False,"ospf_route_advertised":False,"ospf_route_installed":False,"route_filter_allows_prefix":True}

def diagnose_targeted_ospf_adjacency_failure_v2(vector:dict[str,object], *, repository_root:Path)->dict[str,object]:
    values=vector["values"]; missing=[name for name in FEATURES if values[name]["availability"]!="observed"]
    observed={name:values[name]["value"] for name in FEATURES}
    if missing: status,pred,candidates,refs="insufficient_evidence",None,[],["missing:"+name for name in missing]
    elif observed==SIGNATURE: status,pred,candidates,refs="diagnosed",{"fault_type":"dynamic_routing_adjacency_failure","score":1.0,"location":"r2:eth2","affected_resource":"ospf_adjacency_r2_r3"},[{"fault_type":"dynamic_routing_adjacency_failure","score":1.0,"location":"r2:eth2","affected_resource":"ospf_adjacency_r2_r3"}],["rule:R_X5_OSPF_001"]
    else: status,pred,candidates,refs="abstained",None,[],["conflict:x5_r4_signature_not_exact"]
    result={"schema_version":2,"result_id":vector["vector_id"]+":rule_based_v2","input_vector_id":vector["vector_id"],"method":"rule_based_v2","truth_model":"single_fault","status":status,"prediction":pred,"ranked_candidates":candidates,"evidence_assessment":{"completeness_ratio":(len(FEATURES)-len(missing))/len(FEATURES),"conflict_detected":status=="abstained","missing_domains":["routing"] if missing else []},"explanation_refs":refs};validate_diagnosis_result_v2(result,repository_root=repository_root);return result

def diagnose_route_suppression_v2_corrected(vector:dict[str,object], *, repository_root:Path)->dict[str,object]:
    values=vector["values"]; missing=[name for name in FEATURES if values[name]["availability"]!="observed"];observed={name:values[name]["value"] for name in FEATURES};signature={"ospf_adjacency_full":True,"ospf_route_advertised":False,"ospf_route_installed":False,"route_filter_allows_prefix":False}
    if missing: status,pred,candidates,refs="insufficient_evidence",None,[],["missing:"+name for name in missing]
    elif observed==signature: status,pred,candidates,refs="diagnosed",{"fault_type":"route_filtering_or_advertisement_problem","score":1.0,"location":"r3:ospf","affected_resource":"ospf_prefix_10.51.3.0_24"},[{"fault_type":"route_filtering_or_advertisement_problem","score":1.0,"location":"r3:ospf","affected_resource":"ospf_prefix_10.51.3.0_24"}],["rule:R_X5_OSPF_002"]
    else: status,pred,candidates,refs="abstained",None,[],["conflict:x5_r2_signature_not_exact"]
    result={"schema_version":2,"result_id":vector["vector_id"]+":rule_based_v2","input_vector_id":vector["vector_id"],"method":"rule_based_v2","truth_model":"single_fault","status":status,"prediction":pred,"ranked_candidates":candidates,"evidence_assessment":{"completeness_ratio":(len(FEATURES)-len(missing))/len(FEATURES),"conflict_detected":status=="abstained","missing_domains":["routing"] if missing else []},"explanation_refs":refs};validate_diagnosis_result_v2(result,repository_root=repository_root);return result
