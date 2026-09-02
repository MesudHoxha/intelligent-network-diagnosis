"""Synthetic source tests for X6-R1.3.2; fixtures are never runtime evidence."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

import src.expansion.x6_r1_3_2_baseline_execution_provenance_correction as contract
from src.collection.x6_r0_3_pre_runtime_validation import canonical_threshold_manifest_bytes


ROOT = Path(__file__).resolve().parents[2]
FEATURES = {
    "packet_loss_ratio": "0.000000", "round_trip_latency_ms_p95": "1.000000", "throughput_mbps": "1.000000",
    "interface_utilization_ratio": "0.100000", "queue_drop_count": "0.000000",
}
IDENTITY = {
    "git_commit": "a" * 40, "git_tree": "b" * 40, "topology_path": "topologies/x6_r1.clab.yml",
    "topology_sha256": "c" * 64, "runtime_image_tag": "local/x6-r1:fixed",
    "runtime_image_id": "sha256:" + "d" * 64, "runtime_image_repo_digest": "local/x6-r1@sha256:" + "e" * 64,
}


def _write(root: Path, relative: str, value: object) -> dict[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode())
    return {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _command(field_id: str) -> list[str]:
    commands = {
        "kernel_identity": ["uname", "-r"], "kernel_netem_config": ["zgrep", "CONFIG_NET_SCH_NETEM", "/proc/config.gz"],
        "sch_netem_loaded_module": ["lsmod"], "sch_netem_module_provenance": ["modinfo", "sch_netem"],
        "python_executable_version": ["python3", "--version"], "ip_executable_version": ["ip", "-V"],
        "tc_executable_version": ["tc", "-V"], "ethtool_executable_version": ["ethtool", "--version"],
        "ping_executable_version": ["ping", "-V"], "iperf3_executable_version": ["iperf3", "--version"],
        "docker_version": ["docker", "version", "--format", "json"], "containerlab_version": ["containerlab", "version"],
        "runtime_image_identity": ["docker", "image", "inspect", "local/x6-r1:fixed"],
        "topology_identity": ["sha256sum", "topologies/x6_r1.clab.yml"],
        "git_commit_source_tree_identity": ["git", "rev-parse", "HEAD", "HEAD^{tree}"],
    }
    return commands[field_id]


def _provenance(root: Path) -> dict[str, object]:
    records = []
    for index, field_id in enumerate(contract.REQUIRED_PROVENANCE_FIELDS):
        value: object = {"identity": field_id, "version": "verified-v1"}
        if field_id == "runtime_image_identity": value = {"tag": IDENTITY["runtime_image_tag"], "id": IDENTITY["runtime_image_id"], "digest": IDENTITY["runtime_image_repo_digest"]}
        if field_id == "topology_identity": value = {"path": IDENTITY["topology_path"], "sha256": IDENTITY["topology_sha256"]}
        if field_id == "git_commit_source_tree_identity": value = {"commit": IDENTITY["git_commit"], "tree": IDENTITY["git_tree"]}
        command = _command(field_id)
        raw = _write(root, f"raw/provenance/{field_id}.json", {"field_id": field_id, "value": value, "command": command, "return_code": 0, "stdout": field_id + " output", "stderr": "", "captured_at_utc": "2026-09-01T00:00:00Z", "monotonic_ns": index})
        record = {"command": command, "shell": False, "return_code": 0, "stdout": field_id + " output", "stderr": "", "captured_at_utc": "2026-09-01T00:00:00Z", "monotonic_ns": index, "raw_artifact": raw}
        records.append({"field_id": field_id, "availability": "observed", "value": value, "raw_artifact": raw, "command_record": record})
    return {"schema_version": 1, "release_id": contract.RELEASE_ID, "records": records, "source_identity": dict(IDENTITY)}


def _phase(start: int, seconds: int) -> dict[str, int]:
    return {"scheduled_start_ns": start, "scheduled_end_ns": start + seconds * contract.NS_PER_SECOND, "actual_start_ns": start, "actual_end_ns": start + seconds * contract.NS_PER_SECOND}


def _manifest(root: Path, *, status: str = "QUALIFIED") -> dict[str, object]:
    schedule = {"readiness": _phase(0, 5), "warmup": _phase(5 * contract.NS_PER_SECOND, 5), "cooldown": {}}
    windows = []
    start = 10 * contract.NS_PER_SECOND
    for window_id in contract.COHORT_IDS:
        raw = _write(root, f"raw/windows/{window_id}.json", {"window_id": window_id, "canonical_features": dict(FEATURES), "rate_limit_detected": False})
        windows.append({"window_id": window_id, **_phase(start, 20), "duration_seconds": "20.000000", "startup_skew_seconds": "0.000000", "mutation": "NONE", "retry_of": None, "replacement_for": None, "consumed_pilot_input": False, "rate_limit_detected": False, "measurements": dict(FEATURES), "observations": dict(FEATURES), "raw_artifact": raw})
        start += 25 * contract.NS_PER_SECOND
    schedule["cooldown"] = _phase(start, 5)
    threshold = contract.build_threshold_manifest({feature: [FEATURES[feature]] * 10 for feature in contract.NUMERIC_FEATURES}, topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH", traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
    freeze = {"after_window_id": "C10", "before_window_id": "C11", "manifest_sha256": threshold["sha256"], "byte_sha256": hashlib.sha256(canonical_threshold_manifest_bytes(threshold)).hexdigest(), "frozen_at_monotonic_ns": windows[9]["actual_end_ns"]}
    normalized = [{"phase": {key: row[key] for key in ("scheduled_start_ns", "scheduled_end_ns", "actual_start_ns", "actual_end_ns")}, "features": row["measurements"], "raw_artifact": row["raw_artifact"]} for row in windows]
    calibration = contract._cohort_result(normalized[10:20], contract.CALIBRATION_IDS, threshold)
    holdout = contract._cohort_result(normalized[20:], contract.HOLDOUT_IDS, threshold)
    schedule_hash = hashlib.sha256((json.dumps({"schedule": schedule, "windows": [row["phase"] for row in normalized]}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()).hexdigest()
    controls = {
        "timing": {"control_id": "timing", "status": "TIMING_SCHEDULE_CAPTURED", "schedule_sha256": schedule_hash, "window_ids": list(contract.COHORT_IDS)},
        "threshold_freeze": {"control_id": "threshold_freeze", "status": "FROZEN_C10_BEFORE_C11", "threshold_sha256": threshold["sha256"], "frozen_at_monotonic_ns": freeze["frozen_at_monotonic_ns"]},
        "qdisc_filter_state": {"control_id": "qdisc_filter_state", "status": "EXACT_NOQUEUE_0_NO_FILTERS", "window_ids": list(contract.COHORT_IDS)},
        "counter_continuity": {"control_id": "counter_continuity", "status": "COUNTER_CONTINUITY_CONFIRMED", "window_ids": list(contract.COHORT_IDS)},
        "cleanup": {"control_id": "cleanup", "status": "CLEANUP_CONFIRMED_NO_CONTAINERS_NAMESPACES_OR_IPERF", "lingering_iperf_processes": []},
        "replay": {"control_id": "replay", "status": "VERIFY_ONLY_REPLAY_CONFIRMED"},
    }
    control_rows = [{"control_id": control_id, "raw_artifact": _write(root, f"raw/controls/{control_id}.json", payload)} for control_id, payload in controls.items()]
    return {"schema_version": 1, "release_id": contract.RELEASE_ID, "execution_kind": "BASELINE_ONLY_VERIFY_ONLY_NO_MUTATION", "input_origin": "FUTURE_BASELINE_ONLY_QUALIFICATION", "schedule": schedule, "windows": windows, "threshold_manifest": threshold, "threshold_freeze": freeze, "calibration_validation": calibration, "holdout": holdout, "provenance": _provenance(root), "control_artifacts": control_rows, "terminal": {"status": status, "baseline_after": "NOT_APPLICABLE_NO_MUTATION", "replay": "VERIFY_ONLY_REPLAY_REQUIRED", "cleanup": "REQUIRED_BEFORE_TERMINAL", "all_windows_complete": True, "provenance_valid": True, "timing_valid": True, "source_identity_valid": True, "qdisc_filter_state_valid": True, "counter_continuity_valid": True, "cleanup_valid": True, "replay_valid": True}, "authorization": "0/10_FALSE"}


def _verify(value: dict[str, object], root: Path) -> dict[str, object]:
    return contract.verify_materialized_baseline_execution_manifest(value, repository_root=ROOT, run_root=root, expected_source_identity=IDENTITY)


def test_materialized_complete_physical_schedule_can_qualify(tmp_path: Path) -> None:
    value = _manifest(tmp_path)
    assert _verify(value, tmp_path)["status"] == "QUALIFIED"
    with pytest.raises(contract.X6R132ContractError, match="structural validation"):
        contract.validate_baseline_execution_manifest_structure(value, repository_root=ROOT)


@pytest.mark.parametrize("mutation", ["overlap", "spacing", "c10_c11", "c20_h01", "readiness", "warmup", "cooldown", "negative_skew", "large_skew"])
def test_physical_schedule_adversaries_fail_closed(tmp_path: Path, mutation: str) -> None:
    value = _manifest(tmp_path)
    if mutation == "overlap": value["windows"][1]["actual_start_ns"] = value["windows"][0]["actual_end_ns"] - 1
    elif mutation == "spacing": value["windows"][1]["scheduled_start_ns"] -= contract.NS_PER_SECOND
    elif mutation == "c10_c11": value["windows"][10]["scheduled_start_ns"] -= contract.NS_PER_SECOND
    elif mutation == "c20_h01": value["windows"][20]["scheduled_start_ns"] -= contract.NS_PER_SECOND
    elif mutation == "readiness": value["schedule"].pop("readiness")
    elif mutation == "warmup": value["schedule"]["warmup"]["actual_end_ns"] += contract.NS_PER_SECOND
    elif mutation == "cooldown": value["schedule"]["cooldown"]["scheduled_start_ns"] -= contract.NS_PER_SECOND
    elif mutation == "negative_skew": value["windows"][0]["startup_skew_seconds"] = "-0.100000"
    else: value["windows"][0]["startup_skew_seconds"] = "0.251000"
    with pytest.raises(contract.X6R132ContractError): _verify(value, tmp_path)


@pytest.mark.parametrize("mutation", ["contradictory", "c01_rate_limit", "retry", "replacement", "missing", "duplicate", "reordered", "pilot"])
def test_window_cohort_and_representation_adversaries_fail_closed(tmp_path: Path, mutation: str) -> None:
    value = _manifest(tmp_path)
    if mutation == "contradictory": value["windows"][10]["measurements"]["throughput_mbps"] = "1.010000"
    elif mutation == "c01_rate_limit": value["windows"][0]["rate_limit_detected"] = True
    elif mutation == "retry": value["windows"][1]["retry_of"] = "C01"
    elif mutation == "replacement": value["windows"][1]["replacement_for"] = "C01"
    elif mutation == "missing": value["windows"].pop()
    elif mutation == "duplicate": value["windows"][1]["window_id"] = "C01"
    elif mutation == "reordered": value["windows"][1], value["windows"][2] = value["windows"][2], value["windows"][1]
    else: value["windows"][0]["consumed_pilot_input"] = True
    with pytest.raises(contract.X6R132ContractError): _verify(value, tmp_path)


def test_later_cohort_values_never_change_the_c01_to_c10_manifest(tmp_path: Path) -> None:
    value = _manifest(tmp_path, status="INCONCLUSIVE")
    frozen = value["threshold_manifest"]["sha256"]
    value["windows"][10]["measurements"]["throughput_mbps"] = "1.010000"
    value["windows"][10]["observations"]["throughput_mbps"] = "1.010000"
    assert contract._threshold_inputs([{"features": row["measurements"]} for row in value["windows"]]) == {feature: [FEATURES[feature]] * 10 for feature in contract.NUMERIC_FEATURES}
    assert value["threshold_manifest"]["sha256"] == frozen


@pytest.mark.parametrize("mutation", ["bad_sha", "short_sha", "missing_path", "traversal", "hash_mismatch", "empty_identity", "wrong_source", "wrong_topology", "wrong_image", "wrapped_sudo", "wrapped_modprobe", "non_allowlisted", "shell_true"])
def test_materialized_provenance_and_command_policy_fail_closed(tmp_path: Path, mutation: str) -> None:
    value = _manifest(tmp_path)
    record = value["provenance"]["records"][0]
    if mutation == "bad_sha": record["raw_artifact"]["sha256"] = "z" * 64; record["command_record"]["raw_artifact"] = record["raw_artifact"]
    elif mutation == "short_sha": record["raw_artifact"]["sha256"] = "a" * 63; record["command_record"]["raw_artifact"] = record["raw_artifact"]
    elif mutation == "missing_path": record["raw_artifact"]["path"] = "raw/provenance/missing.json"; record["command_record"]["raw_artifact"] = record["raw_artifact"]
    elif mutation == "traversal": record["raw_artifact"]["path"] = "../outside.json"; record["command_record"]["raw_artifact"] = record["raw_artifact"]
    elif mutation == "hash_mismatch": (tmp_path / record["raw_artifact"]["path"]).write_text("{}")
    elif mutation == "empty_identity": value["provenance"]["source_identity"]["runtime_image_tag"] = "unknown"
    elif mutation == "wrong_source": value["provenance"]["source_identity"]["git_commit"] = "f" * 40
    elif mutation == "wrong_topology": value["provenance"]["source_identity"]["topology_sha256"] = "f" * 64
    elif mutation == "wrong_image": value["provenance"]["source_identity"]["runtime_image_id"] = "sha256:" + "f" * 64
    elif mutation == "wrapped_sudo": record["command_record"]["command"] = ["bash", "-c", "sudo uname -r"]
    elif mutation == "wrapped_modprobe": record["command_record"]["command"] = ["bash", "-c", "modprobe sch_netem"]
    elif mutation == "non_allowlisted": record["command_record"]["command"] = ["echo", "kernel"]
    else: record["command_record"]["shell"] = True
    with pytest.raises(contract.X6R132ContractError): _verify(value, tmp_path)


def test_terminal_controls_and_false_qualified_are_materially_derived(tmp_path: Path) -> None:
    value = _manifest(tmp_path)
    value["terminal"]["timing_valid"] = False
    with pytest.raises(contract.X6R132ContractError, match="terminal summary"):
        _verify(value, tmp_path)
    value = _manifest(tmp_path)
    value["windows"][10]["measurements"]["throughput_mbps"] = "2.000000"
    value["windows"][10]["observations"]["throughput_mbps"] = "2.000000"
    raw = _write(tmp_path, "raw/windows/C11.json", {"window_id": "C11", "canonical_features": value["windows"][10]["measurements"], "rate_limit_detected": False})
    value["windows"][10]["raw_artifact"] = raw
    value["calibration_validation"] = contract._cohort_result([{"features": row["measurements"]} for row in value["windows"][10:20]], contract.CALIBRATION_IDS, value["threshold_manifest"])
    with pytest.raises(contract.X6R132ContractError, match="false QUALIFIED"):
        _verify(value, tmp_path)


def test_false_but_rehashed_threshold_manifest_is_rejected(tmp_path: Path) -> None:
    value = _manifest(tmp_path)
    value["threshold_manifest"]["features"][0]["upper_threshold"] = "0.999999"
    unsigned = dict(value["threshold_manifest"]); unsigned.pop("sha256")
    value["threshold_manifest"]["sha256"] = hashlib.sha256(canonical_threshold_manifest_bytes(unsigned)).hexdigest()
    with pytest.raises(contract.X6R132ContractError, match="false, rehashed"):
        _verify(value, tmp_path)
