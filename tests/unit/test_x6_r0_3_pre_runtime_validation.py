from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from src.collection.x6_r0_2_measurement_semantics import build_threshold_manifest as build_r0_2_threshold_manifest
from src.collection.x6_r0_3_pre_runtime_validation import (
    FROZEN_FORMULA,
    FROZEN_ROUNDING,
    METHODOLOGY_VERSION,
    X6MeasurementSemanticsError,
    build_threshold_manifest,
    canonical_threshold_manifest_bytes,
    parse_iputils_ping_probe,
    validate_threshold_manifest,
)


ROOT = Path(__file__).resolve().parents[2]


def _ping_record(*, received: int, return_code: int, loss: str | None = None) -> dict[str, object]:
    lines = ["PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data."]
    lines.extend(
        f"64 bytes from 10.0.0.2: icmp_seq={sequence} ttl=64 time={sequence / 10:.3f} ms"
        for sequence in range(1, received + 1)
    )
    percentage = loss if loss is not None else str((50 - received) * 2)
    lines.extend(
        ["", "--- 10.0.0.2 ping statistics ---", f"50 packets transmitted, {received} received, {percentage}% packet loss, time 9800ms"]
    )
    return {"return_code": return_code, "stdout": "\n".join(lines) + "\n", "stderr": ""}


@pytest.mark.parametrize(
    ("received", "return_code", "expected_loss"),
    [(50, 0, 0.0), (49, 0, 0.02), (48, 0, 0.04), (1, 0, 0.98), (0, 1, 1.0)],
)
def test_iputils_return_code_and_count_table(received: int, return_code: int, expected_loss: float) -> None:
    result = parse_iputils_ping_probe(_ping_record(received=received, return_code=return_code))
    assert result["packet_loss_ratio"] == {"availability": "observed", "value": expected_loss}
    expected_rtt_availability = "observed" if received else "collection_unavailable"
    assert result["round_trip_latency_ms_p95"]["availability"] == expected_rtt_availability


def test_iputils_partial_reply_p95_is_exact_nearest_rank() -> None:
    result = parse_iputils_ping_probe(_ping_record(received=49, return_code=0))
    assert result["round_trip_latency_ms_p95"] == {"availability": "observed", "value": 4.7}
    result = parse_iputils_ping_probe(_ping_record(received=48, return_code=0))
    assert result["round_trip_latency_ms_p95"] == {"availability": "observed", "value": 4.6}


@pytest.mark.parametrize(
    ("record", "reason"),
    [
        (_ping_record(received=49, return_code=1), "contradictory_return_code"),
        (_ping_record(received=0, return_code=0), "contradictory_return_code"),
        ({"return_code": 1, "stdout": "ping: bad address 'invalid'\n", "stderr": ""}, "missing_or_malformed_summary"),
        ({"return_code": 2, "stdout": "", "stderr": "ping: socket: Operation not permitted"}, "timeout_or_execution_failure"),
        ({"return_code": 124, "stdout": "", "stderr": "wrapper timeout"}, "timeout_or_execution_failure"),
        ({"return_code": 0, "stdout": "malformed", "stderr": ""}, "missing_or_malformed_summary"),
        (_ping_record(received=48, return_code=0, loss="2"), "contradictory_summary_loss_ratio"),
    ],
)
def test_iputils_parser_rejects_return_code_errors_and_malformed_summaries(
    record: dict[str, object], reason: str
) -> None:
    result = parse_iputils_ping_probe(record)
    assert result["packet_loss_ratio"] == {"availability": "collection_unavailable", "value": None, "reason": reason}
    assert result["round_trip_latency_ms_p95"]["availability"] == "collection_unavailable"


def test_iputils_parser_rejects_reply_count_and_sequence_contradictions() -> None:
    missing_reply = _ping_record(received=2, return_code=0)
    missing_reply["stdout"] = str(missing_reply["stdout"]).replace(
        "64 bytes from 10.0.0.2: icmp_seq=2 ttl=64 time=0.200 ms\n", ""
    )
    assert parse_iputils_ping_probe(missing_reply)["packet_loss_ratio"]["reason"] == "reply_summary_count_mismatch"

    duplicate = _ping_record(received=2, return_code=0)
    duplicate["stdout"] = str(duplicate["stdout"]).replace("icmp_seq=2", "icmp_seq=1")
    assert parse_iputils_ping_probe(duplicate)["packet_loss_ratio"]["reason"] == "invalid_reply_sequence"


def _baselines() -> dict[str, list[object]]:
    return {
        "packet_loss_ratio": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "round_trip_latency_ms_p95": [1.0, 1.1, 0.9, 1.2, 1.0, 1.1, 0.9, 1.0, 1.2, 1.1],
        "throughput_mbps": [100, 99, 101, 100, 99, 101, 100, 100, 99, 101],
        "interface_utilization_ratio": [0.10, 0.11, 0.09, 0.10, 0.11, 0.09, 0.10, 0.10, 0.11, 0.09],
        "queue_drop_count": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    }


def _rehash(manifest: dict[str, object]) -> dict[str, object]:
    unsigned = copy.deepcopy(manifest)
    unsigned.pop("sha256", None)
    unsigned["sha256"] = hashlib.sha256(canonical_threshold_manifest_bytes(unsigned)).hexdigest()
    return unsigned


def _manifest() -> dict[str, object]:
    return build_threshold_manifest(_baselines(), topology_context_id="x6-top", traffic_context_id="x6-traffic")


def test_builder_manifest_passes_independent_semantic_validation_without_methodology_change() -> None:
    manifest = _manifest()
    historical = build_r0_2_threshold_manifest(_baselines(), topology_context_id="x6-top", traffic_context_id="x6-traffic")
    assert manifest == historical
    assert manifest["methodology_version"] == METHODOLOGY_VERSION
    assert manifest["formula"] == FROZEN_FORMULA
    assert manifest["rounding"] == FROZEN_ROUNDING
    validate_threshold_manifest(manifest, repository_root=ROOT)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("median", "9.000000"),
        ("mad", "9.000000"),
        ("tolerance", "9.000000"),
        ("lower_threshold", "9.000000"),
        ("upper_threshold", "9.000000"),
        ("dispersion_term", "9.000000"),
        ("mad_normal_scale", "9.000000"),
        ("dispersion_multiplier", "9.000000"),
        ("absolute_floor", "9.000000"),
        ("relative_floor", "9.000000"),
        ("unit", "wrong-unit"),
        ("value_type", "integer"),
    ],
)
def test_false_derived_feature_fields_are_rejected_even_when_rehashed(field: str, value: object) -> None:
    manifest = _manifest()
    manifest["features"][1][field] = value
    with pytest.raises(X6MeasurementSemanticsError):
        validate_threshold_manifest(_rehash(manifest), repository_root=ROOT)


def test_duplicate_missing_and_unexpected_features_are_rejected_even_when_rehashed() -> None:
    duplicate = _manifest()
    duplicate["features"][4] = copy.deepcopy(duplicate["features"][0])
    with pytest.raises(X6MeasurementSemanticsError):
        validate_threshold_manifest(_rehash(duplicate), repository_root=ROOT)

    missing = _manifest()
    missing["features"].pop()
    with pytest.raises(X6MeasurementSemanticsError):
        validate_threshold_manifest(_rehash(missing), repository_root=ROOT)

    unexpected = _manifest()
    unexpected["features"][4]["feature_id"] = "unexpected_numeric_feature"
    with pytest.raises(X6MeasurementSemanticsError):
        validate_threshold_manifest(_rehash(unexpected), repository_root=ROOT)


def test_false_formula_rounding_and_baselines_are_rejected_even_when_rehashed() -> None:
    formula = _manifest()
    formula["formula"] = "trust supplied thresholds"
    with pytest.raises(X6MeasurementSemanticsError):
        validate_threshold_manifest(_rehash(formula), repository_root=ROOT)

    rounding = _manifest()
    rounding["rounding"] = {"decimal_places": 3, "mode": "ROUND_UP", "serialization": "arbitrary"}
    with pytest.raises(X6MeasurementSemanticsError):
        validate_threshold_manifest(_rehash(rounding), repository_root=ROOT)

    unsorted = _manifest()
    unsorted["features"][1]["sorted_baseline_values"].reverse()
    with pytest.raises(X6MeasurementSemanticsError):
        validate_threshold_manifest(_rehash(unsorted), repository_root=ROOT)

    altered = _manifest()
    altered["features"][2]["sorted_baseline_values"][3:5] = ["99.000000", "99.000000"]
    with pytest.raises(X6MeasurementSemanticsError):
        validate_threshold_manifest(_rehash(altered), repository_root=ROOT)
