from pathlib import Path
from src.expansion.x6_r1_2_gate import verify_x6_r1_2
def test_x6_r1_2_future_hardening_is_source_only():
 p=verify_x6_r1_2(Path(__file__).resolve().parents[2]); assert not any(p['runtime_scientific_authorization'].values())
