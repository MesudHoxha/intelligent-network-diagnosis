from __future__ import annotations

from pathlib import Path

from src.expansion.scope_gate import verify_scope_gate
from src.expansion.x1_gate import verify_x1_gate
from src.expansion.x2_r5_gate import verify_x2_r5_source_gate
from src.expansion.x3_gate import verify_x3_gate
from src.expansion.x3_r1_gate import verify_x3_r1_gate


ROOT = Path(__file__).resolve().parents[2]


def test_x0_through_x3_r1_gates_compose() -> None:
    assert verify_scope_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x1_gate(ROOT)["status"] == "ACCEPTED_CONTRACT_ONLY"
    assert verify_x2_r5_source_gate(ROOT)["status"] == "ACCEPTED_SOURCE_CLOSEOUT"
    assert verify_x3_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x3_r1_gate(ROOT)["status"] == "IMPLEMENTED_RUNTIME_SLICE"


def test_x3_r1_preserves_tagged_native_flow_separation() -> None:
    manifest = verify_x3_r1_gate(ROOT)
    runtime = manifest["topology_runtime"]
    assert runtime["tagged_flow"] == "hosta_to_hostb_vlan_10"
    assert runtime["native_flow_preserved"] == "hostc_to_hostd_vlan_99"
    assert runtime["wrong_vlan"] == 20


def test_x3_r1_creates_no_dataset_model_or_metric_authority() -> None:
    manifest = verify_x3_r1_gate(ROOT)
    authorization = manifest["runtime_authorization"]
    assert authorization["dataset_generation"] is False
    assert authorization["model_fit_or_selection"] is False
    assert authorization["estimator_deserialization"] is False
    assert authorization["metric_calculation"] is False
    assert authorization["multiple_fault_execution"] is False
