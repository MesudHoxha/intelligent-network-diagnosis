from pathlib import Path
from src.expansion.x6_r0_gate import verify_x6_r0_gate
ROOT=Path(__file__).resolve().parents[2]
def test_x6_r0_has_four_disjoint_controlled_performance_designs()->None:
 plan=verify_x6_r0_gate(ROOT);assert len({tuple(row["signature"]) for row in plan["faults"]})==4;assert all(not value for value in plan["runtime_authorization"].values())
