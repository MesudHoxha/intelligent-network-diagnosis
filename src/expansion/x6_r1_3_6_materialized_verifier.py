"""Independent R1.3.6 reconstruction; it never emits a runtime qualification."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from src.collection.x6_r0_3_pre_runtime_validation import NUMERIC_FEATURES, build_threshold_manifest
from src.orchestration.x6_r1_3_3_baseline_only_runner import WINDOW_IDS
from src.orchestration.x6_r1_3_5_baseline_provenance import X6R135Error, canonical_bytes, sha256, verify_command_inventory
from src.orchestration.x6_r1_3_6_production_path import HISTORICAL_VECTOR, OWNERSHIP, RELEASE_ID, SCHEDULE, X6R136Error, validate_authorization


TERMINAL = "R1.3.6_PRODUCTION_PATH_SOURCE_CONTRACT_COMPLETE_FOR_AUTHORIZATION_REVIEW"


class X6R136VerificationError(ValueError):
    pass


def _fail(message: str) -> None:
    raise X6R136VerificationError("X6-R1.3.6 verifier: " + message)


def _read(root: Path, relative: str) -> dict[str, object]:
    path = Path(root) / relative
    if not path.is_file() or path.is_symlink():
        _fail("missing or unsafe artifact: " + relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise X6R136VerificationError("X6-R1.3.6 verifier: malformed " + relative) from error
    if not isinstance(value, dict):
        _fail("artifact must be an object: " + relative)
    return value


def _verify_ledger(root: Path, auth: Mapping[str, object], run_id: str) -> dict[str, object]:
    ledger = _read(root, "state/authorization_ledger.json")
    unsigned = dict(ledger); digest = unsigned.pop("ledger_sha256", None)
    if digest != sha256(canonical_bytes(unsigned)) or ledger.get("state") != "CONSUMED" or ledger.get("previous_state") != "VALIDATED" or ledger.get("authorization_id") != auth.get("authorization_id") or ledger.get("authorization_sha256") != auth.get("authorization_sha256") or ledger.get("run_id") != run_id or ledger.get("output_root") != auth.get("output_root") or not isinstance(ledger.get("consumed_monotonic_ns"), int):
        _fail("durable one-attempt ledger drift")
    return ledger


def _verify_transitions(root: Path, auth: Mapping[str, object], run_id: str, first_command: int) -> None:
    pairs = (("ABSENT", "LOADED"), ("LOADED", "VALIDATED"), ("VALIDATED", "CONSUMPTION_PLANNED"), ("CONSUMPTION_PLANNED", "CONSUMED_DURABLE"), ("CONSUMED_DURABLE", "STATEFUL_ACTION_PERMITTED"))
    previous = -1
    for order, pair in enumerate(pairs, 1):
        row = _read(root, "state/transition-%03d.json" % order)
        unsigned = dict(row); digest = unsigned.pop("transition_sha256", None)
        if row.get("order") != order or (row.get("previous_state"), row.get("state")) != pair or row.get("run_id") != run_id or row.get("authorization_id") != auth.get("authorization_id") or row.get("authorization_sha256") != auth.get("authorization_sha256") or digest != sha256(canonical_bytes(unsigned)) or not isinstance(row.get("monotonic_ns"), int) or row["monotonic_ns"] < previous:
            _fail("authorization transition chain drift")
        previous = row["monotonic_ns"]
    if previous > first_command:
        _fail("first command precedes durable authorization consumption")


def _verify_inventory(root: Path) -> dict[str, object]:
    inventory = _read(root, "state/artifact_inventory.json")
    rows = inventory.get("artifacts")
    if not isinstance(rows, list) or inventory.get("canonical_inventory_sha256") != sha256(canonical_bytes(rows)):
        _fail("canonical artifact inventory drift")
    declared: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"} or not isinstance(row["path"], str) or not row["path"] or row["path"].startswith("/") or ".." in Path(row["path"]).parts or row["path"] in declared:
            _fail("artifact inventory path drift")
        target = Path(root) / row["path"]
        if not target.is_file() or target.is_symlink() or sha256(target.read_bytes()) != row["sha256"]:
            _fail("artifact inventory hash drift")
        declared.add(row["path"])
    actual = {item.relative_to(root).as_posix() for item in Path(root).rglob("*") if item.is_file() and not item.is_symlink() and item.relative_to(root).as_posix() != "state/artifact_inventory.json"}
    if actual != declared:
        _fail("artifact inventory is stale, missing, or unexpected")
    return {"artifact_count": len(actual), "inventory_sha256": inventory["canonical_inventory_sha256"]}


def _verify_lifecycle(root: Path, *, rows: list[Mapping[str, object]]) -> dict[str, object]:
    if _read(root, "state/schedule.json") != SCHEDULE or _read(root, "state/ownership.json") != OWNERSHIP:
        _fail("schedule or ownership binding drift")
    for phase in ("readiness", "warmup", "cooldown"):
        row = _read(root, "state/" + phase + ".json")
        if set(row) != {"scheduled_start_ns", "scheduled_end_ns", "actual_start_ns", "actual_end_ns"} or not all(isinstance(value, int) and value >= 0 for value in row.values()):
            _fail("phase timing record malformed: " + phase)
        expected = 5_000_000_000
        if row["scheduled_end_ns"] - row["scheduled_start_ns"] != expected or row["actual_end_ns"] - row["actual_start_ns"] < expected:
            _fail("phase timing duration drift: " + phase)
    windows: list[dict[str, object]] = []; previous_end: int | None = None
    for index, window_id in enumerate(WINDOW_IDS):
        row = _read(root, "raw/windows/" + window_id + ".json")
        if row.get("window_id") != window_id or set(row.get("measurements", {})) != set(NUMERIC_FEATURES) or row.get("measurements") != row.get("observations"):
            _fail("window cohort or feature drift: " + window_id)
        timing = row.get("timing")
        if not isinstance(timing, dict) or set(timing) != {"actual_start_ns", "actual_end_ns", "startup_skew_seconds"} or not all(isinstance(timing[key], (int, float)) and not isinstance(timing[key], bool) for key in timing):
            _fail("window timing schema drift: " + window_id)
        start, end, skew = int(timing["actual_start_ns"]), int(timing["actual_end_ns"]), float(timing["startup_skew_seconds"])
        if start < 0 or end - start < 20_000_000_000 or not 0 <= skew <= 0.250 or previous_end is not None and start < previous_end + 5_000_000_000:
            _fail("window duration, skew, or separation drift: " + window_id)
        if start == index * 25_000_000_000:
            _fail("synthetic index timing is not production evidence")
        previous_end = end; windows.append(row)
    manifest = _read(root, "state/threshold_manifest.json")
    expected = build_threshold_manifest({feature: [row["measurements"][feature] for row in windows[:10]] for feature in NUMERIC_FEATURES}, topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH", traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
    freeze = _read(root, "state/threshold_freeze.json")
    if manifest != expected or freeze.get("after_window_id") != "C10" or freeze.get("before_window_id") != "C11" or freeze.get("manifest_sha256") != manifest.get("sha256") or not isinstance(freeze.get("frozen_at_monotonic_ns"), int):
        _fail("C01-C10-only manifest freeze drift")
    if freeze["frozen_at_monotonic_ns"] > int(windows[10]["timing"]["actual_start_ns"]):
        _fail("manifest was not frozen before C11")
    return {"windows": 30, "threshold_sha256": manifest["sha256"]}


def _verify_controls(rows: list[Mapping[str, object]]) -> None:
    required = {"qdisc", "filters", "r2_tx", "r3_rx", "r2_speed", "r3_speed", "processes", "namespaces", "cleanup"}
    if not required <= {str(row["command_name"]) for row in rows} or any(row["return_code"] != 0 or row["timed_out"] or row["interrupted"] for row in rows):
        _fail("raw control command result is missing or nonterminal")
    def selected(name: str) -> list[Mapping[str, object]]: return [row for row in rows if row["command_name"] == name]
    for row in selected("qdisc"):
        try: value = json.loads(str(row["stdout"]))
        except json.JSONDecodeError: _fail("qdisc output malformed")
        if value != [{"kind": "noqueue", "handle": "0:"}]: _fail("qdisc final drift")
    for row in selected("filters"):
        try: value = json.loads(str(row["stdout"]))
        except json.JSONDecodeError: _fail("filter output malformed")
        if value != []: _fail("filter residual state")
    for name in ("r2_tx", "r3_rx"):
        numbers = [int(str(row["stdout"]).strip()) for row in selected(name)]
        if any(next_value < value for value, next_value in zip(numbers, numbers[1:])): _fail("counter continuity reset")
    speeds = [int(str(row["stdout"]).strip()) for row in selected("r2_speed") + selected("r3_speed")]
    if not speeds or any(value <= 0 for value in speeds) or len(set(speeds)) != 1: _fail("interface speed drift")
    for name in ("processes", "namespaces"):
        if any(marker in "\n".join(str(row["stdout"]) for row in selected(name)).lower() for marker in ("clab-x6r1", "x6r1", "iperf3")):
            _fail("owned residual resource")


def verify_materialized_production_path(root: Path, *, identity: Mapping[str, object], allow_source_test: bool = False) -> dict[str, object]:
    root = Path(root); auth = _read(root, "state/authorization.json")
    run_id = str(auth.get("run_id", ""))
    try:
        validate_authorization(auth, identity=identity, run_id=run_id, output_root=str(auth.get("output_root", "")), now_ns=int(auth.get("issued_ns", -1)), allow_source_test=allow_source_test)
    except X6R136Error as error:
        _fail(str(error))
    if auth.get("historical_authorization") != HISTORICAL_VECTOR:
        _fail("historical authorization vector changed")
    rows = verify_command_inventory(root, run_id=run_id, authorization_id=str(auth["authorization_id"]))
    if not rows:
        _fail("command inventory absent")
    ledger = _verify_ledger(root, auth, run_id); _verify_transitions(root, auth, run_id, min(int(row["started_monotonic_ns"]) for row in rows))
    if int(ledger["consumed_monotonic_ns"]) > min(int(row["started_monotonic_ns"]) for row in rows):
        _fail("ledger consumption follows a stateful command")
    lifecycle = _verify_lifecycle(root, rows=rows); _verify_controls(rows)
    recovery = _read(root, "state/recovery.json")
    journal = _read(root, "state/action_journal.json")
    if recovery.get("run_id") != run_id or recovery.get("authorization_id") != auth.get("authorization_id") or recovery.get("original_pid") != journal.get("original_pid") or not recovery.get("prevalidated_before_first_command") or not recovery.get("distinct_process") or not isinstance(recovery.get("recovery_pid"), int) or recovery["recovery_pid"] == recovery["original_pid"]:
        _fail("recovery authority or distinct-process drift")
    first, last = recovery.get("recovery_first_order"), recovery.get("recovery_last_order")
    if not isinstance(first, int) or not isinstance(last, int) or first <= 0 or last < first:
        _fail("recovery ordering drift")
    recovery_rows = [row for row in rows if first <= int(row["order"]) <= last]
    expected = ("processes", "namespaces", "qdisc", "filters", "cleanup", "processes", "namespaces", "qdisc", "filters")
    if tuple(row["command_name"] for row in recovery_rows) != expected or any(row["phase"] != "recovery" for row in recovery_rows):
        _fail("recovery command inventory drift")
    cleanup = recovery_rows[4]
    if any(int(row["started_monotonic_ns"]) < int(cleanup["completed_monotonic_ns"]) for row in recovery_rows[5:]):
        _fail("recovery final observation precedes cleanup")
    inventory = _verify_inventory(root)
    terminal = _read(root, "terminal/terminal.json")
    if terminal.get("status") != TERMINAL or terminal.get("qualified") is not False or terminal.get("source_test_only") != auth.get("source_test_only"):
        _fail("runner-asserted or qualified terminal is invalid")
    return {"terminal_status": TERMINAL, "qualified": False, "lifecycle": lifecycle, "inventory": inventory, "distinct_process_recovery": True}
