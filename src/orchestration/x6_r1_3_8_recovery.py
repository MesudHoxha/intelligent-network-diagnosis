"""Standalone successor recovery from fsynced intents, including interrupted commands."""
from __future__ import annotations
import argparse
import fcntl
import os
import time
from pathlib import Path
from src.orchestration.x6_r1_3_8_contract import RELEASE, canonical_location, identity, load, require, validate_authorization
from src.orchestration.x6_r1_3_8_durable import Recorder, alive, process_identity, records, reservation_path, save, stamp, acquire_topology_lock
from src.orchestration.x6_r1_3_8_observations import catalog
from src.orchestration.x6_r1_3_8_production_path import cleanup, terminal, assert_external_simulation


def recover(root, *, simulation=False):
    if simulation: assert_external_simulation()
    root = canonical_location(str(root))
    candidates = [load(p) for p in (root.parent / ".x6-r1-3-8-consumption").glob("*.json") if not p.name.endswith(".interrupted.json")]
    matches = [row for row in candidates if row.get("output_root") == str(root)]
    require(len(matches) == 1, "missing or ambiguous durable reservation")
    ledger = matches[0]
    auth = ledger["authorization"]
    if (root / "state/authorization.json").exists():
        require(load(root / "state/authorization.json") == auth, "authorization copy drift")
    require(ledger["authorization_sha256"] == auth["authorization_sha256"] and ledger["run_id"] == auth["run_id"] and ledger["output_root"] == str(root), "recovery reservation identity")
    require(not alive(ledger["process"]) and ledger["process"] != process_identity(), "original lifecycle process is active")
    validated_ns = ledger.get("consumed", ledger["reserved"])["monotonic_ns"]
    validate_authorization(auth, root=root, run_id=auth["run_id"], source_identity=identity(), now_ns=validated_ns, simulation=simulation)
    if ledger["state"] == "RESERVED" or not (root / "state/consumption.json").exists():
        classification = {"release_id": RELEASE, "status": "INTERRUPTED", "qualified": False, "detail": "process exited during durable reservation; authorization remains spent", "at": stamp()}
        # A crash between mkdir and recording the inode does not grant authority
        # to write into an unproven existing directory.
        save(reservation_path(root, auth).with_suffix(".interrupted.json"), classification)
        if root.exists() and ledger.get("root_identity") == {"device": root.stat().st_dev, "inode": root.stat().st_ino}:
            require(not list((root / "raw/commands").glob("*.json")), "commands without durable consumption")
            terminal(root, "INTERRUPTED", classification["detail"])
        return classification
    require(ledger.get("root_identity") == {"device": root.stat().st_dev, "inode": root.stat().st_ino}, "run directory replaced")
    require(load(root / "state/consumption.json") == ledger, "consumption copy drift")
    rows = records(root, catalog(), permit_incomplete=True)
    require(all(row["source_test_only"] == simulation for row in rows), "recovery test provenance drift")
    # Failed results remain evidence. Missing results for durable intents are
    # interrupted operations, never invented successful observations.
    topology_lock = acquire_topology_lock()
    lock = os.open(root / "state/recovery.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        old = load(root / "terminal/terminal.json") if (root / "terminal/terminal.json").exists() else None
        if old is None: terminal(root, "INTERRUPTED", "original process exited before durable terminalization")
        recorder = Recorder(root, catalog(), simulation=simulation)
        if (root / "state/deployment_intent.json").exists():
            cleanup(recorder, load(root / "state/host_before.json"))
        save(root / "state/recovery.json", {"release_id": RELEASE, "original_process": ledger["process"], "recovery_process": process_identity(), "at": stamp(), "interrupted_orders": [row["order"] for row in rows if row.get("incomplete")], "failed_orders": [row["order"] for row in rows if row.get("return_code", 0) != 0], "source_test_only": simulation})
        if old and old["status"] == "COLLECTION_COMPLETE_REPLAY_REQUIRED":
            from src.expansion.x6_r1_3_8_materialized_verifier import verify
            verify(root, source_identity=identity(), simulation=simulation)
            terminal(root, "SOURCE_CONTRACT_COMPLETE_REPLAY_VERIFIED")
        return load(root / "terminal/terminal.json")
    finally:
        os.close(lock)
        os.close(topology_lock)


def main():
    parser = argparse.ArgumentParser(description="R1.3.8 standalone owned-resource recovery/replay")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--source-test", action="store_true")
    args = parser.parse_args()
    recover(args.run_root, simulation=args.source_test)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
