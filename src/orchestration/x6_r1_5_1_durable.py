"""Fsynced one-attempt commitment and boot-bound observations for R1.5 F1."""
from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from src.orchestration.x6_r1_5_1_contract import canonical, canonical_location, current_boot_id, digest, load, require

_CLOCK_LOCK = threading.Lock()
_CLOCK_NS = time.monotonic_ns()


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, value, *, exclusive=False):
    path = Path(path)
    if not path.parent.exists():
        path.parent.mkdir(parents=True)
        fsync_directory(path.parent.parent)
    encoded = canonical(value)
    def write_complete(target):
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    if exclusive:
        staging = path.with_name("." + path.name + "." + str(os.getpid()) + "." + str(threading.get_ident()) + ".exclusive")
        try:
            write_complete(staging)
            os.link(staging, path, follow_symlinks=False)  # atomic create-if-absent publication
            fsync_directory(path.parent)
            return
        finally:
            staging.unlink(missing_ok=True)
    temporary = path.with_name("." + path.name + "." + str(os.getpid()) + "." + str(threading.get_ident()))
    try:
        write_complete(temporary)
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def stamp():
    global _CLOCK_NS
    if os.environ.get("X6_R1_5_1_CONTROLLED_CLOCK") == "1":
        with _CLOCK_LOCK:
            _CLOCK_NS += 1_000_000
            value = _CLOCK_NS
    else:
        value = time.monotonic_ns()
    return {"monotonic_ns": value, "utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "boot_id": current_boot_id()}


def advance_clock(nanoseconds):
    global _CLOCK_NS
    require(os.environ.get("X6_R1_5_1_CONTROLLED_CLOCK") == "1", "controlled clock is source-test only")
    with _CLOCK_LOCK:
        _CLOCK_NS += nanoseconds


def process_identity():
    return {"pid": os.getpid(), "start_ticks": Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19], "boot_id": current_boot_id()}


def alive(identity):
    try:
        value = Path("/proc/" + str(identity["pid"]) + "/stat").read_text().rsplit(")", 1)[1].split()
        return value[19] == identity["start_ticks"] and identity["boot_id"] == current_boot_id() and value[0] != "Z"
    except FileNotFoundError:
        return False


def reservation_path(root, auth):
    return canonical_location(str(root)).parent / ".x6-r1-5-1-consumption" / (auth["authorization_id"] + ".json")


def reserve(root, auth, *, admission_validator):
    """Spend once, then durably commit the sole lifecycle-entry decision."""
    root = canonical_location(str(root))
    require(not root.exists(), "run root already exists")
    ledger = reservation_path(root, auth)
    ledger.parent.mkdir(exist_ok=True)
    fsync_directory(ledger.parent.parent)
    require(not ledger.parent.is_symlink(), "unsafe consumption directory")
    if ledger.exists():
        raise FileExistsError("authorization was already reserved")
    row = {
        "authorization_sha256": auth["authorization_sha256"],
        "authorization_id": auth["authorization_id"],
        "run_id": auth["run_id"],
        "output_root": str(root),
        "process": process_identity(),
        "reservation": {"started": stamp()},
        "state": "RESERVED_UNDECIDED",
        "authorization": auth,
    }
    # The staged O_EXCL write is published with an atomic no-replace hard link.
    # That publication is the one-attempt linearization point: before it there
    # is no reservation, and once the final name exists its bytes are complete.
    # Any crash or rejection after publication leaves the authorization spent.
    save(ledger, row, exclusive=True)
    durable = stamp()  # observed only after the exclusive file and directory fsyncs returned
    row["reservation"]["durable_observed"] = durable
    try:
        admission_validator(durable)
    except BaseException as error:
        row["admission"] = {"decision": "REJECTED_BEFORE_LIFECYCLE", "observed_after_reservation": durable}
        row["state"] = "REJECTED"
        row["rejection"] = {"type": type(error).__name__, "detail": str(error), "recorded": stamp()}
        save(ledger, row)
        raise
    row["admission"] = {"decision": "AUTHORIZED_LIFECYCLE_ENTRY", "observed_after_reservation": durable}
    row["state"] = "ADMITTED"
    save(ledger, row)  # lifecycle entry is forbidden until this decision is durable
    root.mkdir()
    fsync_directory(root.parent)
    st = root.stat()
    row["root_identity"] = {"device": st.st_dev, "inode": st.st_ino}
    save(ledger, row)
    save(root / "state/authorization.json", auth, exclusive=True)
    row["consumed"] = stamp()
    row["state"] = "CONSUMED"
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
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = proc.communicate()
            else:
                stdout, stderr = "", ""
            stderr += type(error).__name__ + ": " + str(error)
            code, interrupted, timed_out = 125, True, False
        if self.simulation and os.environ.get("X6_R1_5_1_CONTROLLED_CLOCK") == "1":
            if name == "iperf": advance_clock(20_000_000_000)
            elif name == "traffic_ping": advance_clock(10_000_000_000)
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
            rows.append({**intent, "incomplete": True})
            continue
        row = load(result_path)
        require(all(row[k] == v for k, v in intent.items()) and row["intent_sha256"] == digest(canonical(intent)), "command intent/result contradiction")
        require(type(row["return_code"]) is int and type(row["timed_out"]) is bool and type(row["interrupted"]) is bool and type(row["source_test_only"]) is bool, "command result types")
        points = (intent["intent_at"], row["started"], row["completed"])
        require(len({point.get("boot_id") for point in points}) == 1 and next(iter({point.get("boot_id") for point in points})), "command boot context")
        for point in points:
            require(set(point) == {"monotonic_ns", "utc", "boot_id"} and type(point["monotonic_ns"]) is int and point["monotonic_ns"] >= 0 and point["utc"].endswith("Z"), "command timestamp schema")
            datetime.fromisoformat(point["utc"].replace("Z", "+00:00"))
        require(row["stdout_sha256"] == digest(row["stdout"].encode()) and row["stderr_sha256"] == digest(row["stderr"].encode()), "command stream drift")
        require(intent["intent_at"]["monotonic_ns"] <= row["started"]["monotonic_ns"] <= row["completed"]["monotonic_ns"], "command timing drift")
        rows.append(row)
    require(len(list((Path(root) / "raw/commands").glob("*.result.json"))) == sum(not row.get("incomplete", False) for row in rows), "orphan command result")
    return rows


def acquire_topology_lock():
    path = Path("/tmp") / ("ind-x6r1-" + str(os.getuid()) + ".lock")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        require(os.fstat(descriptor).st_uid == os.getuid(), "foreign topology lease")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise
