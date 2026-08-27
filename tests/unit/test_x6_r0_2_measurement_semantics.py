from __future__ import annotations

import copy
from pathlib import Path

import pytest

from src.collection.x6_r0_2_measurement_semantics import (
    F1_QDISC_HIERARCHY,
    METHODOLOGY_VERSION,
    X6MeasurementSemanticsError,
    build_threshold_manifest,
    canonical_threshold_manifest_bytes,
    f1_counter_deltas,
    parse_iputils_ping_probe,
    ping_probe_command,
    validate_threshold_manifest,
)


def _ping_record(*, received: int, return_code: int, rtts: list[float] | None = None, loss: str | None = None) -> dict[str, object]:
    rtts = list(rtts or [])
    lines = ["PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data."]
    lines.extend(f"64 bytes from 10.0.0.2: icmp_seq={index} ttl=64 time={rtt:.3f} ms" for index, rtt in enumerate(rtts, 1))
    percentage = loss if loss is not None else str((50 - received) * 2)
    lines.extend(["", "--- 10.0.0.2 ping statistics ---", f"50 packets transmitted, {received} received, {percentage}% packet loss, time 9800ms"])
    return {"return_code": return_code, "stdout": "\n".join(lines) + "\n", "stderr": ""}


def test_nonquiet_probe_freezes_locale_command_and_shared_packets() -> None:
    probe = ping_probe_command("10.51.3.2")
    assert probe["environment"] == {"LC_ALL": "C"}
    assert "-q" not in probe["command"]
    assert probe["packet_count"] == 50 and probe["measurement_window_seconds"] == "10.0"


def test_ping_parser_all_success_and_exact_p95() -> None:
    result = parse_iputils_ping_probe(_ping_record(received=50, return_code=0, rtts=[float(index) / 10 for index in range(1, 51)]))
    assert result["packet_loss_ratio"] == {"availability": "observed", "value": 0.0}
    assert result["round_trip_latency_ms_p95"] == {"availability": "observed", "value": 4.8}


def test_ping_parser_partial_and_complete_loss_keep_latency_semantics_distinct() -> None:
    partial = parse_iputils_ping_probe(_ping_record(received=48, return_code=1, rtts=[1.0] * 48))
    complete = parse_iputils_ping_probe(_ping_record(received=0, return_code=1))
    assert partial["packet_loss_ratio"]["value"] == 0.04 and partial["round_trip_latency_ms_p95"]["availability"] == "observed"
    assert complete["packet_loss_ratio"]["value"] == 1.0
    assert complete["round_trip_latency_ms_p95"] == {"availability": "collection_unavailable", "value": None, "reason": "no_successful_rtt_samples"}


def test_ping_parser_p95_is_deterministic_for_odd_and_even_success_counts() -> None:
    odd = parse_iputils_ping_probe(_ping_record(received=49, return_code=1, rtts=[float(index) for index in range(1, 50)]))
    even = parse_iputils_ping_probe(_ping_record(received=48, return_code=1, rtts=[float(index) for index in range(1, 49)]))
    assert odd["round_trip_latency_ms_p95"]["value"] == 47.0
    assert even["round_trip_latency_ms_p95"]["value"] == 46.0


@pytest.mark.parametrize(
    "record,reason",
    [
        ({"return_code": 0, "stdout": "not ping", "stderr": ""}, "missing_or_malformed_summary"),
        (_ping_record(received=50, return_code=0, rtts=[]), "reply_summary_count_mismatch"),
        (_ping_record(received=49, return_code=1, rtts=[1.0] * 49, loss="0"), "contradictory_summary_loss_ratio"),
        ({"return_code": 124, "stdout": "", "stderr": "timeout"}, "timeout_or_execution_failure"),
    ],
)
def test_ping_parser_fails_closed_for_unavailable_or_contradictory_output(record: dict[str, object], reason: str) -> None:
    result = parse_iputils_ping_probe(record)
    assert result["packet_loss_ratio"]["availability"] == "collection_unavailable"
    assert result["packet_loss_ratio"]["reason"] == reason
    assert result["round_trip_latency_ms_p95"]["availability"] == "collection_unavailable"


def _baselines() -> dict[str, list[object]]:
    return {
        "packet_loss_ratio": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "round_trip_latency_ms_p95": [1.0, 1.1, 0.9, 1.2, 1.0, 1.1, 0.9, 1.0, 1.2, 1.1],
        "throughput_mbps": [100, 99, 101, 100, 99, 101, 100, 100, 99, 101],
        "interface_utilization_ratio": [0.10, 0.11, 0.09, 0.10, 0.11, 0.09, 0.10, 0.10, 0.11, 0.09],
        "queue_drop_count": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    }


def test_threshold_manifest_is_canonical_order_independent_and_hash_bound() -> None:
    baseline = _baselines()
    first = build_threshold_manifest(baseline, topology_context_id="x6-top", traffic_context_id="x6-traffic")
    reordered = {name: list(reversed(values)) for name, values in baseline.items()}
    second = build_threshold_manifest(reordered, topology_context_id="x6-top", traffic_context_id="x6-traffic")
    assert first == second
    assert first["methodology_version"] == METHODOLOGY_VERSION
    assert canonical_threshold_manifest_bytes(first).endswith(b"\n")
    validate_threshold_manifest(first, repository_root=Path(__file__).resolve().parents[2])


def test_threshold_manifest_changes_with_baseline_and_rejects_fault_or_override_inputs() -> None:
    baseline = _baselines(); changed = _baselines(); changed["throughput_mbps"][0] = 98
    first = build_threshold_manifest(baseline, topology_context_id="x6-top", traffic_context_id="x6-traffic")
    second = build_threshold_manifest(changed, topology_context_id="x6-top", traffic_context_id="x6-traffic")
    assert first["sha256"] != second["sha256"]
    with pytest.raises(X6MeasurementSemanticsError):
        build_threshold_manifest({**baseline, "fault_window": [1]}, topology_context_id="x6-top", traffic_context_id="x6-traffic")
    tampered = copy.deepcopy(first); tampered["features"][0]["absolute_floor"] = "9.999999"
    with pytest.raises(X6MeasurementSemanticsError):
        validate_threshold_manifest(tampered, repository_root=Path(__file__).resolve().parents[2])


def _snapshot(*, netem_drops: int, queue_drops: int) -> dict[str, object]:
    return {"qdiscs": [
        {"kind": "netem", "handle": "10:", "parent": "root", "stats": {"dropped": netem_drops}},
        {"kind": "pfifo", "handle": "20:", "parent": "10:1", "stats": {"dropped": queue_drops}},
    ]}


def test_f1_qdisc_counters_separate_impairment_from_congestion_overflow() -> None:
    result = f1_counter_deltas(_snapshot(netem_drops=3, queue_drops=7), _snapshot(netem_drops=9, queue_drops=7))
    assert result["netem_impairment_drop_delta"] == 6
    assert result["queue_drop_count"] == 0
    assert "queue_delta_zero" not in result
    assert result["counter_owners"]["queue_drop_count"] == F1_QDISC_HIERARCHY["congestion_queue"]


def test_f1_qdisc_counter_handles_overflow_and_invalid_snapshots_fail_closed() -> None:
    assert f1_counter_deltas(_snapshot(netem_drops=0, queue_drops=2), _snapshot(netem_drops=0, queue_drops=5))["queue_drop_count"] == 3
    with pytest.raises(X6MeasurementSemanticsError):
        f1_counter_deltas(_snapshot(netem_drops=0, queue_drops=0), {"qdiscs": []})
    with pytest.raises(X6MeasurementSemanticsError):
        f1_counter_deltas(_snapshot(netem_drops=0, queue_drops=0), {"qdiscs": [{"kind": "netem", "handle": "99:", "parent": "root", "stats": {"dropped": 0}}]})
    with pytest.raises(X6MeasurementSemanticsError):
        f1_counter_deltas(_snapshot(netem_drops=1, queue_drops=1), _snapshot(netem_drops=0, queue_drops=0))
