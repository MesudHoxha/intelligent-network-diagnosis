"""Independent reconstruction of successor command observations; never QUALIFIED."""
from __future__ import annotations
import json
import re
from pathlib import Path
from src.collection.x6_performance_collector import validate_speed_pair
from src.collection.x6_r0_3_pre_runtime_validation import NUMERIC_FEATURES, build_threshold_manifest
from src.orchestration.x6_r1_3_8_contract import RELEASE, WINDOW_IDS, canonical, digest, load, require, validate_authorization
from src.orchestration.x6_r1_3_8_durable import records, reservation_path
from src.orchestration.x6_r1_3_8_observations import catalog, controls, host_state, reconstruct_window, success, bootstrap


def verify(root, *, source_identity, simulation=False, permit_interrupted=False):
    root = Path(root)
    auth = load(root / "state/authorization.json")
    consumption = load(root / "state/consumption.json")
    require(consumption == load(reservation_path(root, auth)), "consumption ledger contradiction")
    require(consumption["state"] == "CONSUMED" and consumption["authorization_sha256"] == auth["authorization_sha256"] and consumption["output_root"] == str(root) and consumption["run_id"] == auth["run_id"], "consumption identity")
    validate_authorization(auth, root=root, run_id=auth["run_id"], source_identity=source_identity, now_ns=consumption["consumed"]["monotonic_ns"], simulation=simulation)
    rows = records(root, catalog(), permit_incomplete=permit_interrupted)
    require(all(row["source_test_only"] == simulation and row["intent_at"]["monotonic_ns"] >= consumption["consumed"]["monotonic_ns"] for row in rows), "command before consumption or test identity drift")
    paths = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    require(not any(p.is_symlink() for p in root.rglob("*")), "symlink artifact")
    state_files = {"authorization.json", "consumption.json", "lifecycle.json", "host_before.json", "image.json", "deployment_intent.json", "deployment.json", "threshold_manifest.json", "threshold_freeze.json", "cleanup.json", "recovery.json", "recovery.lock"}
    for name in paths:
        require(bool(re.fullmatch(r"raw/commands/[0-9]{5}\.(intent|result)\.json", name)) or name in {"raw/windows/" + n + ".json" for n in WINDOW_IDS} or name in {"state/" + n for n in state_files} or bool(re.fullmatch(r"state/phases/(readiness|warmup|cooldown|separation-(C[0-9]{2}|H[0-9]{2}))\.json", name)) or name == "terminal/terminal.json", "forbidden or unexpected artifact: " + name)
    def phase(name): return [row for row in rows if row["phase"] == name]
    terminal = load(root / "terminal/terminal.json")
    require(terminal["release_id"] == RELEASE and terminal["qualified"] is False, "terminal scope")
    if permit_interrupted:
        require(terminal["status"] in {"INTERRUPTED", "COLLECTION_UNAVAILABLE", "ENVIRONMENT_INELIGIBLE", "CLEANUP_FAILED"}, "failure terminal")
        return {"terminal": terminal["status"], "qualified": False, "command_count": len(rows)}
    for row in rows: success(row, absent_process=row["name"] == "server_stop")
    deployment = phase("deployment")
    require(len(deployment) == 1 and deployment[0]["name"] == "deploy", "deployment missing or repeated")
    for row in rows:
        if row["argv"][:2] == ["docker", "exec"]:
            require(row["started"]["monotonic_ns"] >= deployment[0]["completed"]["monotonic_ns"], "container operation before deployment")
    provenance = phase("provenance")
    require({r["name"] for r in provenance} == {"kernel", "kernel_config", "module", "module_provenance", "python", "ip", "tc", "ethtool", "docker", "containerlab", "git", "image"}, "incomplete provenance")
    require(all(row["stdout"].strip() for row in provenance), "empty provenance")
    prov = {row["name"]: row for row in provenance}
    require("CONFIG_NET_SCH_NETEM=m" in prov["kernel_config"]["stdout"] or "CONFIG_NET_SCH_NETEM=y" in prov["kernel_config"]["stdout"], "kernel configuration")
    require("sch_netem" in prov["module"]["stdout"] and prov["kernel"]["stdout"].strip() in prov["module_provenance"]["stdout"], "module identity")
    require(prov["git"]["stdout"].splitlines() == [source_identity["git_commit"], source_identity["git_tree"]], "Git observation")
    images = json.loads(prov["image"]["stdout"])
    require(len(images) == 1 and {k: images[0].get(k) for k in ("Id", "RepoDigests")} == auth["runtime_image"] and images[0] == load(root / "state/image.json"), "image observation")
    require(max(r["completed"]["monotonic_ns"] for r in provenance) <= deployment[0]["started"]["monotonic_ns"], "provenance after deployment")
    bootstrap(phase("bootstrap"))
    controls(phase("initial_controls"))
    speed_rows = phase("speed")
    require([row["name"] for row in speed_rows] == ["r2_speed", "r3_speed", "r2_ethtool", "r3_ethtool"], "speed inventory")
    speed = validate_speed_pair(*speed_rows)
    windows = []
    previous = None
    window_rows = [row for row in rows if row["phase"] == "window"]
    require(list(dict.fromkeys(row["window"] for row in window_rows)) == list(WINDOW_IDS), "cohort order/cardinality")
    for window_id in WINDOW_IDS:
        selected = [row for row in window_rows if row["window"] == window_id]
        reconstructed = reconstruct_window(selected, speed)
        summary = load(root / "raw/windows" / (window_id + ".json"))
        require(canonical(summary) == canonical({**reconstructed, "window_id": window_id, "command_orders": [row["order"] for row in selected], "source_test_only": simulation}), "measurement/timing summary contradicts raw observations")
        if previous is not None:
            require(reconstructed["timing"]["start_ns"] >= previous["timing"]["end_ns"] + 5_000_000_000, "window separation")
            require(all(b >= a for a, b in zip(previous["counter_after"], reconstructed["counter_before"])), "inter-window counter reset")
        windows.append(reconstructed); previous = reconstructed
    manifest = build_threshold_manifest({feature: [r["measurements"][feature] for r in windows[:10]] for feature in NUMERIC_FEATURES}, topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH", traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
    require(load(root / "state/threshold_manifest.json") == manifest, "canonical ten-sample threshold drift")
    freeze = load(root / "state/threshold_freeze.json")
    require(freeze["after"] == "C10" and freeze["before"] == "C11" and freeze["sha256"] == digest((root / "state/threshold_manifest.json").read_bytes()), "threshold freeze identity")
    require(windows[9]["timing"]["end_ns"] <= freeze["at"]["monotonic_ns"] <= windows[10]["timing"]["start_ns"], "threshold freeze order")
    for name in ("readiness", "warmup", "cooldown", *("separation-" + n for n in WINDOW_IDS[1:])):
        phase_record = load(root / "state/phases" / (name + ".json"))
        require(phase_record["seconds"] == 5 and phase_record["completed"]["monotonic_ns"] - phase_record["started"]["monotonic_ns"] >= 5_000_000_000, "phase duration")
    readiness = load(root / "state/phases/readiness.json")
    warmup = load(root / "state/phases/warmup.json")
    require(deployment[0]["completed"]["monotonic_ns"] <= readiness["started"]["monotonic_ns"] <= readiness["completed"]["monotonic_ns"] <= warmup["started"]["monotonic_ns"] <= warmup["completed"]["monotonic_ns"] <= windows[0]["timing"]["start_ns"], "readiness/warmup order")
    initial = host_state(phase("host_before"))
    require(initial == load(root / "state/host_before.json") and not initial["containers"], "initial host drift")
    controls(phase("final_controls"))
    cleanups = phase("cleanup")
    require(len(cleanups) == 1 and cleanups[0]["name"] == "cleanup", "cleanup command inventory")
    require(max(row["completed"]["monotonic_ns"] for row in phase("final_controls")) <= cleanups[0]["started"]["monotonic_ns"], "destroy before final controls")
    require(not any(row["argv"][:2] == ["docker", "exec"] and row["started"]["monotonic_ns"] >= cleanups[0]["completed"]["monotonic_ns"] for row in rows), "in-container observation after destruction")
    final_rows = phase("cleanup_after")
    require(len(final_rows) % 5 == 0, "cleanup observation cardinality")
    for offset in range(0, len(final_rows), 5):
        final = host_state(final_rows[offset:offset+5])
        require(not final["containers"] and not any("x6r1" in line for line in final["namespaces"]) and initial["links"] == final["links"] and initial["qdisc"] == final["qdisc"], "post-destruction drift")
    require(cleanups[0]["completed"]["monotonic_ns"] <= load(root / "state/phases/cooldown.json")["started"]["monotonic_ns"], "cooldown before cleanup")
    if terminal["status"] == "SOURCE_CONTRACT_COMPLETE_REPLAY_VERIFIED":
        recovery = load(root / "state/recovery.json")
        require(recovery["original_process"] == consumption["process"] and recovery["original_process"] != recovery["recovery_process"] and recovery["source_test_only"] == simulation, "distinct-process replay identity")
    require(terminal["status"] in {"COLLECTION_COMPLETE_REPLAY_REQUIRED", "SOURCE_CONTRACT_COMPLETE_REPLAY_VERIFIED"}, "completion terminal")
    return {"release_id": RELEASE, "qualified": False, "source_test_only": simulation, "windows": 30, "threshold_sha256": manifest["sha256"], "command_count": len(rows), "status": "SOURCE_CONTRACT_COMPLETE_FOR_REVIEW"}
