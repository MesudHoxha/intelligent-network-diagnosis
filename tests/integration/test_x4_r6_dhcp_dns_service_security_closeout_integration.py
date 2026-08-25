from pathlib import Path

from src.expansion.scope_gate import verify_scope_gate
from src.expansion.x1_gate import verify_x1_gate
from src.expansion.x2_r5_gate import verify_x2_r5_source_gate
from src.expansion.x3_r5_gate import verify_x3_r5_source_gate
from src.expansion.x4_gate import verify_x4_gate
from src.expansion.x4_r6_gate import verify_x4_r6_source_gate

ROOT = Path(__file__).resolve().parents[2]

def test_x0_through_x4_r6_closeout_gates_compose_without_runtime() -> None:
    assert verify_scope_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x1_gate(ROOT)["status"] == "ACCEPTED_CONTRACT_ONLY"
    assert verify_x2_r5_source_gate(ROOT)["status"] == "ACCEPTED_SOURCE_CLOSEOUT"
    assert verify_x3_r5_source_gate(ROOT)["status"] == "ACCEPTED_SOURCE_CLOSEOUT"
    assert verify_x4_gate(ROOT)["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verify_x4_r6_source_gate(ROOT)["status"] == "ACCEPTED_SOURCE_CLOSEOUT"
