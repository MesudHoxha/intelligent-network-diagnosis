"""Prospective X6 baseline-only harness; it is intentionally disabled until X6-R1.4.

This module contains no Containerlab invocation at import time.  The CLI rejects
the absent future authorization before any external command can be started.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from time import monotonic_ns
from typing import Any, Callable, Mapping, Sequence

from src.runtime.subprocesses import run_capture

RELEASE_ID = "X6_R1_3_3_BASELINE_ONLY_RUNTIME_HARNESS_AND_CONTROL_EVIDENCE_PREPARATION"
SCOPE = "BASELINE_ONLY_QUALIFICATION"
WINDOW_IDS = tuple([f"C{i:02d}" for i in range(1, 21)] + [f"H{i:02d}" for i in range(1, 11)])
TERMINAL_STATUSES = {"QUALIFIED", "UNSTABLE", "COLLECTION_UNAVAILABLE", "ENVIRONMENT_INELIGIBLE", "TIMING_INVALID", "COUNTER_RESET", "CLEANUP_FAILED", "INTERRUPTED", "INCONCLUSIVE"}
PROHIBITED = {"sudo", "modprobe", "bash", "sh", "zsh", "fish", "cmd", "powershell", "pwsh", "env", "-c", "-lc", "/bin/sh", "/bin/bash", "netem", "pfifo", "tbf", "htb", "cake", "police"}
ALLOWED_PREFIXES = {
    ("uname", "-r"), ("zgrep", "CONFIG_NET_SCH_NETEM", "/proc/config.gz"), ("lsmod",), ("modinfo", "sch_netem"),
    ("python3", "--version"), ("ip", "-V"), ("tc", "-V"), ("ethtool", "--version"), ("ping", "-V"),
    ("iperf3", "--version"), ("docker", "version", "--format", "json"), ("containerlab", "version"),
    ("git", "rev-parse", "HEAD", "HEAD^{tree}"), ("docker", "image", "inspect"), ("sha256sum",),
}


class X6R133HarnessError(ValueError): pass


def _fail(message: str) -> None: raise X6R133HarnessError("X6-R1.3.3: " + message)
def _utc() -> str: return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def _sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def _canonical(value: object) -> bytes: return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def write_json_fsync(path: Path, value: object) -> None:
    """Atomic file replacement plus directory fsync for every durable state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_canonical(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path); _fsync_directory(path.parent)
    except BaseException:
        Path(temporary).unlink(missing_ok=True); raise


def safe_relative(path: str) -> str:
    candidate = PurePosixPath(path)
    if not path or candidate.is_absolute() or ".." in candidate.parts or candidate.as_posix() != path: _fail("unsafe artifact path")
    return path


def _authorization_unsigned(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "authorization_sha256"}


def validate_authorization(record: Mapping[str, Any], *, expected_source: Mapping[str, str], expected_bindings: Mapping[str, str]) -> dict[str, Any]:
    required = {"schema_version", "authorization_id", "scope", "maximum_attempts", "source_identity", "bindings", "mutation_prohibited", "runtime_enabled", "authorization_sha256"}
    if set(record) != required or record.get("schema_version") != 1: _fail("authorization schema drift")
    if not isinstance(record.get("authorization_id"), str) or not record["authorization_id"]: _fail("authorization ID missing")
    if record.get("scope") != SCOPE or record.get("maximum_attempts") != 1 or record.get("mutation_prohibited") is not True: _fail("authorization scope/attempt/mutation policy invalid")
    if record.get("source_identity") != dict(expected_source) or record.get("bindings") != dict(expected_bindings): _fail("authorization source or binding mismatch")
    digest = record.get("authorization_sha256")
    if not isinstance(digest, str) or digest != _sha(_canonical(_authorization_unsigned(record))): _fail("authorization SHA-256 mismatch")
    if record.get("runtime_enabled") is not True: _fail("future X6-R1.4 runtime enablement is absent")
    return dict(record)


def consume_attempt(ledger_root: Path, authorization: Mapping[str, Any], *, run_id: str, pid: int | None = None) -> Path:
    """Create an irreversible, fsynced PLANNED then CONSUMED authorization ledger."""
    ledger_root = Path(ledger_root); ledger_root.mkdir(parents=True, exist_ok=True); _fsync_directory(ledger_root)
    ident = str(authorization["authorization_id"]); ledger = ledger_root / (ident + ".json")
    payload = {"schema_version": 1, "authorization_id": ident, "authorization_sha256": authorization["authorization_sha256"], "source_identity": authorization["source_identity"], "run_id": run_id, "pid": os.getpid() if pid is None else pid, "planned_at_utc": _utc(), "planned_monotonic_ns": monotonic_ns(), "state": "PLANNED"}
    encoded = _canonical(payload)
    try:
        descriptor = os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise X6R133HarnessError("X6-R1.3.3: authorization is already reserved or consumed") from error
    try:
        os.write(descriptor, encoded); os.fsync(descriptor)
    finally: os.close(descriptor)
    _fsync_directory(ledger_root)
    payload["state"] = "CONSUMED"; payload["consumed_at_utc"] = _utc(); payload["consumed_monotonic_ns"] = monotonic_ns()
    write_json_fsync(ledger, payload)
    return ledger


def validate_command(command: Sequence[str]) -> list[str]:
    argv = list(command)
    if not argv or not all(isinstance(item, str) and item for item in argv): _fail("structured argv required")
    lower = {item.lower() for item in argv}
    if lower & PROHIBITED or (argv and argv[0] == "ip" and "route" in argv): _fail("prohibited mutation, privilege, route, or shell command")
    if not any(tuple(argv[:len(prefix)]) == prefix for prefix in ALLOWED_PREFIXES): _fail("command is outside baseline-only allowlist")
    return argv


def capture_command(command: Sequence[str], *, timeout_seconds: float, cwd: Path | None = None) -> dict[str, object]:
    argv = validate_command(command)
    if timeout_seconds <= 0: _fail("bounded timeout required")
    started_utc, started_ns = _utc(), monotonic_ns()
    result = run_capture(argv, timeout_seconds=timeout_seconds, cwd=cwd)
    return {"command": argv, "shell": False, "timeout_seconds": timeout_seconds, "started_at_utc": started_utc, "completed_at_utc": _utc(), "started_monotonic_ns": started_ns, "completed_monotonic_ns": monotonic_ns(), "return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def planned_actions() -> list[dict[str, str]]:
    return [{"action_id": action, "state": "PLANNED"} for action in ("topology_deploy", "traffic_server", "traffic_client", "threshold_finalize", "cleanup")]


def frozen_schedule() -> dict[str, object]:
    """The immutable prospective chronology, expressed without wall-clock values."""
    return {"readiness_seconds": 5, "warmup_seconds": 5, "window_seconds": 20, "post_window_spacing_seconds": 5, "maximum_startup_skew_seconds": "0.250000", "windows": list(WINDOW_IDS), "threshold_construction": list(WINDOW_IDS[:10]), "calibration": list(WINDOW_IDS[10:20]), "holdout": list(WINDOW_IDS[20:]), "cooldown_seconds": 5, "mutation": "FORBIDDEN"}


def initialize_attempt(run_root: Path, *, authorization: Mapping[str, Any], ledger_root: Path, run_id: str) -> dict[str, object]:
    """The only pre-deployment entry point; callers must validate authorization first."""
    root = Path(run_root)
    if root.exists(): _fail("run root already exists; copied or reused tree rejected")
    root.mkdir(parents=True); _fsync_directory(root.parent)
    ledger = consume_attempt(ledger_root, authorization, run_id=run_id)
    journal = {"schema_version": 1, "release_id": RELEASE_ID, "run_id": run_id, "authorization_id": authorization["authorization_id"], "authorization_sha256": authorization["authorization_sha256"], "state": "CONSUMED_BEFORE_STATEFUL_ACTION", "actions": planned_actions()}
    write_json_fsync(root / "state" / "action_journal.json", journal)
    return {"run_root": str(root), "ledger": str(ledger), "journal": journal}


def terminalize_attempt(run_root: Path, *, status: str, detail: str) -> dict[str, object]:
    if status not in TERMINAL_STATUSES: _fail("unsupported terminal status")
    record = {"schema_version": 1, "release_id": RELEASE_ID, "status": status, "detail": detail, "terminal_at_utc": _utc(), "terminal_monotonic_ns": monotonic_ns(), "evidence_v4": False, "feature_vector_v2": False, "diagnosis": False, "dataset": False, "scientific_claim": False, "f1_authorized": False}
    write_json_fsync(Path(run_root) / "terminal" / "terminal.json", record); return record


def recover_attempt(run_root: Path, *, replay_pid: int | None = None) -> dict[str, object]:
    """New-process recovery entry: it never broad-deletes processes or containers."""
    root = Path(run_root); journal = root / "state" / "action_journal.json"
    if not journal.is_file(): _fail("missing durable action journal")
    if replay_pid is not None and replay_pid == os.getpid(): _fail("standalone replay must execute in a new process")
    return terminalize_attempt(root, status="INTERRUPTED", detail="idempotent recovery requires owned-resource raw checks before cleanup")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("--authorization", type=Path); parser.add_argument("--run-root", type=Path); parser.add_argument("--ledger-root", type=Path); parser.add_argument("--recover", type=Path)
    args = parser.parse_args()
    if args.recover is not None: recover_attempt(args.recover, replay_pid=-1); return 0
    parser.error("X6-R1.3.3 is preparation only: a future X6-R1.4 authorization and programmatic expected bindings are required")
    return 2


if __name__ == "__main__": raise SystemExit(main())
