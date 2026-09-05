import json
from pathlib import Path

import pytest

from src.expansion.x6_r1_3_5_gate import verify_x6_r1_3_5
from src.expansion.x6_r1_3_6_gate import (
    HISTORICAL_PLAN, PREDECESSOR, _validate_frozen_shared_documents,
    _validate_historical_r1_3_5_bindings, verify_r1_3_5_predecessor_snapshot,
    verify_x6_r1_3_6,
)


def test_x6_r1_3_6_gate_preserves_disabled_historical_vector() -> None:
    plan = verify_x6_r1_3_6()
    assert all(value is False for value in plan["runtime_scientific_authorization"].values())
    assert plan["future_authorization"]["artifact"] == "ABSENT"


def test_historical_r1_3_5_gate_is_validated_only_in_its_exact_snapshot() -> None:
    historical = verify_r1_3_5_predecessor_snapshot()
    assert all(value is False for value in historical["runtime_scientific_authorization"].values())
    current = verify_x6_r1_3_5()
    assert current["runtime_scientific_authorization"] == historical["runtime_scientific_authorization"]


def test_historical_binding_validator_rejects_changed_historical_blob() -> None:
    import src.expansion.x6_r1_3_6_gate as gate
    original = gate._historical_blob
    plan = json.loads(original(gate.ROOT, PREDECESSOR, HISTORICAL_PLAN))
    changed_path = Path(plan["source_bindings"][0]["path"])
    def substituted(root: Path, commit: str, path: Path) -> bytes:
        data = original(root, commit, path)
        return data + b"substituted" if path == changed_path else data
    with pytest.raises(ValueError, match="historical R1.3.5 binding drift"):
        _validate_historical_r1_3_5_bindings(gate.ROOT, blob_reader=substituted)


def test_historical_binding_validator_rejects_wrong_predecessor_and_successor_substitution() -> None:
    import src.expansion.x6_r1_3_6_gate as gate
    with pytest.raises(ValueError, match="work must extend"):
        _validate_historical_r1_3_5_bindings(gate.ROOT, commit="ff13ab744fcfc41f016cee768a59f74ea14f0e5f")
    historical = _validate_historical_r1_3_5_bindings(gate.ROOT)
    assert all("x6_r1_3_6" not in row["path"] for row in historical["source_bindings"])


def test_successor_gate_rejects_skipped_historical_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.expansion.x6_r1_3_6_gate as gate
    monkeypatch.setattr(gate, "_run_historical_r1_3_5_gate", lambda *_args: (_ for _ in ()).throw(ValueError("historical gate required")))
    with pytest.raises(ValueError, match="historical gate required"):
        gate.verify_x6_r1_3_6()


def test_frozen_shared_document_validator_rejects_historical_rewrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import src.expansion.x6_r1_3_6_gate as gate
    for path in gate.FROZEN_SHARED_DOCUMENTS:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"rewritten")
    monkeypatch.setattr(gate, "_historical_blob", lambda _root, _commit, _path: b"historical")
    with pytest.raises(ValueError, match="frozen shared document drift"):
        _validate_frozen_shared_documents(tmp_path)


def test_gate_binds_versioned_successor_decision_and_status_documents() -> None:
    plan = verify_x6_r1_3_6()
    paths = {row["path"] for row in plan["source_bindings"]}
    assert "docs/DECISION_X6_R1_3_6.md" in paths
    assert "docs/STATUS_X6_R1_3_6.md" in paths
    assert "docs/DECISIONS.md" not in paths
    assert "docs/STATUS.md" not in paths
