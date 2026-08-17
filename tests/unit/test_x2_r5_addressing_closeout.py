from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.expansion.x2_addressing import X2AddressingError
from src.expansion.x2_r5_gate import (
    EXPECTED_SLICES,
    REQUIRED_RUN_ARTIFACTS,
    _tree_hash,
    verify_x2_r5_receipt,
    verify_x2_r5_source_gate,
)

ROOT = Path(__file__).resolve().parents[2]


def _receipt(tmp_path: Path, *, materialize: bool = False) -> Path:
    runs = []
    for index, (release_id, (fault_type, rule_id)) in enumerate(EXPECTED_SLICES.items(), 1):
        relative_run = f"data/raw/x2_r{index}_acceptance.test/x2-r{index}-real"
        artifacts = []
        for relative in sorted(REQUIRED_RUN_ARTIFACTS):
            content = f"{release_id}:{relative}\n".encode()
            digest = hashlib.sha256(content).hexdigest()
            artifacts.append({"path": relative, "sha256": digest, "size_bytes": len(content)})
            if materialize:
                path = tmp_path / relative_run / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        runs.append({
            "release_id": release_id,
            "fault_type": fault_type,
            "rule_id": rule_id,
            "relative_run_path": relative_run,
            "run_tree_sha256": _tree_hash(artifacts),
            "artifacts": artifacts,
        })
    receipt = {
        "schema_version": 1,
        "receipt_id": "x2_r5_addressing_evidence_receipt_v1",
        "source_commit": "cb8a9feaccc8a040a3a1f7fe472cbc9c0d70ecb1",
        "created_at_utc": "2026-08-17T12:00:00Z",
        "runs": runs,
        "summary": {
            "run_count": 4,
            "all_completed": True,
            "all_diagnosed": True,
            "all_restored": True,
            "all_baselines_valid": True,
            "all_raw_hashes_verified": True,
        },
    }
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


def test_source_gate_closes_four_disjoint_slices() -> None:
    plan = verify_x2_r5_source_gate(ROOT)
    assert plan["status"] == "ACCEPTED_SOURCE_CLOSEOUT"
    assert len(plan["accepted_slices"]) == 4
    assert plan["track"]["next_release"] == "X3_R0_LAYER2_VLAN_DESIGN_GATE"


def test_closeout_authorizes_no_runtime() -> None:
    runtime = verify_x2_r5_source_gate(ROOT)["runtime_authorization"]
    assert len(runtime) == 10
    assert all(value is False for value in runtime.values())


def test_claim_boundary_is_explicitly_limited() -> None:
    boundary = verify_x2_r5_source_gate(ROOT)["claim_boundary"]
    assert "four controlled single-fault addressing variants" in boundary["proves"]
    assert "ML or Hybrid performance" in boundary["does_not_prove"]
    assert "unseen topology generalization" in boundary["does_not_prove"]


def test_receipt_accepts_exact_four_hash_bound_runs(tmp_path: Path) -> None:
    receipt = verify_x2_r5_receipt(_receipt(tmp_path), repository_root=ROOT)
    assert receipt["summary"]["run_count"] == 4


def test_receipt_can_reverify_materialized_artifacts(tmp_path: Path) -> None:
    path = _receipt(tmp_path, materialize=True)
    receipt = verify_x2_r5_receipt(path, repository_root=tmp_path, schema_root=ROOT, verify_materialized=True)
    assert len(receipt["runs"]) == 4


def test_receipt_rejects_tree_hash_drift(tmp_path: Path) -> None:
    path = _receipt(tmp_path)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["runs"][0]["run_tree_sha256"] = "0" * 64
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(X2AddressingError, match="tree hash drifted"):
        verify_x2_r5_receipt(path, repository_root=ROOT)


def test_receipt_rejects_missing_required_artifact(tmp_path: Path) -> None:
    path = _receipt(tmp_path)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt["runs"][0]["artifacts"].pop()
    receipt["runs"][0]["run_tree_sha256"] = _tree_hash(receipt["runs"][0]["artifacts"])
    path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(X2AddressingError, match="incomplete"):
        verify_x2_r5_receipt(path, repository_root=ROOT)


def test_receipt_rejects_materialized_hash_drift(tmp_path: Path) -> None:
    path = _receipt(tmp_path, materialize=True)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    run = receipt["runs"][0]
    artifact = run["artifacts"][0]
    (tmp_path / run["relative_run_path"] / artifact["path"]).write_text("tampered", encoding="utf-8")
    with pytest.raises(X2AddressingError, match="materialized evidence drifted"):
        verify_x2_r5_receipt(path, repository_root=tmp_path, schema_root=ROOT, verify_materialized=True)
