"""Normal successor CLI. Imports do not authorize or execute an attempt."""
from __future__ import annotations
import argparse
import json
import os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from src.collection.x6_r0_3_pre_runtime_validation import NUMERIC_FEATURES, build_threshold_manifest
from src.collection.x6_performance_collector import validate_speed_pair
from src.orchestration.x6_r1_3_8_contract import ROOT, RELEASE, WINDOW_IDS, Invalid, canonical, digest, identity, load, require, validate_authorization
from src.orchestration.x6_r1_3_8_durable import Recorder, alive, fsync_directory, process_identity, records, reservation_path, reserve, save, stamp, acquire_topology_lock
from src.orchestration.x6_r1_3_8_observations import catalog, controls, host_state, reconstruct_window, success, bootstrap, BOOTSTRAP_NAMES
from src.runtime.subprocesses import run_capture

HOST = ("host_containers", "host_namespaces", "host_links", "host_qdisc", "host_processes")
CONTROLS = ("r2_counter", "r3_counter", "qdisc", "filters_root", "filters_ingress")


def capture_group(recorder, names, phase, window=None):
    return [recorder.capture(name, phase, window=window) for name in names]


def phase_wait(root, name, seconds):
    start = stamp()
    deadline = start["monotonic_ns"] + int(seconds * 1e9)
    while time.monotonic_ns() < deadline:
        time.sleep(min(.1, max(0, (deadline-time.monotonic_ns())/1e9)))
    save(root / "state/phases" / (name + ".json"), {"started": start, "completed": stamp(), "seconds": seconds}, exclusive=True)


def window(recorder, window_id, speed):
    rows = [recorder.capture("server_stop", "window", window=window_id), recorder.capture("server_start", "window", window=window_id)]
    success(rows[0], absent_process=True); success(rows[1])
    deadline = time.monotonic_ns() + 5_000_000_000
    while True:
        row = recorder.capture("server_ready", "window", window=window_id); rows.append(row)
        success(row)
        if row["stdout"].strip(): break
        require(time.monotonic_ns() < deadline, "server readiness timeout")
        time.sleep(.1)
    rows.extend(capture_group(recorder, CONTROLS, "window", window_id)); controls(rows[-5:])
    started = {"event": threading.Event()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        iperf = pool.submit(recorder.capture, "iperf", "window", window=window_id, started_event=started)
        require(started["event"].wait(5), "client did not start")
        target = started["stamp"]["monotonic_ns"] + 5_000_000_000
        while time.monotonic_ns() < target:
            time.sleep(min(.01, max(0, (target-time.monotonic_ns())/1e9)))
        ping = pool.submit(recorder.capture, "traffic_ping", "window", window=window_id)
        rows.extend((iperf.result(), ping.result()))
    rows.extend(capture_group(recorder, CONTROLS, "window", window_id))
    rows.extend(capture_group(recorder, ("server_output", "server_stop"), "window", window_id))
    value = reconstruct_window(rows, speed)
    value.update(window_id=window_id, command_orders=[row["order"] for row in rows], source_test_only=recorder.simulation)
    save(recorder.root / "raw/windows" / (window_id + ".json"), value, exclusive=True)
    return value


def terminal(root, status, detail=""):
    save(root / "terminal/terminal.json", {"release_id": RELEASE, "status": status, "qualified": False, "detail": detail, "at": stamp()})


def preflight(recorder, source):
    before = host_state(capture_group(recorder, HOST, "host_before"))
    require(not before["containers"] and not any("x6r1" in name for name in before["namespaces"]), "pre-existing experiment resources")
    save(recorder.root / "state/host_before.json", before, exclusive=True)
    names = ("kernel", "kernel_config", "module", "module_provenance", "python", "ip", "tc", "ethtool", "docker", "containerlab", "git", "image")
    provenance = {name: success(recorder.capture(name, "provenance")) for name in names}
    require(all(row["stdout"].strip() for row in provenance.values()), "empty provenance")
    require("CONFIG_NET_SCH_NETEM=m" in provenance["kernel_config"]["stdout"] or "CONFIG_NET_SCH_NETEM=y" in provenance["kernel_config"]["stdout"], "kernel prerequisite absent")
    require("sch_netem" in provenance["module"]["stdout"] and provenance["kernel"]["stdout"].strip() in provenance["module_provenance"]["stdout"], "module provenance mismatch")
    require(provenance["git"]["stdout"].splitlines() == [source["git_commit"], source["git_tree"]], "runtime Git provenance")
    images = json.loads(provenance["image"]["stdout"])
    require(isinstance(images, list) and len(images) == 1 and isinstance(images[0].get("Id"), str) and images[0]["Id"].startswith("sha256:") and "ind-linux:0.1" in images[0].get("RepoTags", []), "image provenance")
    auth = load(recorder.root / "state/authorization.json")
    require({k: images[0].get(k) for k in ("Id", "RepoDigests")} == auth["runtime_image"], "runtime image differs from authorization")
    save(recorder.root / "state/image.json", images[0], exclusive=True)
    return before


def cleanup(recorder, before):
    current = host_state(capture_group(recorder, HOST, "cleanup_before"))
    if current["containers"]:
        require(all(row.get("Image") == "ind-linux:0.1" and "containerlab=x6r1" in row.get("Labels", "") for row in current["containers"]), "foreign container ownership")
        deployed_path = recorder.root / "state/deployment.json"
        if deployed_path.exists():
            owned_ids = {row["ID"] for row in load(deployed_path)["containers"]}
            require(all(row["ID"] in owned_ids for row in current["containers"]), "container replaced after owned deployment")
        # Only the accepted topology's named resources can be destroyed.
        success(recorder.capture("cleanup", "cleanup"))
    final = host_state(capture_group(recorder, HOST, "cleanup_after"))
    require(not final["containers"] and not any("x6r1" in name for name in final["namespaces"]), "residual experiment resources")
    require(final["links"] == before["links"] and final["qdisc"] == before["qdisc"], "host networking drift")
    save(recorder.root / "state/cleanup.json", {"before": before, "after": final, "at": stamp()})


def lifecycle(recorder, source):
    root = recorder.root
    before = preflight(recorder, source)
    save(root / "state/deployment_intent.json", {"at": stamp(), "host_before_sha256": digest(canonical(before))}, exclusive=True)
    success(recorder.capture("deploy", "deployment"))
    deployed = host_state(capture_group(recorder, HOST, "deployment_after"))
    require(len(deployed["containers"]) == 5, "incomplete topology")
    save(root / "state/deployment.json", deployed, exclusive=True)
    for i in range(4): success(recorder.capture("container_tool_" + str(i), "container_provenance"))
    bootstrap(capture_group(recorder, BOOTSTRAP_NAMES, "bootstrap"))
    controls(capture_group(recorder, CONTROLS, "initial_controls"))
    phase_wait(root, "readiness", 5)
    phase_wait(root, "warmup", 5)
    speed_rows = capture_group(recorder, ("r2_speed", "r3_speed", "r2_ethtool", "r3_ethtool"), "speed")
    speed = validate_speed_pair(*speed_rows)
    values = []; manifest_bytes = None
    for index, window_id in enumerate(WINDOW_IDS):
        if index:
            phase_wait(root, "separation-" + window_id, 5)
        if index >= 10:
            require((root / "state/threshold_manifest.json").read_bytes() == manifest_bytes, "frozen threshold replaced")
        row = window(recorder, window_id, speed); values.append(row)
        if index == 9:
            manifest = build_threshold_manifest({feature: [r["measurements"][feature] for r in values] for feature in NUMERIC_FEATURES}, topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH", traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
            save(root / "state/threshold_manifest.json", manifest, exclusive=True)
            manifest_bytes = (root / "state/threshold_manifest.json").read_bytes()
            save(root / "state/threshold_freeze.json", {"at": stamp(), "after": "C10", "before": "C11", "sha256": digest(manifest_bytes)}, exclusive=True)
    require((root / "state/threshold_manifest.json").read_bytes() == manifest_bytes, "final manifest drift")
    controls(capture_group(recorder, CONTROLS, "final_controls"))
    cleanup(recorder, before)
    phase_wait(root, "cooldown", 5)
    terminal(root, "COLLECTION_COMPLETE_REPLAY_REQUIRED")


def assert_external_simulation():
    import shutil
    stub = ROOT / "tests/fixtures/x6_r1_3_8_external_stub.py"
    for executable in {argv[0] for argv, timeout in catalog().values()}:
        resolved = shutil.which(executable)
        require(resolved is not None and Path(resolved).resolve() == stub.resolve(), "source tests require every external executable to resolve to the repository simulation stub")
    fixture = Path(os.environ.get("X6_STUB_STATE", ""))
    require(fixture.is_file() and not fixture.is_symlink(), "source-test external state is missing")

def execute(auth_path, root, run_id, *, simulation=False):
    if simulation: assert_external_simulation()
    source = identity()
    auth = load(auth_path)
    validate_authorization(auth, root=root, run_id=run_id, source_identity=source, now_ns=time.monotonic_ns(), simulation=simulation)
    if not simulation:
        status = run_capture(["git", "-C", str(ROOT), "status", "--porcelain"], timeout_seconds=30)
        require(status.returncode == 0, "production source status failed: " + status.stderr)
        require(not status.stdout, "production source must be clean")
    topology_lock = acquire_topology_lock()
    try:
        reserve(root, auth)
    except BaseException:
        os.close(topology_lock)
        raise
    recorder = Recorder(root, catalog(), simulation=simulation)
    previous_handlers = {}
    def interrupt(signum, frame): raise KeyboardInterrupt("signal " + str(signum))
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.signal(signum, interrupt)
        lifecycle(recorder, source)
    except BaseException as error:
        status = "INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "COLLECTION_UNAVAILABLE" if (root / "state/deployment_intent.json").exists() else "ENVIRONMENT_INELIGIBLE"
        terminal(root, status, type(error).__name__ + ": " + str(error))
        if (root / "state/deployment_intent.json").exists():
            try: cleanup(recorder, load(root / "state/host_before.json"))
            except BaseException as cleanup_error: terminal(root, "CLEANUP_FAILED", str(cleanup_error))
        raise
    finally:
        for signum, handler in previous_handlers.items(): signal.signal(signum, handler)
        os.close(topology_lock)


def main():
    parser = argparse.ArgumentParser(description="R1.3.8 separately authorized baseline-only successor")
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-test", action="store_true", help="accept only explicitly synthetic authorization; external executables must be isolated by the test harness")
    args = parser.parse_args()
    require(args.execute, "separate explicit execution instruction required")
    execute(args.authorization, args.run_root, args.run_id, simulation=args.source_test)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
