"""Bounded X6 F1 composite-window collection and feature derivation."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
from statistics import median
from time import monotonic, monotonic_ns, sleep
from typing import Any

from src.collection.x6_r0_3_pre_runtime_validation import parse_iputils_ping_probe
from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2
from src.fault_injection.phase6_common import utc_now, write_json_atomic

FEATURES = ("packet_loss_ratio", "round_trip_latency_ms_p95", "throughput_mbps", "interface_utilization_ratio", "queue_drop_count", "rate_limit_detected")
CommandExecutor = Callable[[list[str]], dict[str, object]]

def unavailable(reason: str) -> dict[str, object]: return {"availability": "collection_unavailable", "value": None, "reason": reason}
def observed(value: object) -> dict[str, object]: return {"availability": "observed", "value": value}

def parse_iperf3(record: Mapping[str, object]) -> dict[str, object]:
    if record.get("return_code") != 0 or not isinstance(record.get("stdout"), str): return unavailable("iperf_execution_failure")
    try: value = json.loads(str(record["stdout"]))["end"]["sum_received"]["bits_per_second"]
    except (json.JSONDecodeError, KeyError, TypeError): return unavailable("malformed_iperf_json")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0: return unavailable("invalid_iperf_throughput")
    return observed(value / 1_000_000)

def _qdiscs(record: Mapping[str, object]) -> list[dict[str, Any]] | None:
    if record.get("return_code") != 0: return None
    try: value = json.loads(str(record.get("stdout", "")))
    except json.JSONDecodeError: return None
    return value if isinstance(value, list) and all(isinstance(row, dict) for row in value) else None

def exact_noqueue(qdisc: Mapping[str, object], filters: Sequence[Mapping[str, object]]) -> bool:
    rows = _qdiscs(qdisc)
    return rows is not None and len(rows) == 1 and rows[0].get("kind") == "noqueue" and rows[0].get("handle") == "0:" and all(_qdiscs(row) == [] for row in filters)

def exact_fault_hierarchy(qdisc: Mapping[str, object]) -> bool:
    rows = _qdiscs(qdisc)
    if rows is None: return False
    netem = [r for r in rows if r.get("kind") == "netem" and r.get("handle") == "10:" and r.get("parent") in {None, "root"}]
    pfifo = [r for r in rows if r.get("kind") == "pfifo" and r.get("handle") == "20:" and r.get("parent") == "10:1"]
    return len(netem) == len(pfifo) == 1 and len(rows) == 2

def qdisc_dropped(record: Mapping[str, object], *, kind: str, handle: str) -> int | None:
    rows = _qdiscs(record)
    if rows is None: return None
    matches = [row for row in rows if row.get("kind") == kind and row.get("handle") == handle]
    if len(matches) != 1: return None
    value = matches[0].get("stats", {}).get("drops") if isinstance(matches[0].get("stats"), dict) else matches[0].get("drops")
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

def rate_limit_absent(qdisc: Mapping[str, object], filters: Sequence[Mapping[str, object]], *, phase: str) -> dict[str, object]:
    rows = _qdiscs(qdisc); filter_rows = [_qdiscs(row) for row in filters]
    if rows is None or any(row is None for row in filter_rows): return unavailable("malformed_tc_configuration")
    text = json.dumps([rows, filter_rows], sort_keys=True).lower()
    if any(token in text for token in ('"kind": "tbf"', '"kind": "htb"', '"kind": "cake"', '"police"', '"rate"')): return observed(False)
    approved = exact_noqueue(qdisc, filters) if phase != "fault" else exact_fault_hierarchy(qdisc)
    return observed(False) if approved else unavailable("unapproved_qdisc_or_filter")

def parse_speed(record: Mapping[str, object]) -> int | None:
    if record.get("return_code") != 0: return None
    try: value = int(str(record.get("stdout", "")).strip())
    except ValueError: return None
    return value if value > 0 else None

def validate_speed_pair(r2: Mapping[str, object], r3: Mapping[str, object], r2_ethtool: Mapping[str, object], r3_ethtool: Mapping[str, object]) -> int:
    left, right = parse_speed(r2), parse_speed(r3)
    if left is None or right is None or left != right: raise RuntimeError("X6-R1 trustworthy equal interface speed unavailable")
    if r2_ethtool.get("return_code") != 0 or r3_ethtool.get("return_code") != 0 or f"Speed: {left}Mb/s" not in str(r2_ethtool.get("stdout", "")) or f"Speed: {right}Mb/s" not in str(r3_ethtool.get("stdout", "")): raise RuntimeError("X6-R1 ethtool speed corroboration failed")
    return left

def _counter(record: Mapping[str, object]) -> int | None:
    if record.get("return_code") != 0: return None
    try: value = int(str(record.get("stdout", "")).strip())
    except ValueError: return None
    return value if value >= 0 else None

def derive_window(raw: Mapping[str, object], *, phase: str, speed_mbps: int) -> dict[str, object]:
    ping = parse_iputils_ping_probe(raw["ping"]); throughput = parse_iperf3(raw["iperf"])
    before, after = _counter(raw["r2_tx_before"]), _counter(raw["r2_tx_after"])
    peer_before, peer_after = _counter(raw["r3_rx_before"]), _counter(raw["r3_rx_after"])
    elapsed = raw.get("elapsed_seconds")
    if None in (before, after, peer_before, peer_after) or not isinstance(elapsed, (int, float)) or elapsed <= 0 or after < before or peer_after < peer_before:
        utilization = unavailable("invalid_interface_counter_chain")
    else:
        ratio = 8 * (after-before) / (elapsed * speed_mbps * 1_000_000)
        utilization = observed(ratio) if 0 <= ratio <= 1 else unavailable("utilization_outside_domain")
    q_before = qdisc_dropped(raw["qdisc_before"], kind="pfifo", handle="20:") if phase == "fault" else 0
    q_after = qdisc_dropped(raw["qdisc_after"], kind="pfifo", handle="20:") if phase == "fault" else 0
    queue = observed(q_after-q_before) if q_before is not None and q_after is not None and q_after >= q_before else unavailable("invalid_pfifo_counter_chain")
    return {"packet_loss_ratio": ping["packet_loss_ratio"], "round_trip_latency_ms_p95": ping["round_trip_latency_ms_p95"], "throughput_mbps": throughput, "interface_utilization_ratio": utilization, "queue_drop_count": queue, "rate_limit_detected": rate_limit_absent(raw["qdisc_after"], raw["filters_after"], phase=phase)}

def aggregate_windows(windows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, object]]:
    if len(windows) != 3: raise ValueError("fault/restoration aggregation requires exactly three windows")
    for feature in FEATURES:
        if any(row[feature].get("availability") != "observed" for row in windows):
            return {name: unavailable("one_or_more_required_windows_unavailable") for name in FEATURES}
    loss = sum(float(row["packet_loss_ratio"]["value"]) for row in windows) / 3
    # Window p95 values are not pooled; caller supplies raw RTT samples separately for accepted runtime.
    return {
        "packet_loss_ratio": observed(loss),
        "round_trip_latency_ms_p95": observed(max(float(row["round_trip_latency_ms_p95"]["value"]) for row in windows)),
        "throughput_mbps": observed(median(float(row["throughput_mbps"]["value"]) for row in windows)),
        "interface_utilization_ratio": observed(median(float(row["interface_utilization_ratio"]["value"]) for row in windows)),
        "queue_drop_count": observed(sum(int(row["queue_drop_count"]["value"]) for row in windows)),
        "rate_limit_detected": observed(any(bool(row["rate_limit_detected"]["value"]) for row in windows)),
    }

def collect_window(window_id: str, phase: str, context: Mapping[str, Any], executor: CommandExecutor) -> dict[str, object]:
    traffic, qdisc = context["traffic"], context["qdisc"]
    def run(command: list[str]) -> dict[str, object]: return executor(command)
    teardown = run(traffic["server_teardown_command"]); server = run(traffic["server_command"])
    deadline = monotonic() + traffic["timeouts_seconds"]["server_readiness"]
    while True:
        ready = run(traffic["server_readiness_command"])
        if ready.get("return_code") == 0 and str(ready.get("stdout", "")).strip(): break
        if monotonic() >= deadline: raise RuntimeError("X6-R1 iperf server readiness failed")
        sleep(.1)
    before_ns = monotonic_ns()
    raw: dict[str, object] = {"window_id": window_id, "phase": phase, "server_start": server, "server_readiness": ready, "server_teardown_before": teardown}
    for key, command in (("r2_tx_before", ["docker","exec","clab-x6r1-r2","cat","/sys/class/net/eth2/statistics/tx_bytes"]),("r3_rx_before",["docker","exec","clab-x6r1-r3","cat","/sys/class/net/eth1/statistics/rx_bytes"]),("qdisc_before",qdisc["capture_command"])): raw[key]=run(command)
    with ThreadPoolExecutor(max_workers=2) as pool:
        iperf_started = monotonic_ns(); iperf = pool.submit(run, traffic["client_command"])
        target = iperf_started + 5_000_000_000
        while monotonic_ns() < target: sleep(min(.01, (target-monotonic_ns())/1e9))
        ping_started = monotonic_ns(); ping = pool.submit(run, traffic["ping_command"])
        raw["iperf"], raw["ping"] = iperf.result(), ping.result()
    expected_ping = iperf_started + 5_000_000_000
    raw["startup_skew_seconds"] = abs(ping_started-expected_ping)/1e9
    if raw["startup_skew_seconds"] > .250: raise RuntimeError("X6-R1 composite startup skew exceeded 0.250s")
    for key, command in (("r2_tx_after",["docker","exec","clab-x6r1-r2","cat","/sys/class/net/eth2/statistics/tx_bytes"]),("r3_rx_after",["docker","exec","clab-x6r1-r3","cat","/sys/class/net/eth1/statistics/rx_bytes"]),("qdisc_after",qdisc["capture_command"])): raw[key]=run(command)
    raw["filters_after"]=[run(command) for command in qdisc["filter_commands"]]
    raw["server_output"] = run(traffic["server_output_command"]); raw["server_teardown_after"] = run(traffic["server_teardown_command"])
    raw["elapsed_seconds"]=(monotonic_ns()-before_ns)/1e9; raw["collected_at_utc"]=utc_now()
    return raw

def materialize_evidence(root: Path, values: Mapping[str, Mapping[str, object]], raw_files: Sequence[Path], *, repository_root: Path) -> tuple[dict[str, object], dict[str, object]]:
    catalog_path=repository_root/"plans/expansion/X1_FEATURE_CATALOG_V1.json"; catalog=json.loads(catalog_path.read_text())
    artifacts=[{"path":str(path.relative_to(root)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()} for path in raw_files]
    owner="performance_collector:v1"; primary=artifacts[0]
    observations={name:{"value":values[name]["value"],"value_type":next(row["value_type"] for row in catalog["features"] if row["feature_id"]==name),"availability":values[name]["availability"],"collector_id":owner,"raw_artifact":primary["path"],"raw_artifact_sha256":primary["sha256"]} for name in FEATURES}
    evidence={"schema_version":4,"evidence_id":"x6_r1_packet_loss:evidence:v4","topology_context_id":"X6_TOP_01_CONTROLLED_PERFORMANCE_PATH","collected_at_utc":utc_now(),"observation_path":{"direction":"hosta_to_hostb","source_node":"hosta","destination_node":"hostb","observer_nodes":["r2","r3"]},"collector_runs":[{"schema_version":1,"collector_id":owner,"collector_version":"v1","domain":"performance","status":"completed","started_at_utc":utc_now(),"completed_at_utc":utc_now(),"feature_ids":list(FEATURES),"raw_artifacts":artifacts,"errors":[]}],"observations":observations,"compatibility":{"origin":"native_v4","source_schema_version":None,"source_artifact_sha256":None}}
    validate_evidence_v4(evidence,catalog,repository_root=repository_root); write_json_atomic(root/"parsed/evidence_v4.json",evidence)
    ep=root/"parsed/evidence_v4.json"; vector={"schema_version":2,"vector_id":"x6_r1_packet_loss:vector:v2","catalog_id":catalog["catalog_id"],"evidence_id":evidence["evidence_id"],"values":{name:{"value":values[name]["value"],"availability":values[name]["availability"]} for name in FEATURES},"mask_id":None,"provenance":{"evidence_sha256":hashlib.sha256(ep.read_bytes()).hexdigest(),"feature_catalog_sha256":hashlib.sha256(catalog_path.read_bytes()).hexdigest()}}
    validate_feature_vector_v2(vector,catalog,repository_root=repository_root); write_json_atomic(root/"parsed/feature_vector_v2.json",vector); return evidence,vector
