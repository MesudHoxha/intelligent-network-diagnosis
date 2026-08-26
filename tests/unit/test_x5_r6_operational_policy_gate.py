from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.collection.ospf_state_collector_x5_r6 import _json_object
from src.expansion.x5_r6_gate import X5R6GateError, verify_x5_r6_gate
from src.rules.ospf_rule_engine_x5_r6 import diagnose_x5_r6_operational_policy_c5


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "plans/expansion/X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION_V1.json"


def test_x5_r6_gate_binds_operational_attached_policy() -> None:
    plan = verify_x5_r6_gate(ROOT)
    assert plan["slice"]["signature"] == {"ospf_adjacency_full": True, "ospf_route_advertised": False, "ospf_route_installed": False, "route_filter_allows_prefix": False}
    assert plan["mutation"]["forbidden_action"] == "remove network 10.51.3.0/24 area 0"


def test_x5_r6_rejects_empty_or_malformed_structured_observations() -> None:
    assert _json_object({"return_code": 0, "stdout": ""}, allow_empty=False) is None
    assert _json_object({"return_code": 0, "stdout": "not-json"}, allow_empty=True) is None
    assert _json_object({"return_code": 0, "stdout": "{}"}, allow_empty=True) == {}


def test_x5_r6_rule_validates_vector_and_fails_closed_for_unavailable_evidence() -> None:
    vector = json.loads((ROOT / "data/raw/x5_r2/x5-r2-route-filter-20260825T124415388794Z-9117d813357e4d3d8cd74e68c6c2d9d1/parsed/feature_vector_v2.json").read_text())
    vector = copy.deepcopy(vector); vector["values"]["ospf_route_installed"] = {"value": None, "availability": "collection_unavailable"}
    result = diagnose_x5_r6_operational_policy_c5(vector, repository_root=ROOT)
    assert result["status"] == "insufficient_evidence" and result["evidence_assessment"]["completeness_ratio"] == 0.75


def test_x5_r6_gate_rejects_runtime_authorization_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    changed = copy.deepcopy(json.loads(PLAN.read_text())); changed["runtime_authorization"]["dataset_generation"] = True
    import src.expansion.x5_r6_gate as gate
    monkeypatch.setattr(gate, "verify_x5_r5_c5_operational_policy_correction_gate", lambda root: {"track": {"next_release": "X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION"}})
    monkeypatch.setattr(gate.json, "loads", lambda value: changed)
    with pytest.raises(X5R6GateError): verify_x5_r6_gate(ROOT)
