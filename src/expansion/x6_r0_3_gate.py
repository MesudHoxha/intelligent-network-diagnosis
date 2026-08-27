"""Source gate for the append-only X6-R0.3 pre-runtime correction."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from src.collection.x6_r0_3_pre_runtime_validation import (
    FROZEN_FORMULA,
    FROZEN_ROUNDING,
    METHODOLOGY_VERSION,
)
from src.expansion.x6_r0_2_gate import verify_x6_r0_2_f1_measurement_semantics


ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X6_R0_3_F1_PRE_RUNTIME_VALIDATION_CORRECTION_V1.json")


class X6R03GateError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X6R03GateError(message)


def verify_x6_r0_3_f1_pre_runtime_validation(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root)
    verify_x6_r0_2_f1_measurement_semantics(root)
    plan = json.loads((root / PLAN).read_text(encoding="utf-8"))
    _require(plan.get("release_id") == "X6_R0_3_F1_PRE_RUNTIME_VALIDATION_CORRECTION", "X6-R0.3 release drifted")
    _require(plan.get("status") == "ACCEPTED_SOURCE_ONLY_PRE_RUNTIME_SUCCESSOR", "X6-R0.3 status drifted")
    _require(plan.get("source_boundary") == {"parent_commit": "2e47edecea1294e7b5281f9640db47da529a0ed9", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}, "X6-R0.3 source boundary drifted")
    _require(plan.get("historical_predecessor") == {"x6_r0_2": "PRESERVED_PUBLISHED_SOURCE_ONLY_5_OF_5_BINDINGS"}, "X6-R0.2 history drifted")
    _require(plan.get("authoritative_source") == "src/collection/x6_r0_3_pre_runtime_validation.py", "X6-R0.3 source authority drifted")

    ping = plan.get("ping_contract", {})
    _require(ping.get("exact_command") == ["LC_ALL=C", "/usr/bin/ping", "-n", "-i", "0.2", "-c", "50", "-W", "1", "-s", "56", "<destination>"], "X6-R0.3 ping command drifted")
    _require(ping.get("return_code_alone_is_observation") is False and len(ping.get("return_code_count_table", [])) == 5, "X6-R0.3 return-code contract drifted")

    threshold = plan.get("threshold_semantic_contract", {})
    _require(threshold.get("methodology_version") == METHODOLOGY_VERSION, "X6-R0.3 methodology changed")
    _require(threshold.get("formula") == FROZEN_FORMULA and threshold.get("rounding") == FROZEN_ROUNDING, "X6-R0.3 threshold identity changed")
    _require(threshold.get("required_pipeline") == ["build_threshold_manifest", "semantic_validation", "canonical_freeze", "mutation"], "X6-R0.3 threshold pipeline drifted")
    _require(threshold.get("schema_or_hash_only_acceptance") == "FORBIDDEN", "X6-R0.3 permits shallow threshold acceptance")
    _require(threshold.get("threshold_values_constants_formula_inputs") == "UNCHANGED_FROM_X6_R0_2", "X6-R0.3 changed frozen thresholds")

    current = plan.get("current_release_authorization")
    _require(isinstance(current, dict) and len(current) == 10 and not any(current.values()), "X6-R0.3 must remain 0/10 runtime/scientific authorization")
    next_authorization = plan.get("next_release_authorization", {})
    _require(next_authorization.get("x6_r1_source_implementation") is True and next_authorization.get("x6_r1_controlled_runtime_pilot") is True, "X6-R1 source/pilot authorization drifted")
    _require(not any(value for key, value in next_authorization.items() if key not in {"x6_r1_source_implementation", "x6_r1_controlled_runtime_pilot"}), "X6-R0.3 over-authorized later work")
    _require(plan.get("track") == {"next_release": "X6_R1_PACKET_LOSS", "p9_r2_status": "PAUSED_BY_USER", "x6_r3_status": "BLOCKED_UNTIL_X6_R3", "x6_r4_status": "BLOCKED_UNTIL_X6_R4"}, "X6-R0.3 track drifted")

    bindings = plan.get("source_bindings")
    _require(isinstance(bindings, list) and len(bindings) == 6, "X6-R0.3 requires six source bindings")
    for row in bindings:
        _require(isinstance(row, dict) and isinstance(row.get("path"), str) and isinstance(row.get("sha256"), str), "X6-R0.3 binding malformed")
        path = root / row["path"]
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], "X6-R0.3 binding drifted: " + row["path"])
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    plan = verify_x6_r0_3_f1_pre_runtime_validation(parser.parse_args().repository_root)
    print("x6_r0_3_f1_pre_runtime_validation=VERIFIED")
    print("source_bindings=" + str(len(plan["source_bindings"])) + "/6_HASH_BOUND_PASS")
    print("current_runtime_scientific_authorization=0/10_FALSE_PASS")
    print("next_release_authorization=X6_R1_PACKET_LOSS_SOURCE_AND_CONTROLLED_PILOT_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
