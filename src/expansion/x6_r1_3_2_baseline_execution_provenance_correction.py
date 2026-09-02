"""X6-R1.3.2 source-only baseline execution and provenance correction.

The structural validator deliberately does not qualify a run.  Qualification is
available only through the materialized verifier, which binds its complete
record to regular files beneath a caller-supplied future run root.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from src.collection.x6_r0_3_pre_runtime_validation import (
    NUMERIC_FEATURES,
    THRESHOLD_SPECS,
    build_threshold_manifest,
    canonical_threshold_manifest_bytes,
    validate_threshold_manifest,
)


class X6R132ContractError(ValueError):
    """Raised when a prospective X6-R1.3.2 qualification is invalid."""


RELEASE_ID = "X6_R1_3_2_BASELINE_EXECUTION_AND_PROVENANCE_ENFORCEMENT_CORRECTION"
COHORT_IDS = tuple([f"C{index:02d}" for index in range(1, 21)] + [f"H{index:02d}" for index in range(1, 11)])
THRESHOLD_IDS = tuple(f"C{index:02d}" for index in range(1, 11))
CALIBRATION_IDS = tuple(f"C{index:02d}" for index in range(11, 21))
HOLDOUT_IDS = tuple(f"H{index:02d}" for index in range(1, 11))
REQUIRED_PROVENANCE_FIELDS = (
    "kernel_identity", "kernel_netem_config", "sch_netem_loaded_module", "sch_netem_module_provenance",
    "python_executable_version", "ip_executable_version", "tc_executable_version", "ethtool_executable_version",
    "ping_executable_version", "iperf3_executable_version", "docker_version", "containerlab_version",
    "runtime_image_identity", "topology_identity", "git_commit_source_tree_identity",
)
CONTROL_IDS = ("timing", "threshold_freeze", "qdisc_filter_state", "counter_continuity", "cleanup", "replay")
TERMINAL_CONTROLS = (
    "provenance_valid", "timing_valid", "source_identity_valid", "qdisc_filter_state_valid",
    "counter_continuity_valid", "cleanup_valid", "replay_valid",
)
TERMINAL_STATUSES = {"QUALIFIED", "UNSTABLE", "COLLECTION_UNAVAILABLE", "ENVIRONMENT_INELIGIBLE", "INCONCLUSIVE"}
NS_PER_SECOND = 1_000_000_000
READINESS_SECONDS = Decimal("5.000000")
WARMUP_SECONDS = Decimal("5.000000")
WINDOW_SECONDS = Decimal("20.000000")
SPACING_SECONDS = Decimal("5.000000")
COOLDOWN_SECONDS = Decimal("5.000000")
MAXIMUM_SKEW_SECONDS = Decimal("0.250000")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
MEANINGLESS = {"", "unknown", "none", "null", "n/a", "na", "synthetic", "placeholder", "todo"}


def _fail(message: str) -> None:
    raise X6R132ContractError("X6-R1.3.2: " + message)


def _number(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        _fail(label + " must be numeric")
    try:
        result = Decimal(str(value))
    except Exception as error:
        raise X6R132ContractError("X6-R1.3.2: " + label + " must be numeric") from error
    if not result.is_finite():
        _fail(label + " must be finite")
    return result


def _six(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN), "f")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _safe_relative(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(label + " must be a non-empty run-root-relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        _fail(label + " is not a safe canonical relative path")
    return value


def _artifact_ref(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256"}:
        _fail(label + " artifact identity is malformed")
    path = _safe_relative(value.get("path"), label + " path")
    digest = value.get("sha256")
    if not isinstance(digest, str) or SHA256.fullmatch(digest) is None:
        _fail(label + " SHA-256 must be lowercase hexadecimal")
    return {"path": path, "sha256": digest}


def _meaningful(value: object, label: str) -> None:
    if isinstance(value, str):
        if value.strip().lower() in MEANINGLESS:
            _fail(label + " must be meaningful")
        return
    if isinstance(value, Mapping) and value and all(isinstance(key, str) and key for key in value):
        for key, item in value.items():
            _meaningful(item, label + "." + key)
        return
    _fail(label + " must be a meaningful identity value")


def _timestamp(value: object, label: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        _fail(label + " must be an RFC3339 UTC timestamp")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise X6R132ContractError("X6-R1.3.2: " + label + " must be an RFC3339 UTC timestamp") from error


def _ns(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(label + " must be a non-negative monotonic nanosecond timestamp")
    return value


def _duration_ns(seconds: Decimal) -> int:
    return int(seconds * NS_PER_SECOND)


def _canonical_features(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != set(NUMERIC_FEATURES):
        _fail(label + " must contain exactly the canonical numeric features")
    result: dict[str, str] = {}
    for feature in NUMERIC_FEATURES:
        number = _number(value[feature], label + "." + feature)
        spec = THRESHOLD_SPECS[feature]
        minimum = _number(spec["minimum"], feature + " minimum")
        maximum = _number(spec["maximum"], feature + " maximum") if spec["maximum"] is not None else None
        if number < minimum or (maximum is not None and number > maximum):
            _fail(label + "." + feature + " is outside the frozen domain")
        if spec["value_type"] == "integer" and number != number.to_integral_value():
            _fail(label + "." + feature + " must be integral")
        result[feature] = _six(number)
    return result


def _require_canonical_mapping(value: object, label: str) -> dict[str, str]:
    canonical = _canonical_features(value, label)
    if dict(value) != canonical:
        _fail(label + " must use exact six-place canonical feature values")
    return canonical


def _allowed_command(field_id: str, command: list[str]) -> bool:
    fixed = {
        "kernel_identity": ["uname", "-r"],
        "kernel_netem_config": ["zgrep", "CONFIG_NET_SCH_NETEM", "/proc/config.gz"],
        "sch_netem_loaded_module": ["lsmod"],
        "sch_netem_module_provenance": ["modinfo", "sch_netem"],
        "python_executable_version": ["python3", "--version"],
        "ip_executable_version": ["ip", "-V"],
        "tc_executable_version": ["tc", "-V"],
        "ethtool_executable_version": ["ethtool", "--version"],
        "ping_executable_version": ["ping", "-V"],
        "iperf3_executable_version": ["iperf3", "--version"],
        "docker_version": ["docker", "version", "--format", "json"],
        "containerlab_version": ["containerlab", "version"],
        "git_commit_source_tree_identity": ["git", "rev-parse", "HEAD", "HEAD^{tree}"],
    }
    if field_id in fixed:
        return command == fixed[field_id]
    if field_id == "runtime_image_identity":
        return len(command) == 4 and command[:3] == ["docker", "image", "inspect"] and bool(command[3])
    if field_id == "topology_identity":
        return len(command) == 2 and command[0] == "sha256sum" and bool(command[1])
    return False


def _command_record(value: object, field_id: str, row_artifact: Mapping[str, str]) -> dict[str, object]:
    required = {"command", "shell", "return_code", "stdout", "stderr", "captured_at_utc", "monotonic_ns", "raw_artifact"}
    if not isinstance(value, Mapping) or set(value) != required:
        _fail("command record schema drift: " + field_id)
    command = value.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        _fail("structured command array required: " + field_id)
    if value.get("shell") is not False:
        _fail("qualification command records require shell=False: " + field_id)
    wrappers = {"sudo", "modprobe", "bash", "sh", "zsh", "fish", "cmd", "powershell", "pwsh", "env", "-c", "/bin/sh", "/bin/bash"}
    if any(item.lower() in wrappers for item in command) or not _allowed_command(field_id, command):
        _fail("unrecognized, wrapped, or prohibited qualification command: " + field_id)
    if value.get("return_code") != 0 or not isinstance(value.get("stdout"), str) or not isinstance(value.get("stderr"), str):
        _fail("successful command result required: " + field_id)
    _timestamp(value.get("captured_at_utc"), field_id + " capture time")
    _ns(value.get("monotonic_ns"), field_id + " capture monotonic timestamp")
    if _artifact_ref(value.get("raw_artifact"), field_id + " command") != dict(row_artifact):
        _fail("command record must bind the field raw artifact: " + field_id)
    return dict(value)


def _identity(value: object) -> dict[str, str]:
    required = {"git_commit", "git_tree", "topology_path", "topology_sha256", "runtime_image_tag", "runtime_image_id", "runtime_image_repo_digest"}
    if not isinstance(value, Mapping) or set(value) != required or not all(isinstance(value[key], str) for key in required):
        _fail("source identity schema drift")
    result = {key: str(value[key]) for key in required}
    if GIT_SHA.fullmatch(result["git_commit"]) is None or GIT_SHA.fullmatch(result["git_tree"]) is None:
        _fail("source commit/tree identity must be exact lowercase Git object IDs")
    _safe_relative(result["topology_path"], "topology path")
    if SHA256.fullmatch(result["topology_sha256"]) is None:
        _fail("topology SHA-256 must be lowercase hexadecimal")
    if not result["runtime_image_tag"] or not re.fullmatch(r"sha256:[0-9a-f]{64}", result["runtime_image_id"]):
        _fail("runtime image tag/ID identity is invalid")
    if "@sha256:" not in result["runtime_image_repo_digest"] or SHA256.fullmatch(result["runtime_image_repo_digest"].rsplit("@sha256:", 1)[-1]) is None:
        _fail("runtime image repository digest is invalid")
    return result


def validate_environment_provenance_structure(value: Mapping[str, Any]) -> dict[str, object]:
    """Validate only structure and semantics; this never reads a raw file."""
    required = {"schema_version", "release_id", "records", "source_identity"}
    if set(value) != required or value.get("schema_version") != 1 or value.get("release_id") != RELEASE_ID:
        _fail("environment provenance identity/schema drift")
    records = value.get("records")
    if not isinstance(records, list) or len(records) != len(REQUIRED_PROVENANCE_FIELDS):
        _fail("complete explicit provenance catalog required")
    by_id = {row.get("field_id"): row for row in records if isinstance(row, Mapping)}
    if set(by_id) != set(REQUIRED_PROVENANCE_FIELDS) or len(by_id) != len(records):
        _fail("provenance catalog has missing or duplicate fields")
    artifacts: set[tuple[str, str]] = set()
    normalized: dict[str, object] = {}
    for field_id in REQUIRED_PROVENANCE_FIELDS:
        row = by_id[field_id]
        if set(row) != {"field_id", "availability", "value", "raw_artifact", "command_record"} or row.get("availability") != "observed":
            _fail("observed provenance record required: " + field_id)
        _meaningful(row.get("value"), field_id + " value")
        artifact = _artifact_ref(row.get("raw_artifact"), field_id)
        pair = (artifact["path"], artifact["sha256"])
        if pair in artifacts:
            _fail("each provenance field requires a distinct raw artifact")
        artifacts.add(pair)
        command = _command_record(row.get("command_record"), field_id, artifact)
        normalized[field_id] = {"value": row["value"], "raw_artifact": artifact, "command_record": command}
    identity = _identity(value.get("source_identity"))
    required_identity_rows = {
        "runtime_image_identity": {"tag": identity["runtime_image_tag"], "id": identity["runtime_image_id"], "digest": identity["runtime_image_repo_digest"]},
        "topology_identity": {"path": identity["topology_path"], "sha256": identity["topology_sha256"]},
        "git_commit_source_tree_identity": {"commit": identity["git_commit"], "tree": identity["git_tree"]},
    }
    if any(normalized[field_id]["value"] != expected for field_id, expected in required_identity_rows.items()):
        _fail("identity provenance records must exactly bind source commit/tree, topology, and image identity")
    return {"records": normalized, "source_identity": identity}


def _read_bound_json(run_root: Path, artifact: Mapping[str, str], label: str) -> object:
    root = Path(run_root)
    if not root.is_dir() or root.is_symlink():
        _fail("materialized run root must be a regular directory")
    relative = _safe_relative(artifact.get("path"), label + " path")
    path = root / relative
    try:
        resolved_root = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise X6R132ContractError("X6-R1.3.2: materialized raw artifact is missing: " + relative) from error
    if resolved_root not in (resolved, *resolved.parents) or not path.is_file() or path.is_symlink():
        _fail("materialized raw artifact escapes the run root or is not a regular file: " + relative)
    content = path.read_bytes()
    if _sha256(content) != artifact.get("sha256"):
        _fail("materialized raw artifact SHA-256 mismatch: " + relative)
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise X6R132ContractError("X6-R1.3.2: materialized raw artifact must be JSON: " + relative) from error


def verify_materialized_environment_provenance(
    value: Mapping[str, Any], *, run_root: Path, expected_source_identity: Mapping[str, object]
) -> dict[str, object]:
    """Prove the on-disk provenance chain and exact approved source identity."""
    structural = validate_environment_provenance_structure(value)
    expected = _identity(expected_source_identity)
    if structural["source_identity"] != expected:
        _fail("source commit/tree, topology, or image identity does not match the approved source identity")
    records = structural["records"]
    assert isinstance(records, Mapping)
    for field_id, row in records.items():
        assert isinstance(row, Mapping)
        command = row["command_record"]
        assert isinstance(command, Mapping)
        payload = _read_bound_json(run_root, row["raw_artifact"], str(field_id))
        expected_payload = {
            "field_id": field_id,
            "value": row["value"],
            "command": command["command"],
            "return_code": command["return_code"],
            "stdout": command["stdout"],
            "stderr": command["stderr"],
            "captured_at_utc": command["captured_at_utc"],
            "monotonic_ns": command["monotonic_ns"],
        }
        if payload != expected_payload:
            _fail("raw command provenance does not bind its declared record: " + str(field_id))
    return {"provenance_valid": True, "source_identity_valid": True}


def _phase(value: object, label: str, duration: Decimal) -> dict[str, int]:
    required = {"scheduled_start_ns", "scheduled_end_ns", "actual_start_ns", "actual_end_ns"}
    if not isinstance(value, Mapping) or set(value) != required:
        _fail(label + " phase record is missing or malformed")
    result = {key: _ns(value[key], label + " " + key) for key in required}
    expected = _duration_ns(duration)
    if result["scheduled_end_ns"] - result["scheduled_start_ns"] != expected or result["actual_end_ns"] - result["actual_start_ns"] != expected:
        _fail(label + " duration is inconsistent with the frozen schedule")
    if abs(result["actual_start_ns"] - result["scheduled_start_ns"]) > _duration_ns(MAXIMUM_SKEW_SECONDS):
        _fail(label + " actual start exceeds the frozen absolute startup skew")
    return result


def _window(value: object, expected_id: str) -> dict[str, object]:
    required = {
        "window_id", "scheduled_start_ns", "scheduled_end_ns", "actual_start_ns", "actual_end_ns", "duration_seconds",
        "startup_skew_seconds", "mutation", "retry_of", "replacement_for", "consumed_pilot_input", "rate_limit_detected",
        "measurements", "observations", "raw_artifact",
    }
    if not isinstance(value, Mapping) or set(value) != required or value.get("window_id") != expected_id:
        _fail("window schema/identity drift: " + expected_id)
    phase = _phase({key: value[key] for key in ("scheduled_start_ns", "scheduled_end_ns", "actual_start_ns", "actual_end_ns")}, expected_id, WINDOW_SECONDS)
    if _number(value.get("duration_seconds"), expected_id + " duration") != WINDOW_SECONDS:
        _fail(expected_id + " duration does not equal the frozen twenty seconds")
    skew = _number(value.get("startup_skew_seconds"), expected_id + " startup skew")
    derived_skew = Decimal(abs(phase["actual_start_ns"] - phase["scheduled_start_ns"])) / Decimal(NS_PER_SECOND)
    if skew < 0 or skew > MAXIMUM_SKEW_SECONDS or _six(skew) != _six(derived_skew):
        _fail(expected_id + " startup skew is impossible or exceeds the frozen bound")
    if value.get("mutation") != "NONE" or value.get("retry_of") is not None or value.get("replacement_for") is not None or value.get("consumed_pilot_input") is not False:
        _fail(expected_id + " has prohibited mutation, retry, replacement, or consumed-pilot input")
    if value.get("rate_limit_detected") is not False:
        _fail(expected_id + " rate_limit_detected must be directly false")
    measurements = _require_canonical_mapping(value.get("measurements"), expected_id + " measurements")
    observations = _require_canonical_mapping(value.get("observations"), expected_id + " observations")
    if measurements != observations:
        _fail(expected_id + " measurements and observations must be canonically identical")
    return {"phase": phase, "features": measurements, "raw_artifact": _artifact_ref(value.get("raw_artifact"), expected_id)}


def _threshold_inputs(windows: list[dict[str, object]]) -> dict[str, list[object]]:
    selected = windows[:10]
    return {feature: [row["features"][feature] for row in selected] for feature in NUMERIC_FEATURES}


def _within(value: object, threshold: Mapping[str, object]) -> bool:
    measured = _number(value, "feature observation")
    return _number(threshold["lower_threshold"], "lower threshold") <= measured <= _number(threshold["upper_threshold"], "upper threshold")


def _cohort_result(rows: list[dict[str, object]], ids: tuple[str, ...], manifest: Mapping[str, Any]) -> dict[str, object]:
    by_feature = {row["feature_id"]: row for row in manifest["features"]}
    return {window_id: {feature: _within(row["features"][feature], by_feature[feature]) for feature in NUMERIC_FEATURES} for window_id, row in zip(ids, rows, strict=True)}


def _schedule(value: object, windows: list[dict[str, object]]) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {"readiness", "warmup", "cooldown"}:
        _fail("complete readiness, warm-up, and cooldown schedule required")
    readiness = _phase(value["readiness"], "readiness", READINESS_SECONDS)
    warmup = _phase(value["warmup"], "warm-up", WARMUP_SECONDS)
    cooldown = _phase(value["cooldown"], "cooldown", COOLDOWN_SECONDS)
    if warmup["scheduled_start_ns"] != readiness["scheduled_end_ns"] or warmup["actual_start_ns"] < readiness["actual_end_ns"]:
        _fail("readiness-to-warm-up chronology is invalid")
    first = windows[0]["phase"]
    assert isinstance(first, Mapping)
    if first["scheduled_start_ns"] != warmup["scheduled_end_ns"] or first["actual_start_ns"] < warmup["actual_end_ns"]:
        _fail("warm-up-to-C01 chronology is invalid")
    spacing = _duration_ns(SPACING_SECONDS)
    for index in range(1, len(windows)):
        before = windows[index - 1]["phase"]; after = windows[index]["phase"]
        assert isinstance(before, Mapping) and isinstance(after, Mapping)
        if after["scheduled_start_ns"] != before["scheduled_end_ns"] + spacing:
            _fail("scheduled post-window spacing is not exactly five seconds")
        if after["actual_start_ns"] < before["actual_end_ns"] + spacing or after["actual_start_ns"] - before["actual_start_ns"] < _duration_ns(WINDOW_SECONDS + SPACING_SECONDS):
            _fail("actual windows overlap or have insufficient five-second post-window spacing")
    for left, right, label in ((9, 10, "C10-to-C11"), (19, 20, "C20-to-H01")):
        before = windows[left]["phase"]; after = windows[right]["phase"]
        assert isinstance(before, Mapping) and isinstance(after, Mapping)
        if after["scheduled_start_ns"] - before["scheduled_end_ns"] != spacing or after["actual_start_ns"] - before["actual_end_ns"] < spacing:
            _fail(label + " separation is invalid")
    last = windows[-1]["phase"]
    assert isinstance(last, Mapping)
    if cooldown["scheduled_start_ns"] != last["scheduled_end_ns"] + spacing or cooldown["actual_start_ns"] < last["actual_end_ns"] + spacing:
        _fail("H10-to-cooldown separation is invalid")
    return {"readiness": readiness, "warmup": warmup, "cooldown": cooldown}


def _control_artifacts(value: object) -> dict[str, dict[str, str]]:
    if not isinstance(value, list) or len(value) != len(CONTROL_IDS):
        _fail("complete terminal control artifact inventory required")
    result: dict[str, dict[str, str]] = {}
    for row in value:
        if not isinstance(row, Mapping) or set(row) != {"control_id", "raw_artifact"} or row.get("control_id") not in CONTROL_IDS:
            _fail("terminal control artifact schema drift")
        control_id = str(row["control_id"])
        if control_id in result:
            _fail("duplicate terminal control artifact")
        result[control_id] = _artifact_ref(row["raw_artifact"], control_id)
    if set(result) != set(CONTROL_IDS):
        _fail("terminal control artifact is missing")
    return result


def _validate_manifest(value: Mapping[str, Any], *, repository_root: Path, allow_qualified: bool) -> dict[str, object]:
    required = {
        "schema_version", "release_id", "execution_kind", "input_origin", "schedule", "windows", "threshold_manifest",
        "threshold_freeze", "calibration_validation", "holdout", "provenance", "control_artifacts", "terminal", "authorization",
    }
    if set(value) != required or value.get("schema_version") != 1 or value.get("release_id") != RELEASE_ID:
        _fail("execution manifest identity/schema drift")
    if value.get("execution_kind") != "BASELINE_ONLY_VERIFY_ONLY_NO_MUTATION" or value.get("input_origin") != "FUTURE_BASELINE_ONLY_QUALIFICATION" or value.get("authorization") != "0/10_FALSE":
        _fail("execution boundary drift")
    rows = value.get("windows")
    if not isinstance(rows, list) or len(rows) != len(COHORT_IDS):
        _fail("exactly thirty windows are required")
    windows = [_window(row, window_id) for row, window_id in zip(rows, COHORT_IDS, strict=True)]
    schedule = _schedule(value.get("schedule"), windows)
    expected_manifest = build_threshold_manifest(_threshold_inputs(windows), topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH", traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
    supplied_manifest = value.get("threshold_manifest")
    if supplied_manifest != expected_manifest:
        _fail("canonical C01-C10 threshold manifest is false, rehashed, or changed")
    validate_threshold_manifest(supplied_manifest, repository_root=repository_root)
    freeze = value.get("threshold_freeze")
    c10_end = windows[9]["phase"]["actual_end_ns"]; c11_start = windows[10]["phase"]["actual_start_ns"]
    expected_freeze = {
        "after_window_id": "C10", "before_window_id": "C11", "manifest_sha256": supplied_manifest["sha256"],
        "byte_sha256": _sha256(canonical_threshold_manifest_bytes(supplied_manifest)),
        "frozen_at_monotonic_ns": freeze.get("frozen_at_monotonic_ns") if isinstance(freeze, Mapping) else None,
    }
    if freeze != expected_freeze or not isinstance(expected_freeze["frozen_at_monotonic_ns"], int) or not c10_end <= expected_freeze["frozen_at_monotonic_ns"] <= c11_start:
        _fail("threshold manifest freeze is not bound between C10 and C11")
    calibration = _cohort_result(windows[10:20], CALIBRATION_IDS, supplied_manifest)
    holdout = _cohort_result(windows[20:], HOLDOUT_IDS, supplied_manifest)
    if value.get("calibration_validation") != calibration or value.get("holdout") != holdout:
        _fail("calibration/holdout comparison result drift")
    provenance = validate_environment_provenance_structure(value["provenance"])
    controls = _control_artifacts(value.get("control_artifacts"))
    terminal = value.get("terminal")
    terminal_required = {"status", "baseline_after", "replay", "cleanup", "all_windows_complete", *TERMINAL_CONTROLS}
    if not isinstance(terminal, Mapping) or set(terminal) != terminal_required or terminal.get("status") not in TERMINAL_STATUSES or terminal.get("baseline_after") != "NOT_APPLICABLE_NO_MUTATION" or terminal.get("replay") != "VERIFY_ONLY_REPLAY_REQUIRED" or terminal.get("cleanup") != "REQUIRED_BEFORE_TERMINAL" or terminal.get("all_windows_complete") is not True or any(not isinstance(terminal.get(name), bool) for name in TERMINAL_CONTROLS):
        _fail("terminal schema/semantics drift")
    if terminal["status"] == "QUALIFIED" and not allow_qualified:
        _fail("structural validation can never accept QUALIFIED")
    return {"windows": windows, "schedule": schedule, "manifest": supplied_manifest, "freeze": freeze, "calibration": calibration, "holdout": holdout, "provenance": provenance, "controls": controls, "terminal": terminal}


def validate_baseline_execution_manifest_structure(value: Mapping[str, Any], *, repository_root: Path) -> dict[str, object]:
    """Validate semantic structure only; it is intentionally non-authorizing."""
    state = _validate_manifest(value, repository_root=repository_root, allow_qualified=False)
    return {"status": state["terminal"]["status"], "qualification": "STRUCTURAL_ONLY_NEVER_QUALIFIED"}


def _verify_control_artifacts(state: Mapping[str, object], *, run_root: Path) -> dict[str, bool]:
    controls = state["controls"]
    assert isinstance(controls, Mapping)
    schedule_hash = _sha256(_canonical_json({"schedule": state["schedule"], "windows": [row["phase"] for row in state["windows"]]}))
    manifest = state["manifest"]; freeze = state["freeze"]
    assert isinstance(manifest, Mapping) and isinstance(freeze, Mapping)
    expected = {
        "timing": {"control_id": "timing", "status": "TIMING_SCHEDULE_CAPTURED", "schedule_sha256": schedule_hash, "window_ids": list(COHORT_IDS)},
        "threshold_freeze": {"control_id": "threshold_freeze", "status": "FROZEN_C10_BEFORE_C11", "threshold_sha256": manifest["sha256"], "frozen_at_monotonic_ns": freeze["frozen_at_monotonic_ns"]},
        "qdisc_filter_state": {"control_id": "qdisc_filter_state", "status": "EXACT_NOQUEUE_0_NO_FILTERS", "window_ids": list(COHORT_IDS)},
        "counter_continuity": {"control_id": "counter_continuity", "status": "COUNTER_CONTINUITY_CONFIRMED", "window_ids": list(COHORT_IDS)},
        "cleanup": {"control_id": "cleanup", "status": "CLEANUP_CONFIRMED_NO_CONTAINERS_NAMESPACES_OR_IPERF", "lingering_iperf_processes": []},
        "replay": {"control_id": "replay", "status": "VERIFY_ONLY_REPLAY_CONFIRMED"},
    }
    for control_id, payload in expected.items():
        if _read_bound_json(run_root, controls[control_id], control_id) != payload:
            _fail("materialized terminal control artifact is false or incomplete: " + control_id)
    return {
        "timing_valid": True,
        "qdisc_filter_state_valid": True,
        "counter_continuity_valid": True,
        "cleanup_valid": True,
        "replay_valid": True,
    }


def verify_materialized_baseline_execution_manifest(
    value: Mapping[str, Any], *, repository_root: Path, run_root: Path, expected_source_identity: Mapping[str, object]
) -> dict[str, object]:
    """The only verifier that can accept a future materialized qualification."""
    state = _validate_manifest(value, repository_root=repository_root, allow_qualified=True)
    provenance = verify_materialized_environment_provenance(value["provenance"], run_root=run_root, expected_source_identity=expected_source_identity)
    windows = state["windows"]
    assert isinstance(windows, list)
    raw_pairs: set[tuple[str, str]] = set()
    for window_id, row in zip(COHORT_IDS, windows, strict=True):
        pair = (row["raw_artifact"]["path"], row["raw_artifact"]["sha256"])
        if pair in raw_pairs:
            _fail("each window requires its own raw observation artifact")
        raw_pairs.add(pair)
        expected = {"window_id": window_id, "canonical_features": row["features"], "rate_limit_detected": False}
        if _read_bound_json(run_root, row["raw_artifact"], window_id) != expected:
            _fail("window measurements/observations do not bind the same raw artifact: " + window_id)
    derived = {**provenance, **_verify_control_artifacts(state, run_root=run_root)}
    terminal = state["terminal"]
    assert isinstance(terminal, Mapping)
    if any(terminal[name] is not derived[name] for name in TERMINAL_CONTROLS):
        _fail("terminal summary does not equal independently materialized control verification")
    calibration = state["calibration"]; holdout = state["holdout"]
    assert isinstance(calibration, Mapping) and isinstance(holdout, Mapping)
    all_pass = all(all(row.values()) for row in calibration.values()) and all(all(row.values()) for row in holdout.values())
    if terminal["status"] == "QUALIFIED" and not all_pass:
        _fail("false QUALIFIED result")
    if terminal["status"] == "UNSTABLE" and all_pass:
        _fail("UNSTABLE must reflect a failed mandatory comparison")
    return {"status": terminal["status"], "qualified": terminal["status"] == "QUALIFIED", "threshold_sha256": state["manifest"]["sha256"], "calibration_all_pass": all(all(row.values()) for row in calibration.values()), "holdout_all_pass": all(all(row.values()) for row in holdout.values())}


__all__ = [
    "CALIBRATION_IDS", "COHORT_IDS", "HOLDOUT_IDS", "RELEASE_ID", "REQUIRED_PROVENANCE_FIELDS", "TERMINAL_CONTROLS",
    "X6R132ContractError", "validate_baseline_execution_manifest_structure", "validate_environment_provenance_structure",
    "verify_materialized_baseline_execution_manifest", "verify_materialized_environment_provenance",
]
