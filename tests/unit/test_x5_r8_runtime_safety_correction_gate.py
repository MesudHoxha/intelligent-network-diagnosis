from __future__ import annotations

import json
from pathlib import Path

from src.expansion.x5_r8_gate import verify_x5_r8_runtime_safety_gate
from src.orchestration.x5_r9_c5_runtime_safety_revalidation_runner import (
    _new_journal,
    _record_forward_attempt,
    recover_x5_r9_experiment,
)
from src.fault_injection.phase6_common import write_json_atomic


ROOT = Path(__file__).resolve().parents[2]


def test_x5_r8_gate_freezes_append_only_crash_safe_sequence() -> None:
    plan = verify_x5_r8_runtime_safety_gate(ROOT)
    assert plan["track"]["next_release"] == "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION"
    assert all(value is False for value in plan["runtime_authorization"].values())


def test_x5_r9_journal_is_planned_before_any_forward_command(tmp_path: Path) -> None:
    intent = {"target": "r3:attached_prefix_list:X5-R5-C5-TARGET"}
    journal = _new_journal(intent)
    assert journal["status"] == "PLANNED"
    assert journal["actions"][0]["status"] == "PLANNED"
    assert journal["events"][0]["detail"] == "durable_before_forward_command"


def test_x5_r9_standalone_recovery_replays_a_planned_partial_action_idempotently(tmp_path: Path) -> None:
    mutation = tmp_path / "mutation"
    mutation.mkdir()
    intent = {"schema_version": 2, "release_id": "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION", "target": "r3:attached_prefix_list:X5-R5-C5-TARGET"}
    write_json_atomic(mutation / "recovery_intent.json", intent)
    write_json_atomic(mutation / "mutation_journal.json", _new_journal(intent))
    commands: list[list[str]] = []

    def executor(command: list[str]) -> dict[str, object]:
        commands.append(command)
        return {"command": command, "return_code": 0, "stdout": "", "stderr": ""}

    first = recover_x5_r9_experiment(tmp_path, command_executor=executor)
    second = recover_x5_r9_experiment(tmp_path, command_executor=executor)
    journal = json.loads((mutation / "mutation_journal.json").read_text())
    assert first["status"] == second["status"] == "RECOVERY_APPLIED"
    assert first["prior_action_status"] == "PLANNED" and second["prior_action_status"] == "RESTORED"
    assert len(commands) == 2 and all("no ip prefix-list X5-R5-C5-TARGET seq 1" in command[-1] for command in commands)
    assert journal["actions"][0]["status"] == "RESTORED"


def test_x5_r9_records_attempt_before_forward_command_and_retains_acceptance_separately(tmp_path: Path) -> None:
    mutation = tmp_path / "mutation"
    mutation.mkdir()
    intent = {"target": "r3:attached_prefix_list:X5-R5-C5-TARGET"}
    write_json_atomic(mutation / "mutation_journal.json", _new_journal(intent))
    seen_statuses: list[str] = []

    def executor(command: list[str]) -> dict[str, object]:
        journal = json.loads((mutation / "mutation_journal.json").read_text())
        seen_statuses.append(journal["actions"][0]["status"])
        return {"command": command, "return_code": 0, "stdout": "", "stderr": ""}

    _record_forward_attempt(tmp_path, executor)
    journal = json.loads((mutation / "mutation_journal.json").read_text())
    injection = json.loads((mutation / "injection_record.json").read_text())
    assert seen_statuses == ["ATTEMPTED"]
    assert journal["actions"][0]["status"] == injection["status"] == "COMMAND_ACCEPTED"
    assert injection["physical_effectiveness_status"] == "NOT_YET_OBSERVED"


def test_x5_r9_recovery_rejects_unapproved_durable_action(tmp_path: Path) -> None:
    mutation = tmp_path / "mutation"
    mutation.mkdir()
    intent = {"schema_version": 2, "release_id": "X5_R9_C5_RUNTIME_SAFETY_REVALIDATION", "target": "r3:attached_prefix_list:X5-R5-C5-TARGET"}
    write_json_atomic(mutation / "recovery_intent.json", intent)
    journal = _new_journal(intent)
    journal["actions"][0]["action_id"] = "UNAPPROVED"
    write_json_atomic(mutation / "mutation_journal.json", journal)
    try:
        recover_x5_r9_experiment(tmp_path)
    except RuntimeError as error:
        assert "not approved" in str(error)
    else:
        raise AssertionError("unapproved durable state must fail closed")
