from pathlib import Path
import pytest

from tests.accepted_runtime import require_materialized_receipts
from src.expansion.x5_r7_closeout_gate import verify_x5_r7_closeout
ROOT=Path(__file__).resolve().parents[2]
RECEIPT=ROOT / "plans/expansion/X5_R7_AUTHORITATIVE_SUCCESSOR_RECEIPT_V1.json"


@pytest.mark.accepted_runtime
def test_x5_r7_binds_corrected_authoritative_runs()->None:
 require_materialized_receipts(ROOT, RECEIPT, ROOT / "plans/expansion/X5_R4_OSPF_CORRECTED_SUCCESSOR_RECEIPT_V1.json")
 r=verify_x5_r7_closeout(ROOT,verify_materialized=True);assert len(r["c5_artifacts"])==13
