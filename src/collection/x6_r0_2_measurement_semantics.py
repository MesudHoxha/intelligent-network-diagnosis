"""Deterministic, source-only measurement semantics for the future X6 F1 slice.

This module neither executes a probe nor configures ``tc``.  It defines the
inputs a future collector must preserve and the parsing/threshold/counter
semantics it must use before it may produce Evidence v4 observations.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
THRESHOLD_SCHEMA = Path("schemas/x6_threshold_manifest_v1.schema.json")
METHODOLOGY_VERSION = "x6_r0_2_f1_measurement_semantics_v1"
PING_PROBE_CONTRACT_ID = "x6_f1_iputils_ping_nonquiet_v1"
PING_EXECUTABLE = "/usr/bin/ping"
PING_VERSION_COMMAND = (PING_EXECUTABLE, "-V")
PING_FLAGS = ("-n", "-i", "0.2", "-c", "50", "-W", "1", "-s", "56")
PING_PACKET_COUNT = 50
PING_INTERVAL_SECONDS = Decimal("0.2")
PING_TIMEOUT_SECONDS = 1
PING_PAYLOAD_BYTES = 56
PING_WARM_UP_SECONDS = 5
PING_MEASUREMENT_WINDOW_SECONDS = Decimal("10.0")
CANONICAL_DECIMAL_PLACES = 6
DECIMAL_QUANTUM = Decimal("0.000001")
NUMERIC_FEATURES = (
    "packet_loss_ratio",
    "round_trip_latency_ms_p95",
    "throughput_mbps",
    "interface_utilization_ratio",
    "queue_drop_count",
)


class X6MeasurementSemanticsError(ValueError):
    """Raised when a source-only X6 measurement contract is violated."""


def _unavailable(reason: str) -> dict[str, object]:
    return {"availability": "collection_unavailable", "value": None, "reason": reason}


def _observed(value: int | float) -> dict[str, object]:
    return {"availability": "observed", "value": value}


def ping_probe_command(destination_ip: str) -> dict[str, object]:
    """Return the immutable, non-quiet command/provenance contract for F1."""
    if not isinstance(destination_ip, str) or not destination_ip:
        raise X6MeasurementSemanticsError("The ping destination must be a non-empty string.")
    return {
        "contract_id": PING_PROBE_CONTRACT_ID,
        "environment": {"LC_ALL": "C"},
        "command": [PING_EXECUTABLE, *PING_FLAGS, destination_ip],
        "version_command": list(PING_VERSION_COMMAND),
        "packet_count": PING_PACKET_COUNT,
        "interval_seconds": str(PING_INTERVAL_SECONDS),
        "timeout_seconds": PING_TIMEOUT_SECONDS,
        "payload_bytes": PING_PAYLOAD_BYTES,
        "warm_up_seconds": PING_WARM_UP_SECONDS,
        "measurement_window_seconds": str(PING_MEASUREMENT_WINDOW_SECONDS),
        "direction": "hosta_to_hostb",
        "raw_output_required": ["stdout", "stderr", "return_code"],
    }


_SUMMARY = re.compile(
    r"(?m)^(?P<transmitted>\d+) packets transmitted, (?P<received>\d+)(?: packets)? received, "
    r"(?P<loss>[0-9]+(?:\.[0-9]+)?)% packet loss(?:,.*)?$"
)
_REPLY = re.compile(
    r"(?m)^\d+ bytes from .+?: icmp_seq=(?P<sequence>\d+)(?:[^\n]*?) time=(?P<rtt>[0-9]+(?:\.[0-9]+)?)\s*ms$"
)


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise X6MeasurementSemanticsError(label + " must be numeric.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise X6MeasurementSemanticsError(label + " must be numeric.") from error
    if not number.is_finite():
        raise X6MeasurementSemanticsError(label + " must be finite.")
    return number


def _p95(samples: Sequence[Decimal]) -> Decimal:
    if not samples:
        raise X6MeasurementSemanticsError("p95 requires at least one successful RTT sample.")
    ordered = sorted(samples)
    return ordered[math.ceil(Decimal("0.95") * len(ordered)) - 1]


def parse_iputils_ping_probe(record: Mapping[str, object]) -> dict[str, object]:
    """Parse only the frozen non-quiet iputils output, failing closed on drift."""
    return_code = record.get("return_code")
    stdout = record.get("stdout")
    stderr = record.get("stderr")
    provenance = {"stdout": stdout, "stderr": stderr, "return_code": return_code, "contract_id": PING_PROBE_CONTRACT_ID}
    if isinstance(return_code, bool) or not isinstance(return_code, int) or not isinstance(stdout, str) or not isinstance(stderr, str):
        return {"packet_loss_ratio": _unavailable("malformed_command_record"), "round_trip_latency_ms_p95": _unavailable("malformed_command_record"), "provenance": provenance}
    if return_code not in {0, 1}:
        return {"packet_loss_ratio": _unavailable("timeout_or_execution_failure"), "round_trip_latency_ms_p95": _unavailable("timeout_or_execution_failure"), "provenance": provenance}
    summary = _SUMMARY.search(stdout)
    if summary is None:
        return {"packet_loss_ratio": _unavailable("missing_or_malformed_summary"), "round_trip_latency_ms_p95": _unavailable("missing_or_malformed_summary"), "provenance": provenance}
    transmitted = int(summary.group("transmitted")); received = int(summary.group("received"))
    if transmitted != PING_PACKET_COUNT or received < 0 or received > transmitted:
        return {"packet_loss_ratio": _unavailable("contradictory_summary_counts"), "round_trip_latency_ms_p95": _unavailable("contradictory_summary_counts"), "provenance": provenance}
    expected_loss = Decimal(transmitted - received) / Decimal(transmitted)
    if _decimal(summary.group("loss"), "packet loss percentage") != expected_loss * Decimal("100"):
        return {"packet_loss_ratio": _unavailable("contradictory_summary_loss_ratio"), "round_trip_latency_ms_p95": _unavailable("contradictory_summary_loss_ratio"), "provenance": provenance}
    if (return_code == 0) != (received == transmitted):
        return {"packet_loss_ratio": _unavailable("contradictory_return_code"), "round_trip_latency_ms_p95": _unavailable("contradictory_return_code"), "provenance": provenance}
    replies = _REPLY.findall(stdout)
    sequences = [int(sequence) for sequence, _ in replies]
    if len(sequences) != len(set(sequences)) or any(sequence < 1 or sequence > transmitted for sequence in sequences):
        return {"packet_loss_ratio": _unavailable("invalid_reply_sequence"), "round_trip_latency_ms_p95": _unavailable("invalid_reply_sequence"), "provenance": provenance}
    if len(replies) != received:
        return {"packet_loss_ratio": _unavailable("reply_summary_count_mismatch"), "round_trip_latency_ms_p95": _unavailable("reply_summary_count_mismatch"), "provenance": provenance}
    loss = _observed(float(expected_loss))
    if received == 0:
        return {"packet_loss_ratio": loss, "round_trip_latency_ms_p95": _unavailable("no_successful_rtt_samples"), "provenance": provenance}
    try:
        samples = [_decimal(rtt, "RTT sample") for _, rtt in replies]
    except X6MeasurementSemanticsError:
        return {"packet_loss_ratio": _unavailable("malformed_rtt_sample"), "round_trip_latency_ms_p95": _unavailable("malformed_rtt_sample"), "provenance": provenance}
    return {"packet_loss_ratio": loss, "round_trip_latency_ms_p95": _observed(float(_p95(samples))), "provenance": provenance}


THRESHOLD_SPECS: dict[str, dict[str, object]] = {
    "packet_loss_ratio": {"value_type": "number", "unit": "ratio", "minimum": "0", "maximum": "1", "comparison": "upper", "absolute_floor": "0.020000", "relative_floor": "0.000000", "rationale": "One loss event is the 1/50 probe-resolution floor."},
    "round_trip_latency_ms_p95": {"value_type": "number", "unit": "ms", "minimum": "0", "maximum": None, "comparison": "upper", "absolute_floor": "0.100000", "relative_floor": "0.050000", "rationale": "0.1 ms is a conservative reporting-resolution and numeric-stability floor."},
    "throughput_mbps": {"value_type": "number", "unit": "Mbps", "minimum": "0", "maximum": None, "comparison": "lower", "absolute_floor": "0.100000", "relative_floor": "0.050000", "rationale": "0.1 Mbps plus five percent avoids classifying negligible tool/window variation as degradation."},
    "interface_utilization_ratio": {"value_type": "number", "unit": "ratio", "minimum": "0", "maximum": "1", "comparison": "upper", "absolute_floor": "0.020000", "relative_floor": "0.000000", "rationale": "Two percent is a conservative bounded-ratio measurement floor."},
    "queue_drop_count": {"value_type": "integer", "unit": "packets", "minimum": "0", "maximum": None, "comparison": "upper", "absolute_floor": "1.000000", "relative_floor": "0.000000", "rationale": "A counter is integral; one packet is its minimum non-zero resolution."},
}
MAD_NORMAL_SCALE = Decimal("1.482600")
MAD_MULTIPLIER = Decimal("3.000000")


def _canonical_decimal(value: Decimal) -> str:
    return format(value.quantize(DECIMAL_QUANTUM, rounding=ROUND_HALF_EVEN), "f")


def _median(values: Sequence[Decimal]) -> Decimal:
    ordered = sorted(values); middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def _threshold_row(feature_id: str, values: Sequence[object]) -> dict[str, object]:
    spec = THRESHOLD_SPECS[feature_id]
    if len(values) != 10:
        raise X6MeasurementSemanticsError(feature_id + " requires exactly ten baseline windows.")
    decimals = [_decimal(value, feature_id) for value in values]
    minimum = _decimal(spec["minimum"], feature_id + " minimum")
    maximum = _decimal(spec["maximum"], feature_id + " maximum") if spec["maximum"] is not None else None
    if any(value < minimum or (maximum is not None and value > maximum) for value in decimals):
        raise X6MeasurementSemanticsError(feature_id + " baseline is outside its frozen domain.")
    if spec["value_type"] == "integer" and any(value != value.to_integral_value() for value in decimals):
        raise X6MeasurementSemanticsError(feature_id + " baseline must be integral.")
    center = _median(decimals); mad = _median([abs(value - center) for value in decimals])
    dispersion = MAD_MULTIPLIER * MAD_NORMAL_SCALE * mad
    absolute = _decimal(spec["absolute_floor"], feature_id + " absolute floor")
    relative = _decimal(spec["relative_floor"], feature_id + " relative floor")
    tolerance = max(absolute, relative * abs(center), dispersion)
    lower, upper = center - tolerance, center + tolerance
    lower = max(minimum, lower)
    if maximum is not None:
        upper = min(maximum, upper)
    return {
        "feature_id": feature_id,
        "value_type": spec["value_type"],
        "unit": spec["unit"],
        "comparison_direction": spec["comparison"],
        "sorted_baseline_values": [_canonical_decimal(value) for value in sorted(decimals)],
        "center_estimator": "median_sorted_middle_or_even_mean_v1",
        "median": _canonical_decimal(center),
        "dispersion_estimator": "mad_about_median_v1",
        "mad": _canonical_decimal(mad),
        "mad_normal_scale": _canonical_decimal(MAD_NORMAL_SCALE),
        "dispersion_multiplier": _canonical_decimal(MAD_MULTIPLIER),
        "dispersion_term": _canonical_decimal(dispersion),
        "absolute_floor": _canonical_decimal(absolute),
        "relative_floor": _canonical_decimal(relative),
        "tolerance": _canonical_decimal(tolerance),
        "lower_threshold": _canonical_decimal(lower),
        "upper_threshold": _canonical_decimal(upper),
        "rationale": spec["rationale"],
    }


def canonical_threshold_manifest_bytes(manifest: Mapping[str, object]) -> bytes:
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def build_threshold_manifest(
    baseline_windows: Mapping[str, Sequence[object]], *, topology_context_id: str, traffic_context_id: str
) -> dict[str, object]:
    """Build a byte-stable manifest from baseline values only; no fault input exists."""
    if set(baseline_windows) != set(NUMERIC_FEATURES):
        raise X6MeasurementSemanticsError("Threshold derivation requires exactly the five numeric X1 feature baselines.")
    if not topology_context_id or not traffic_context_id:
        raise X6MeasurementSemanticsError("Threshold manifest contexts must be non-empty.")
    manifest: dict[str, object] = {
        "schema_version": 1,
        "methodology_version": METHODOLOGY_VERSION,
        "topology_context_id": topology_context_id,
        "traffic_context_id": traffic_context_id,
        "formula": "median +/- max(absolute_floor, relative_floor * abs(median), 3.000000 * 1.482600 * MAD)",
        "rounding": {"decimal_places": CANONICAL_DECIMAL_PLACES, "mode": "ROUND_HALF_EVEN", "serialization": "canonical_json_sort_keys_compact_newline_v1"},
        "features": [_threshold_row(feature_id, baseline_windows[feature_id]) for feature_id in NUMERIC_FEATURES],
        "boolean_feature_excluded": "rate_limit_detected",
        "fault_window_input": "FORBIDDEN",
        "post_hoc_override": "FORBIDDEN",
    }
    manifest["sha256"] = hashlib.sha256(canonical_threshold_manifest_bytes(manifest)).hexdigest()
    validate_threshold_manifest(manifest, repository_root=ROOT)
    return manifest


def validate_threshold_manifest(manifest: Mapping[str, object], *, repository_root: Path) -> None:
    schema = json.loads((repository_root / THRESHOLD_SCHEMA).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        raise X6MeasurementSemanticsError("Threshold manifest schema failure: " + errors[0].message)
    unsigned = dict(manifest); actual = unsigned.pop("sha256")
    expected = hashlib.sha256(canonical_threshold_manifest_bytes(unsigned)).hexdigest()
    if actual != expected:
        raise X6MeasurementSemanticsError("Threshold manifest SHA-256 does not bind its canonical content.")


F1_QDISC_HIERARCHY = {
    "netem_impairment": {"kind": "netem", "handle": "10:", "parent": "root", "counter_field": "dropped", "meaning": "intentional impairment drops; provenance/effectiveness only"},
    "congestion_queue": {"kind": "pfifo", "handle": "20:", "parent": "10:1", "counter_field": "dropped", "meaning": "X1 queue_drop_count owner; congestion-queue overflow only"},
    "snapshot_command": ["tc", "-s", "qdisc", "show", "dev", "<r2_egress>"],
}


def _qdisc_drop(snapshot: Mapping[str, object], role: str) -> int:
    expected = F1_QDISC_HIERARCHY[role]
    rows = snapshot.get("qdiscs")
    if not isinstance(rows, list):
        raise X6MeasurementSemanticsError("Missing qdisc snapshot rows.")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("handle") == expected["handle"]]
    if len(matches) != 1:
        raise X6MeasurementSemanticsError("Missing or duplicate expected qdisc handle: " + str(expected["handle"]))
    row = matches[0]
    if row.get("kind") != expected["kind"] or row.get("parent") != expected["parent"]:
        raise X6MeasurementSemanticsError("Unexpected qdisc kind or parent for " + role)
    stats = row.get("stats")
    drops = stats.get(expected["counter_field"]) if isinstance(stats, Mapping) else None
    if isinstance(drops, bool) or not isinstance(drops, int) or drops < 0:
        raise X6MeasurementSemanticsError("Missing or invalid qdisc dropped counter for " + role)
    return drops


def f1_counter_deltas(before: Mapping[str, object], after: Mapping[str, object]) -> dict[str, object]:
    """Return raw counters only; Rule-Based predicates are deliberately absent."""
    before_netem, after_netem = _qdisc_drop(before, "netem_impairment"), _qdisc_drop(after, "netem_impairment")
    before_queue, after_queue = _qdisc_drop(before, "congestion_queue"), _qdisc_drop(after, "congestion_queue")
    if after_netem < before_netem or after_queue < before_queue:
        raise X6MeasurementSemanticsError("Qdisc counter reset, wrap, or inconsistent snapshot order.")
    return {
        "availability": "observed",
        "queue_drop_count": after_queue - before_queue,
        "netem_impairment_drop_delta": after_netem - before_netem,
        "counter_owners": {"queue_drop_count": F1_QDISC_HIERARCHY["congestion_queue"], "netem_impairment_drop_delta": F1_QDISC_HIERARCHY["netem_impairment"]},
    }
