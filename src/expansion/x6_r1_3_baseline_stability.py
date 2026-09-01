"""Prospective X6-R1.3 provenance and baseline-only qualification contract.

This module validates future source/materialized qualification artifacts.  It
does not collect host state, execute traffic, derive thresholds, or authorize
a fault pilot.  Host context remains methodology/provenance data, never a
diagnosis or ML feature.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from src.contracts.expansion import ExpansionContractError, validate_schema_contract


class X6R13ContractError(ValueError):
    """Raised when future qualification evidence is incomplete or inconsistent."""


STATIC_FIELDS: dict[str, tuple[str, str, str, str, bool, str]] = {
    "host_kernel_release_architecture": ("host_operator", "uname -srmo", "uname_release_arch_parser_v1", "text", True, "BLOCKS_MUTATION"),
    "wsl_version": ("host_operator", "wsl.exe --version where available", "wsl_version_parser_v1", "text", False, "RECORDED_LIMITATION"),
    "docker_engine_version": ("docker_operator", "docker version --format json", "docker_version_parser_v1", "text", True, "BLOCKS_MUTATION"),
    "containerlab_version": ("containerlab_operator", "containerlab version", "containerlab_version_parser_v1", "text", True, "BLOCKS_MUTATION"),
    "cgroup_version_mode": ("host_operator", "stat -fc %T /sys/fs/cgroup and /proc/cmdline", "cgroup_mode_parser_v1", "text", True, "BLOCKS_ACCEPTANCE"),
    "host_cpu_model_logical_count": ("host_operator", "lscpu -J", "lscpu_json_parser_v1", "count", True, "BLOCKS_ACCEPTANCE"),
    "host_memory_swap_configuration": ("host_operator", "free -b and /proc/swaps", "memory_swap_parser_v1", "bytes", True, "BLOCKS_ACCEPTANCE"),
    "container_cpu_quota_cpuset_memory_limits": ("container_operator", "docker inspect and cgroup files", "container_limit_parser_v1", "mixed", True, "BLOCKS_ACCEPTANCE"),
    "topology_sha256": ("repository", "sha256sum accepted topology", "sha256_parser_v1", "sha256", True, "BLOCKS_MUTATION"),
    "dockerfile_sha256": ("repository", "sha256sum frozen Dockerfile", "sha256_parser_v1", "sha256", True, "BLOCKS_MUTATION"),
    "runtime_image_identity": ("docker_operator", "docker image inspect", "image_identity_parser_v1", "text", True, "BLOCKS_MUTATION"),
    "tc_iproute2_versions": ("container_operator", "tc -V and dpkg-query iproute2", "tool_version_parser_v1", "text", True, "BLOCKS_ACCEPTANCE"),
    "ping_version": ("container_operator", "ping -V", "tool_version_parser_v1", "text", True, "BLOCKS_ACCEPTANCE"),
    "iperf3_client_server_versions": ("container_operator", "iperf3 --version", "tool_version_parser_v1", "text", True, "BLOCKS_ACCEPTANCE"),
    "interface_identity_mtu_offload_speed": ("container_operator", "ip -j link, ethtool -k/-i", "interface_provenance_parser_v1", "mixed", True, "BLOCKS_ACCEPTANCE"),
    "clock_source": ("host_operator", "cat /sys/devices/system/clocksource/clocksource0/current_clocksource", "clock_source_parser_v1", "text", True, "BLOCKS_ACCEPTANCE"),
}

DYNAMIC_FIELDS: dict[str, tuple[str, str, str, str, bool, str]] = {
    "host_cpu_utilization_delta": ("host_operator", "procstat sampled delta", "procstat_delta_parser_v1", "ratio", True, "BLOCKS_ACCEPTANCE"),
    "host_load_average": ("host_operator", "cat /proc/loadavg", "loadavg_parser_v1", "load", True, "BLOCKS_ACCEPTANCE"),
    "cpu_pressure_stall": ("host_operator", "cat /proc/pressure/cpu", "psi_parser_v1", "microseconds", True, "BLOCKS_ACCEPTANCE"),
    "memory_availability_pressure": ("host_operator", "meminfo and /proc/pressure/memory", "memory_pressure_parser_v1", "bytes", True, "BLOCKS_ACCEPTANCE"),
    "swap_activity": ("host_operator", "vmstat sampled delta", "vmstat_delta_parser_v1", "pages", True, "BLOCKS_ACCEPTANCE"),
    "container_cgroup_cpu_usage": ("container_operator", "cgroup cpu.stat", "cgroup_cpu_parser_v1", "microseconds", True, "BLOCKS_ACCEPTANCE"),
    "container_cpu_throttling": ("container_operator", "cgroup cpu.stat", "cgroup_throttle_parser_v1", "count", True, "BLOCKS_ACCEPTANCE"),
    "container_memory_use": ("container_operator", "cgroup memory.current", "cgroup_memory_parser_v1", "bytes", True, "BLOCKS_ACCEPTANCE"),
    "iperf_process_lifecycle": ("container_operator", "ps and process start/exit records", "process_lifecycle_parser_v1", "state", True, "BLOCKS_ACCEPTANCE"),
    "interface_counter_deltas": ("container_operator", "ip -s -j link sampled delta", "interface_counter_delta_parser_v1", "packets_bytes", True, "BLOCKS_ACCEPTANCE"),
    "window_clock_bounds": ("qualification_runner", "runner wall/monotonic timestamps", "window_clock_parser_v1", "timestamp", True, "BLOCKS_ACCEPTANCE"),
    "startup_scheduling_skew": ("qualification_runner", "iperf/ping process timestamps", "startup_skew_parser_v1", "seconds", True, "BLOCKS_ACCEPTANCE"),
    "measurement_command_results": ("qualification_runner", "bounded command records", "command_record_parser_v1", "record", True, "BLOCKS_ACCEPTANCE"),
}

METRICS = ("packet_loss_ratio", "round_trip_latency_ms_p95", "throughput_mbps", "interface_utilization_ratio", "queue_drop_count")
QUALIFICATION_STATUSES = {"QUALIFIED", "UNSTABLE", "COLLECTION_UNAVAILABLE", "ENVIRONMENT_INELIGIBLE", "INCONCLUSIVE"}


def _fail(message: str) -> None:
    raise X6R13ContractError("X6-R1.3: " + message)


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail("canonical relative raw provenance path required")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        _fail("unsafe raw provenance path")
    return value


def _catalog(section: str) -> dict[str, tuple[str, str, str, str, bool, str]]:
    return STATIC_FIELDS if section == "static_environment_identity" else DYNAMIC_FIELDS


def validate_host_runtime_provenance(value: Mapping[str, Any], *, repository_root: Path) -> None:
    try:
        validate_schema_contract("x6_host_runtime_provenance_v1", value, repository_root=repository_root)
    except ExpansionContractError as error:
        _fail(str(error))
    for section in ("static_environment_identity", "dynamic_execution_context"):
        rows = value[section]
        assert isinstance(rows, list)
        expected = _catalog(section)
        by_id = {row.get("field_id"): row for row in rows if isinstance(row, dict)}
        if set(by_id) != set(expected) or len(by_id) != len(rows):
            _fail(section + " must contain each catalog field exactly once")
        for field_id, spec in expected.items():
            row = by_id[field_id]
            owner, source, parser, unit, required, absence = spec
            if tuple(row.get(key) for key in ("owner", "source", "parser", "unit", "required", "absence_effect")) != spec:
                _fail("field contract drift: " + field_id)
            _safe_relative(row.get("raw_provenance_path"))
            if row.get("availability") == "observed":
                if row.get("value") is None:
                    _fail("observed provenance cannot become null/healthy default: " + field_id)
                if section == "dynamic_execution_context" and not isinstance(row.get("value"), Mapping):
                    _fail("dynamic provenance must retain structured raw-derived data: " + field_id)
                if field_id == "interface_counter_deltas":
                    counter = row["value"]
                    assert isinstance(counter, Mapping)
                    if counter.get("counter_reset_or_wrap") is not False or counter.get("delta_valid") is not True:
                        _fail("counter reset or wrap cannot be interpreted as a queue-drop delta")
            elif row.get("value") is not None:
                _fail("unavailable provenance value must be null: " + field_id)
            if row.get("failure_behavior") != "FAIL_CLOSED_NEVER_COERCE_TO_HEALTHY":
                _fail("provenance failure behavior drift: " + field_id)


def provenance_admission(value: Mapping[str, Any]) -> str:
    """Classify availability only; this never diagnoses a network fault."""
    for section in ("static_environment_identity", "dynamic_execution_context"):
        catalog = _catalog(section)
        for row in value[section]:
            assert isinstance(row, Mapping)
            field_id = str(row["field_id"])
            if catalog[field_id][4] and row["availability"] != "observed":
                return "ENVIRONMENT_INELIGIBLE" if section == "static_environment_identity" else "COLLECTION_UNAVAILABLE"
    return "ELIGIBLE_FOR_BASELINE_QUALIFICATION_ONLY"


def _six(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN), "f")


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values); length = len(ordered); midpoint = length // 2
    return ordered[midpoint] if length % 2 else (ordered[midpoint - 1] + ordered[midpoint]) / Decimal(2)


def _statistics(values: list[Decimal]) -> tuple[str, str]:
    center = _median(values)
    return _six(center), _six(_median([abs(item - center) for item in values]))


def qualification_canonical_sha256(value: Mapping[str, Any]) -> str:
    copy = dict(value); copy.pop("sha256", None)
    return hashlib.sha256(json.dumps(copy, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_baseline_qualification(value: Mapping[str, Any]) -> None:
    required = {"schema_version", "release_id", "execution_kind", "numeric_limits_status", "windows", "calibration_window_ids", "holdout_window_ids", "statistics", "decision", "sha256"}
    if set(value) != required or value.get("schema_version") != 1 or value.get("release_id") != "X6_R1_3_BASELINE_STABILITY_AND_HOST_PROVENANCE_METHOD_GATE":
        _fail("qualification manifest identity/schema invalid")
    if value.get("execution_kind") != "BASELINE_ONLY_NO_MUTATION" or value.get("numeric_limits_status") != "UNRESOLVED_NO_RUNTIME_DERIVATION":
        _fail("qualification must remain prospective baseline-only with unresolved limits")
    if value.get("sha256") != qualification_canonical_sha256(value):
        _fail("qualification manifest hash is false or stale")
    windows = value.get("windows")
    if not isinstance(windows, list) or len(windows) != 30:
        _fail("qualification requires exactly 20 calibration and 10 holdout windows")
    ids: list[str] = []
    calibration: list[Mapping[str, Any]] = []; holdout: list[Mapping[str, Any]] = []
    previous = -1
    for row in windows:
        if not isinstance(row, Mapping) or not isinstance(row.get("window_id"), str) or not isinstance(row.get("monotonic_start_ns"), int):
            _fail("qualification window malformed")
        _safe_relative(row.get("raw_provenance_path"))
        if not isinstance(row.get("raw_provenance_sha256"), str):
            _fail("qualification window requires raw hash provenance")
        if row["monotonic_start_ns"] <= previous or row.get("mutation") != "NONE" or row.get("startup_skew_seconds") is None or float(row["startup_skew_seconds"]) > 0.250:
            _fail("qualification window ordering/mutation/skew invalid")
        previous = row["monotonic_start_ns"]; ids.append(row["window_id"])
        measures = row.get("measurements")
        if not isinstance(measures, Mapping) or set(measures) != set(METRICS):
            _fail("qualification window metric inventory invalid")
        if row.get("phase") == "calibration": calibration.append(row)
        elif row.get("phase") == "holdout": holdout.append(row)
        else: _fail("qualification window phase invalid")
    if len(set(ids)) != len(ids) or len(calibration) != 20 or len(holdout) != 10:
        _fail("qualification windows duplicate or have wrong cardinality")
    calibration_ids = value.get("calibration_window_ids"); holdout_ids = value.get("holdout_window_ids")
    if calibration_ids != [row["window_id"] for row in calibration] or holdout_ids != [row["window_id"] for row in holdout] or set(calibration_ids or []) & set(holdout_ids or []):
        _fail("calibration/holdout separation or chronology invalid")
    statistics = value.get("statistics")
    if not isinstance(statistics, Mapping) or set(statistics) != set(METRICS):
        _fail("qualification statistics inventory invalid")
    for metric in METRICS:
        calibration_values = [Decimal(str(row["measurements"][metric])) for row in calibration]
        holdout_values = [Decimal(str(row["measurements"][metric])) for row in holdout]
        calibration_median, calibration_mad = _statistics(calibration_values)
        holdout_median, holdout_mad = _statistics(holdout_values)
        expected = {"formula": "median_mad_independent_calibration_holdout_v1", "calibration_median": calibration_median, "calibration_mad": calibration_mad, "holdout_median": holdout_median, "holdout_mad": holdout_mad, "drift": _six(Decimal(holdout_median) - Decimal(calibration_median)), "numeric_limit": "UNRESOLVED"}
        if statistics[metric] != expected:
            _fail("qualification statistic recomputation/limit drift: " + metric)
    decision = value.get("decision")
    if not isinstance(decision, Mapping) or decision.get("status") not in QUALIFICATION_STATUSES or decision.get("status") != "INCONCLUSIVE" or decision.get("mutation_authorized") is not False or decision.get("pilot_authorized") is not False:
        _fail("qualification decision must remain inconclusive and non-authorizing")


def verify_future_baseline_qualification(experiment_root: Path, repository_root: Path) -> dict[str, object]:
    """Independent future-only verifier; rejects any attempt to treat this as F1 evidence."""
    root = Path(experiment_root)
    def load(relative: str) -> dict[str, Any]:
        try: value = json.loads((root / relative).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error: _fail("cannot read " + relative); raise AssertionError from error
        if not isinstance(value, dict): _fail("object required: " + relative)
        return value
    provenance = load("provenance/host_runtime_provenance_v1.json")
    qualification = load("qualification/baseline_qualification_v1.json")
    hashes = load("validation/raw_hashes.json")
    cleanup = load("validation/cleanup_provenance.json")
    validate_host_runtime_provenance(provenance, repository_root=repository_root)
    if provenance_admission(provenance) != "ELIGIBLE_FOR_BASELINE_QUALIFICATION_ONLY":
        _fail("required provenance is unavailable")
    validate_baseline_qualification(qualification)
    artifacts = hashes.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        _fail("raw qualification inventory missing")
    for relative, digest in artifacts.items():
        path = root / _safe_relative(relative)
        if not path.is_file() or not isinstance(digest, str) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            _fail("raw qualification hash mismatch")
    bound_paths = {
        row["raw_provenance_path"]: row["raw_provenance_sha256"]
        for row in qualification["windows"]
    }
    for section in ("static_environment_identity", "dynamic_execution_context"):
        for row in provenance[section]:
            bound_paths[row["raw_provenance_path"]] = row["raw_provenance_sha256"]
    if any(artifacts.get(path) != digest for path, digest in bound_paths.items()):
        _fail("qualification/provenance observation-to-raw hash chain invalid")
    if cleanup != {"status": "CLEANUP_CONFIRMED_NO_CONTAINERS_NAMESPACES_OR_IPERF", "lingering_iperf_processes": []}:
        _fail("cleanup/iperf lifecycle incomplete")
    return {"status": "INCONCLUSIVE", "authorization": "0/10_FALSE", "qualification": qualification}
