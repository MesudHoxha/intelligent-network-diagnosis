from __future__ import annotations
import json
from pathlib import Path
from typing import Mapping
from src.contracts.expansion import validate_diagnosis_result_v2, validate_feature_vector_v2
FEATURES=("ospf_adjacency_full","ospf_route_advertised","ospf_route_installed","route_filter_allows_prefix")
SIGNATURE={"ospf_adjacency_full":False,"ospf_route_advertised":False,"ospf_route_installed":False,"route_filter_allows_prefix":True}
def diagnose_ospf_adjacency_failure_v2(vector: Mapping[str,object], *, repository_root: Path) -> dict[str,object]:
 catalog=json.loads((repository_root/"plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text()); validate_feature_vector_v2(vector,catalog,repository_root=repository_root); values=vector["values"]; unavailable=[x for x in FEATURES if values[x]["availability"]!="observed"]; observed={x:values[x]["value"] for x in FEATURES}
 if unavailable: status,pred,candidates,refs="insufficient_evidence",None,[],["missing:"+x for x in unavailable]
 elif observed==SIGNATURE: status,pred,candidates,refs="diagnosed",{"fault_type":"dynamic_routing_adjacency_failure","score":1.0,"location":"r2:eth2","affected_resource":"ospf_adjacency_r2_r3"},[{"fault_type":"dynamic_routing_adjacency_failure","score":1.0,"location":"r2:eth2","affected_resource":"ospf_adjacency_r2_r3"}],["rule:R_X5_OSPF_001"]
 else: status,pred,candidates,refs="abstained",None,[],["conflict:x5_r1_signature_not_exact"]
 result={"schema_version":2,"result_id":str(vector["vector_id"])+":rule_based_v2","input_vector_id":vector["vector_id"],"method":"rule_based_v2","truth_model":"single_fault","status":status,"prediction":pred,"ranked_candidates":candidates,"evidence_assessment":{"completeness_ratio":(len(FEATURES)-len(unavailable))/len(FEATURES),"conflict_detected":status=="abstained","missing_domains":["routing"] if unavailable else []},"explanation_refs":refs}; validate_diagnosis_result_v2(result,repository_root=repository_root); return result
