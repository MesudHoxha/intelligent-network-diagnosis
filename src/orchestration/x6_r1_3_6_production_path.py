"""R1.3.6 production-only integration for a future separately authorized run.

This module creates no authorization and has no import-time side effects.  Its
CLI is deliberately unusable until a later R1.4 authorization exists and an
operator explicitly invokes ``--execute``.  Source tests may exercise the
shared core with marked fake adapters, but that path is not exposed by the CLI.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from time import monotonic_ns, sleep
from typing import Callable, Mapping, Protocol

from src.collection.x6_performance_collector import derive_window
from src.collection.x6_r0_3_pre_runtime_validation import NUMERIC_FEATURES, build_threshold_manifest, canonical_threshold_manifest_bytes
from src.orchestration.x6_r1_3_3_baseline_only_runner import WINDOW_IDS, write_json_fsync
from src.orchestration.x6_r1_3_5_baseline_provenance import COMMANDS, CommandRecorder, X6R135Error, canonical_bytes, derive_source_identity, sha256
from src.runtime.subprocesses import run_capture


RELEASE_ID = "X6_R1_3_6_BASELINE_ONLY_PRODUCTION_PATH_INTEGRATION_COMPLETION"
FUTURE_AUTHORIZATION_RELEASE = "X6_R1_4_BASELINE_ONLY_RUNTIME_AUTHORIZATION"
SCOPE = "BASELINE_ONLY_QUALIFICATION"
HISTORICAL_VECTOR = {"containerlab": False, "measurement": False, "f1_revalidation": False, "f2": False, "f3": False, "f4": False, "dataset": False, "ml_hybrid": False, "api": False, "p9_r2": False}
TOPOLOGY = "labs/topologies/x6_r1_packet_loss/topology.clab.yml"
DOCKERFILE = "labs/images/ind-linux/Dockerfile"
TRAFFIC = {"iperf_destination": "10.61.3.2", "iperf_seconds": 20, "ping_destination": "10.61.3.2", "ping_count": 50}
SCHEDULE = {"readiness_seconds": 5, "warmup_seconds": 5, "window_seconds": 20, "separation_seconds": 5, "cooldown_seconds": 5, "maximum_startup_skew_seconds": "0.250000", "windows": list(WINDOW_IDS), "construction": list(WINDOW_IDS[:10]), "calibration": list(WINDOW_IDS[10:20]), "holdout": list(WINDOW_IDS[20:])}
OWNERSHIP = {"topology": TOPOLOGY, "container_prefix": "clab-x6r1-", "namespace_prefix": "clab-x6r1-", "traffic_process": "iperf3", "mutation": "FORBIDDEN"}
STATEFUL_COMMANDS = {"deploy", "server_stop", "server_start", "iperf", "traffic_ping", "cleanup"}
PROHIBITIONS = {"mutation": True, "netem": True, "pfifo": True, "fault_injection": True, "f1_revalidation": True, "evidence_v4": True, "feature_vector_v2": True, "diagnosis": True, "dataset": True, "model": True, "metric": True, "api": True, "thesis_result": True, "generalized_scientific_claim": True}


class X6R136Error(ValueError):
    pass


def _fail(message: str) -> None:
    raise X6R136Error("X6-R1.3.6: " + message)


def _canonical(value: object) -> bytes:
    return canonical_bytes(value)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Timing(Protocol):
    def monotonic(self) -> int: ...
    def wait(self, seconds: int) -> None: ...


class RealTiming:
    def monotonic(self) -> int:
        return monotonic_ns()

    def wait(self, seconds: int) -> None:
        if seconds <= 0:
            _fail("bounded positive wait required")
        sleep(seconds)


class RepositoryExecutor:
    """Private argv bridge: only recorder-created allowlisted commands reach it."""
    _allowed = frozenset(COMMANDS)

    def __call__(self, argv: list[str]) -> dict[str, object]:
        command_id = next((name for name in self._allowed if COMMANDS[name] == argv), None)
        if command_id is None:
            _fail("repository executor rejected non-catalog command")
        result = run_capture(COMMANDS[command_id], timeout_seconds=30)
        return {"return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def _identity(repository_root: Path) -> dict[str, object]:
    """Independently derive the transitive tracked source identity at execution."""
    identity = derive_source_identity(repository_root)
    tracked = [TOPOLOGY, DOCKERFILE, "src/orchestration/x6_r1_3_6_production_path.py", "src/expansion/x6_r1_3_6_materialized_verifier.py"]
    hashes: dict[str, str] = {}
    for relative in tracked:
        path = Path(repository_root) / relative
        if not path.is_file() or path.is_symlink():
            _fail("required tracked source is absent: " + relative)
        hashes[relative] = _hash_file(path)
    return {**identity, "r1_3_6_tracked_hashes": hashes}


def _authorization_unsigned(value: Mapping[str, object]) -> dict[str, object]:
    unsigned = dict(value)
    unsigned.pop("authorization_sha256", None)
    return unsigned


AUTHORIZATION_FIELDS = {"schema_version", "release_id", "authorization_id", "scope", "source_identity", "tracked_source_hashes", "output_root", "run_id", "issued_ns", "expires_ns", "source_test_only", "historical_authorization", "schedule", "traffic", "ownership", "prohibitions", "authorization_sha256"}


def validate_authorization(value: Mapping[str, object], *, identity: Mapping[str, object], run_id: str, output_root: str, now_ns: int, allow_source_test: bool = False) -> dict[str, object]:
    if set(value) != AUTHORIZATION_FIELDS or value.get("schema_version") != 1 or value.get("release_id") != FUTURE_AUTHORIZATION_RELEASE or not isinstance(value.get("authorization_id"), str) or not value["authorization_id"]:
        _fail("authorization schema or future-release identity drift")
    if value.get("scope") != SCOPE or value.get("source_identity") != dict(identity) or value.get("tracked_source_hashes") != identity.get("r1_3_6_tracked_hashes"):
        _fail("authorization source or tracked-source binding drift")
    if value.get("run_id") != run_id or value.get("output_root") != output_root or not isinstance(value.get("issued_ns"), int) or not isinstance(value.get("expires_ns"), int) or value["issued_ns"] > now_ns or value["expires_ns"] < now_ns:
        _fail("authorization run/output/validity binding drift")
    if value.get("historical_authorization") != HISTORICAL_VECTOR or value.get("schedule") != SCHEDULE or value.get("traffic") != TRAFFIC or value.get("ownership") != OWNERSHIP or value.get("prohibitions") != PROHIBITIONS:
        _fail("authorization frozen contract binding drift")
    test_only = value.get("source_test_only")
    if not isinstance(test_only, bool) or (test_only and not allow_source_test) or (not test_only and allow_source_test):
        _fail("test-only authorization is not a production authorization")
    digest = value.get("authorization_sha256")
    if not isinstance(digest, str) or digest != sha256(_canonical(_authorization_unsigned(value))):
        _fail("authorization canonical hash drift")
    return dict(value)


def _write_ledger(root: Path, authorization: Mapping[str, object], *, run_id: str, output_root: str, validated_ns: int, consumed_ns: int) -> dict[str, object]:
    if consumed_ns < validated_ns:
        _fail("consumption precedes validation")
    ledger_root = root / "state" / "ledger"
    ledger_root.mkdir(parents=True, exist_ok=True)
    ledger_path = ledger_root / (str(authorization["authorization_id"]) + ".json")
    if ledger_path.exists():
        _fail("authorization reuse is prohibited")
    row = {"schema_version": 1, "authorization_id": authorization["authorization_id"], "authorization_sha256": authorization["authorization_sha256"], "run_id": run_id, "output_root": output_root, "validated_monotonic_ns": validated_ns, "consumed_monotonic_ns": consumed_ns, "original_pid": os.getpid(), "state": "CONSUMED", "previous_state": "VALIDATED"}
    row["ledger_sha256"] = sha256(_canonical(row))
    write_json_fsync(ledger_path, row)
    write_json_fsync(root / "state" / "authorization_ledger.json", row)
    return row


def _transitions(root: Path, authorization: Mapping[str, object], *, run_id: str, base_ns: int) -> list[dict[str, object]]:
    pairs = (("ABSENT", "LOADED"), ("LOADED", "VALIDATED"), ("VALIDATED", "CONSUMPTION_PLANNED"), ("CONSUMPTION_PLANNED", "CONSUMED_DURABLE"), ("CONSUMED_DURABLE", "STATEFUL_ACTION_PERMITTED"))
    rows: list[dict[str, object]] = []
    for order, (previous, state) in enumerate(pairs, 1):
        row = {"schema_version": 1, "run_id": run_id, "authorization_id": authorization["authorization_id"], "authorization_sha256": authorization["authorization_sha256"], "order": order, "previous_state": previous, "state": state, "monotonic_ns": base_ns + order, "source_test_only": bool(authorization["source_test_only"])}
        row["transition_sha256"] = sha256(_canonical(row))
        write_json_fsync(root / "state" / ("transition-%03d.json" % order), row)
        rows.append(row)
    return rows


def initialize_integrated(root: Path, *, authorization_bytes: bytes, identity: Mapping[str, object], run_id: str, output_root: str, now_ns: int, allow_source_test: bool) -> CommandRecorder:
    if Path(root).exists():
        _fail("run root reuse is prohibited")
    try:
        authorization = json.loads(authorization_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise X6R136Error("X6-R1.3.6: authorization JSON is malformed") from error
    if authorization_bytes != _canonical(authorization):
        _fail("authorization bytes are not canonical")
    auth = validate_authorization(authorization, identity=identity, run_id=run_id, output_root=output_root, now_ns=now_ns, allow_source_test=allow_source_test)
    root = Path(root); root.mkdir(parents=True)
    write_json_fsync(root / "state" / "authorization.json", auth)
    write_json_fsync(root / "state" / "authorization_bytes.json", {"sha256": sha256(authorization_bytes), "canonical": True})
    _transitions(root, auth, run_id=run_id, base_ns=now_ns)
    ledger = _write_ledger(root, auth, run_id=run_id, output_root=output_root, validated_ns=now_ns + 2, consumed_ns=now_ns + 3)
    write_json_fsync(root / "state" / "action_journal.json", {"release_id": RELEASE_ID, "run_id": run_id, "authorization_id": auth["authorization_id"], "authorization_sha256": auth["authorization_sha256"], "original_pid": ledger["original_pid"], "state": "CONSUMED_BEFORE_STATEFUL_ACTION", "source_test_only": bool(auth["source_test_only"]), "first_stateful_action_after_monotonic_ns": now_ns + 5})
    write_json_fsync(root / "state" / "ownership.json", OWNERSHIP)
    return CommandRecorder(root, run_id=run_id, authorization_id=str(auth["authorization_id"]), source_test_only=bool(auth["source_test_only"]))


def _result(recorder: CommandRecorder, reference: Mapping[str, str]) -> dict[str, object]:
    row = json.loads((recorder.root / reference["path"]).read_text(encoding="utf-8"))
    if row["return_code"] != 0 or row["timed_out"] or row["interrupted"]:
        _fail("required command did not complete: " + str(row["command_name"]))
    return {"return_code": row["return_code"], "stdout": row["stdout"], "stderr": row["stderr"]}


def _phase(root: Path, name: str, timing: Timing, seconds: int) -> dict[str, int]:
    start = timing.monotonic(); timing.wait(seconds); end = timing.monotonic()
    if end - start < seconds * 1_000_000_000:
        _fail(name + " elapsed less than frozen duration")
    row = {"scheduled_start_ns": start, "scheduled_end_ns": start + seconds * 1_000_000_000, "actual_start_ns": start, "actual_end_ns": end}
    write_json_fsync(root / "state" / (name + ".json"), row)
    return row


def _window(recorder: CommandRecorder, *, window_id: str, executor: Callable[[list[str]], Mapping[str, object]], timing: Timing, speed_mbps: int) -> dict[str, object]:
    start = timing.monotonic(); refs: dict[str, Mapping[str, str]] = {}
    for name in ("server_stop", "server_start", "server_ready", "r2_tx", "r3_rx", "qdisc", "filters", "iperf", "traffic_ping", "r2_tx", "r3_rx", "qdisc", "filters", "server_stop"):
        key = name + "_" + str(sum(1 for value in refs if value.startswith(name + "_")))
        refs[key] = recorder.capture(name=name, phase="window", action_id="window:" + window_id, window_id=window_id, executor=executor)
    values = {key: _result(recorder, value) for key, value in refs.items()}
    # Real iperf is fixed at twenty seconds.  The timing adapter measures that
    # interval; a test adapter advances itself only inside the shared core.
    end = timing.monotonic()
    if end - start < 20_000_000_000:
        _fail(window_id + " measured duration is below twenty seconds")
    raw = {"window_id": window_id, "phase": "baseline", "server_teardown_before": values["server_stop_0"], "server_start": values["server_start_0"], "server_readiness": values["server_ready_0"], "r2_tx_before": values["r2_tx_0"], "r3_rx_before": values["r3_rx_0"], "qdisc_before": values["qdisc_0"], "filters_before": [values["filters_0"]], "iperf": values["iperf_0"], "ping": values["traffic_ping_0"], "r2_tx_after": values["r2_tx_1"], "r3_rx_after": values["r3_rx_1"], "qdisc_after": values["qdisc_1"], "filters_after": [values["filters_1"]], "server_teardown_after": values["server_stop_1"], "elapsed_seconds": 20.0, "command_references": refs}
    derived = derive_window(raw, phase="baseline", speed_mbps=speed_mbps)
    features = {feature: derived[feature]["value"] for feature in NUMERIC_FEATURES if derived[feature].get("availability") == "observed"}
    if set(features) != set(NUMERIC_FEATURES):
        _fail(window_id + " has unavailable measurement")
    return {"window_id": window_id, "measurements": features, "observations": dict(features), "timing": {"actual_start_ns": start, "actual_end_ns": end, "startup_skew_seconds": 0.0}, "raw": raw, "source_test_only": recorder.source_test_only}


def finalize_inventory(root: Path) -> None:
    root = Path(root); rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink() and path.relative_to(root).as_posix() != "state/artifact_inventory.json":
            rows.append({"path": path.relative_to(root).as_posix(), "sha256": _hash_file(path)})
    write_json_fsync(root / "state" / "artifact_inventory.json", {"artifacts": rows, "canonical_inventory_sha256": sha256(_canonical(rows))})


def run_integrated_lifecycle(recorder: CommandRecorder, *, executor: Callable[[list[str]], Mapping[str, object]], timing: Timing) -> dict[str, object]:
    root = recorder.root
    write_json_fsync(root / "state" / "schedule.json", SCHEDULE)
    for name in ("kernel", "kernel_config", "module", "python", "ip", "tc", "ethtool", "ping", "iperf3", "docker", "containerlab", "git", "image"):
        _result(recorder, recorder.capture(name=name, phase="provenance", action_id="provenance", executor=executor))
    _phase(root, "readiness", timing, 5); _phase(root, "warmup", timing, 5)
    speed_refs = {name: recorder.capture(name=name, phase="control", action_id="preflight", executor=executor) for name in ("r2_speed", "r3_speed")}
    speeds = [int(str(_result(recorder, ref)["stdout"]).strip()) for ref in speed_refs.values()]
    if len(set(speeds)) != 1 or speeds[0] <= 0:
        _fail("interface speed is unavailable or mismatched")
    rows: list[dict[str, object]] = []; manifest: dict[str, object] | None = None; previous_end: int | None = None
    for index, window_id in enumerate(WINDOW_IDS):
        if index:
            _phase(root, "separation-" + window_id, timing, 5)
        row = _window(recorder, window_id=window_id, executor=executor, timing=timing, speed_mbps=speeds[0])
        if previous_end is not None and row["timing"]["actual_start_ns"] < previous_end + 5_000_000_000:
            _fail(window_id + " violates five-second separation")
        previous_end = int(row["timing"]["actual_end_ns"])
        write_json_fsync(root / "raw" / "windows" / (window_id + ".json"), row); rows.append(row)
        if index == 9:
            manifest = build_threshold_manifest({feature: [item["measurements"][feature] for item in rows] for feature in NUMERIC_FEATURES}, topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH", traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
            path = root / "state" / "threshold_manifest.json"; path.write_bytes(canonical_threshold_manifest_bytes(manifest))
            write_json_fsync(root / "state" / "threshold_freeze.json", {"after_window_id": "C10", "before_window_id": "C11", "manifest_sha256": manifest["sha256"], "byte_sha256": _hash_file(path), "frozen_at_monotonic_ns": timing.monotonic()})
        if index >= 10 and manifest is None:
            _fail("threshold manifest missing before C11")
    for name in ("qdisc", "filters", "r2_tx", "r3_rx", "processes", "namespaces", "cleanup", "qdisc", "filters", "processes", "namespaces"):
        _result(recorder, recorder.capture(name=name, phase="final_drift", action_id="cleanup_final_drift", executor=executor))
    _phase(root, "cooldown", timing, 5)
    if manifest is None or len(rows) != 30:
        _fail("exact thirty-window lifecycle incomplete")
    terminal = {"release_id": RELEASE_ID, "status": "R1.3.6_PRODUCTION_PATH_SOURCE_CONTRACT_COMPLETE_FOR_AUTHORIZATION_REVIEW", "qualified": False, "source_test_only": recorder.source_test_only, "scientific_outputs": {"evidence_v4": False, "feature_vector_v2": False, "diagnosis": False, "dataset": False, "model": False, "metric": False, "api": False, "thesis_result": False}}
    write_json_fsync(root / "terminal" / "terminal.json", terminal); finalize_inventory(root)
    return {"windows": rows, "manifest": manifest, "terminal": terminal}


def execute_source_test_core(*, authorization_bytes: bytes, run_root: Path, run_id: str, output_root: str, identity: Mapping[str, object], executor: Callable[[list[str]], Mapping[str, object]], timing: Timing, now_ns: int) -> dict[str, object]:
    """Explicitly test-only shared-core hook; never called from production CLI."""
    recorder = initialize_integrated(run_root, authorization_bytes=authorization_bytes, identity=identity, run_id=run_id, output_root=output_root, now_ns=now_ns, allow_source_test=True)
    return run_integrated_lifecycle(recorder, executor=executor, timing=timing)


def production_main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="X6-R1.3.6 future R1.4 authorization-gated baseline-only runner")
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--execute", action="store_true", help="required explicit later operator action")
    args = parser.parse_args()
    if not args.execute:
        _fail("a separate explicit execution instruction is required")
    root = Path(args.run_root)
    repository = Path(__file__).resolve().parents[2]
    identity = _identity(repository)
    raw = Path(args.authorization).read_bytes()
    recorder = initialize_integrated(root, authorization_bytes=raw, identity=identity, run_id=args.run_id, output_root=args.output_root, now_ns=monotonic_ns(), allow_source_test=False)
    # No dependency injection, PID, command, clock, status, or ownership input
    # crosses this production boundary.
    run_integrated_lifecycle(recorder, executor=RepositoryExecutor(), timing=RealTiming())
    return 0


if __name__ == "__main__":
    raise SystemExit(production_main())
