"""Synthetic source-only adversarial tests for the future X6-R1.3.1 contract."""
from __future__ import annotations

import copy
import hashlib

import pytest

import src.expansion.x6_r1_3_1_baseline_execution_contract as contract
from src.collection.x6_r0_3_pre_runtime_validation import canonical_threshold_manifest_bytes


ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


def _row(window_id: str, index: int) -> dict[str, object]:
    measures = {feature: 1 for feature in contract.NUMERIC_FEATURES}
    return {"window_id": window_id, "monotonic_start_ns": index * 1_000_000_000, "duration_seconds": "20.000000", "startup_skew_seconds": "0.100000", "mutation": "NONE", "retry_of": None, "replacement_for": None, "consumed_pilot_input": False, "counter_continuity": True, "qdisc_filter_state": "EXACT_NOQUEUE_0_NO_FILTERS", "timing_valid": True, "source_identity_match": True, "measurements": measures, "observations": dict(measures), "rate_limit_detected": False}


def _manifest() -> dict[str, object]:
    windows = [_row(window_id, index) for index, window_id in enumerate(contract.COHORT_IDS, 1)]
    threshold = contract.build_threshold_manifest(contract._threshold_inputs(windows), topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH", traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
    freeze = {"after_window_id": "C10", "before_window_id": "C11", "manifest_sha256": threshold["sha256"], "byte_sha256": hashlib.sha256(canonical_threshold_manifest_bytes(threshold)).hexdigest()}
    calibration = contract._cohort_result(windows[10:20], threshold)
    holdout = contract._cohort_result(windows[20:], threshold)
    return {"schema_version": 1, "release_id": contract.RELEASE_ID, "execution_kind": "BASELINE_ONLY_VERIFY_ONLY_NO_MUTATION", "input_origin": "FUTURE_BASELINE_ONLY_QUALIFICATION", "windows": windows, "threshold_manifest": threshold, "threshold_freeze": freeze, "calibration_validation": calibration, "holdout": holdout, "terminal": {"status": "QUALIFIED", "baseline_after": "NOT_APPLICABLE_NO_MUTATION", "replay": "VERIFY_ONLY_REPLAY_REQUIRED", "cleanup": "REQUIRED_BEFORE_TERMINAL", "all_windows_complete": True, "provenance_valid": True, "timing_valid": True, "source_identity_valid": True, "qdisc_filter_state_valid": True, "counter_continuity_valid": True, "cleanup_valid": True, "replay_valid": True}, "authorization": "0/10_FALSE"}


def _provenance() -> dict[str, object]:
    records = []
    for index, field_id in enumerate(contract.REQUIRED_PROVENANCE_FIELDS):
        records.append({"field_id": field_id, "availability": "observed", "value": "synthetic" if field_id in {"kernel_netem_config", "sch_netem_loaded_module", "sch_netem_module_provenance"} else {"synthetic": True}, "raw_path": f"raw/provenance/{field_id}.json", "raw_sha256": "a" * 64, "command_record": {"command": ["collector", field_id], "return_code": 0, "stdout": "synthetic", "stderr": "", "captured_at_utc": "2026-09-01T00:00:00Z", "monotonic_ns": index}})
    return {"schema_version": 1, "release_id": contract.RELEASE_ID, "records": records, "authorization": "0/10_FALSE"}


def test_c01_to_c10_are_the_only_threshold_construction_inputs() -> None:
    value = _manifest()
    result = contract.validate_baseline_execution_manifest(value, repository_root=ROOT)
    assert result["status"] == "QUALIFIED"
    assert len(value["threshold_manifest"]["features"][0]["sorted_baseline_values"]) == 10


@pytest.mark.parametrize("mutation", ["reassign", "missing", "retry", "reorder", "pilot_input"])
def test_cohort_and_window_adversaries_fail_closed(mutation: str) -> None:
    value = _manifest()
    if mutation == "reassign": value["windows"][10]["window_id"] = "C10"
    elif mutation == "missing": value["windows"].pop()
    elif mutation == "retry": value["windows"][11]["retry_of"] = "C11"
    elif mutation == "reorder": value["windows"][11]["monotonic_start_ns"] = 1
    else: value["windows"][0]["consumed_pilot_input"] = True
    with pytest.raises(contract.X6R131ContractError):
        contract.validate_baseline_execution_manifest(value, repository_root=ROOT)


def test_validation_and_holdout_cannot_change_frozen_manifest() -> None:
    value = _manifest()
    frozen = value["threshold_manifest"]["sha256"]
    value["windows"][10]["measurements"]["packet_loss_ratio"] = 999
    value["windows"][20]["measurements"]["packet_loss_ratio"] = 999
    assert contract.validate_baseline_execution_manifest(value, repository_root=ROOT)["threshold_sha256"] == frozen


def test_false_but_rehashed_manifest_and_false_qualified_are_rejected() -> None:
    value = _manifest(); value["threshold_manifest"]["features"][0]["upper_threshold"] = "999.000000"
    value["threshold_manifest"]["sha256"] = hashlib.sha256(canonical_threshold_manifest_bytes({key: item for key, item in value["threshold_manifest"].items() if key != "sha256"})).hexdigest()
    with pytest.raises(contract.X6R131ContractError):
        contract.validate_baseline_execution_manifest(value, repository_root=ROOT)
    value = _manifest(); value["windows"][10]["observations"]["packet_loss_ratio"] = 99
    value["calibration_validation"] = contract._cohort_result(value["windows"][10:20], value["threshold_manifest"])
    with pytest.raises(contract.X6R131ContractError, match="false QUALIFIED"):
        contract.validate_baseline_execution_manifest(value, repository_root=ROOT)


def test_explicit_provenance_is_direct_complete_and_fail_closed() -> None:
    provenance = _provenance(); contract.validate_environment_provenance(provenance)
    unavailable = copy.deepcopy(provenance); unavailable["records"][2]["availability"] = "collection_unavailable"
    with pytest.raises(contract.X6R131ContractError, match="unavailable"):
        contract.validate_environment_provenance(unavailable)
    forbidden = copy.deepcopy(provenance); forbidden["records"][0]["command_record"]["command"] = ["sudo", "modprobe", "sch_netem"]
    with pytest.raises(contract.X6R131ContractError, match="sudo or modprobe"):
        contract.validate_environment_provenance(forbidden)
    netem_missing = copy.deepcopy(provenance); netem_missing["records"][1]["value"] = ""
    assert contract.environment_eligibility(netem_missing) == "ENVIRONMENT_INELIGIBLE"
