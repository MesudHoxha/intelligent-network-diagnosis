"""R1.3.5 durable provenance primitives for a future baseline-only attempt.

This module has no import-time effects and creates no authorization.  A future
runner may use its fixed command recorder only after a separately reviewed
authorization has been validated.  Unit tests inject an executor; no test
fixture is runtime evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from time import monotonic_ns
from typing import Callable, Mapping

from src.orchestration.x6_r1_3_3_baseline_only_runner import write_json_fsync
from src.runtime.subprocesses import run_capture

RELEASE_ID = "X6_R1_3_5_BASELINE_RUNTIME_PROVENANCE_AND_INDEPENDENT_VERIFICATION_COMPLETION"
TOPOLOGY = "labs/topologies/x6_r1_packet_loss/topology.clab.yml"
DOCKERFILE = "labs/images/ind-linux/Dockerfile"
AUTHORIZATION_VECTOR = {"containerlab": False, "measurement": False, "f1_revalidation": False, "f2": False, "f3": False, "f4": False, "dataset": False, "ml_hybrid": False, "api": False, "p9_r2": False}
FORBIDDEN = {"sudo", "modprobe", "bash", "sh", "zsh", "fish", "cmd", "powershell", "pwsh", "netem", "pfifo", "tbf", "htb", "cake", "police", "replace", "add", "del"}
COMMANDS = {
    "kernel": ["uname", "-r"], "kernel_config": ["zgrep", "CONFIG_NET_SCH_NETEM", "/proc/config.gz"], "module": ["lsmod"],
    "python": ["python3", "--version"], "ip": ["ip", "-V"], "tc": ["tc", "-V"], "ethtool": ["ethtool", "--version"],
    "ping": ["ping", "-V"], "iperf3": ["iperf3", "--version"], "docker": ["docker", "version", "--format", "json"],
    "containerlab": ["containerlab", "version"], "git": ["git", "rev-parse", "HEAD", "HEAD^{tree}"],
    "image": ["docker", "image", "inspect", "local/ind-linux:latest"], "processes": ["docker", "ps", "--format", "json"],
    "namespaces": ["ip", "netns", "list"], "qdisc": ["docker", "exec", "clab-x6r1-r2", "/usr/sbin/tc", "-j", "-s", "qdisc", "show", "dev", "eth2"],
    "filters": ["docker", "exec", "clab-x6r1-r2", "/usr/sbin/tc", "-j", "filter", "show", "dev", "eth2", "root"],
    "deploy": ["containerlab", "deploy", "-t", TOPOLOGY], "cleanup": ["containerlab", "destroy", "-t", TOPOLOGY, "--cleanup"],
    "server_stop": ["docker", "exec", "clab-x6r1-hostb", "/usr/bin/pkill", "-x", "iperf3"], "server_start": ["docker", "exec", "-d", "clab-x6r1-hostb", "/usr/bin/iperf3", "-s", "--one-off", "-p", "5201", "--json"],
    "server_ready": ["docker", "exec", "clab-x6r1-hostb", "/usr/bin/ss", "-H", "-ltn", "sport", "=", ":5201"], "iperf": ["docker", "exec", "clab-x6r1-hosta", "/usr/bin/iperf3", "-c", "10.61.3.2", "-t", "20", "-P", "1", "-p", "5201", "-J"],
    "traffic_ping": ["docker", "exec", "--env", "LC_ALL=C", "clab-x6r1-hosta", "/usr/bin/ping", "-n", "-i", "0.2", "-c", "50", "-W", "1", "-s", "56", "10.61.3.2"],
    "r2_tx": ["docker", "exec", "clab-x6r1-r2", "cat", "/sys/class/net/eth2/statistics/tx_bytes"], "r3_rx": ["docker", "exec", "clab-x6r1-r3", "cat", "/sys/class/net/eth1/statistics/rx_bytes"], "r2_speed": ["docker", "exec", "clab-x6r1-r2", "cat", "/sys/class/net/eth2/speed"], "r3_speed": ["docker", "exec", "clab-x6r1-r3", "cat", "/sys/class/net/eth1/speed"],
}
Executor = Callable[[list[str]], Mapping[str, object]]


class X6R135Error(ValueError):
    pass


def _fail(message: str) -> None:
    raise X6R135Error("X6-R1.3.5: " + message)


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        _fail("unsafe artifact path")
    return value


def _record_digest(value: Mapping[str, object]) -> str:
    unsigned = dict(value); unsigned.pop("record_sha256", None)
    return sha256(canonical_bytes(unsigned))


def _command(name: str) -> list[str]:
    if name not in COMMANDS:
        _fail("command is not allowlisted")
    command = list(COMMANDS[name])
    if any(not isinstance(item, str) or not item or item.lower() in FORBIDDEN for item in command):
        _fail("prohibited command token")
    return command


class CommandRecorder:
    """Atomically persist a complete, ordered record for every command."""
    def __init__(self, root: Path, *, run_id: str, authorization_id: str, source_test_only: bool, clock: Callable[[], int] = monotonic_ns, resume: bool = False) -> None:
        self.root, self.run_id, self.authorization_id, self.source_test_only, self.clock = Path(root), run_id, authorization_id, source_test_only, clock
        if not run_id or not authorization_id:
            _fail("run and authorization identity are required")
        self.inventory = self.root / "state" / "command_inventory.json"
        if self.inventory.exists() and not resume: _fail("command inventory already exists; copied/reused run rejected")
        self.rows: list[dict[str, object]] = []
        if resume:
            value = json.loads(self.inventory.read_text(encoding="utf-8"))
            if value.get("run_id") != run_id or value.get("authorization_id") != authorization_id or value.get("source_test_only") != source_test_only or not isinstance(value.get("records"), list): _fail("cannot resume foreign command inventory")
            self.rows = list(value["records"])

    def capture(self, *, name: str, phase: str, action_id: str, executor: Executor, window_id: str | None = None, timeout_seconds: int = 30) -> dict[str, str]:
        if timeout_seconds <= 0 or not phase or not action_id:
            _fail("command metadata is incomplete")
        command = _command(name)
        order = len(self.rows) + 1
        started_ns, started_utc = self.clock(), utc_now()
        try:
            result = dict(executor(command))
            interrupted = False
        except BaseException as error:
            result, interrupted = {"return_code": 125, "stdout": "", "stderr": type(error).__name__}, True
        ended_ns, ended_utc = self.clock(), utc_now()
        if ended_ns < started_ns or set(result) != {"return_code", "stdout", "stderr"} or isinstance(result["return_code"], bool) or not isinstance(result["return_code"], int) or not isinstance(result["stdout"], str) or not isinstance(result["stderr"], str):
            _fail("executor produced malformed command result")
        record: dict[str, object] = {"schema_version": 1, "record_id": f"{order:05d}:{phase}:{window_id or 'GLOBAL'}:{name}", "order": order, "run_id": self.run_id, "authorization_id": self.authorization_id, "parent_action_id": action_id, "phase": phase, "window_id": window_id, "command_name": name, "argv": command, "shell": False, "environment": {"LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"}, "timeout_seconds": timeout_seconds, "started_at_utc": started_utc, "completed_at_utc": ended_utc, "started_monotonic_ns": started_ns, "completed_monotonic_ns": ended_ns, "elapsed_ns": ended_ns - started_ns, "return_code": result["return_code"], "timed_out": result["return_code"] == 124, "interrupted": interrupted, "stdout": result["stdout"], "stderr": result["stderr"], "source_test_only": self.source_test_only}
        record["record_sha256"] = _record_digest(record)
        relative = f"raw/commands/{order:05d}-{name}.json"; path = self.root / relative
        write_json_fsync(path, record)
        reference = {"path": relative, "sha256": sha256(path.read_bytes())}
        self.rows.append({"record_id": record["record_id"], "order": order, "reference": reference})
        write_json_fsync(self.inventory, {"schema_version": 1, "release_id": RELEASE_ID, "run_id": self.run_id, "authorization_id": self.authorization_id, "records": self.rows, "source_test_only": self.source_test_only})
        return reference


def verify_command_inventory(root: Path, *, run_id: str, authorization_id: str) -> list[dict[str, object]]:
    root = Path(root); inventory_path = root / "state" / "command_inventory.json"
    if not inventory_path.is_file() or inventory_path.is_symlink(): _fail("command inventory missing or unsafe")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if not isinstance(inventory, Mapping) or inventory.get("release_id") != RELEASE_ID or inventory.get("run_id") != run_id or inventory.get("authorization_id") != authorization_id or not isinstance(inventory.get("records"), list): _fail("command inventory identity drift")
    rows: list[dict[str, object]] = []
    for expected_order, item in enumerate(inventory["records"], 1):
        if not isinstance(item, Mapping) or item.get("order") != expected_order or not isinstance(item.get("reference"), Mapping): _fail("command inventory ordering drift")
        reference = item["reference"]; path = root / safe_relative(str(reference.get("path", "")))
        if not path.is_file() or path.is_symlink() or not isinstance(reference.get("sha256"), str) or sha256(path.read_bytes()) != reference["sha256"]: _fail("command record hash drift")
        record = json.loads(path.read_text(encoding="utf-8"))
        required = {"schema_version", "record_id", "order", "run_id", "authorization_id", "parent_action_id", "phase", "window_id", "command_name", "argv", "shell", "environment", "timeout_seconds", "started_at_utc", "completed_at_utc", "started_monotonic_ns", "completed_monotonic_ns", "elapsed_ns", "return_code", "timed_out", "interrupted", "stdout", "stderr", "source_test_only", "record_sha256"}
        if not isinstance(record, Mapping) or set(record) != required or record.get("order") != expected_order or record.get("run_id") != run_id or record.get("authorization_id") != authorization_id or record.get("shell") is not False or record.get("argv") != _command(str(record.get("command_name"))) or record.get("environment") != {"LC_ALL": "C", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"} or record.get("record_sha256") != _record_digest(record): _fail("command record semantic drift")
        a, b, elapsed = record["started_monotonic_ns"], record["completed_monotonic_ns"], record["elapsed_ns"]
        try:
            started_utc, completed_utc = str(record["started_at_utc"]), str(record["completed_at_utc"])
            if not started_utc.endswith("Z") or not completed_utc.endswith("Z"): raise ValueError
            datetime.fromisoformat(started_utc[:-1] + "+00:00"); datetime.fromisoformat(completed_utc[:-1] + "+00:00")
        except ValueError:
            _fail("command record UTC timestamp drift")
        if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in (a, b, elapsed)) or b < a or elapsed != b - a or not isinstance(record["stdout"], str) or not isinstance(record["stderr"], str) or isinstance(record["return_code"], bool) or not isinstance(record["return_code"], int) or not isinstance(record["timed_out"], bool) or not isinstance(record["interrupted"], bool): _fail("command record timing/result drift")
        rows.append(dict(record))
    if len({str(row["record_id"]) for row in rows}) != len(rows): _fail("duplicate command record")
    return rows


def derive_source_identity(repository_root: Path) -> dict[str, object]:
    root = Path(repository_root).resolve()
    def git(*args: str) -> str:
        completed = run_capture(["git", "-C", str(root), *args], timeout_seconds=30, cwd=root)
        if completed.returncode != 0: _fail("unable to derive checked-out Git identity")
        return completed.stdout.strip()
    if git("status", "--porcelain=v1"): _fail("checked-out source is dirty")
    paths = [TOPOLOGY, DOCKERFILE, "src/orchestration/x6_r1_3_4_baseline_execution.py", "src/expansion/x6_r1_3_4_materialized_verifier.py"]
    hashes: dict[str, str] = {}
    for relative in paths:
        path = root / relative
        if not path.is_file() or path.is_symlink(): _fail("required source binding is unavailable")
        hashes[relative] = sha256(path.read_bytes())
    return {"git_commit": git("rev-parse", "HEAD"), "git_tree": git("rev-parse", "HEAD^{tree}"), "topology_path": TOPOLOGY, "topology_sha256": hashes[TOPOLOGY], "dockerfile_path": DOCKERFILE, "dockerfile_sha256": hashes[DOCKERFILE], "source_hashes": hashes}


def collect_full_provenance(recorder: CommandRecorder, *, executor: Executor, repository_root: Path) -> dict[str, object]:
    """Collect every accepted host/tool observation through durable records.

    The returned identity is calculated from the actual checkout, never from a
    caller-supplied expected-identity document.  A future authorization may
    compare against it but cannot replace it.
    """
    names = ("kernel", "kernel_config", "module", "python", "ip", "tc", "ethtool", "ping", "iperf3", "docker", "containerlab", "git", "image")
    records: dict[str, dict[str, str]] = {}
    for name in names:
        reference = recorder.capture(name=name, phase="provenance", action_id="provenance", executor=executor)
        path = recorder.root / reference["path"]
        row = json.loads(path.read_text(encoding="utf-8"))
        if row["return_code"] != 0 or row["timed_out"] or row["interrupted"]:
            _fail("required provenance command failed: " + name)
        records[name] = reference
    identity = derive_source_identity(repository_root)
    result = {"release_id": RELEASE_ID, "identity": identity, "command_records": records, "source_test_only": recorder.source_test_only}
    write_json_fsync(recorder.root / "state" / "provenance.json", result)
    return result


def verify_recovery(root: Path, *, original_pid: int, recovery_pid: int, run_id: str, authorization_id: str) -> dict[str, object]:
    if original_pid <= 0 or recovery_pid <= 0 or original_pid == recovery_pid: _fail("recovery process is not distinct")
    rows = verify_command_inventory(root, run_id=run_id, authorization_id=authorization_id)
    recovery = [row for row in rows if row["phase"] == "recovery"]
    if not recovery or any(row["return_code"] != 0 or row["timed_out"] or row["interrupted"] for row in recovery): _fail("recovery command evidence is incomplete or failed")
    return {"original_pid": original_pid, "recovery_pid": recovery_pid, "distinct_process": True, "recovery_commands": len(recovery)}
