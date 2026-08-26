from pathlib import Path

import pytest

from src.expansion.x5_r10_closeout_gate import verify_x5_r10_closeout
from tests.accepted_runtime import require_materialized_receipts


ROOT = Path(__file__).resolve().parents[2]
RECEIPT = ROOT / "plans/expansion/X5_R10_CRASH_SAFE_AUTHORITATIVE_SUCCESSOR_RECEIPT_V1.json"


def test_x5_r10_source_closeout_boundary_is_frozen() -> None:
    receipt = verify_x5_r10_closeout(ROOT)
    assert receipt["summary"]["c4_signature"] == [False, False, False, True]
    assert receipt["summary"]["c5_signature"] == [True, False, False, False]


@pytest.mark.accepted_runtime
def test_x5_r10_binds_only_authoritative_materialized_runs() -> None:
    require_materialized_receipts(ROOT, RECEIPT)
    receipt = verify_x5_r10_closeout(ROOT, verify_materialized=True)
    assert len(receipt["runs"][1]["artifacts"]) == 22
