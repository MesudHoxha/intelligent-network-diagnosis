import copy,json
from pathlib import Path
from src.collection.ospf_state_collector_x5_r4 import target_state
from src.expansion.x5_r4_gate import verify_x5_r4_gate
from src.rules.ospf_rule_engine_x5_r4 import diagnose_route_suppression_v2_corrected
ROOT=Path(__file__).resolve().parents[2]
def test_x5_r4_contract_is_hash_bound_and_preserves_historical_c4()->None:
 assert verify_x5_r4_gate(ROOT)["corrections"]["x5_r2_marker"].endswith("NOT_AN_ATTACHED_FILTER")
def test_corrected_r2_unavailable_evidence_fails_closed()->None:
 vector=json.loads((ROOT/"data/raw/x5_r2/x5-r2-route-filter-20260825T124415388794Z-9117d813357e4d3d8cd74e68c6c2d9d1/parsed/feature_vector_v2.json").read_text());vector=copy.deepcopy(vector);vector["values"]["ospf_route_installed"]={"value":None,"availability":"collection_unavailable"};result=diagnose_route_suppression_v2_corrected(vector,repository_root=ROOT);assert result["status"]=="insufficient_evidence" and result["evidence_assessment"]["completeness_ratio"]==0.75
def test_targeted_adjacency_does_not_aggregate_another_full_neighbor()->None:
 raw={"stdout":json.dumps({"neighbors":{"3.3.3.3":[{"address":"10.51.23.2","ifaceName":"eth2:10.51.23.1","converged":"2-Way"}],"1.1.1.1":[{"address":"10.51.12.1","ifaceName":"eth1:10.51.12.2","converged":"Full"}]}})}
 assert target_state(raw)=={"r2_r3_state":"2-Way","r2_r3_full":False,"r1_r2_state":"Full","r1_r2_full":True}
