import inspect
from pathlib import Path
from src.expansion.x6_r1_gate import verify_x6_r1_source
ROOT=Path(__file__).resolve().parents[2]
def test_x6_r1_source_gate():
 plan=verify_x6_r1_source(ROOT);assert len(plan["source_bindings"])==12 and plan["rule_id"]=="R_X6_PERFORMANCE_001" and "six-decimal" in plan["threshold_input_contract"]

def test_x6_r1_source_gate_uses_only_transitive_predecessor_entrypoint():
 source=inspect.getsource(verify_x6_r1_source)
 assert "verify_x6_r0_6(root)" in source
 assert "verify_x6_r0_4_f1_runtime_parameter_freeze(root)" not in source
 assert "verify_x6_r0_5(root)" not in source
