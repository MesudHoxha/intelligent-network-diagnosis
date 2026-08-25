from pathlib import Path

from src.expansion.x5_r4_closeout_gate import verify_x5_r4_corrected_successor_receipt


ROOT = Path(__file__).resolve().parents[2]


def test_x5_r4_corrected_successor_receipt_hash_binds_corrected_c4_and_unchanged_c5() -> None:
    receipt = verify_x5_r4_corrected_successor_receipt(repository_root=ROOT, verify_materialized=True)
    assert receipt["summary"]["corrected_c4_authoritative"] is True
    assert receipt["summary"]["c5_unchanged_accepted"] is True
