"""Standalone R1.5 classification, owned cleanup, and read-only replay."""
from __future__ import annotations
import argparse
import fcntl
import os
from pathlib import Path
from src.orchestration.x6_r1_5_contract import RELEASE, canonical_location, identity, load, require, validate_committed_attempt, validate_partial_attempt
from src.orchestration.x6_r1_5_durable import Recorder, acquire_topology_lock, alive, process_identity, records, reservation_path, save, stamp
from src.orchestration.x6_r1_5_observations import catalog, failed_command_orders
from src.orchestration.x6_r1_5_production_path import assert_external_simulation, cleanup, restore, terminal


def _record_partial_classification(root, ledger, auth, partial):
    path = reservation_path(root, auth).with_suffix(".interrupted.json")
    fixed = {
        "release_id": RELEASE,
        "authorization_id": auth["authorization_id"],
        "authorization_sha256": auth["authorization_sha256"],
        "run_id": auth["run_id"],
        "output_root": str(root),
        "status": partial["status"],
        "qualified": False,
        "detail": partial["detail"],
        "ledger_state": partial["ledger_state"],
        "authorization_committed": partial["authorization_committed"],
        "consumption_complete": partial["consumption_complete"],
    }
    if path.exists():
        require(not path.is_symlink(), "unsafe partial-attempt classification")
        existing = load(path)
        observed = existing.get("classified_at")
        require(all(existing.get(key) == value for key, value in fixed.items()) and set(existing) == set(fixed) | {"classified_at"}, "partial-attempt classification contradiction")
        require(isinstance(observed, dict) and set(observed) == {"monotonic_ns", "utc", "boot_id"} and type(observed["monotonic_ns"]) is int and observed["monotonic_ns"] >= 0 and isinstance(observed["utc"], str) and observed["utc"].endswith("Z") and isinstance(observed["boot_id"], str) and observed["boot_id"], "partial-attempt classification timestamp")
        return existing
    classification = {**fixed, "classified_at": stamp()}
    save(path, classification, exclusive=True)
    return classification


def recover(root, *, simulation=False):
    if simulation:
        assert_external_simulation()
    root = canonical_location(str(root))
    candidate_paths = [p for p in (root.parent / ".x6-r1-5-consumption").glob("*.json") if not p.name.endswith(".interrupted.json")]
    require(all(p.is_file() and not p.is_symlink() for p in candidate_paths), "unsafe durable reservation")
    candidates = [load(p) for p in candidate_paths]
    matches = [row for row in candidates if row.get("output_root") == str(root)]
    require(len(matches) == 1, "missing or ambiguous durable reservation")
    ledger = matches[0]
    auth = ledger["authorization"]
    source = identity()
    partial = validate_partial_attempt(auth, ledger, root=root, run_id=auth["run_id"], source_identity=source, simulation=simulation)
    require(not alive(ledger["process"]) and ledger["process"] != process_identity(), "original lifecycle process is active")
    if partial is not None:
        return _record_partial_classification(root, ledger, auth, partial)
    validate_committed_attempt(auth, ledger, root=root, run_id=auth["run_id"], source_identity=source, simulation=simulation)
    prior_rows = records(root, catalog(), permit_incomplete=True)
    require(all(row["source_test_only"] == simulation for row in prior_rows), "recovery test provenance drift")
    topology_lock = acquire_topology_lock()
    lock = os.open(root / "state/recovery.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        old = load(root / "terminal/terminal.json") if (root / "terminal/terminal.json").exists() else None
        if old is None:
            terminal(root, "INTERRUPTED", "original process exited before durable terminalization")
        journal_path = root / "state/recovery.json"
        journal = load(journal_path) if journal_path.exists() else {
            "release_id": RELEASE, "run_id": auth["run_id"], "output_root": str(root),
            "original_process": ledger["process"], "source_test_only": simulation, "sessions": []}
        require(journal["release_id"] == RELEASE and journal["run_id"] == auth["run_id"] and journal["output_root"] == str(root) and journal["original_process"] == ledger["process"] and journal["source_test_only"] == simulation, "recovery journal identity")
        if journal["sessions"] and journal["sessions"][-1]["status"] == "STARTED":
            interrupted = journal["sessions"][-1]
            selected = [row for row in prior_rows if row["order"] >= interrupted["first_order"]]
            require(all(row["intent_at"]["boot_id"] == interrupted["boot_id"] and row["phase"] in {"restoration_probe", "restoration", "restoration_controls", "cleanup_before", "cleanup", "cleanup_after"} for row in selected), "interrupted recovery command scope/boot")
            interrupted["last_order"] = len(prior_rows)
            interrupted["completed"] = (selected[-1].get("completed") or selected[-1]["intent_at"]) if selected else interrupted["started"]
            interrupted["status"] = "INTERRUPTED"
            save(journal_path, journal)
        recovery_process = process_identity()
        session = {"index": len(journal["sessions"]) + 1, "process": recovery_process,
                   "boot_id": recovery_process["boot_id"], "started": stamp(),
                   "first_order": len(prior_rows) + 1, "last_order": len(prior_rows), "status": "STARTED"}
        journal["sessions"].append(session)
        save(journal_path, journal)
        recorder = Recorder(root, catalog(), simulation=simulation)
        try:
            if (root / "state/mutation.json").exists():
                restore(recorder)
            if (root / "state/deployment_intent.json").exists():
                cleanup(recorder, load(root / "state/host_before.json"))
            current_rows = records(root, catalog(), permit_incomplete=True)
            session["last_order"] = len(current_rows)
            session["completed"] = stamp()
            session["status"] = "CLEANUP_COMPLETE"
            journal["interrupted_orders"] = [row["order"] for row in current_rows if row.get("incomplete")]
            journal["nonzero_orders"] = [row["order"] for row in current_rows if row.get("return_code", 0) != 0]
            journal["failed_orders"] = failed_command_orders(current_rows)
            save(journal_path, journal)
        except BaseException as error:
            current_rows = records(root, catalog(), permit_incomplete=True)
            session["last_order"] = len(current_rows)
            session["completed"] = stamp()
            session["status"] = "CLEANUP_FAILED"
            session["detail"] = type(error).__name__ + ": " + str(error)
            save(journal_path, journal)
            terminal(root, "CLEANUP_FAILED", session["detail"])
            raise
        if old and old["status"] in {"F1_SOURCE_CONTRACT_COMPLETE_REPLAY_REQUIRED", "F1_SOURCE_CONTRACT_COMPLETE_REPLAY_VERIFIED"}:
            from src.expansion.x6_r1_5_materialized_verifier import verify
            verify(root, source_identity=source, simulation=simulation)
            terminal(root, "F1_SOURCE_CONTRACT_COMPLETE_REPLAY_VERIFIED")
        return load(root / "terminal/terminal.json")
    finally:
        os.close(lock)
        os.close(topology_lock)


def main():
    parser = argparse.ArgumentParser(description="R1.5 standalone classification, owned cleanup, and read-only replay")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--source-test", action="store_true")
    args = parser.parse_args()
    recover(args.run_root, simulation=args.source_test)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
