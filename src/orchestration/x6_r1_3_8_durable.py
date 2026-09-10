"""Fsynced reservation, command intent and completion records for R1.3.8."""
from __future__ import annotations
import fcntl
import os
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from src.orchestration.x6_r1_3_8_contract import canonical, canonical_location, digest, load, require


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def save(path, value, *, exclusive=False):
    path = Path(path)
    if not path.parent.exists():
        path.parent.mkdir(parents=True)
        fsync_directory(path.parent.parent)
    encoded = canonical(value)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
        fsync_directory(path.parent)
        return
    temporary = path.with_name("." + path.name + "." + str(os.getpid()) + "." + str(threading.get_ident()))
    try:
        save(temporary, value, exclusive=True)
        os.replace(temporary, path); fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def stamp():
    return {"monotonic_ns": time.monotonic_ns(), "utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}


def process_identity():
    # PID alone cannot identify a process after PID reuse.
    return {"pid": os.getpid(), "start_ticks": Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19], "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def alive(identity):
    try:
        value = Path("/proc/" + str(identity["pid"]) + "/stat").read_text().rsplit(")", 1)[1].split()
        return value[19] == identity["start_ticks"] and identity["boot_id"] == Path("/proc/sys/kernel/random/boot_id").read_text().strip() and value[0] != "Z"
    except FileNotFoundError:
        return False


def reservation_path(root, auth):
    return canonical_location(str(root)).parent / ".x6-r1-3-8-consumption" / (auth["authorization_id"] + ".json")


def reserve(root, auth):
    root = canonical_location(str(root))
    require(not root.exists(), "run root already exists")
    ledger = reservation_path(root, auth)
    ledger.parent.mkdir(exist_ok=True); fsync_directory(ledger.parent.parent)
    require(not ledger.parent.is_symlink(), "unsafe consumption directory")
    row = {"authorization_sha256": auth["authorization_sha256"], "authorization_id": auth["authorization_id"], "run_id": auth["run_id"], "output_root": str(root), "process": process_identity(), "reserved": stamp(), "state": "RESERVED", "authorization": auth}
    # O_EXCL is the single attempt's linearization point. A partial record is
    # still spent and is never repaired into an unused authorization.
    save(ledger, row, exclusive=True)
    root.mkdir(); fsync_directory(root.parent)
    st = root.stat(); row["root_identity"] = {"device": st.st_dev, "inode": st.st_ino}
    save(ledger, row)
    save(root / "state/authorization.json", auth, exclusive=True)
    row["consumed"] = stamp(); row["state"] = "CONSUMED"
    save(ledger, row)
    save(root / "state/consumption.json", row, exclusive=True)
    save(root / "state/lifecycle.json", {"state": "CONSUMED", "process": row["process"], "at": stamp()}, exclusive=True)
    return row


class Recorder:
    def __init__(self, root, catalog, *, simulation=False):
        self.root, self.catalog, self.simulation = Path(root), catalog, simulation
        self.lock = threading.Lock()
        self.order = len(list((self.root / "raw/commands").glob("*.intent.json")))

    def capture(self, name, phase, *, window=None, started_event=None):
        require(name in self.catalog, "command outside successor allowlist")
        argv, timeout = self.catalog[name]
        with self.lock:
            self.order += 1
            order = self.order
            intent = {"order": order, "name": name, "phase": phase, "window": window, "argv": argv, "timeout_seconds": timeout, "shell": False, "source_test_only": self.simulation, "intent_at": stamp()}
            save(self.root / f"raw/commands/{order:05d}.intent.json", intent, exclusive=True)
        start = stamp()
        if started_event is not None:
            started_event["stamp"] = start
            started_event["event"].set()
        proc = None
        try:
            proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False, start_new_session=True)
            stdout, stderr = proc.communicate(timeout=timeout)
            code, interrupted, timed_out = proc.returncode, False, False
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            code, interrupted, timed_out = 124, False, True
        except BaseException as error:
            if proc is not None:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                stdout, stderr = proc.communicate()
            else: stdout, stderr = "", ""
            stderr += type(error).__name__ + ": " + str(error)
            code, interrupted, timed_out = 125, True, False
        row = {**intent, "intent_sha256": digest(canonical(intent)), "started": start, "completed": stamp(), "return_code": code, "stdout": stdout, "stderr": stderr, "stdout_sha256": digest(stdout.encode()), "stderr_sha256": digest(stderr.encode()), "interrupted": interrupted, "timed_out": timed_out}
        save(self.root / f"raw/commands/{order:05d}.result.json", row, exclusive=True)
        return row


def records(root, catalog, *, permit_incomplete=False):
    rows = []
    intents = sorted((Path(root) / "raw/commands").glob("*.intent.json"))
    for order, path in enumerate(intents, 1):
        intent = load(path)
        require(intent["order"] == order and path.name == f"{order:05d}.intent.json", "command order")
        require(intent["name"] in catalog and [intent["argv"], intent["timeout_seconds"]] == list(catalog[intent["name"]]) and intent["shell"] is False, "command identity")
        result_path = path.with_name(f"{order:05d}.result.json")
        if not result_path.exists():
            require(permit_incomplete, "incomplete command")
            rows.append({**intent, "incomplete": True}); continue
        row = load(result_path)
        require(all(row[k] == v for k, v in intent.items()) and row["intent_sha256"] == digest(canonical(intent)), "command intent/result contradiction")
        require(type(row["return_code"]) is int and type(row["timed_out"]) is bool and type(row["interrupted"]) is bool and type(row["source_test_only"]) is bool, "command result types")
        for point in (intent["intent_at"], row["started"], row["completed"]):
            require(type(point["monotonic_ns"]) is int and point["monotonic_ns"] >= 0 and point["utc"].endswith("Z"), "command timestamp schema")
            datetime.fromisoformat(point["utc"].replace("Z", "+00:00"))
        require(row["stdout_sha256"] == digest(row["stdout"].encode()) and row["stderr_sha256"] == digest(row["stderr"].encode()), "command stream drift")
        require(intent["intent_at"]["monotonic_ns"] <= row["started"]["monotonic_ns"] <= row["completed"]["monotonic_ns"], "command timing drift")
        rows.append(row)
    require(len(list((Path(root) / "raw/commands").glob("*.result.json"))) == sum(not row.get("incomplete", False) for row in rows), "orphan command result")
    return rows


def acquire_topology_lock():
    # The topology name is fixed by accepted source, so it has one host-wide
    # cooperating-controller lease, independent of authorization/run directory.
    path = Path("/tmp") / ("ind-x6r1-" + str(os.getuid()) + ".lock")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        require(os.fstat(descriptor).st_uid == os.getuid(), "foreign topology lease")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise
