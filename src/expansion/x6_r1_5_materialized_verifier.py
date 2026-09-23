"""Independent raw reconstruction for the future-F1 successor."""
from __future__ import annotations

import json
import math
import re
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from src.collection.x6_performance_collector import FEATURES, aggregate_windows, exact_fault_hierarchy, qdisc_dropped, validate_speed_pair
from src.collection.x6_r0_2_measurement_semantics import _REPLY
from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2
from src.expansion.x6_r1_5_evidence import build_f1_artifacts
from src.expansion.x6_r1_performance_rule import diagnose_x6_r1, predicates_from_vector
from src.orchestration.x6_r1_5_contract import FREEZE_RECORD_SHA256, MANIFEST_EMBEDDED_SHA256, PHASE_BY_WINDOW, RELEASE, WINDOW_IDS, accepted_manifest, canonical, canonical_location, digest, load, require, validate_committed_attempt, validate_partial_attempt
from src.orchestration.x6_r1_5_durable import records, reservation_path
from src.orchestration.x6_r1_5_observations import bootstrap, catalog, controls, failed_command_orders, host_state, reconstruct_cleanup_cycles, reconstruct_window, success, validate_owned_cleanup_state

NUMERIC = FEATURES[:5]


def inclusive(row, manifest):
    bounds = {item["feature_id"]: item for item in manifest["features"]}
    for feature in NUMERIC:
        value = Decimal(str(row["measurements"][feature])).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
        require(Decimal(bounds[feature]["lower_threshold"]) <= value <= Decimal(bounds[feature]["upper_threshold"]), "baseline/restoration bound: " + feature)
    require(row["measurements"]["rate_limit_detected"] is False, "rate-limit exclusion")


def _fault_artifacts(root, rows, windows, manifest, *, repository_root):
    """Rebuild every derived F1 artifact from raw fault command observations."""
    fault_windows = windows[10:13]
    wrapped = [
        {name: {"availability": "observed", "value": row["measurements"][name]} for name in FEATURES}
        for row in fault_windows
    ]
    values = aggregate_windows(wrapped)
    fault_rows = [row for row in rows if row.get("window") in WINDOW_IDS[10:13]]
    replies = sorted(
        float(rtt)
        for row in fault_rows
        if row["name"] == "traffic_ping"
        for _, rtt in _REPLY.findall(row["stdout"])
    )
    require(replies, "fault RTT samples absent")
    values["round_trip_latency_ms_p95"] = {
        "availability": "observed",
        "value": replies[math.ceil(.95 * len(replies)) - 1],
    }
    qdisc_rows = [row for row in fault_rows if row["name"] == "qdisc"]
    require(len(qdisc_rows) == 6 and all(exact_fault_hierarchy(row) for row in qdisc_rows), "fault hierarchy evidence")
    deltas = []
    for index in range(0, 6, 2):
        before = qdisc_dropped(qdisc_rows[index], kind="netem", handle="10:")
        after = qdisc_dropped(qdisc_rows[index + 1], kind="netem", handle="10:")
        require(before is not None and after is not None and after >= before, "netem counter continuity")
        deltas.append(after - before)
    lost = round(float(values["packet_loss_ratio"]["value"]) * 150)
    netem = sum(deltas)
    pfifo = int(values["queue_drop_count"]["value"])
    effective = 6 <= lost <= 25 and netem >= 0 and pfifo == 0
    expected_effect = {
        "status": "MUTATION_EFFECTIVE" if effective else "DIAGNOSTIC_NON_AUTHORITATIVE",
        "lost_packet_count": lost,
        "accepted_range": [6, 25],
        "netem_drop_delta": netem,
        "pfifo_drop_delta": pfifo,
        "hierarchy_exact": True,
        "diagnosis_not_used": True,
    }
    require(load(root / "state/fault_effectiveness.json") == expected_effect, "fault effectiveness contradiction")
    require(effective, "fault effectiveness failed")
    raw_files = [root / "raw/windows" / (name + ".json") for name in WINDOW_IDS[10:13]]
    expected_evidence, expected_vector = build_f1_artifacts(
        root, values, raw_files, fault_rows, repository_root=repository_root
    )
    evidence = load(root / "parsed/evidence_v4.json")
    vector = load(root / "parsed/feature_vector_v2.json")
    catalog_value = json.loads((repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json").read_text())
    validate_evidence_v4(evidence, catalog_value, repository_root=repository_root)
    validate_feature_vector_v2(vector, catalog_value, repository_root=repository_root)
    require(canonical(evidence) == canonical(expected_evidence), "Evidence v4 contradicts raw fault observations")
    require(canonical(vector) == canonical(expected_vector), "Feature Vector v2 contradicts raw fault observations")
    expected_predicates = predicates_from_vector(expected_vector, manifest, repository_root=repository_root)
    expected_diagnosis = diagnose_x6_r1(expected_vector, manifest, repository_root=repository_root)
    expected_record = {"rule_id": "R_X6_PERFORMANCE_001", "predicates": expected_predicates, "result": expected_diagnosis}
    require(load(root / "state/diagnosis.json") == expected_record, "diagnosis contradiction")
    require(expected_predicates is not None and all(expected_predicates.values()) and expected_diagnosis["status"] == "diagnosed", "diagnosis reconstruction")
    return expected_effect, expected_diagnosis


def _interrupted_cleanup(root, rows, auth, terminal, recovery):
    """Verify cleanup claims without imposing successful-run deployment cardinality."""
    intent = root / "state/deployment_intent.json"
    cleanup_path = root / "state/cleanup.json"
    cleanup_rows = [row for row in rows if row["phase"] in {"cleanup_before", "cleanup", "cleanup_after"}]
    sessions = recovery.get("sessions", [])
    if not intent.exists():
        require(not cleanup_rows and not cleanup_path.exists(), "cleanup evidence exists without deployment intent")
        require(terminal["status"] == "ENVIRONMENT_INELIGIBLE", "pre-deployment terminal contradiction")
        return "NOT_REQUIRED_BEFORE_DEPLOYMENT_INTENT"
    require((root / "state/host_before.json").is_file(), "cleanup lacks initial host observation")
    deployment = load(root / "state/deployment.json") if (root / "state/deployment.json").exists() else None
    initial_rows = [row for row in rows if row["phase"] == "host_before"]
    initial = host_state(initial_rows)
    require(initial == load(root / "state/host_before.json"), "initial host observation contradiction")
    completed_claim = cleanup_path.exists()
    if sessions and sessions[-1]["status"] == "CLEANUP_COMPLETE":
        require(completed_claim, "recovery claims cleanup without cleanup journal")
    if completed_claim:
        require(all(not row.get("incomplete") for row in cleanup_rows), "cleanup claim uses incomplete observations")
        reconstruct_cleanup_cycles(
            rows,
            initial=initial,
            deployment=deployment,
            journal=load(cleanup_path),
            run_id=auth["run_id"],
            output_root=str(root),
            release_id=RELEASE,
            successful=False,
        )
        if (root / "state/mutation.json").exists():
            mutation = load(root / "state/mutation.json")
            require(mutation["status"] == "RESTORATION_CONFIRMED", "interrupted mutation was not restored")
            controls([row for row in rows if row["phase"] == "restoration_controls"], phase="restored")
        require(not sessions or sessions[-1]["status"] == "CLEANUP_COMPLETE", "recovery terminal contradicts completed cleanup")
        require(terminal["status"] != "CLEANUP_FAILED", "failed terminal claims completed cleanup")
        return "CLEANUP_RECONSTRUCTED"
    require(terminal["status"] == "CLEANUP_FAILED", "interrupted attempt lacks required cleanup evidence")
    require(not sessions or sessions[-1]["status"] == "CLEANUP_FAILED", "cleanup failure session contradiction")
    before = [row for row in cleanup_rows if row["phase"] == "cleanup_before"]
    if before:
        expected = ["host_containers", "host_namespaces", "host_links", "host_qdisc", "host_processes"]
        require([row["name"] for row in before] == expected[:len(before)] and len(before) <= 5, "cleanup failure observation order")
        if len(before) == 5 and all(not row.get("incomplete") and row.get("return_code") == 0 for row in before):
            validate_owned_cleanup_state(host_state(before), deployment, require_complete=False)
    actions = [row for row in cleanup_rows if row["phase"] == "cleanup"]
    require(len(actions) <= 1, "cleanup failure action cardinality")
    if actions:
        action = actions[0]
        require(action["name"] == "cleanup" and (action.get("incomplete") or action.get("return_code") != 0 or action.get("interrupted") or action.get("timed_out")), "successful cleanup action lacks terminal evidence")
    return "CLEANUP_FAILED_NO_SUCCESS_CLAIM"


def verify(root, *, source_identity, simulation=False, permit_interrupted=False):
    root = canonical_location(str(root))
    candidate_paths = [p for p in (root.parent / ".x6-r1-5-consumption").glob("*.json") if not p.name.endswith(".interrupted.json")]
    require(all(p.is_file() and not p.is_symlink() for p in candidate_paths), "unsafe durable reservation")
    matches = [row for row in map(load, candidate_paths) if row.get("output_root") == str(root)]
    require(len(matches) == 1, "missing or ambiguous durable reservation")
    consumption = matches[0]; auth = consumption["authorization"]
    partial = validate_partial_attempt(auth, consumption, root=root, run_id=auth["run_id"], source_identity=source_identity, simulation=simulation)
    if partial is not None:
        require(permit_interrupted, "attempt persistence is incomplete")
        return {"terminal": partial["status"], "qualified": False, "scientific_acceptance": False, "command_count": 0, "authorization_committed": partial["authorization_committed"], "consumption_complete": partial["consumption_complete"]}
    require(consumption == load(reservation_path(root, auth)), "consumption ledger contradiction")
    validate_committed_attempt(auth, consumption, root=root, run_id=auth["run_id"], source_identity=source_identity, simulation=simulation)
    rows = records(root, catalog(), permit_incomplete=permit_interrupted)
    require(all(row["source_test_only"] == simulation for row in rows), "command test identity drift")
    original_boot = consumption["admission"]["observed_after_reservation"]["boot_id"]
    recovery = load(root / "state/recovery.json") if (root / "state/recovery.json").exists() else {"sessions": []}
    sessions = recovery.get("sessions", []); covered = set()
    for index, session in enumerate(sessions, 1):
        require(session["index"] == index and session["first_order"] <= session["last_order"] + 1, "recovery session order")
        require(session["status"] in {"INTERRUPTED", "CLEANUP_COMPLETE", "CLEANUP_FAILED"}, "unterminated recovery session")
        require(session["started"]["boot_id"] == session["completed"]["boot_id"] == session["boot_id"], "recovery boot identity")
        selected = [row for row in rows if session["first_order"] <= row["order"] <= session["last_order"]]
        require([row["order"] for row in selected] == list(range(session["first_order"], session["last_order"] + 1)), "recovery command coverage")
        require(all(row["intent_at"]["boot_id"] == session["boot_id"] and row["phase"] in {"restoration_probe", "restoration", "restoration_controls", "cleanup_before", "cleanup", "cleanup_after"} for row in selected), "recovery scope/boot")
        covered.update(row["order"] for row in selected)
    original = [row for row in rows if row["order"] not in covered]
    require(all(row["intent_at"]["boot_id"] == original_boot and row["intent_at"]["monotonic_ns"] >= consumption["consumed"]["monotonic_ns"] for row in original), "original command timing/boot")
    paths = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()]
    require(not any(p.is_symlink() for p in root.rglob("*")), "symlink artifact")
    state_files = {"authorization.json", "consumption.json", "lifecycle.json", "host_before.json", "image.json", "deployment_intent.json", "deployment.json", "threshold_manifest.json", "threshold_freeze.json", "mutation.json", "fault_effectiveness.json", "diagnosis.json", "restoration.json", "cleanup.json", "recovery.json", "recovery.lock"}
    for name in paths:
        allowed = bool(re.fullmatch(r"raw/commands/[0-9]{5}\.(intent|result)\.json", name)) or name in {"raw/windows/" + n + ".json" for n in WINDOW_IDS} or name in {"state/" + n for n in state_files} or bool(re.fullmatch(r"state/phases/(readiness|warmup|cooldown|separation-(B|F|R)[0-9]{2})\.json", name)) or name in {"terminal/terminal.json", "parsed/evidence_v4.json", "parsed/feature_vector_v2.json"}
        require(allowed, "forbidden or unexpected artifact: " + name)
    def phase(name): return [row for row in rows if row["phase"] == name]
    terminal = load(root / "terminal/terminal.json")
    require(terminal["release_id"] == RELEASE and terminal["qualified"] is False and terminal["scientific_acceptance"] is False, "terminal scope")
    if permit_interrupted:
        require(terminal["status"] in {"INTERRUPTED", "F1_ATTEMPT_FAILED", "ENVIRONMENT_INELIGIBLE", "CLEANUP_FAILED"}, "failure terminal")
        cleanup_status = _interrupted_cleanup(root, rows, auth, terminal, recovery)
        return {"terminal": terminal["status"], "qualified": False, "scientific_acceptance": False, "command_count": len(rows), "cleanup": cleanup_status}
    for row in rows:
        if row["name"] != "server_process_probe": success(row)
    deployment = phase("deployment"); require(len(deployment) == 1 and deployment[0]["name"] == "deploy", "deployment inventory")
    provenance = phase("provenance"); require({r["name"] for r in provenance} == {"kernel", "kernel_config", "module", "module_provenance", "python", "ip", "tc", "ethtool", "docker", "containerlab", "git", "image"}, "provenance inventory")
    require(all(row["stdout"].strip() for row in provenance), "empty provenance")
    prov = {row["name"]: row for row in provenance}
    require(prov["git"]["stdout"].splitlines() == [source_identity["git_commit"], source_identity["git_tree"]], "Git observation")
    require("sch_netem" in prov["module"]["stdout"] and prov["kernel"]["stdout"].strip() in prov["module_provenance"]["stdout"], "module identity")
    images = json.loads(prov["image"]["stdout"]); require(len(images) == 1 and {k: images[0].get(k) for k in ("Id", "RepoDigests")} == auth["runtime_image"] and images[0] == load(root / "state/image.json"), "image observation")
    bootstrap(phase("bootstrap")); controls(phase("initial_controls"), phase="baseline")
    speed_rows = phase("speed"); require([row["name"] for row in speed_rows] == ["r2_speed", "r3_speed", "r2_ethtool", "r3_ethtool"], "speed inventory")
    speed = validate_speed_pair(*speed_rows)
    manifest = accepted_manifest(); require(load(root / "state/threshold_manifest.json") == manifest, "accepted manifest drift")
    freeze = load(root / "state/threshold_freeze.json")
    require(freeze == {"status": "ACCEPTED_SOURCE_MANIFEST_BOUND_BEFORE_MUTATION", "record_sha256": FREEZE_RECORD_SHA256, "embedded_sha256": MANIFEST_EMBEDDED_SHA256, "run_local_sha256": digest((root / "state/threshold_manifest.json").read_bytes()), "runtime_baseline_role": "VALIDATION_ONLY_NEVER_CALIBRATION", "at": freeze["at"]}, "threshold freeze binding")
    mutation_orders = [row["order"] for row in phase("mutation")]; require(len(mutation_orders) == 2, "mutation command inventory")
    require(freeze["at"]["monotonic_ns"] <= min(mutation_orders and [row["started"]["monotonic_ns"] for row in phase("mutation")]), "manifest bound after mutation")
    window_rows = [row for row in rows if row["phase"] == "window"]
    require(list(dict.fromkeys(row["window"] for row in window_rows)) == list(WINDOW_IDS), "window order/cardinality")
    windows = []; previous = None
    for window_id in WINDOW_IDS:
        selected = [row for row in window_rows if row["window"] == window_id]
        reconstructed = reconstruct_window(selected, speed, phase=PHASE_BY_WINDOW[window_id])
        expected = {**reconstructed, "window_id": window_id, "phase": PHASE_BY_WINDOW[window_id], "command_orders": [row["order"] for row in selected], "source_test_only": simulation}
        require(canonical(load(root / "raw/windows" / (window_id + ".json"))) == canonical(expected), "window summary contradiction")
        if previous is not None:
            require(all(b >= a for a, b in zip(previous["counter_after"], reconstructed["counter_before"])), "inter-window counter reset")
        if window_id in WINDOW_IDS[:10] or window_id in WINDOW_IDS[13:]: inclusive(reconstructed, manifest)
        windows.append(reconstructed); previous = reconstructed
    controls(phase("fault_controls"), phase="fault"); controls(phase("restoration_controls"), phase="restored"); controls(phase("final_controls"), phase="restored")
    journal = load(root / "state/mutation.json")
    require(journal["status"] == "RESTORATION_CONFIRMED" and [row["status"] for row in journal["actions"]] == ["COMMAND_ACCEPTED", "COMMAND_ACCEPTED"], "mutation/restoration journal")
    repository_root = Path(__file__).resolve().parents[2]
    effect, expected_diagnosis = _fault_artifacts(root, rows, windows, manifest, repository_root=repository_root)
    require(load(root / "state/restoration.json") == {"status": "RESTORATION_CONFIRMED", "windows": list(WINDOW_IDS[13:]), "manifest_sha256": MANIFEST_EMBEDDED_SHA256}, "restoration evidence")
    for name in ("readiness", "warmup", "cooldown", *("separation-" + n for n in (*WINDOW_IDS[1:10], *WINDOW_IDS[11:13], *WINDOW_IDS[14:]))):
        wait = load(root / "state/phases" / (name + ".json")); require(wait["seconds"] == 5 and wait["completed"]["monotonic_ns"] - wait["started"]["monotonic_ns"] >= 5_000_000_000, "phase wait: " + name)
    initial = host_state(phase("host_before")); require(initial == load(root / "state/host_before.json") and not initial["containers"], "initial host drift")
    cleanups = phase("cleanup"); require(len(cleanups) == 1 and cleanups[0]["name"] == "cleanup", "cleanup inventory")
    reconstruct_cleanup_cycles(rows, initial=initial, deployment=load(root / "state/deployment.json"), journal=load(root / "state/cleanup.json"), run_id=auth["run_id"], output_root=str(root), release_id=RELEASE, successful=True)
    if terminal["status"] == "F1_SOURCE_CONTRACT_COMPLETE_REPLAY_VERIFIED":
        require(sessions and recovery["original_process"] == consumption["process"] and recovery["original_process"] != sessions[-1]["process"], "distinct replay process")
        require(recovery["failed_orders"] == failed_command_orders(rows), "recovery command classification")
    require(terminal["status"] in {"F1_SOURCE_CONTRACT_COMPLETE_REPLAY_REQUIRED", "F1_SOURCE_CONTRACT_COMPLETE_REPLAY_VERIFIED"}, "completion terminal")
    return {"release_id": RELEASE, "qualified": False, "scientific_acceptance": False, "source_test_only": simulation, "windows": len(WINDOW_IDS), "threshold_sha256": manifest["sha256"], "fault_effectiveness": effect["status"], "diagnosis": expected_diagnosis["status"], "restoration": "RESTORATION_CONFIRMED", "command_count": len(rows), "status": "F1_SOURCE_CONTRACT_COMPLETE_FOR_REVIEW"}
