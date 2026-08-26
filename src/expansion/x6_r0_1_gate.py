from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.expansion.x5_r8_gate import verify_x5_r8_runtime_safety_gate
from src.expansion.x6_r0_gate import verify_x6_r0_gate


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R0_1_MEASUREMENT_AND_TRAFFIC_METHOD_GATE_V1.json")


class X6R01MethodologyError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X6R01MethodologyError(message)


def verify_x6_r0_1_measurement_and_traffic_method_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    verify_x5_r8_runtime_safety_gate(root)
    verify_x6_r0_gate(root)
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    _require(plan.get("status") == "ACCEPTED_SOURCE_ONLY_METHODOLOGY_GATE", "X6-R0.1 status drifted")
    _require(plan.get("source_boundary") == {"parent_commit": "01b66272acd803ba8aa23c12809b2a1a81dd03b1", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}, "X6-R0.1 source boundary drifted")
    track = plan.get("track")
    _require(track == {"current_release": "X6_R0_1_MEASUREMENT_AND_TRAFFIC_METHOD_GATE", "x5_status": "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION_REQUIRED_BEFORE_X5_AUTHORITY", "x6_r1_status": "PAUSED_PENDING_THIS_METHOD_AND_FUTURE_RUNTIME_AUTHORIZATION", "p9_r2_status": "PAUSED_BY_USER", "next_release": "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION"}, "X6-R0.1 track drifted")
    tools = plan.get("tools_and_direct_observations", {})
    _require(tools.get("loss_probe") == "ping -n -q -i 0.2 -c 50 -W 1 -s 56 <hostb_ip>", "X6-R0.1 loss probe drifted")
    _require(tools.get("throughput_client") == "iperf3 -c <hostb_ip> -t 20 -P 1 -J", "X6-R0.1 throughput command drifted")
    transport = tools.get("transport", {})
    _require(transport.get("baseline_window_count") == 10 and transport.get("warm_up_seconds") == 5 and transport.get("measurement_seconds") == 20, "X6-R0.1 window method drifted")
    numeric = plan.get("numeric_measurement_contract", {})
    _require("ceil(0.95*n)-1" in str(numeric.get("p95")), "X6-R0.1 p95 method drifted")
    _require("threshold_manifest" in str(numeric.get("baseline_threshold_formula")) and "not future ML labels" in str(numeric.get("predicate_boundary")), "X6-R0.1 leakage-safe threshold boundary drifted")
    faults = plan.get("fault_contexts")
    _require(isinstance(faults, list) and [(row.get("code"), row.get("fault_type")) for row in faults if isinstance(row, dict)] == [("F1", "packet_loss"), ("F2", "high_latency"), ("F3", "congestion"), ("F4", "bandwidth_rate_limiting")], "X6-R0.1 fault order drifted")
    _require(all(isinstance(row, dict) and row.get("conditional_predicates") and row.get("independent_effectiveness") for row in faults), "X6-R0.1 needs conditional signatures and independent effectiveness")
    _require(isinstance(faults[2], dict) and isinstance(faults[2].get("finite_bottleneck"), dict), "X6-R0.1 F3 finite bottleneck drifted")
    _require("at or below" in str(faults[3].get("independent_effectiveness")), "X6-R0.1 F4 dual proof drifted")
    authorization = plan.get("runtime_authorization")
    _require(isinstance(authorization, dict) and len(authorization) == 10 and all(value is False for value in authorization.values()), "X6-R0.1 must authorize 0/10 runtime/scientific operations")
    bindings = plan.get("source_bindings")
    _require(isinstance(bindings, list) and len(bindings) == 5, "X6-R0.1 requires five source bindings")
    for row in bindings:
        _require(isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str), "X6-R0.1 source binding malformed")
        path = root / row["path"]
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], "X6-R0.1 source binding drifted: " + row["path"])
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    plan = verify_x6_r0_1_measurement_and_traffic_method_gate(parser.parse_args().repository_root)
    print("x6_r0_1_measurement_and_traffic_method_gate=VERIFIED")
    print("conditional_performance_designs=4/4_METHOD_BOUND_PASS")
    print("runtime_scientific_authorization=0/10_FALSE_PASS")
    print("next_release=" + str(plan["track"]["next_release"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
