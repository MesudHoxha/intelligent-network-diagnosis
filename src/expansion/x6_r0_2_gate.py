"""Source gate for the append-only X6-R0.2 F1 measurement correction."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.collection.x6_r0_2_measurement_semantics import (
    F1_QDISC_HIERARCHY,
    METHODOLOGY_VERSION,
    PING_PROBE_CONTRACT_ID,
    THRESHOLD_SPECS,
)
from src.expansion.x5_r10_closeout_gate import verify_x5_r10_closeout
from src.expansion.x6_r0_1_gate import verify_x6_r0_1_measurement_and_traffic_method_gate


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R0_2_F1_MEASUREMENT_SEMANTICS_CORRECTION_V1.json")


class X6R02MethodologyError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X6R02MethodologyError(message)


def verify_x6_r0_2_f1_measurement_semantics(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    verify_x5_r10_closeout(root)
    verify_x6_r0_1_measurement_and_traffic_method_gate(root)
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    _require(plan.get("status") == "ACCEPTED_SOURCE_ONLY_METHODOLOGY_SUCCESSOR", "X6-R0.2 status drifted")
    _require(plan.get("source_boundary") == {"parent_commit": "72c9ba2a00f6e9a7606447c8ae89ceba93a95e7f", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}, "X6-R0.2 source boundary drifted")
    _require(plan.get("historical_predecessors") == {"x6_r0": "PRESERVED_DESIGN_ONLY", "x6_r0_1": "PRESERVED_SOURCE_ONLY_0_OF_10_AUTHORIZATION"}, "X6-R0.2 historical preservation drifted")
    probe = plan.get("probe_contract", {})
    _require(probe.get("contract_id") == PING_PROBE_CONTRACT_ID and probe.get("forbidden_flag") == "-q" and "-q" not in probe.get("flags", []), "X6-R0.2 non-quiet probe drifted")
    threshold = plan.get("threshold_manifest_contract", {})
    _require(threshold.get("methodology_version") == METHODOLOGY_VERSION and threshold.get("fault_window_input") == "FORBIDDEN" and threshold.get("post_hoc_override") == "FORBIDDEN", "X6-R0.2 threshold determinism drifted")
    _require(set(threshold.get("floors", {})) == set(THRESHOLD_SPECS), "X6-R0.2 threshold feature floors drifted")
    qdisc = plan.get("f1_qdisc_counter_contract", {})
    _require(qdisc.get("netem_impairment") == {**F1_QDISC_HIERARCHY["netem_impairment"], "role": "mutation_effectiveness_and_provenance_only"}, "X6-R0.2 netem ownership drifted")
    _require(qdisc.get("congestion_queue") == {**F1_QDISC_HIERARCHY["congestion_queue"], "role": "sole_X1_queue_drop_count_owner"}, "X6-R0.2 congestion queue ownership drifted")
    current = plan.get("current_release_authorization")
    _require(isinstance(current, dict) and len(current) == 10 and not any(current.values()), "X6-R0.2 current release must remain 0/10 runtime/scientific authorization")
    next_authorization = plan.get("next_release_authorization")
    _require(isinstance(next_authorization, dict) and next_authorization.get("x6_r1_source_implementation") is True and next_authorization.get("x6_r1_controlled_runtime_pilot") is True and not any(next_authorization[key] for key in ("f2_high_latency", "f3_congestion", "f4_rate_limiting", "dataset_generation", "ml_or_hybrid", "metrics", "api_dashboard_thesis")), "X6-R0.2 next-release authorization drifted")
    _require(plan.get("track") == {"next_release": "X6_R1_PACKET_LOSS", "p9_r2_status": "PAUSED_BY_USER", "x6_r3_status": "BLOCKED_PENDING_FINITE_BOTTLENECK_DESIGN", "x6_r4_status": "BLOCKED_PENDING_CAP_TOLERANCE_AND_NEUTRAL_IMPLEMENTATION"}, "X6-R0.2 track drifted")
    bindings = plan.get("source_bindings")
    _require(isinstance(bindings, list) and len(bindings) == 5, "X6-R0.2 requires five source bindings")
    for row in bindings:
        _require(isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str), "X6-R0.2 binding malformed")
        path = root / row["path"]
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], "X6-R0.2 binding drifted: " + row["path"])
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    plan = verify_x6_r0_2_f1_measurement_semantics(parser.parse_args().repository_root)
    print("x6_r0_2_f1_measurement_semantics=VERIFIED")
    print("source_bindings=" + str(len(plan["source_bindings"])) + "/5_HASH_BOUND_PASS")
    print("current_runtime_scientific_authorization=0/10_FALSE_PASS")
    print("next_release_authorization=X6_R1_PACKET_LOSS_SOURCE_AND_CONTROLLED_PILOT_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
