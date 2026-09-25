"""Normal future-F1 successor CLI. Imports never authorize execution."""
from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from src.collection.x6_performance_collector import FEATURES, exact_fault_hierarchy, exact_noqueue, qdisc_dropped, validate_speed_pair
from src.expansion.x6_r1_5_1_evidence import build_f1_artifacts
from src.collection.x6_r0_2_measurement_semantics import _REPLY
from src.expansion.x6_r1_5_1_performance_rule import diagnose_x6_r1, predicates_from_vector
from src.orchestration.x6_r1_5_1_contract import ACCEPTED_IMAGE, MANIFEST_EMBEDDED_SHA256, PHASE_BY_WINDOW, ROOT, RELEASE, WINDOW_IDS, accepted_manifest, canonical, digest, identity, load, require, validate_new_attempt
from src.orchestration.x6_r1_5_1_durable import Recorder, acquire_topology_lock, advance_clock, records, reserve, save, stamp
from src.orchestration.x6_r1_5_1_observations import BOOTSTRAP_NAMES, aggregate_fault_windows, bootstrap, catalog, cleanup_cycle, controls, finite_decimal, host_state, reconstruct_window, server_process_state, success
from src.runtime.subprocesses import run_capture

HOST = ("host_containers", "host_namespaces", "host_links", "host_qdisc", "host_processes")
CONTROLS = ("r2_counter", "r3_counter", "qdisc", "filters_root", "filters_ingress")
NUMERIC = FEATURES[:5]


def capture_group(recorder, names, phase, window=None):
    return [recorder.capture(name, phase, window=window) for name in names]


def phase_wait(root, name, seconds):
    start = stamp()
    if os.environ.get("X6_R1_5_1_CONTROLLED_CLOCK") == "1":
        advance_clock(int(seconds * 1e9))
    else:
        deadline = start["monotonic_ns"] + int(seconds * 1e9)
        while time.monotonic_ns() < deadline:
            time.sleep(min(.1, max(0, (deadline - time.monotonic_ns()) / 1e9)))
    save(root / "state/phases" / (name + ".json"), {"started": start, "completed": stamp(), "seconds": seconds}, exclusive=True)


def teardown(recorder, rows, window_id):
    probes = capture_group(recorder, ("server_container_probe", "server_process_probe"), "window", window_id)
    rows.extend(probes)
    if server_process_state(*probes) == "PRESENT":
        stopped = recorder.capture("server_stop", "window", window=window_id)
        rows.append(stopped)
        success(stopped)
        probes = capture_group(recorder, ("server_container_probe", "server_process_probe"), "window", window_id)
        rows.extend(probes)
        require(server_process_state(*probes) == "ABSENT", "server remains after teardown")


def window(recorder, window_id, speed):
    phase = PHASE_BY_WINDOW[window_id]
    rows = []
    teardown(recorder, rows, window_id)
    row = recorder.capture("server_start", "window", window=window_id); rows.append(row); success(row)
    deadline = time.monotonic_ns() + 5_000_000_000
    while True:
        row = recorder.capture("server_ready", "window", window=window_id); rows.append(row); success(row)
        if row["stdout"].strip(): break
        require(time.monotonic_ns() < deadline, "server readiness timeout")
        time.sleep(.1)
    rows.extend(capture_group(recorder, CONTROLS, "window", window_id)); controls(rows[-5:], phase=phase)
    started = {"event": threading.Event()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        iperf = pool.submit(recorder.capture, "iperf", "window", window=window_id, started_event=started)
        require(started["event"].wait(5), "client did not start")
        target = started["stamp"]["monotonic_ns"] + 5_000_000_000
        def capture_ping():
            if os.environ.get("X6_R1_5_1_CONTROLLED_CLOCK") == "1":
                advance_clock(5_000_000_000)
            else:
                while time.monotonic_ns() < target:
                    time.sleep(min(.01, max(0, (target - time.monotonic_ns()) / 1e9)))
            return recorder.capture("traffic_ping", "window", window=window_id)
        ping = pool.submit(capture_ping)
        rows.extend((iperf.result(), ping.result()))
    rows.extend(capture_group(recorder, CONTROLS, "window", window_id))
    row = recorder.capture("server_output", "window", window=window_id); rows.append(row); success(row)
    teardown(recorder, rows, window_id)
    value = reconstruct_window(rows, speed, phase=phase)
    value.update(window_id=window_id, phase=phase, command_orders=[row["order"] for row in rows], source_test_only=recorder.simulation)
    save(recorder.root / "raw/windows" / (window_id + ".json"), value, exclusive=True)
    return value


def terminal(root, status, detail=""):
    save(root / "terminal/terminal.json", {"release_id": RELEASE, "status": status, "qualified": False, "scientific_acceptance": False, "detail": detail, "at": stamp()})


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
    require(isinstance(images, list) and len(images) == 1 and {k: images[0].get(k) for k in ("Id", "RepoDigests")} == ACCEPTED_IMAGE, "image outside accepted freeze scope")
    auth = load(recorder.root / "state/authorization.json")
    require({k: images[0].get(k) for k in ("Id", "RepoDigests")} == auth["runtime_image"], "runtime image differs from authorization")
    save(recorder.root / "state/image.json", images[0], exclusive=True)
    return before


def cleanup(recorder, before, *, require_complete=False):
    before_rows = capture_group(recorder, HOST, "cleanup_before")
    current = host_state(before_rows)
    deployed_path = recorder.root / "state/deployment.json"
    deployment = load(deployed_path) if deployed_path.exists() else None
    action = None
    if current["containers"]:
        from src.orchestration.x6_r1_5_1_observations import validate_owned_cleanup_state
        validate_owned_cleanup_state(current, deployment, require_complete=require_complete)
        action = recorder.capture("cleanup", "cleanup"); success(action)
    after_rows = capture_group(recorder, HOST, "cleanup_after")
    auth = load(recorder.root / "state/authorization.json")
    path = recorder.root / "state/cleanup.json"
    journal = load(path) if path.exists() else {"release_id": RELEASE, "run_id": auth["run_id"], "output_root": str(recorder.root), "cycles": []}
    require(journal["release_id"] == RELEASE and journal["run_id"] == auth["run_id"] and journal["output_root"] == str(recorder.root), "cleanup journal run identity")
    cycle = cleanup_cycle(before_rows, action, after_rows, initial=before, deployment=deployment, require_complete=require_complete, run_id=auth["run_id"], output_root=str(recorder.root), index=len(journal["cycles"]) + 1)
    journal["cycles"].append(cycle); save(path, journal)


def inclusive(row, manifest):
    bounds = {item["feature_id"]: item for item in manifest["features"]}
    for feature in NUMERIC:
        value = Decimal(str(row["measurements"][feature])).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
        require(Decimal(bounds[feature]["lower_threshold"]) <= value <= Decimal(bounds[feature]["upper_threshold"]), "baseline compatibility failed: " + feature)
    require(row["measurements"]["rate_limit_detected"] is False, "rate-limit exclusion failed")


def persist_manifest(root):
    manifest = accepted_manifest()
    save(root / "state/threshold_manifest.json", manifest, exclusive=True)
    raw = (root / "state/threshold_manifest.json").read_bytes()
    require(digest(canonical(manifest)) == digest(raw) and manifest["sha256"] == MANIFEST_EMBEDDED_SHA256, "accepted manifest serialization")
    save(root / "state/threshold_freeze.json", {"status": "ACCEPTED_SOURCE_MANIFEST_BOUND_BEFORE_MUTATION", "record_sha256": "635d62272c593a6ddf6de490a96e664aa94ce3ec2ea4bba5e44a4396cfb18402", "embedded_sha256": MANIFEST_EMBEDDED_SHA256, "run_local_sha256": digest(raw), "runtime_baseline_role": "VALIDATION_ONLY_NEVER_CALIBRATION", "at": stamp()}, exclusive=True)
    return manifest, raw


def mutate(recorder):
    root = recorder.root
    journal = {"status": "PLANNED", "commands": ["mutation_root", "mutation_child"], "recovery": "mutation_restore", "actions": []}
    save(root / "state/mutation.json", journal, exclusive=True)
    for name in ("mutation_root", "mutation_child"):
        journal["status"] = "ATTEMPTED"; journal["actions"].append({"name": name, "status": "ATTEMPTED", "at": stamp()}); save(root / "state/mutation.json", journal)
        row = recorder.capture(name, "mutation"); success(row)
        journal["actions"][-1].update(status="COMMAND_ACCEPTED", order=row["order"]); save(root / "state/mutation.json", journal)
    fault = controls(capture_group(recorder, CONTROLS, "fault_controls"), phase="fault")
    journal["status"] = "COMMANDS_ACCEPTED_FAULT_CONTROL_OBSERVED"; journal["fault_control_counters"] = fault; save(root / "state/mutation.json", journal)


def restore(recorder):
    journal = load(recorder.root / "state/mutation.json")
    require(journal["status"] in {"ATTEMPTED", "COMMANDS_ACCEPTED_FAULT_CONTROL_OBSERVED", "RESTORATION_CONFIRMED"}, "mutation recovery state")
    if journal["status"] != "RESTORATION_CONFIRMED":
        probe = capture_group(recorder, CONTROLS, "restoration_probe")
        for item in probe: success(item)
        if exact_noqueue(probe[2], probe[3:]):
            restoration_order = None
        else:
            qdiscs = json.loads(probe[2]["stdout"]); filters = [json.loads(item["stdout"]) for item in probe[3:]]
            allowed = isinstance(qdiscs, list) and filters == [[], []] and len(qdiscs) in {1, 2} and qdiscs[0].get("kind") == "netem" and qdiscs[0].get("handle") == "10:"
            if len(qdiscs) == 2:
                allowed = allowed and qdiscs[1].get("kind") == "pfifo" and qdiscs[1].get("handle") == "20:" and qdiscs[1].get("parent") == "10:1"
            require(allowed, "ambiguous or foreign mutation ownership")
            row = recorder.capture("mutation_restore", "restoration"); success(row); restoration_order = row["order"]
        controls(capture_group(recorder, CONTROLS, "restoration_controls"), phase="restored")
        journal["status"] = "RESTORATION_CONFIRMED"; journal["restoration_order"] = restoration_order; journal["restored_at"] = stamp(); save(recorder.root / "state/mutation.json", journal)
    return journal


def _assessment_failpoint(recorder, name):
    if recorder.simulation and os.environ.get("X6_R1_5_1_ASSESSMENT_FAILPOINT") == name:
        raise RuntimeError("synthetic assessment failpoint: " + name)


def _assessment_basis(recorder, fault_windows, manifest, source, all_rows):
    auth = load(recorder.root / "state/authorization.json")
    consumption = load(recorder.root / "state/consumption.json")
    raw = []
    for row in fault_windows:
        path = recorder.root / "raw/windows" / (row["window_id"] + ".json")
        raw.append({"window_id": row["window_id"], "path": str(path.relative_to(recorder.root)), "sha256": digest(path.read_bytes()), "command_orders": row["command_orders"]})
    fault_orders = [row["order"] for row in all_rows if row.get("window") in WINDOW_IDS[10:13]]
    require(fault_orders and fault_orders == list(range(min(fault_orders), max(fault_orders) + 1)), "fault command continuity")
    return {
        "schema_version": 1,
        "release_id": RELEASE,
        "run_id": auth["run_id"],
        "authorization_id": auth["authorization_id"],
        "authorization_sha256": auth["authorization_sha256"],
        "source_identity": source,
        "original_boot_id": consumption["admission"]["observed_after_reservation"]["boot_id"],
        "admission_observation": consumption["admission"]["observed_after_reservation"],
        "consumption_observation": consumption["consumed"],
        "manifest_embedded_sha256": MANIFEST_EMBEDDED_SHA256,
        "manifest_file_sha256": digest((recorder.root / "state/threshold_manifest.json").read_bytes()),
        "fault_windows": raw,
        "fault_command_range": [min(fault_orders), max(fault_orders)],
    }


def fault_outputs(recorder, fault_windows, manifest, source):
    all_rows = records(recorder.root, catalog())
    replies = [rtt for row in all_rows if row.get("window") in WINDOW_IDS[10:13] and row["name"] == "traffic_ping" for _, rtt in _REPLY.findall(row["stdout"])]
    values = aggregate_fault_windows(fault_windows, replies)
    basis = _assessment_basis(recorder, fault_windows, manifest, source, all_rows)
    _assessment_failpoint(recorder, "before_intent")
    intent = {**basis, "status": "FAULT_ASSESSMENT_STARTED", "started_at": stamp()}
    save(recorder.root / "state/fault_assessment_intent.json", intent, exclusive=True)
    _assessment_failpoint(recorder, "after_intent")
    lost = int((finite_decimal(values["packet_loss_ratio"]["value"], "packet_loss_ratio aggregate") * 150).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    qdisc_rows = [row for row in all_rows if row.get("window") in WINDOW_IDS[10:13] and row["name"] == "qdisc"]
    require(len(qdisc_rows) == 6 and all(exact_fault_hierarchy(row) for row in qdisc_rows), "fault hierarchy evidence")
    netem_deltas = []
    for index in range(0, 6, 2):
        before = qdisc_dropped(qdisc_rows[index], kind="netem", handle="10:")
        after = qdisc_dropped(qdisc_rows[index + 1], kind="netem", handle="10:")
        require(before is not None and after is not None and after >= before, "netem counter continuity")
        netem_deltas.append(after - before)
    netem = sum(netem_deltas)
    pfifo = int(values["queue_drop_count"]["value"])
    effective = 6 <= lost <= 25 and netem >= 0 and pfifo == 0
    effect = {"status": "MUTATION_EFFECTIVE" if effective else "DIAGNOSTIC_NON_AUTHORITATIVE", "lost_packet_count": lost, "accepted_range": [6, 25], "netem_drop_delta": netem, "pfifo_drop_delta": pfifo, "hierarchy_exact": True, "diagnosis_not_used": True}
    save(recorder.root / "state/fault_effectiveness.json", effect, exclusive=True)
    _assessment_failpoint(recorder, "after_effectiveness")
    raw_files = [recorder.root / "raw/windows" / (name + ".json") for name in WINDOW_IDS[10:13]]
    fault_records = [row for row in all_rows if row.get("window") in WINDOW_IDS[10:13]]
    evidence, vector = build_f1_artifacts(
        recorder.root, values, raw_files, fault_records, repository_root=ROOT
    )
    evidence_path = recorder.root / "parsed/evidence_v4.json"
    save(evidence_path, evidence, exclusive=True)
    _assessment_failpoint(recorder, "after_evidence")
    require(digest(evidence_path.read_bytes()) == vector["provenance"]["evidence_sha256"], "evidence persistence drift")
    save(recorder.root / "parsed/feature_vector_v2.json", vector, exclusive=True)
    _assessment_failpoint(recorder, "after_vector")
    predicates = predicates_from_vector(vector, manifest, repository_root=ROOT)
    diagnosis = diagnose_x6_r1(vector, manifest, repository_root=ROOT)
    save(recorder.root / "state/diagnosis.json", {"rule_id": "R_X6_PERFORMANCE_001", "predicates": predicates, "result": diagnosis}, exclusive=True)
    _assessment_failpoint(recorder, "after_diagnosis")
    artifacts = {
        "fault_effectiveness": {"path": "state/fault_effectiveness.json", "sha256": digest((recorder.root / "state/fault_effectiveness.json").read_bytes())},
        "evidence_v4": {"path": "parsed/evidence_v4.json", "sha256": digest((recorder.root / "parsed/evidence_v4.json").read_bytes())},
        "feature_vector_v2": {"path": "parsed/feature_vector_v2.json", "sha256": digest((recorder.root / "parsed/feature_vector_v2.json").read_bytes())},
        "diagnosis": {"path": "state/diagnosis.json", "sha256": digest((recorder.root / "state/diagnosis.json").read_bytes())},
    }
    committed = {**basis, "status": "FAULT_ASSESSMENT_COMMITTED", "artifacts": artifacts, "effectiveness_status": effect["status"], "diagnosis_status": diagnosis["status"], "predicates": predicates, "committed_at": stamp()}
    save(recorder.root / "state/fault_assessment.json", committed, exclusive=True)
    _assessment_failpoint(recorder, "after_commit")
    require(effective, "fault effectiveness failed")
    require(diagnosis["status"] in {"diagnosed", "abstained"} and predicates is not None, "fault assessment evidence incomplete")
    return committed


def lifecycle(recorder, source):
    root = recorder.root
    before = preflight(recorder, source)
    manifest, manifest_bytes = persist_manifest(root)
    save(root / "state/deployment_intent.json", {"at": stamp(), "host_before_sha256": digest(canonical(before))}, exclusive=True)
    success(recorder.capture("deploy", "deployment"))
    deployed = host_state(capture_group(recorder, HOST, "deployment_after")); require(len(deployed["containers"]) == 5, "incomplete topology")
    save(root / "state/deployment.json", deployed, exclusive=True)
    for i in range(4): success(recorder.capture("container_tool_" + str(i), "container_provenance"))
    bootstrap(capture_group(recorder, BOOTSTRAP_NAMES, "bootstrap"))
    controls(capture_group(recorder, CONTROLS, "initial_controls"), phase="baseline")
    phase_wait(root, "readiness", 5); phase_wait(root, "warmup", 5)
    speed = validate_speed_pair(*capture_group(recorder, ("r2_speed", "r3_speed", "r2_ethtool", "r3_ethtool"), "speed"))
    windows = []
    for index, window_id in enumerate(WINDOW_IDS[:10]):
        if index: phase_wait(root, "separation-" + window_id, 5)
        require((root / "state/threshold_manifest.json").read_bytes() == manifest_bytes, "accepted manifest replaced")
        row = window(recorder, window_id, speed); inclusive(row, manifest); windows.append(row)
    mutate(recorder)
    fault = []
    for index, window_id in enumerate(WINDOW_IDS[10:13]):
        if index: phase_wait(root, "separation-" + window_id, 5)
        require((root / "state/threshold_manifest.json").read_bytes() == manifest_bytes, "accepted manifest replaced")
        fault.append(window(recorder, window_id, speed))
    assessment = fault_outputs(recorder, fault, manifest, source)
    restore(recorder)
    phase_wait(root, "cooldown", 5)
    restored = []
    for index, window_id in enumerate(WINDOW_IDS[13:]):
        if index: phase_wait(root, "separation-" + window_id, 5)
        row = window(recorder, window_id, speed); inclusive(row, manifest); restored.append(row)
    save(root / "state/restoration.json", {"status": "RESTORATION_CONFIRMED", "windows": list(WINDOW_IDS[13:]), "manifest_sha256": MANIFEST_EMBEDDED_SHA256}, exclusive=True)
    controls(capture_group(recorder, CONTROLS, "final_controls"), phase="restored")
    cleanup(recorder, before, require_complete=True)
    require((root / "state/threshold_manifest.json").read_bytes() == manifest_bytes, "final manifest drift")
    if assessment["diagnosis_status"] == "diagnosed":
        terminal(root, "F1_SOURCE_CONTRACT_COMPLETE_REPLAY_REQUIRED")
    else:
        terminal(root, "F1_DIAGNOSTIC_ABSTENTION_RESTORATION_COMPLETE_REPLAY_REQUIRED", "diagnosis abstained; restoration validation completed")


def assert_external_simulation():
    import shutil
    stub = ROOT / "tests/fixtures/x6_r1_5_1_external_stub.py"
    for executable in {argv[0] for argv, timeout in catalog().values()}:
        resolved = shutil.which(executable)
        require(resolved is not None and Path(resolved).resolve() == stub.resolve(), "source tests require repository simulation stub")
    fixture = Path(os.environ.get("X6_STUB_STATE", "")); require(fixture.is_file() and not fixture.is_symlink(), "source-test external state is missing")


def execute(auth_path, root, run_id, *, simulation=False):
    require(simulation or os.environ.get("X6_R1_5_1_CONTROLLED_CLOCK") != "1", "controlled clock cannot enter production")
    if simulation: assert_external_simulation()
    source = identity(); auth = load(auth_path)
    validate_new_attempt(auth, root=root, run_id=run_id, source_identity=source, observation=stamp(), simulation=simulation)
    if not simulation:
        status = run_capture(["git", "-C", str(ROOT), "status", "--porcelain"], timeout_seconds=30)
        require(status.returncode == 0 and not status.stdout, "production source must be clean")
    topology_lock = acquire_topology_lock()
    try:
        reserve(root, auth, admission_validator=lambda observation: validate_new_attempt(auth, root=root, run_id=run_id, source_identity=source, observation=observation, simulation=simulation))
    except BaseException:
        os.close(topology_lock); raise
    recorder = Recorder(root, catalog(), simulation=simulation)
    previous = {}
    def interrupt(signum, frame): raise KeyboardInterrupt("signal " + str(signum))
    try:
        for signum in (signal.SIGTERM, signal.SIGINT): previous[signum] = signal.signal(signum, interrupt)
        lifecycle(recorder, source)
    except BaseException as error:
        status = "INTERRUPTED" if isinstance(error, KeyboardInterrupt) else "F1_ATTEMPT_FAILED" if (root / "state/deployment_intent.json").exists() else "ENVIRONMENT_INELIGIBLE"
        terminal(root, status, type(error).__name__ + ": " + str(error))
        if (root / "state/mutation.json").exists():
            try: restore(recorder)
            except BaseException: pass
        if (root / "state/deployment_intent.json").exists():
            try: cleanup(recorder, load(root / "state/host_before.json"))
            except BaseException as cleanup_error: terminal(root, "CLEANUP_FAILED", str(cleanup_error))
        raise
    finally:
        for signum, handler in previous.items(): signal.signal(signum, handler)
        os.close(topology_lock)


def main():
    parser = argparse.ArgumentParser(description="Separately authorized future-F1 successor")
    parser.add_argument("--authorization", type=Path, required=True); parser.add_argument("--run-root", type=Path, required=True); parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute", action="store_true"); parser.add_argument("--source-test", action="store_true")
    args = parser.parse_args(); require(args.execute, "separate explicit execution instruction required")
    execute(args.authorization, args.run_root, args.run_id, simulation=args.source_test); return 0


if __name__ == "__main__":
    raise SystemExit(main())
