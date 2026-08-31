"""Synthetic source tests for the future-only X6-R1 acceptance contract.

The fixture is deliberately synthetic and is never an accepted runtime tree.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import src.expansion.x6_r1_2_authoritative_verifier as verifier
from src.expansion.x6_r1_gate import X6R1GateError

ROOT = Path(__file__).resolve().parents[2]


def _write(root: Path, relative: str, value: dict[str, object]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"return_code": 0, "stdout": json.dumps(rows), "stderr": ""}


def _fixture(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verifier, "verify_x6_r1_source", lambda repository_root: {})
    monkeypatch.setattr(verifier, "validate_threshold_manifest", lambda threshold, repository_root: None)
    monkeypatch.setattr(verifier, "validate_evidence_v4", lambda evidence, catalog, repository_root: None)
    monkeypatch.setattr(verifier, "validate_feature_vector_v2", lambda vector, catalog, repository_root: None)
    predicate = {"loss_above_baseline": True, "latency_within_baseline": True, "throughput_within_baseline": True, "utilization_within_baseline": True, "queue_delta_zero": True, "rate_limit_false": True}
    monkeypatch.setattr(verifier, "predicates_from_vector", lambda vector, threshold, repository_root: predicate)
    noqueue = _record([{"kind": "noqueue", "handle": "0:"}])
    nofilters = [_record([])]
    fault = _record([{"kind": "netem", "handle": "10:", "stats": {"drops": 9}}, {"kind": "pfifo", "handle": "20:", "parent": "10:1", "stats": {"drops": 0}}])
    raw_hashes: dict[str, str] = {}
    for phase, count in (("baseline", 10), ("fault", 3), ("restored", 3)):
        for index in range(1, count + 1):
            qdisc = fault if phase == "fault" else noqueue
            row = {"window_id": f"{phase}-{index:02d}", "phase": phase, "elapsed_seconds": 1.0, "startup_skew_seconds": 0.1, "qdisc_before": qdisc, "qdisc_after": qdisc, "filters_before": nofilters, "filters_after": nofilters, "queue_drop_derivation": "COUNTER_DELTA_CHILD_PFIFO_20" if phase == "fault" else "STRUCTURAL_ZERO_NO_MANAGED_QUEUE"}
            relative = f"raw/v4/performance_collector/{phase}_window_{index:02d}.json"
            _write(root, relative, row)
            raw_hashes[relative] = _sha(root / relative)
    aggregate = "raw/v4/performance_collector/fault_aggregate_provenance.json"
    _write(root, aggregate, {"window_ids": ["fault-01", "fault-02", "fault-03"], "input_sha256": {name: raw_hashes[name] for name in sorted(raw_hashes) if "/fault_" in name}})
    raw_hashes[aggregate] = _sha(root / aggregate)
    _write(root, "manifest.json", {"status": "AUTHORITATIVE", "release_id": "X6_R1_PACKET_LOSS", "threshold_sha256": ""})
    _write(root, "validation/source_identity.json", {"topology_sha256": verifier.TOPOLOGY_SHA256, "dockerfile_sha256": "a" * 64})
    _write(root, "validation/runtime_image_identity.json", {"captured_before_deployment": True, "image_id": "sha256:" + "b" * 64})
    _write(root, "validation/netem_prerequisite.json", {"status": "X6_R0_7_HOST_NETEM_PREREQUISITE_VERIFIED", "policy": "VERIFY_ONLY_NEVER_PRIVILEGED_MODULE_LOAD"})
    threshold = {"fault_window_input": "FORBIDDEN", "post_hoc_override": "FORBIDDEN"}
    _write(root, "validation/threshold_manifest_v1.json", threshold)
    threshold_hash = _sha(root / "validation/threshold_manifest_v1.json")
    _write(root, "validation/threshold_freeze_record.json", {"status": "FROZEN_BEFORE_MUTATION", "sha256": threshold_hash})
    _write(root, "manifest.json", {"status": "AUTHORITATIVE", "release_id": "X6_R1_PACKET_LOSS", "threshold_sha256": threshold_hash})
    _write(root, "validation/authoritative_acceptance_v1.json", {"status": "COMPLETED_NO_RETRY_NO_OVERLAP", "window_order": [f"{phase}-{index:02d}" for phase, count in (("baseline", 10), ("fault", 3), ("restored", 3)) for index in range(1, count + 1)], "baseline_window_count": 10, "fault_window_count": 3, "restored_window_count": 3, "traffic_schedule": {"iperf3_offset_seconds": 0, "ping_offset_seconds": 5, "maximum_skew_seconds": 0.250}, "threshold_input_window_ids": [f"baseline-{index:02d}" for index in range(1, 11)]})
    _write(root, "mutation/action_journal.json", {"actions": [{"status": "COMMAND_ACCEPTED"}, {"status": "COMMAND_ACCEPTED"}]})
    _write(root, "mutation/command_acceptance.json", {"status": "COMMAND_ACCEPTED", "physical_effectiveness": "NOT_INFERRED"})
    _write(root, "mutation/mutation_effectiveness.json", {"status": "MUTATION_EFFECTIVE", "lost_packet_count": 10, "pfifo_drop_delta": 0, "hierarchy_exact": True})
    _write(root, "mutation/restoration_record.json", {"status": "RESTORATION_CONFIRMED"})
    _write(root, "mutation/standalone_replay.json", {"status": "STANDALONE_REPLAY_CONFIRMED"})
    _write(root, "validation/baseline_after.json", {"status": "BASELINE_VALID_AFTER"})
    _write(root, "validation/raw_hashes.json", {"artifacts": raw_hashes})
    aggregate_hash = raw_hashes[aggregate]
    _write(root, "parsed/evidence_v4.json", {"collector_runs": [{"raw_artifacts": [{"path": aggregate, "sha256": aggregate_hash}]}]})
    evidence_hash = _sha(root / "parsed/evidence_v4.json")
    values = {name: {"availability": "observed", "value": False if name == "rate_limit_detected" else 0} for name in verifier.FEATURES}
    _write(root, "parsed/feature_vector_v2.json", {"values": values, "provenance": {"evidence_sha256": evidence_hash}})
    _write(root, "diagnosis/conditional_predicates.json", {"rule_id": "R_X6_PERFORMANCE_001", "predicates": predicate})
    _write(root, "diagnosis/diagnosis_result_v2.json", {"status": "diagnosed", "explanation_refs": ["rule:R_X6_PERFORMANCE_001"]})
    _write(root, "validation/cleanup_provenance.json", {"status": "CLEANUP_CONFIRMED_ZERO_CONTAINERS_AND_NAMESPACES"})


def test_future_authoritative_verifier_accepts_only_complete_synthetic_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture(tmp_path, monkeypatch)
    assert verifier.verify_x6_r1_authoritative_independently(tmp_path, ROOT)["status"] == "AUTHORITATIVE"


@pytest.mark.parametrize("relative,replacement", [
    ("manifest.json", {"status": "DIAGNOSTIC_NON_AUTHORITATIVE"}),
    ("validation/authoritative_acceptance_v1.json", {"status": "COMPLETED_NO_RETRY_NO_OVERLAP", "window_order": []}),
    ("mutation/mutation_effectiveness.json", {"status": "MUTATION_EFFECTIVE", "lost_packet_count": 5, "pfifo_drop_delta": 0, "hierarchy_exact": True}),
    ("mutation/command_acceptance.json", {"status": "COMMAND_ACCEPTED", "physical_effectiveness": "MUTATION_EFFECTIVE"}),
    ("validation/cleanup_provenance.json", {"status": "FAILED"}),
])
def test_future_authoritative_verifier_rejects_adversarial_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str, replacement: dict[str, object]) -> None:
    _fixture(tmp_path, monkeypatch)
    _write(tmp_path, relative, replacement)
    with pytest.raises(X6R1GateError):
        verifier.verify_x6_r1_authoritative_independently(tmp_path, ROOT)


def test_future_authoritative_verifier_rejects_queue_provenance_and_raw_hash_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fixture(tmp_path, monkeypatch)
    path = tmp_path / "raw/v4/performance_collector/fault_window_01.json"
    row = json.loads(path.read_text()); row["queue_drop_derivation"] = "STRUCTURAL_ZERO_NO_MANAGED_QUEUE"; path.write_text(json.dumps(row))
    with pytest.raises(X6R1GateError):
        verifier.verify_x6_r1_authoritative_independently(tmp_path, ROOT)
