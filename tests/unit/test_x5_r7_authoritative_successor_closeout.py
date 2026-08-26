from pathlib import Path
from src.expansion.x5_r7_closeout_gate import verify_x5_r7_closeout
ROOT=Path(__file__).resolve().parents[2]
def test_x5_r7_binds_corrected_authoritative_runs()->None:
 r=verify_x5_r7_closeout(ROOT,verify_materialized=True);assert len(r["c5_artifacts"])==13
