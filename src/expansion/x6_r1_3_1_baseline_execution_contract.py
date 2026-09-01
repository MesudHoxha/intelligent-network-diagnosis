"""Prospective, mutation-free X6-R1 baseline qualification contract.

This is a source-only contract for a future separately authorised baseline
qualification.  It deliberately cannot run commands, deploy a topology, load
modules, mutate qdiscs, or create scientific evidence.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any, Mapping

from src.collection.x6_r0_3_pre_runtime_validation import (
    NUMERIC_FEATURES,
    build_threshold_manifest,
    canonical_threshold_manifest_bytes,
    validate_threshold_manifest,
)


class X6R131ContractError(ValueError):
    """Raised for a malformed or non-authorising future qualification."""


RELEASE_ID = "X6_R1_3_1_BASELINE_ONLY_EXECUTION_CONTRACT_FREEZE"
COHORT_IDS = tuple([f"C{index:02d}" for index in range(1, 21)] + [f"H{index:02d}" for index in range(1, 11)])
THRESHOLD_IDS = tuple(f"C{index:02d}" for index in range(1, 11))
CALIBRATION_VALIDATION_IDS = tuple(f"C{index:02d}" for index in range(11, 21))
HOLDOUT_IDS = tuple(f"H{index:02d}" for index in range(1, 11))
REQUIRED_PROVENANCE_FIELDS = (
    "kernel_identity", "kernel_netem_config", "sch_netem_loaded_module", "sch_netem_module_provenance",
    "python_executable_version", "ip_executable_version", "tc_executable_version", "ethtool_executable_version",
    "ping_executable_version", "iperf3_executable_version", "docker_version", "containerlab_version",
    "runtime_image_identity", "topology_identity", "git_commit_source_tree_identity",
)
TERMINAL_STATUSES = {"QUALIFIED", "UNSTABLE", "COLLECTION_UNAVAILABLE", "ENVIRONMENT_INELIGIBLE", "INCONCLUSIVE"}
WINDOW_DURATION_SECONDS = Decimal("20.000000")
WARMUP_SECONDS = Decimal("5.000000")
COHORT_SEPARATION_SECONDS = Decimal("5.000000")
COOLDOWN_SECONDS = Decimal("5.000000")
MAXIMUM_SKEW_SECONDS = Decimal("0.250000")


def _fail(message: str) -> None:
    raise X6R131ContractError("X6-R1.3.1: " + message)


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _number(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        _fail(label + " must be numeric")
    try:
        result = Decimal(str(value))
    except Exception as error:
        raise X6R131ContractError("X6-R1.3.1: " + label + " must be numeric") from error
    if not result.is_finite():
        _fail(label + " must be finite")
    return result


def _six(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN), "f")


def _record_is_direct(value: object, field_id: str) -> None:
    if not isinstance(value, Mapping):
        _fail("provenance command record required: " + field_id)
    command = value.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        _fail("provenance command array required: " + field_id)
    if any(item in {"sudo", "modprobe"} for item in command):
        _fail("qualification provenance may never execute sudo or modprobe")
    if value.get("return_code") != 0 or not isinstance(value.get("stdout"), str) or not isinstance(value.get("stderr"), str):
        _fail("successful direct command record required: " + field_id)
    if not isinstance(value.get("captured_at_utc"), str) or not isinstance(value.get("monotonic_ns"), int):
        _fail("timestamp provenance required: " + field_id)


def validate_environment_provenance(value: Mapping[str, Any]) -> None:
    if set(value) != {"schema_version", "release_id", "records", "authorization"}:
        _fail("environment provenance schema drift")
    if value.get("schema_version") != 1 or value.get("release_id") != RELEASE_ID:
        _fail("environment provenance identity drift")
    if value.get("authorization") != "0/10_FALSE":
        _fail("environment provenance cannot authorise runtime or science")
    records = value.get("records")
    if not isinstance(records, list) or len(records) != len(REQUIRED_PROVENANCE_FIELDS):
        _fail("complete explicit provenance catalog required")
    by_id = {row.get("field_id"): row for row in records if isinstance(row, Mapping)}
    if set(by_id) != set(REQUIRED_PROVENANCE_FIELDS) or len(by_id) != len(records):
        _fail("provenance catalog has missing or duplicate fields")
    for field_id in REQUIRED_PROVENANCE_FIELDS:
        row = by_id[field_id]
        if row.get("availability") != "observed" or not isinstance(row.get("raw_path"), str) or not isinstance(row.get("raw_sha256"), str):
            _fail("required provenance unavailable: " + field_id)
        _record_is_direct(row.get("command_record"), field_id)
    for field_id in ("kernel_netem_config", "sch_netem_loaded_module", "sch_netem_module_provenance"):
        if not by_id[field_id].get("value"):
            _fail("NetEm prerequisite unavailable: " + field_id)


def environment_eligibility(value: Mapping[str, Any]) -> str:
    """Return the only admissible prospective state without running anything."""
    try:
        validate_environment_provenance(value)
    except X6R131ContractError:
        return "ENVIRONMENT_INELIGIBLE"
    return "ELIGIBLE_FOR_SEPARATE_BASELINE_ONLY_AUTHORIZATION"


def _threshold_inputs(windows: list[Mapping[str, Any]]) -> dict[str, list[object]]:
    selected = [row for row in windows if row["window_id"] in THRESHOLD_IDS]
    if [row["window_id"] for row in selected] != list(THRESHOLD_IDS):
        _fail("threshold construction must use exactly chronological C01-C10")
    return {feature: [row["measurements"][feature] for row in selected] for feature in NUMERIC_FEATURES}


def _within(value: object, threshold: Mapping[str, object]) -> bool:
    measured = Decimal(_six(_number(value, "feature measurement")))
    lower = _number(threshold["lower_threshold"], "lower threshold")
    upper = _number(threshold["upper_threshold"], "upper threshold")
    return lower <= measured <= upper


def _cohort_result(windows: list[Mapping[str, Any]], manifest: Mapping[str, Any]) -> dict[str, object]:
    by_feature = {row["feature_id"]: row for row in manifest["features"]}
    results: dict[str, object] = {}
    for row in windows:
        observed = row.get("observations")
        if not isinstance(observed, Mapping) or set(observed) != set(NUMERIC_FEATURES):
            _fail("complete observed numeric features required: " + str(row.get("window_id")))
        if row.get("rate_limit_detected") is not False:
            _fail("baseline-only rate-limit exclusion must be directly false")
        results[str(row["window_id"])] = {feature: _within(observed[feature], by_feature[feature]) for feature in NUMERIC_FEATURES}
    return results


def validate_baseline_execution_manifest(value: Mapping[str, Any], *, repository_root: Path) -> dict[str, object]:
    required = {"schema_version", "release_id", "execution_kind", "input_origin", "windows", "threshold_manifest", "threshold_freeze", "calibration_validation", "holdout", "terminal", "authorization"}
    if set(value) != required or value.get("schema_version") != 1 or value.get("release_id") != RELEASE_ID:
        _fail("execution manifest identity/schema drift")
    if value.get("execution_kind") != "BASELINE_ONLY_VERIFY_ONLY_NO_MUTATION" or value.get("input_origin") != "FUTURE_BASELINE_ONLY_QUALIFICATION" or value.get("authorization") != "0/10_FALSE":
        _fail("execution contract boundary drift")
    windows = value.get("windows")
    if not isinstance(windows, list) or len(windows) != 30:
        _fail("exactly thirty scheduled windows required")
    ids = [row.get("window_id") if isinstance(row, Mapping) else None for row in windows]
    if ids != list(COHORT_IDS):
        _fail("cohort identities, chronology, retry, or reassignment drift")
    previous = -1
    for row in windows:
        assert isinstance(row, Mapping)
        if row.get("mutation") != "NONE" or row.get("retry_of") is not None or row.get("replacement_for") is not None:
            _fail("selective retry, replacement, or mutation is prohibited")
        start = row.get("monotonic_start_ns")
        if not isinstance(start, int) or start <= previous or _number(row.get("duration_seconds"), "window duration") != WINDOW_DURATION_SECONDS:
            _fail("window chronology/duration drift")
        if _number(row.get("startup_skew_seconds"), "startup skew") > MAXIMUM_SKEW_SECONDS:
            _fail("window skew exceeds frozen bound")
        if row.get("consumed_pilot_input") is not False:
            _fail("consumed pilot may never be an input")
        if row.get("counter_continuity") is not True or row.get("qdisc_filter_state") != "EXACT_NOQUEUE_0_NO_FILTERS" or row.get("timing_valid") is not True or row.get("source_identity_match") is not True:
            _fail("counter/qdisc/timing/source exclusion control invalid")
        measures = row.get("measurements")
        if not isinstance(measures, Mapping) or set(measures) != set(NUMERIC_FEATURES):
            _fail("complete threshold-construction metrics required")
        for feature in NUMERIC_FEATURES:
            _number(measures[feature], feature)
        previous = start
    expected_manifest = build_threshold_manifest(_threshold_inputs(windows), topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH", traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
    supplied_manifest = value.get("threshold_manifest")
    if supplied_manifest != expected_manifest:
        _fail("canonical C01-C10 threshold manifest is false, rehashed, or changed")
    validate_threshold_manifest(supplied_manifest, repository_root=repository_root)
    freeze = value.get("threshold_freeze")
    if freeze != {"after_window_id": "C10", "before_window_id": "C11", "manifest_sha256": supplied_manifest["sha256"], "byte_sha256": hashlib.sha256(canonical_threshold_manifest_bytes(supplied_manifest)).hexdigest()}:
        _fail("manifest must be frozen byte-identically after C10 and before C11")
    calibration_rows = windows[10:20]; holdout_rows = windows[20:]
    calibration = _cohort_result(calibration_rows, supplied_manifest)
    holdout = _cohort_result(holdout_rows, supplied_manifest)
    if value.get("calibration_validation") != calibration or value.get("holdout") != holdout:
        _fail("C11-C20/H01-H10 comparison result drift")
    all_pass = all(all(features.values()) for features in calibration.values()) and all(all(features.values()) for features in holdout.values())
    terminal = value.get("terminal")
    if not isinstance(terminal, Mapping) or terminal.get("status") not in TERMINAL_STATUSES or terminal.get("baseline_after") != "NOT_APPLICABLE_NO_MUTATION" or terminal.get("replay") != "VERIFY_ONLY_REPLAY_REQUIRED" or terminal.get("cleanup") != "REQUIRED_BEFORE_TERMINAL" or terminal.get("all_windows_complete") is not True:
        _fail("terminal semantics drift")
    required_terminal_controls = ("provenance_valid", "timing_valid", "source_identity_valid", "qdisc_filter_state_valid", "counter_continuity_valid", "cleanup_valid", "replay_valid")
    if any(terminal.get(name) is not True for name in required_terminal_controls):
        _fail("terminal qualification control is absent or false")
    if terminal.get("status") == "QUALIFIED" and not all_pass:
        _fail("false QUALIFIED result")
    if terminal.get("status") == "UNSTABLE" and all_pass:
        _fail("UNSTABLE must reflect a failed mandatory threshold comparison")
    return {"status": terminal["status"], "threshold_sha256": supplied_manifest["sha256"], "calibration_all_pass": all(all(row.values()) for row in calibration.values()), "holdout_all_pass": all(all(row.values()) for row in holdout.values())}


__all__ = ["CALIBRATION_VALIDATION_IDS", "COHORT_IDS", "HOLDOUT_IDS", "RELEASE_ID", "REQUIRED_PROVENANCE_FIELDS", "THRESHOLD_IDS", "X6R131ContractError", "environment_eligibility", "validate_baseline_execution_manifest", "validate_environment_provenance"]
