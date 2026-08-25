from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.expansion.x5_r5_gate import X5R5CorrectionDesignError, verify_x5_r5_c5_operational_policy_correction_gate


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "plans/expansion/X5_R5_C5_OPERATIONAL_POLICY_CORRECTION_DESIGN_GATE_V1.json"


def test_x5_r5_c5_uses_an_attached_operational_policy_and_preserves_only_a_conditional_signature() -> None:
    plan = verify_x5_r5_c5_operational_policy_correction_gate(ROOT)
    assert plan["operational_policy"]["baseline_attachment"] == "redistribute connected route-map X5-R5-C5-EXPORT"
    assert plan["frozen_feature_contract"]["conditional_runtime_signature"] == [True, False, False, False]
    assert "provenance metadata" in plan["frozen_feature_contract"]["truthfulness"]


def test_x5_r5_requires_bounded_effectiveness_validation_and_partial_mutation_recovery() -> None:
    contract = verify_x5_r5_c5_operational_policy_correction_gate(ROOT)["future_runtime_contract"]
    assert any("bounded state-based loop" in value for value in contract["observation_contract"])
    assert any("Feature Vector v2" in value for value in contract["preconditions"])
    assert any("partial mutation" in value for value in contract["mutation_and_recovery"])


def test_x5_r5_rejects_runtime_authorization_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    changed = copy.deepcopy(json.loads(PLAN.read_text(encoding="utf-8")))
    changed["runtime_authorization"]["network_mutation"] = True
    import src.expansion.x5_r5_gate as gate
    monkeypatch.setattr(gate, "_load", lambda path: changed)
    with pytest.raises(X5R5CorrectionDesignError):
        verify_x5_r5_c5_operational_policy_correction_gate(ROOT)
