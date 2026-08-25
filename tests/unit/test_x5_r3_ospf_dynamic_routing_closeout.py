from pathlib import Path

from src.expansion.x5_r3_gate import SLICES, verify_x5_r3_receipt, verify_x5_r3_source_gate

ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "plans/expansion/X5_R3_OSPF_DYNAMIC_ROUTING_EVIDENCE_RECEIPT_V1.json"


def test_x5_r3_binds_the_exact_two_disjoint_ospf_slices() -> None:
    plan = verify_x5_r3_source_gate(ROOT)
    assert plan["status"] == "ACCEPTED_SOURCE_CLOSEOUT"
    assert plan["track"]["next_release"] == "X6_R0_PERFORMANCE_FAULT_DESIGN_GATE"
    assert len(plan["source_bindings"]) == 13
    assert len({signature for _, _, signature in SLICES.values()}) == 2


def test_x5_r3_materialized_receipt_reverifies_c4_and_c5() -> None:
    receipt = verify_x5_r3_receipt(RECEIPT, repository_root=ROOT, verify_materialized=True)
    assert receipt["evidence_kind"] == "ACCEPTED_RUNTIME_EVIDENCE_NOT_RECOVERED_OR_REPLACED"
    assert receipt["summary"] == {"run_count": 2, "all_completed": True, "all_diagnosed": True, "all_restored": True, "all_baselines_valid": True, "all_raw_hashes_verified": True}
