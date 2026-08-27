"""Authoritative pre-runtime validation semantics for the future X6 F1 slice.

X6-R0.2 remains immutable published history.  This append-only successor
reuses its frozen measurement constants and mathematical primitives while
correcting iputils return-code interpretation and independently validating
every derived threshold-manifest field.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from src.collection.x6_r0_2_measurement_semantics import (
    CANONICAL_DECIMAL_PLACES,
    F1_QDISC_HIERARCHY,
    MAD_MULTIPLIER,
    MAD_NORMAL_SCALE,
    METHODOLOGY_VERSION,
    NUMERIC_FEATURES,
    PING_PACKET_COUNT,
    PING_PROBE_CONTRACT_ID,
    THRESHOLD_SCHEMA,
    THRESHOLD_SPECS,
    X6MeasurementSemanticsError,
    _canonical_decimal,
    _decimal,
    _observed,
    _p95,
    _REPLY,
    _SUMMARY,
    _threshold_row,
    _unavailable,
    canonical_threshold_manifest_bytes,
    f1_counter_deltas,
    ping_probe_command,
)


ROOT = Path(__file__).resolve().parents[2]
FROZEN_FORMULA = "median +/- max(absolute_floor, relative_floor * abs(median), 3.000000 * 1.482600 * MAD)"
FROZEN_ROUNDING = {
    "decimal_places": CANONICAL_DECIMAL_PLACES,
    "mode": "ROUND_HALF_EVEN",
    "serialization": "canonical_json_sort_keys_compact_newline_v1",
}


def _ping_unavailable(reason: str, provenance: Mapping[str, object]) -> dict[str, object]:
    return {
        "packet_loss_ratio": _unavailable(reason),
        "round_trip_latency_ms_p95": _unavailable(reason),
        "provenance": dict(provenance),
    }


def parse_iputils_ping_probe(record: Mapping[str, object]) -> dict[str, object]:
    """Parse the frozen iputils probe and fail closed on any incomplete chain."""
    return_code = record.get("return_code")
    stdout = record.get("stdout")
    stderr = record.get("stderr")
    provenance = {
        "stdout": stdout,
        "stderr": stderr,
        "return_code": return_code,
        "contract_id": PING_PROBE_CONTRACT_ID,
    }
    if (
        isinstance(return_code, bool)
        or not isinstance(return_code, int)
        or not isinstance(stdout, str)
        or not isinstance(stderr, str)
    ):
        return _ping_unavailable("malformed_command_record", provenance)
    if return_code not in {0, 1}:
        return _ping_unavailable("timeout_or_execution_failure", provenance)

    summary = _SUMMARY.search(stdout)
    if summary is None:
        return _ping_unavailable("missing_or_malformed_summary", provenance)
    transmitted = int(summary.group("transmitted"))
    received = int(summary.group("received"))
    if transmitted != PING_PACKET_COUNT or received < 0 or received > transmitted:
        return _ping_unavailable("contradictory_summary_counts", provenance)

    expected_loss = Decimal(transmitted - received) / Decimal(transmitted)
    try:
        reported_loss = _decimal(summary.group("loss"), "packet loss percentage")
    except X6MeasurementSemanticsError:
        return _ping_unavailable("contradictory_summary_loss_ratio", provenance)
    if reported_loss != expected_loss * Decimal("100"):
        return _ping_unavailable("contradictory_summary_loss_ratio", provenance)

    # With this exact iputils command and no overall deadline, partial success
    # exits zero; one means that no replies were received.  Neither code is
    # evidence without the complete summary/reply chain above and below.
    if (return_code == 0 and not 1 <= received <= transmitted) or (return_code == 1 and received != 0):
        return _ping_unavailable("contradictory_return_code", provenance)

    replies = _REPLY.findall(stdout)
    sequences = [int(sequence) for sequence, _ in replies]
    if len(sequences) != len(set(sequences)) or any(sequence < 1 or sequence > transmitted for sequence in sequences):
        return _ping_unavailable("invalid_reply_sequence", provenance)
    if len(replies) != received:
        return _ping_unavailable("reply_summary_count_mismatch", provenance)

    loss = _observed(float(expected_loss))
    if received == 0:
        return {
            "packet_loss_ratio": loss,
            "round_trip_latency_ms_p95": _unavailable("no_successful_rtt_samples"),
            "provenance": provenance,
        }
    try:
        samples = [_decimal(rtt, "RTT sample") for _, rtt in replies]
    except X6MeasurementSemanticsError:
        return _ping_unavailable("malformed_rtt_sample", provenance)
    return {
        "packet_loss_ratio": loss,
        "round_trip_latency_ms_p95": _observed(float(_p95(samples))),
        "provenance": provenance,
    }


def _validate_threshold_semantics(manifest: Mapping[str, object]) -> None:
    if manifest.get("formula") != FROZEN_FORMULA:
        raise X6MeasurementSemanticsError("Threshold manifest formula drifted.")
    if manifest.get("rounding") != FROZEN_ROUNDING:
        raise X6MeasurementSemanticsError("Threshold manifest rounding metadata drifted.")

    features = manifest.get("features")
    if not isinstance(features, list) or len(features) != len(NUMERIC_FEATURES):
        raise X6MeasurementSemanticsError("Threshold manifest requires exactly five numeric X1 features.")
    identifiers = [row.get("feature_id") if isinstance(row, Mapping) else None for row in features]
    if len(set(identifiers)) != len(identifiers):
        raise X6MeasurementSemanticsError("Threshold manifest feature IDs must be unique.")
    if set(identifiers) != set(NUMERIC_FEATURES):
        raise X6MeasurementSemanticsError("Threshold manifest feature IDs are missing or unexpected.")
    if tuple(identifiers) != NUMERIC_FEATURES:
        raise X6MeasurementSemanticsError("Threshold manifest feature order is not canonical.")

    for supplied in features:
        if not isinstance(supplied, Mapping):
            raise X6MeasurementSemanticsError("Threshold manifest feature row is malformed.")
        feature_id = supplied["feature_id"]
        baseline = supplied.get("sorted_baseline_values")
        if not isinstance(baseline, list) or len(baseline) != 10:
            raise X6MeasurementSemanticsError(str(feature_id) + " requires exactly ten baseline windows.")
        try:
            decimals = [_decimal(value, str(feature_id) + " baseline") for value in baseline]
        except X6MeasurementSemanticsError:
            raise
        canonical_sorted = [_canonical_decimal(value) for value in sorted(decimals)]
        if baseline != canonical_sorted:
            raise X6MeasurementSemanticsError(str(feature_id) + " baselines are not canonical and sorted.")

        # Recompute center, MAD, scaled dispersion, all three tolerance
        # contributions, bounds, domain clamping and canonical rounding from
        # the baseline values.  No supplied derived field participates.
        expected = _threshold_row(str(feature_id), baseline)
        for field, expected_value in expected.items():
            if supplied.get(field) != expected_value:
                raise X6MeasurementSemanticsError(
                    str(feature_id) + " semantic mismatch for " + field + "."
                )


def validate_threshold_manifest(manifest: Mapping[str, object], *, repository_root: Path = ROOT) -> None:
    """Validate schema, independently recomputed semantics, and canonical SHA."""
    schema = json.loads((Path(repository_root) / THRESHOLD_SCHEMA).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        raise X6MeasurementSemanticsError("Threshold manifest schema failure: " + errors[0].message)
    _validate_threshold_semantics(manifest)
    unsigned = dict(manifest)
    actual = unsigned.pop("sha256")
    expected = hashlib.sha256(canonical_threshold_manifest_bytes(unsigned)).hexdigest()
    if actual != expected:
        raise X6MeasurementSemanticsError("Threshold manifest SHA-256 does not bind its canonical content.")


def build_threshold_manifest(
    baseline_windows: Mapping[str, Sequence[object]], *, topology_context_id: str, traffic_context_id: str
) -> dict[str, object]:
    """Build and semantically validate the unchanged X6-R0.2 manifest."""
    if set(baseline_windows) != set(NUMERIC_FEATURES):
        raise X6MeasurementSemanticsError("Threshold derivation requires exactly the five numeric X1 feature baselines.")
    if not topology_context_id or not traffic_context_id:
        raise X6MeasurementSemanticsError("Threshold manifest contexts must be non-empty.")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "methodology_version": METHODOLOGY_VERSION,
        "topology_context_id": topology_context_id,
        "traffic_context_id": traffic_context_id,
        "formula": FROZEN_FORMULA,
        "rounding": dict(FROZEN_ROUNDING),
        "features": [_threshold_row(feature_id, baseline_windows[feature_id]) for feature_id in NUMERIC_FEATURES],
        "boolean_feature_excluded": "rate_limit_detected",
        "fault_window_input": "FORBIDDEN",
        "post_hoc_override": "FORBIDDEN",
    }
    manifest["sha256"] = hashlib.sha256(canonical_threshold_manifest_bytes(manifest)).hexdigest()
    validate_threshold_manifest(manifest, repository_root=ROOT)
    return manifest


__all__ = [
    "F1_QDISC_HIERARCHY",
    "FROZEN_FORMULA",
    "FROZEN_ROUNDING",
    "METHODOLOGY_VERSION",
    "X6MeasurementSemanticsError",
    "build_threshold_manifest",
    "canonical_threshold_manifest_bytes",
    "f1_counter_deltas",
    "parse_iputils_ping_probe",
    "ping_probe_command",
    "validate_threshold_manifest",
]
