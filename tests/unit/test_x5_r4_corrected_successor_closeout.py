from pathlib import Path

from src.expansion.x5_r4_closeout_gate import verify_x5_r4_corrected_successor_receipt
import pytest
from tests.accepted_runtime import require_materialized_receipts


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "plans/expansion/X5_R4_OSPF_CORRECTED_SUCCESSOR_RECEIPT_V1.json"


@pytest.mark.accepted_runtime
def test_x5_r4_corrected_successor_receipt_hash_binds_corrected_c4_and_unchanged_c5() -> None:
    require_materialized_receipts(ROOT, RECEIPT, ROOT / "plans/expansion/X5_R3_OSPF_DYNAMIC_ROUTING_EVIDENCE_RECEIPT_V1.json")
    receipt = verify_x5_r4_corrected_successor_receipt(repository_root=ROOT, verify_materialized=True)
    assert receipt["summary"]["corrected_c4_authoritative"] is True
    assert receipt["summary"]["c5_unchanged_accepted"] is True
