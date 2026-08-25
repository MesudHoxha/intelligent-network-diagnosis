from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src.expansion.x3_r5_gate import X3R5CloseoutError, verify_x3_r5_receipt, verify_x3_r5_source_gate
from tests.accepted_runtime import require_materialized_receipts


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "plans/expansion/X3_R5_LAYER2_VLAN_CLOSEOUT_V1.json"
RECEIPT = ROOT / "plans/expansion/X3_R5_LAYER2_VLAN_EVIDENCE_RECEIPT_V1.json"


def test_closeout_binds_exact_disjoint_x3_slices() -> None:
    plan = verify_x3_r5_source_gate(ROOT)
    assert plan["status"] == "ACCEPTED_SOURCE_CLOSEOUT"
    assert plan["track"]["next_release"] == "X4_DHCP_DNS_SERVICE_SECURITY"
    assert len(plan["accepted_slices"]) == 4
    assert len({json.dumps(row["expected_signature"], sort_keys=True) for row in plan["accepted_slices"]}) == 4


def test_closeout_authorizes_no_runtime_or_scientific_operation() -> None:
    runtime = verify_x3_r5_source_gate(ROOT)["runtime_authorization"]
    assert len(runtime) == 10 and all(value is False for value in runtime.values())


@pytest.mark.accepted_runtime
def test_receipt_reverifies_all_materialized_accepted_runs() -> None:
    require_materialized_receipts(ROOT, RECEIPT)
    receipt = verify_x3_r5_receipt(RECEIPT, repository_root=ROOT, verify_materialized=True)
    assert receipt["summary"]["run_count"] == 4
    assert receipt["summary"]["all_raw_hashes_verified"] is True


def test_source_gate_rejects_runtime_and_signature_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    changed = copy.deepcopy(plan); changed["runtime_authorization"]["metric_calculation"] = True
    import src.expansion.x3_r5_gate as gate
    original = gate._load
    monkeypatch.setattr(gate, "_load", lambda path, label: changed if path == ROOT / gate.PLAN else original(path, label))
    with pytest.raises(X3R5CloseoutError): verify_x3_r5_source_gate(ROOT)
