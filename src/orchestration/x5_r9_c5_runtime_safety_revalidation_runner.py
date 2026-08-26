"""Crash-safe orchestration for the future X5-R9 C5 revalidation.

This source-only module deliberately does not alter the accepted X5-R6 runner.
Its journal is a recovery authority, so every possible forward action is made
durable before its command is attempted and recovery reconstructs only the
approved inverse operation from that durable state.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import monotonic, sleep
from typing import Any
from uuid import uuid4

from src.collection.ospf_state_collector_x5_r4 import capture, target_state
from src.collection.ospf_state_collector_x5_r6 import (
    PREFIX,
    _expected_lsa_present,
    _json_object,
    _policy_state,
    _route_installed,
)
from src.collection.ospf_state_collector_x5_r9 import build_x5_r9_feature_vector, collect_x5_r9_evidence
from src.fault_injection.phase6_common import utc_now, write_json_atomic
from src.rules.ospf_rule_engine_x5_r6 import diagnose_x5_r6_operational_policy_c5
from src.runtime.subprocesses import TIMEOUT_RETURN_CODE, run_capture


ROOT = Path(__file__).resolve().parents[2]
NODES = "clab-x5r5c5-"
EXPECTED_IMAGE_DIGEST = "frrouting/frr@sha256:0f8c174d95add7916101077d4716822552c758b8ff3d2dcb55104f6534202e3e"
ACTION_ID = "ADD_ACTIVE_DENY_CRITERION"
CommandExecutor = Callable[[list[str]], dict[str, object]]


def _ok(record: dict[str, object], label: str) -> None:
    if record.get("return_code") != 0:
        raise RuntimeError(label + ": " + str(record.get("stderr", "")))


def _approved_forward_command() -> list[str]:
    return ["docker", "exec", NODES + "r3", "vtysh", "-c", "configure terminal", "-c", "ip prefix-list X5-R5-C5-TARGET seq 1 deny " + PREFIX]


def _approved_recovery_command() -> list[str]:
    return ["docker", "exec", NODES + "r3", "vtysh", "-c", "configure terminal", "-c", "no ip prefix-list X5-R5-C5-TARGET seq 1"]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("X5-R9 durable state must be an object: " + str(path))
    return value


def _write_journal(root: Path, journal: dict[str, Any]) -> None:
    write_json_atomic(root / "mutation/mutation_journal.json", journal)


def _new_journal(intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "release_id": "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION",
        "status": "PLANNED",
        "created_at_utc": utc_now(),
        "actions": [{
            "action_id": ACTION_ID,
            "target": intent["target"],
            "status": "PLANNED",
            "forward_operation": "add_active_attached_prefix_list_deny",
            "recovery_operation": "remove_active_attached_prefix_list_deny",
            "planned_at_utc": utc_now(),
        }],
        "events": [{"state": "PLANNED", "at_utc": utc_now(), "detail": "durable_before_forward_command"}],
    }


def _find_action(journal: dict[str, Any]) -> dict[str, Any]:
    actions = journal.get("actions")
    if not isinstance(actions, list) or len(actions) != 1 or not isinstance(actions[0], dict):
        raise RuntimeError("X5-R9 durable journal must contain exactly one action")
    action = actions[0]
    if action.get("action_id") != ACTION_ID or action.get("forward_operation") != "add_active_attached_prefix_list_deny" or action.get("recovery_operation") != "remove_active_attached_prefix_list_deny":
        raise RuntimeError("X5-R9 durable journal action is not approved for recovery")
    return action


def _append_event(journal: dict[str, Any], state: str, detail: str) -> None:
    events = journal.setdefault("events", [])
    if not isinstance(events, list):
        raise RuntimeError("X5-R9 journal events must be a list")
    events.append({"state": state, "at_utc": utc_now(), "detail": detail})


def _record_forward_attempt(root: Path, command_executor: CommandExecutor) -> dict[str, object]:
    journal = _read_json(root / "mutation/mutation_journal.json")
    action = _find_action(journal)
    action["status"] = "ATTEMPTED"
    action["attempted_at_utc"] = utc_now()
    journal["status"] = "ATTEMPTED"
    _append_event(journal, "ATTEMPTED", "durably_recorded_before_forward_command")
    _write_journal(root, journal)
    command = command_executor(_approved_forward_command())
    accepted = command.get("return_code") == 0
    action["status"] = "COMMAND_ACCEPTED" if accepted else "COMMAND_REJECTED"
    action["command_record"] = command
    action["command_completed_at_utc"] = utc_now()
    journal["status"] = action["status"]
    _append_event(journal, str(action["status"]), "forward_command_result_recorded")
    _write_journal(root, journal)
    write_json_atomic(root / "mutation/injection_record.json", {
        "schema_version": 2,
        "action_id": ACTION_ID,
        "status": action["status"],
        "command": command,
        "command_acceptance_only": True,
        "physical_effectiveness_status": "NOT_YET_OBSERVED",
    })
    return command


def _state_until_effective(command_executor: CommandExecutor, timeout_seconds: float = 45.0) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    deadline = monotonic() + timeout_seconds
    while True:
        neighbor = command_executor(["docker", "exec", NODES + "r2", "vtysh", "-c", "show ip ospf neighbor json"])
        database = command_executor(["docker", "exec", NODES + "r1", "vtysh", "-c", "show ip ospf database json"])
        route = command_executor(["docker", "exec", NODES + "r1", "vtysh", "-c", "show ip route " + PREFIX + " json"])
        policy = command_executor(["docker", "exec", NODES + "r3", "vtysh", "-c", "show running-config"])
        parsed_neighbor, parsed_database, parsed_route = (_json_object(record, allow_empty=name == "route") for name, record in (("neighbor", neighbor), ("database", database), ("route", route)))
        state = target_state(neighbor) if parsed_neighbor is not None else {"r2_r3_full": None, "r1_r2_full": None}
        policy_state = _policy_state(str(policy.get("stdout", "")))
        values = {
            "target_r2_r3_full": state["r2_r3_full"] is True,
            "control_r1_r2_full": state["r1_r2_full"] is True,
            "structured_lsdb_valid": parsed_database is not None,
            "structured_route_valid": parsed_route is not None,
            "lsa_absent": parsed_database is not None and not _expected_lsa_present(parsed_database),
            "route_absent": parsed_route is not None and not _route_installed(parsed_route),
            **policy_state,
        }
        attempts.append({"state": values, "neighbor": neighbor, "database": database, "route": route, "policy": policy})
        required = ("target_r2_r3_full", "control_r1_r2_full", "structured_lsdb_valid", "structured_route_valid", "lsa_absent", "route_absent", "attachment_present", "route_map_match_present", "active_deny_present", "baseline_permit_retained", "direct_expected_network_absent")
        if all(values[name] for name in required):
            return {"status": "MUTATION_EFFECTIVE", "postcondition": values, "attempts": attempts}
        if monotonic() >= deadline:
            return {"status": "MUTATION_NOT_EFFECTIVE", "attempts": attempts}
        sleep(1)


def _record_effectiveness(root: Path, effectiveness: dict[str, object]) -> None:
    journal = _read_json(root / "mutation/mutation_journal.json")
    action = _find_action(journal)
    status = str(effectiveness.get("status"))
    action["status"] = status
    action["effectiveness"] = effectiveness
    journal["status"] = status
    _append_event(journal, status, "state_based_postcondition_result_recorded")
    _write_journal(root, journal)
    write_json_atomic(root / "mutation/mutation_effectiveness.json", effectiveness)


def recover_x5_r9_experiment(experiment_root: Path, *, command_executor: CommandExecutor = capture) -> dict[str, object]:
    """Recover from durable state in a fresh process, including partial attempts."""
    root = Path(experiment_root)
    intent = _read_json(root / "mutation/recovery_intent.json")
    if intent.get("release_id") != "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION" or intent.get("target") != "r3:attached_prefix_list:X5-R5-C5-TARGET":
        raise RuntimeError("X5-R9 recovery intent is not approved")
    journal = _read_json(root / "mutation/mutation_journal.json")
    action = _find_action(journal)
    prior_status = str(action.get("status"))
    action["recovery_status"] = "ATTEMPTED"
    action["recovery_attempted_at_utc"] = utc_now()
    _append_event(journal, "ATTEMPTED", "standalone_idempotent_recovery_before_inverse_command")
    _write_journal(root, journal)
    command = command_executor(_approved_recovery_command())
    restored = command.get("return_code") == 0
    action["status"] = "RESTORED" if restored else "FAILED"
    action["recovery_status"] = "RESTORED" if restored else "FAILED"
    action["recovery_command_record"] = command
    action["recovery_completed_at_utc"] = utc_now()
    journal["status"] = action["status"]
    _append_event(journal, str(action["status"]), "standalone_idempotent_recovery_result")
    _write_journal(root, journal)
    return {"schema_version": 2, "status": "RECOVERY_APPLIED" if restored else "RECOVERY_FAILED", "prior_action_status": prior_status, "action_status": action["status"], "recovery_command": command, "completed_at_utc": utc_now()}


def _standalone_replay(root: Path, *, bounded_runner: Callable[..., object] = run_capture) -> dict[str, object]:
    command = [sys.executable, "-m", "src.orchestration.x5_r9_c5_runtime_safety_revalidation_runner", "--recover", str(root)]
    started_at_utc = utc_now()
    result = bounded_runner(command, timeout_seconds=20.0, cwd=ROOT)
    return_code = getattr(result, "returncode", None)
    stdout = getattr(result, "stdout", "")
    stderr = getattr(result, "stderr", "")
    record: dict[str, object] = {"command": command, "timeout_seconds": 20.0, "return_code": return_code, "stdout": stdout, "stderr": stderr, "started_at_utc": started_at_utc, "completed_at_utc": utc_now(), "status": "STANDALONE_REPLAY_FAILED"}
    if return_code == 0:
        try: replay = json.loads(result.stdout)
        except json.JSONDecodeError: replay = None
        if isinstance(replay, dict) and replay.get("status") == "RECOVERY_APPLIED": record.update({"status": "STANDALONE_REPLAY_APPLIED", "replay": replay})
    elif return_code == TIMEOUT_RETURN_CODE:
        record["failure_kind"] = "TIMEOUT"
    else:
        record["failure_kind"] = "NONZERO_OR_INVALID_REPLAY"
    write_json_atomic(root / "mutation/standalone_replay_record.json", record)
    return record


def _capture_image_identity(command_executor: CommandExecutor) -> dict[str, object]:
    result = command_executor(["docker", "image", "inspect", "frrouting/frr:v8.4.1"])
    identity: dict[str, object] = {"command": result.get("command"), "return_code": result.get("return_code"), "expected_repo_digest": EXPECTED_IMAGE_DIGEST, "status": "IMAGE_IDENTITY_UNAVAILABLE"}
    if result.get("return_code") != 0:
        identity["stderr"] = result.get("stderr")
        return identity
    try:
        entries = json.loads(str(result.get("stdout", "")))
        entry = entries[0] if isinstance(entries, list) and entries else {}
        digests = entry.get("RepoDigests", []) if isinstance(entry, dict) else []
        if not isinstance(digests, list):
            digests = []
        identity.update({"image_id": entry.get("Id") if isinstance(entry, dict) else None, "repo_digests": digests, "expected_digest_match": EXPECTED_IMAGE_DIGEST in digests, "status": "IMAGE_IDENTITY_RECORDED"})
    except (json.JSONDecodeError, IndexError):
        identity["parse_error"] = "invalid_docker_image_inspect_json"
    return identity


def run_x5_r9_experiment(output_root: Path, baseline: Path, *, experiment_id: str | None = None, command_executor: CommandExecutor = capture) -> dict[str, object]:
    experiment_id = experiment_id or "x5-r9-crash-safe-operational-policy-c5-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex
    root = Path(output_root) / experiment_id
    root.mkdir(parents=True, exist_ok=False)
    (root / "mutation").mkdir()
    image = _capture_image_identity(command_executor)
    write_json_atomic(root / "validation/runtime_image_identity.json", image)
    if image.get("status") != "IMAGE_IDENTITY_RECORDED" or image.get("expected_digest_match") is not True:
        raise RuntimeError("X5-R9 expected FRR image digest is not recorded by Docker")
    before = command_executor(["bash", str(baseline)])
    write_json_atomic(root / "validation/baseline_before.json", before)
    _ok(before, "X5-R9 baseline before failed")
    intent: dict[str, Any] = {"schema_version": 2, "release_id": "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION", "fault_type": "route_filtering_or_advertisement_problem", "target": "r3:attached_prefix_list:X5-R5-C5-TARGET", "status": "RECOVERY_REQUIRED_IF_ACTION_PLANNED", "created_at_utc": utc_now()}
    write_json_atomic(root / "mutation/recovery_intent.json", intent)
    _write_journal(root, _new_journal(intent))
    primary: BaseException | None = None
    try:
        forward = _record_forward_attempt(root, command_executor)
        _ok(forward, "X5-R9 attached policy deny command failed")
        effectiveness = _state_until_effective(command_executor)
        _record_effectiveness(root, effectiveness)
        if effectiveness["status"] != "MUTATION_EFFECTIVE":
            raise RuntimeError("X5-R9 C5 postcondition did not converge")
        evidence = collect_x5_r9_evidence(root, repository_root=ROOT)
        vector = build_x5_r9_feature_vector(root, evidence, repository_root=ROOT)
        diagnosis = diagnose_x5_r6_operational_policy_c5(vector, repository_root=ROOT)
        write_json_atomic(root / "diagnosis/diagnosis_result_v2.json", diagnosis)
        if diagnosis.get("status") != "diagnosed":
            raise RuntimeError("X5-R9 exact C5 rule did not diagnose")
    except BaseException as error:
        primary = error
    recovery = recover_x5_r9_experiment(root, command_executor=command_executor)
    replay = _standalone_replay(root)
    restoration = {"schema_version": 2, **intent, "recovery": recovery, "standalone_replay": replay, "status": "RESTORATION_CONFIRMED" if recovery["status"] == "RECOVERY_APPLIED" and replay["status"] == "STANDALONE_REPLAY_APPLIED" else "RESTORATION_FAILED", "completed_at_utc": utc_now()}
    write_json_atomic(root / "mutation/restoration_record.json", restoration)
    if restoration["status"] != "RESTORATION_CONFIRMED":
        raise RuntimeError("X5-R9 idempotent restoration failed")
    after = command_executor(["bash", str(baseline)])
    write_json_atomic(root / "validation/baseline_after.json", after)
    _ok(after, "X5-R9 baseline after failed")
    if primary:
        raise primary
    write_json_atomic(root / "manifest.json", {"schema_version": 1, "release_id": "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION", "experiment_id": experiment_id, "status": "COMPLETED", "completed_at_utc": utc_now()})
    return {"status": "COMPLETED", "experiment_directory": str(root), "restoration_confirmed": True, "baseline_valid_after": True}


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("--recover", type=Path); arguments = parser.parse_args()
    if arguments.recover is None: parser.error("--recover is required for the standalone recovery entry point")
    print(json.dumps(recover_x5_r9_experiment(arguments.recover), sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
