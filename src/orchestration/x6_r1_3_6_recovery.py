"""R1.3.6 standalone recovery with authority prevalidation before commands."""
from __future__ import annotations

import json
import os
from pathlib import Path
from time import monotonic_ns
from typing import Callable, Mapping

from src.orchestration.x6_r1_3_5_baseline_provenance import COMMANDS, CommandRecorder, X6R135Error, canonical_bytes, sha256, verify_command_inventory
from src.runtime.subprocesses import run_capture
from src.orchestration.x6_r1_3_6_production_path import FUTURE_AUTHORIZATION_RELEASE, OWNERSHIP, RELEASE_ID, RepositoryExecutor, X6R136Error, _identity, finalize_inventory, validate_authorization
from src.orchestration.x6_r1_3_3_baseline_only_runner import write_json_fsync


class X6R136RecoveryError(ValueError):
    pass


def _fail(message: str) -> None:
    raise X6R136RecoveryError("X6-R1.3.6 recovery: " + message)


def _read(root: Path, relative: str) -> dict[str, object]:
    path = Path(root) / relative
    if not path.is_file() or path.is_symlink():
        _fail("required recovery artifact absent or unsafe: " + relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise X6R136RecoveryError("X6-R1.3.6 recovery: malformed " + relative) from error
    if not isinstance(value, dict):
        _fail("recovery artifact object required: " + relative)
    return value


def _verify_transitions(root: Path, auth: Mapping[str, object], run_id: str, first_command_ns: int) -> None:
    expected = (("ABSENT", "LOADED"), ("LOADED", "VALIDATED"), ("VALIDATED", "CONSUMPTION_PLANNED"), ("CONSUMPTION_PLANNED", "CONSUMED_DURABLE"), ("CONSUMED_DURABLE", "STATEFUL_ACTION_PERMITTED"))
    previous = -1
    for order, pair in enumerate(expected, 1):
        row = _read(root, "state/transition-%03d.json" % order)
        unsigned = dict(row); digest = unsigned.pop("transition_sha256", None)
        if row.get("order") != order or (row.get("previous_state"), row.get("state")) != pair or row.get("run_id") != run_id or row.get("authorization_id") != auth.get("authorization_id") or row.get("authorization_sha256") != auth.get("authorization_sha256") or digest != sha256(canonical_bytes(unsigned)) or not isinstance(row.get("monotonic_ns"), int) or row["monotonic_ns"] < previous:
            _fail("transition chain is invalid")
        previous = row["monotonic_ns"]
    if previous > first_command_ns:
        _fail("durable consumption chain follows command evidence")


def prevalidate_recovery(root: Path, *, identity: Mapping[str, object], allow_source_test: bool) -> dict[str, object]:
    """Read and prove every authority binding before constructing an executor."""
    root = Path(root)
    auth = _read(root, "state/authorization.json")
    journal = _read(root, "state/action_journal.json")
    if journal.get("release_id") != RELEASE_ID or journal.get("state") != "CONSUMED_BEFORE_STATEFUL_ACTION" or not isinstance(journal.get("run_id"), str):
        _fail("action journal is not recovery-eligible")
    run_id = str(journal["run_id"])
    validate_authorization(auth, identity=identity, run_id=run_id, output_root=str(auth.get("output_root", "")), now_ns=int(auth.get("issued_ns", -1)), allow_source_test=allow_source_test)
    if auth.get("release_id") != FUTURE_AUTHORIZATION_RELEASE or journal.get("authorization_id") != auth.get("authorization_id") or journal.get("authorization_sha256") != auth.get("authorization_sha256"):
        _fail("authorization and journal binding mismatch")
    ledger = _read(root, "state/authorization_ledger.json")
    unsigned = dict(ledger); digest = unsigned.pop("ledger_sha256", None)
    if digest != sha256(canonical_bytes(unsigned)) or ledger.get("state") != "CONSUMED" or ledger.get("previous_state") != "VALIDATED" or ledger.get("authorization_id") != auth.get("authorization_id") or ledger.get("authorization_sha256") != auth.get("authorization_sha256") or ledger.get("run_id") != run_id or ledger.get("output_root") != auth.get("output_root") or not isinstance(ledger.get("consumed_monotonic_ns"), int):
        _fail("one-attempt ledger is invalid")
    if ledger.get("original_pid") != journal.get("original_pid") or not isinstance(journal.get("original_pid"), int) or journal["original_pid"] <= 0:
        _fail("original process identity is invalid")
    if _read(root, "state/ownership.json") != OWNERSHIP:
        _fail("lifecycle ownership identity drift")
    rows = verify_command_inventory(root, run_id=run_id, authorization_id=str(auth["authorization_id"]))
    if not rows or any(row["return_code"] != 0 or row["timed_out"] or row["interrupted"] for row in rows):
        _fail("pre-recovery command inventory is failed, incomplete, or replaced")
    _verify_transitions(root, auth, run_id, min(int(row["started_monotonic_ns"]) for row in rows))
    terminal = _read(root, "terminal/terminal.json")
    if terminal.get("status") not in {"INTERRUPTED", "ENVIRONMENT_INELIGIBLE", "COLLECTION_UNAVAILABLE"}:
        _fail("recovery requires an interrupted or failed lifecycle terminal")
    inventory = _read(root, "state/artifact_inventory.json")
    declared = inventory.get("artifacts")
    if not isinstance(declared, list) or not declared:
        _fail("pre-recovery inventory missing")
    for item in declared:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"} or not isinstance(item["path"], str):
            _fail("pre-recovery inventory malformed")
        path = root / item["path"]
        if not path.is_file() or path.is_symlink() or sha256(path.read_bytes()) != item["sha256"]:
            _fail("pre-recovery inventory hash drift")
    return {"authorization": auth, "journal": journal, "rows": rows, "run_id": run_id}


def recover_core(root: Path, *, prevalidated: Mapping[str, object], executor: Callable[[list[str]], Mapping[str, object]]) -> dict[str, object]:
    """Shared recovery core.  Callers must supply prevalidated durable state."""
    journal = prevalidated["journal"]
    assert isinstance(journal, Mapping)
    original = int(journal["original_pid"]); current = os.getpid()
    if current == original:
        _fail("recovery must execute in a distinct process")
    recorder = CommandRecorder(Path(root), run_id=str(journal["run_id"]), authorization_id=str(journal["authorization_id"]), source_test_only=bool(journal["source_test_only"]), resume=True)
    first = len(recorder.rows) + 1
    for name in ("processes", "namespaces", "qdisc", "filters", "cleanup", "processes", "namespaces", "qdisc", "filters"):
        reference = recorder.capture(name=name, phase="recovery", action_id="recovery", executor=executor)
        row = json.loads((Path(root) / reference["path"]).read_text(encoding="utf-8"))
        if row["return_code"] != 0 or row["timed_out"] or row["interrupted"]:
            _fail("recovery command failed: " + name)
    recovery = {"release_id": RELEASE_ID, "run_id": journal["run_id"], "authorization_id": journal["authorization_id"], "original_pid": original, "recovery_pid": current, "distinct_process": True, "recovery_first_order": first, "recovery_last_order": len(recorder.rows), "prevalidated_before_first_command": True, "status": "IDEMPOTENT_RECOVERY_CONFIRMED"}
    write_json_fsync(Path(root) / "state" / "recovery.json", recovery)
    write_json_fsync(Path(root) / "terminal" / "terminal.json", {"release_id": RELEASE_ID, "status": "R1.3.6_PRODUCTION_PATH_SOURCE_CONTRACT_COMPLETE_FOR_AUTHORIZATION_REVIEW", "qualified": False, "source_test_only": bool(journal["source_test_only"])})
    finalize_inventory(Path(root)); return recovery


def _fail_closed_terminal(root: Path, detail: str) -> None:
    root = Path(root)
    if root.is_dir() and not root.is_symlink():
        write_json_fsync(root / "terminal" / "recovery_prevalidation_failed.json", {"release_id": RELEASE_ID, "status": "VERIFICATION_FAILED", "qualified": False, "detail": detail, "at_monotonic_ns": monotonic_ns()})


def recovery_main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="X6-R1.3.6 production recovery")
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        state = prevalidate_recovery(args.run_root, identity=_identity(Path(__file__).resolve().parents[2]), allow_source_test=False)
    except (X6R136Error, X6R135Error) as error:
        _fail_closed_terminal(args.run_root, str(error)); return 2
    recover_core(args.run_root, prevalidated=state, executor=RepositoryExecutor())
    return 0


if __name__ == "__main__":
    raise SystemExit(recovery_main())
