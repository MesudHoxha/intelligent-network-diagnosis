"""Read-only arithmetic audit for the consumed X6-R1 pilot."""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("X6-R1.1 audit requires object: " + str(path))
    return value


def audit_baseline_after(root: Path) -> dict[str, Any]:
    """Recompute the frozen throughput decision without writing to the tree."""
    root = Path(root)
    threshold = _load(root / "validation/threshold_manifest_v1.json")
    after = _load(root / "validation/baseline_after.json")
    raw_root = root / "raw/v4/performance_collector"
    baseline = [_load(raw_root / ("baseline_window_%02d.json" % index)) for index in range(1, 11)]
    restored = [_load(raw_root / ("restored_window_%02d.json" % index)) for index in range(1, 4)]
    before = _load(root / "validation/baseline_before.json")
    restoration = _load(root / "mutation/restoration_record.json")
    # The durable baseline-after file is the runner's canonical feature derivation;
    # raw records are independently retained for process/timing provenance.
    baseline_values = [float(json.loads(str(row["iperf"]["stdout"]))["end"]["sum_received"]["bits_per_second"]) / 1_000_000 for row in baseline]
    restored_values = [float(row["throughput_mbps"]["value"]) for row in after["windows"]]
    throughput = next(row for row in threshold["features"] if row["feature_id"] == "throughput_mbps")
    median = statistics.median(baseline_values)
    mad = statistics.median(abs(value - median) for value in baseline_values)
    lower = float(throughput["lower_threshold"])
    valid = all(value >= lower for value in restored_values)
    raw_health = {
        "client_return_codes": [row["iperf"]["return_code"] for row in restored],
        "server_return_codes": [row["server_teardown_after"]["return_code"] for row in restored],
        "ping_return_codes": [row["ping"]["return_code"] for row in restored],
        "qdisc_before_noqueue": ["noqueue" in str(row["qdisc_before"].get("stdout", "")) for row in restored],
        "qdisc_after_noqueue": ["noqueue" in str(row["qdisc_after"].get("stdout", "")) for row in restored],
    }
    window_provenance = []
    for index, row in enumerate(restored):
        iperf = json.loads(str(row["iperf"]["stdout"]))
        summary = iperf.get("end", {}).get("sum_sent", {})
        next_start = restored[index + 1]["server_start"].get("started_at_utc") if index + 1 < len(restored) else None
        window_provenance.append({
            "window_id": row["window_id"],
            "elapsed_seconds": row["elapsed_seconds"],
            "startup_skew_seconds": row["startup_skew_seconds"],
            "client_started_at_utc": row["iperf"].get("started_at_utc"),
            "client_completed_at_utc": row["iperf"].get("completed_at_utc"),
            "server_started_at_utc": row["server_start"].get("started_at_utc"),
            "server_teardown_completed_at_utc": row["server_teardown_after"].get("completed_at_utc"),
            "next_window_server_start_utc": next_start,
            "overlaps_next_window": bool(next_start and row["server_teardown_after"].get("completed_at_utc") and row["server_teardown_after"]["completed_at_utc"] > next_start),
            "retransmits": summary.get("retransmits"),
            "iperf_process_cpu_percent": iperf.get("end", {}).get("cpu_utilization_percent"),
            "r2_tx_bytes_delta": int(row["r2_tx_after"]["stdout"]) - int(row["r2_tx_before"]["stdout"]),
            "r3_rx_bytes_delta": int(row["r3_rx_after"]["stdout"]) - int(row["r3_rx_before"]["stdout"]),
        })
    return {
        "baseline_throughput_mbps": baseline_values,
        "median_mbps": median,
        "mad_mbps": mad,
        "scaled_dispersion_mbps": float(throughput["dispersion_term"]),
        "floor_tolerance_mbps": float(throughput["tolerance"]),
        "lower_threshold_mbps": lower,
        "restored_throughput_mbps": restored_values,
        "baseline_after_status": after["status"],
        "recomputed_status": "BASELINE_VALID_AFTER" if valid else "BASELINE_INVALID_AFTER",
        "raw_health": raw_health,
        "restored_window_provenance": window_provenance,
        "qdisc_removal_completed_at_utc": restoration.get("command_record", {}).get("completed_at_utc") if isinstance(restoration.get("command_record"), dict) else None,
        "first_restored_window_server_start_utc": restored[0]["server_start"].get("started_at_utc"),
        "baseline_route_and_speed_provenance": {"topology_preflight": before.get("topology_preflight"), "speed_mbps": before.get("speed_mbps")},
        "host_cpu_or_load_provenance": "ABSENT; iperf process CPU is not host CPU/load provenance",
        "classification": "C_INSUFFICIENT_EVIDENCE",
        "classification_reason": "The tree proves completed traffic and restored qdisc state but has no CPU/load provenance capable of distinguishing an implementation defect from host-local variability.",
    }
