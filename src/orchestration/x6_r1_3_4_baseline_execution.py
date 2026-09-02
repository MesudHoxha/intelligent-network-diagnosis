"""The separately-bound X6-R1.3.4 future baseline-only execution path.

This module deliberately does not change the published R1.3.3 preparation
runner. It can make stateful calls only after a future, hash-bound,
one-attempt authorization is validated and durably consumed. Importing it has
no effects; unit tests use an injected executor and collector only.
"""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic_ns, sleep
from typing import Callable, Mapping

from src.collection.x6_performance_collector import derive_window
from src.collection.x6_r0_3_pre_runtime_validation import NUMERIC_FEATURES, build_threshold_manifest, canonical_threshold_manifest_bytes
from src.orchestration.x6_r1_3_3_baseline_only_runner import WINDOW_IDS, frozen_schedule, initialize_attempt, terminalize_attempt, validate_authorization, write_json_fsync
from src.runtime.subprocesses import run_capture

RELEASE_ID = "X6_R1_3_4_BASELINE_ONLY_RUNTIME_EXECUTION_AND_MATERIALIZED_CONTROL_COMPLETION"
TOPOLOGY = "labs/topologies/x6_r1_packet_loss/topology.clab.yml"
Executor = Callable[[list[str]], Mapping[str, object]]
Collector = Callable[[str], Mapping[str, object]]

# Structured argv only. The only stateful entries are the documented topology
# lifecycle and the owned iperf server; no qdisc/filter mutation exists here.
COMMANDS = {
    "deploy": ["containerlab", "deploy", "-t", TOPOLOGY],
    "readiness": ["docker", "exec", "clab-x6r1-hosta", "/usr/bin/ping", "-c", "1", "-W", "2", "10.61.3.2"],
    "qdisc": ["docker", "exec", "clab-x6r1-r2", "/usr/sbin/tc", "-j", "-s", "qdisc", "show", "dev", "eth2"],
    "filters_root": ["docker", "exec", "clab-x6r1-r2", "/usr/sbin/tc", "-j", "filter", "show", "dev", "eth2", "root"],
    "filters_ingress": ["docker", "exec", "clab-x6r1-r2", "/usr/sbin/tc", "-j", "filter", "show", "dev", "eth2", "ingress"],
    "r2_tx": ["docker", "exec", "clab-x6r1-r2", "cat", "/sys/class/net/eth2/statistics/tx_bytes"],
    "r3_rx": ["docker", "exec", "clab-x6r1-r3", "cat", "/sys/class/net/eth1/statistics/rx_bytes"],
    "r2_speed": ["docker", "exec", "clab-x6r1-r2", "cat", "/sys/class/net/eth2/speed"],
    "r3_speed": ["docker", "exec", "clab-x6r1-r3", "cat", "/sys/class/net/eth1/speed"],
    "processes": ["docker", "ps", "--format", "json"],
    "namespaces": ["ip", "netns", "list"],
    "server_stop": ["docker", "exec", "clab-x6r1-hostb", "/usr/bin/pkill", "-x", "iperf3"],
    "server_start": ["docker", "exec", "-d", "clab-x6r1-hostb", "/usr/bin/iperf3", "-s", "--one-off", "-p", "5201", "--json"],
    "server_ready": ["docker", "exec", "clab-x6r1-hostb", "/usr/bin/ss", "-H", "-ltn", "sport", "=", ":5201"],
    "iperf": ["docker", "exec", "clab-x6r1-hosta", "/usr/bin/iperf3", "-c", "10.61.3.2", "-t", "20", "-P", "1", "-p", "5201", "-J"],
    "ping": ["docker", "exec", "--env", "LC_ALL=C", "clab-x6r1-hosta", "/usr/bin/ping", "-n", "-i", "0.2", "-c", "50", "-W", "1", "-s", "56", "10.61.3.2"],
    "cleanup": ["containerlab", "destroy", "-t", TOPOLOGY, "--cleanup"],
}
FORBIDDEN = {"sudo", "modprobe", "bash", "sh", "zsh", "fish", "netem", "pfifo", "tbf", "htb", "cake", "police", "replace", "add", "del"}


class X6R134Error(ValueError):
    pass


def _fail(message: str) -> None:
    raise X6R134Error("X6-R1.3.4: " + message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_authorization(path: Path, *, expected_source: Mapping[str, str], expected_bindings: Mapping[str, str]) -> dict[str, object]:
    """Load only a canonical future authorization, before any external action."""
    candidate = Path(path)
    if not candidate.is_file() or candidate.is_symlink():
        _fail("authorization artifact is absent or unsafe")
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise X6R134Error("X6-R1.3.4: authorization artifact is not JSON") from error
    if not isinstance(value, Mapping):
        _fail("authorization artifact object required")
    return validate_authorization(value, expected_source=expected_source, expected_bindings=expected_bindings)


def _capture(root: Path, name: str, executor: Executor, *, source_test_only: bool, command_name: str | None = None) -> dict[str, str]:
    """Execute one exact allowlisted command and bind its complete result."""
    command = COMMANDS[command_name or name]
    if any(item.lower() in FORBIDDEN for item in command):
        _fail("prohibited command token in " + name)
    result = dict(executor(list(command)))
    if set(result) != {"return_code", "stdout", "stderr"}:
        _fail("executor result schema drift for " + name)
    if isinstance(result["return_code"], bool) or not isinstance(result["return_code"], int):
        _fail("return code malformed for " + name)
    if not isinstance(result["stdout"], str) or not isinstance(result["stderr"], str):
        _fail("stdout/stderr malformed for " + name)
    payload = {"command": command, "shell": False, "timeout_seconds": 30, **result, "source_test_only": source_test_only}
    path = root / "raw" / (name + ".json")
    write_json_fsync(path, payload)
    return {"path": str(path.relative_to(root)), "sha256": _sha(path.read_bytes())}


def _record(root: Path, reference: Mapping[str, str]) -> Mapping[str, object]:
    path = root / reference["path"]
    if not path.is_file() or _sha(path.read_bytes()) != reference["sha256"]:
        _fail("raw command record is missing or changed")
    return json.loads(path.read_text(encoding="utf-8"))


def _require_zero(root: Path, reference: Mapping[str, str], name: str) -> None:
    if _record(root, reference)["return_code"] != 0:
        _fail(name + " returned nonzero")


def _phase(clock: Callable[[], int], seconds: int, sleeper: Callable[[float], None]) -> dict[str, int]:
    started = clock(); sleeper(seconds); ended = clock()
    return {"scheduled_start_ns": started, "scheduled_end_ns": started + seconds * 1_000_000_000, "actual_start_ns": started, "actual_end_ns": ended}


def production_collector(root: Path, executor: Executor, *, speed_mbps: int, source_test_only: bool = False) -> Collector:
    """Return the frozen 20-second composite collector bound to raw argv."""
    def collect(window_id: str) -> Mapping[str, object]:
        raw: dict[str, object] = {"window_id": window_id, "phase": "baseline"}
        raw["server_teardown_before"] = dict(executor(list(COMMANDS["server_stop"])))
        raw["server_start"] = dict(executor(list(COMMANDS["server_start"])))
        raw["server_readiness"] = dict(executor(list(COMMANDS["server_ready"])))
        if any(raw[name].get("return_code") != 0 for name in ("server_start", "server_readiness")):
            _fail(window_id + " server preparation failed")
        for key in ("r2_tx", "r3_rx", "qdisc"):
            raw[key + "_before"] = dict(executor(list(COMMANDS[key])))
        raw["filters_before"] = [dict(executor(list(COMMANDS[key]))) for key in ("filters_root", "filters_ingress")]
        with ThreadPoolExecutor(max_workers=2) as pool:
            iperf_started = monotonic_ns(); iperf = pool.submit(executor, list(COMMANDS["iperf"]))
            target = iperf_started + 5_000_000_000
            while monotonic_ns() < target:
                sleep(min(0.01, (target - monotonic_ns()) / 1_000_000_000))
            ping_started = monotonic_ns(); ping = pool.submit(executor, list(COMMANDS["ping"]))
            raw["iperf"], raw["ping"] = dict(iperf.result()), dict(ping.result())
        raw["startup_skew_seconds"] = abs(ping_started - target) / 1_000_000_000
        if raw["startup_skew_seconds"] > 0.250:
            _fail(window_id + " startup skew exceeded 0.250 seconds")
        for key in ("r2_tx", "r3_rx", "qdisc"):
            raw[key + "_after"] = dict(executor(list(COMMANDS[key])))
        raw["filters_after"] = [dict(executor(list(COMMANDS[key]))) for key in ("filters_root", "filters_ingress")]
        raw["server_teardown_after"] = dict(executor(list(COMMANDS["server_stop"])))
        raw["elapsed_seconds"] = 20.0
        timing = {"actual_start_ns": iperf_started, "actual_end_ns": monotonic_ns(), "startup_skew_seconds": raw["startup_skew_seconds"]}
        derived = derive_window(raw, phase="baseline", speed_mbps=speed_mbps)
        values: dict[str, object] = {}
        for feature in NUMERIC_FEATURES:
            item = derived[feature]
            if item.get("availability") != "observed":
                _fail(window_id + " required measurement unavailable: " + feature)
            values[feature] = item["value"]
        raw["source_test_only"] = source_test_only
        return {"measurements": values, "observations": dict(values), "raw": raw, "timing": timing}
    return collect


def collect_thirty_windows(root: Path, collector: Collector, *, source_test_only: bool, clock: Callable[[], int] = monotonic_ns, sleeper: Callable[[float], None] = sleep) -> dict[str, object]:
    """Persist C01..H10 in order and freeze the canonical manifest at C10."""
    rows: list[dict[str, object]] = []
    manifest: dict[str, object] | None = None
    write_json_fsync(root / "state" / "schedule.json", frozen_schedule())
    write_json_fsync(root / "state" / "readiness.json", _phase(clock, 5, sleeper))
    write_json_fsync(root / "state" / "warmup.json", _phase(clock, 5, sleeper))
    for index, window_id in enumerate(WINDOW_IDS):
        if index:
            sleeper(5)
        value = dict(collector(window_id))
        if set(value) != {"measurements", "observations", "raw", "timing"} or value["measurements"] != value["observations"]:
            _fail(window_id + " measurements/observations are not canonically identical")
        features = value["measurements"]
        if not isinstance(features, Mapping) or set(features) != set(NUMERIC_FEATURES):
            _fail(window_id + " feature catalog drift")
        timing = value["timing"]
        if not isinstance(timing, Mapping) or set(timing) != {"actual_start_ns", "actual_end_ns", "startup_skew_seconds"}:
            _fail(window_id + " timing schema drift")
        start, end, skew = timing["actual_start_ns"], timing["actual_end_ns"], timing["startup_skew_seconds"]
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in (start, end, skew)) or start < 0 or end - start < 20_000_000_000 or skew < 0 or skew > 0.250:
            _fail(window_id + " frozen duration or startup-skew violation")
        if rows and start < rows[-1]["actual_end_ns"] + 5_000_000_000:
            _fail(window_id + " overlaps or violates five-second post-window spacing")
        raw_path = root / "raw" / "windows" / (window_id + ".json")
        write_json_fsync(raw_path, {"window_id": window_id, "canonical_features": dict(features), "collector_raw": value["raw"], "timing": dict(timing), "source_test_only": source_test_only})
        rows.append({"window_id": window_id, "measurements": dict(features), "observations": dict(features), "raw_artifact": {"path": str(raw_path.relative_to(root)), "sha256": _sha(raw_path.read_bytes())}, "scheduled_duration_seconds": 20, "actual_start_ns": start, "actual_end_ns": end, "startup_skew_seconds": skew})
        if index == 9:
            inputs = {feature: [row["measurements"][feature] for row in rows] for feature in NUMERIC_FEATURES}
            manifest = build_threshold_manifest(inputs, topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH", traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
            manifest_path = root / "state" / "threshold_manifest.json"
            manifest_path.write_bytes(canonical_threshold_manifest_bytes(manifest))
            write_json_fsync(root / "state" / "threshold_freeze.json", {"after_window_id": "C10", "before_window_id": "C11", "manifest_sha256": manifest["sha256"], "byte_sha256": _sha(manifest_path.read_bytes()), "frozen_at_monotonic_ns": clock()})
        if index >= 10 and manifest is None:
            _fail("threshold manifest was not finalized before C11")
    write_json_fsync(root / "state" / "cooldown.json", _phase(clock, 5, sleeper))
    if manifest is None or len(rows) != len(WINDOW_IDS):
        _fail("exactly thirty non-replacement windows are required")
    return {"windows": rows, "threshold_manifest": manifest, "threshold_sha256": manifest["sha256"], "source_test_only": source_test_only}


def cleanup_owned_resources(root: Path, executor: Executor, *, source_test_only: bool, record_name: str = "cleanup") -> dict[str, str]:
    """The exact destroy command is retained as cleanup evidence on every path."""
    return _capture(root, record_name, executor, source_test_only=source_test_only, command_name="cleanup")


def recover_attempt(run_root: Path, *, executor: Executor, replay_pid: int, source_test_only: bool) -> dict[str, object]:
    """Independent-process recovery uses only owned-resource inspection and cleanup."""
    root = Path(run_root)
    if replay_pid <= 0 or not (root / "state" / "action_journal.json").is_file():
        _fail("standalone recovery requires a durable journal and independent process identity")
    before = {name: _capture(root, "recovery_" + name, executor, source_test_only=source_test_only, command_name=name) for name in ("processes", "namespaces")}
    cleanup = cleanup_owned_resources(root, executor, source_test_only=source_test_only, record_name="recovery_cleanup")
    after = {name: _capture(root, "recovery_after_" + name, executor, source_test_only=source_test_only, command_name=name) for name in ("processes", "namespaces")}
    result = {"new_process": True, "replay_pid": replay_pid, "before": before, "cleanup": cleanup, "after": after, "status": "IDEMPOTENT_RECOVERY_CONFIRMED", "source_test_only": source_test_only}
    write_json_fsync(root / "state" / "recovery.json", result)
    return result


def _terminalize(root: Path, *, status: str, detail: str, source_test_only: bool) -> dict[str, object]:
    inherited = terminalize_attempt(root, status=status, detail=detail)
    result = {"release_id": RELEASE_ID, "status": status, "detail": detail, "source_test_only": source_test_only,
              "qualification": "INDEPENDENT_MATERIALIZED_VERIFIER_REQUIRED", "inherited_terminal": inherited}
    write_json_fsync(root / "state" / "r1_3_4_terminal.json", result)
    return result


def execute(*, authorization_path: Path, run_root: Path, ledger_root: Path, run_id: str, expected_source: Mapping[str, str], expected_bindings: Mapping[str, str], executor: Executor, collector: Collector | None = None, source_test_only: bool = False, clock: Callable[[], int] = monotonic_ns, sleeper: Callable[[float], None] = sleep) -> dict[str, object]:
    """Run one complete authorized lifecycle; every post-consumption path terminals."""
    authorization = load_authorization(authorization_path, expected_source=expected_source, expected_bindings=expected_bindings)
    initialize_attempt(run_root, authorization=authorization, ledger_root=ledger_root, run_id=run_id)
    root = Path(run_root)
    try:
        controls = {name: _capture(root, name, executor, source_test_only=source_test_only) for name in ("deploy", "readiness", "qdisc", "filters_root", "filters_ingress", "r2_tx", "r3_rx", "r2_speed", "r3_speed", "processes", "namespaces")}
        for name, reference in controls.items():
            _require_zero(root, reference, name)
        try:
            r2_speed = int(str(_record(root, controls["r2_speed"])["stdout"]).strip())
            r3_speed = int(str(_record(root, controls["r3_speed"])["stdout"]).strip())
        except (TypeError, ValueError):
            _fail("interface speed control is malformed")
        if r2_speed <= 0 or r2_speed != r3_speed:
            _fail("interface speed control is unequal or unavailable")
        result = collect_thirty_windows(root, collector or production_collector(root, executor, speed_mbps=r2_speed, source_test_only=source_test_only), source_test_only=source_test_only, clock=clock, sleeper=sleeper)
        controls.update({"qdisc_after": _capture(root, "qdisc_after", executor, source_test_only=source_test_only, command_name="qdisc"), "filters_root_after": _capture(root, "filters_root_after", executor, source_test_only=source_test_only, command_name="filters_root"), "filters_ingress_after": _capture(root, "filters_ingress_after", executor, source_test_only=source_test_only, command_name="filters_ingress"), "cleanup": cleanup_owned_resources(root, executor, source_test_only=source_test_only)})
        _require_zero(root, controls["cleanup"], "cleanup")
        write_json_fsync(root / "state" / "control_artifacts.json", controls)
        # Qualification is reserved for the independent materialized verifier.
        return _terminalize(root, status="INCONCLUSIVE" if source_test_only else "COLLECTION_UNAVAILABLE", detail="all windows collected; independent materialized verifier required", source_test_only=source_test_only)
    except X6R134Error as error:
        cleanup_owned_resources(root, executor, source_test_only=source_test_only)
        return _terminalize(root, status="ENVIRONMENT_INELIGIBLE", detail=str(error), source_test_only=source_test_only)
    except BaseException as error:
        try:
            cleanup_owned_resources(root, executor, source_test_only=source_test_only)
        finally:
            _terminalize(root, status="INTERRUPTED", detail=type(error).__name__, source_test_only=source_test_only)
        raise


def _production_executor(command: list[str]) -> Mapping[str, object]:
    result = run_capture(command, timeout_seconds=30)
    return {"return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="X6-R1.3.4 future authorization-gated baseline-only runner")
    parser.add_argument("--authorization", type=Path, required=True); parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--ledger-root", type=Path, required=True); parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-source-json", type=Path, required=True); parser.add_argument("--expected-bindings-json", type=Path, required=True)
    args = parser.parse_args()
    execute(authorization_path=args.authorization, run_root=args.run_root, ledger_root=args.ledger_root, run_id=args.run_id, expected_source=json.loads(args.expected_source_json.read_text(encoding="utf-8")), expected_bindings=json.loads(args.expected_bindings_json.read_text(encoding="utf-8")), executor=_production_executor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
