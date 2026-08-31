"""Atomic, non-scientific terminal records for incomplete X6-R1 lifecycles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.fault_injection.phase6_common import utc_now, write_json_atomic


EXPECTED_ACCEPTANCE_ARTIFACTS = (
    "manifest.json", "parsed/evidence_v4.json", "parsed/feature_vector_v2.json",
    "diagnosis/diagnosis_result_v2.json", "validation/raw_hashes.json",
)


def _inventory(root: Path) -> list[dict[str, object]]:
    return [
        {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size}
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "terminal_lifecycle_v1.json"
    ]


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _state(root: Path) -> dict[str, object]:
    journal = _json(root / "mutation/action_journal.json")
    actions = journal.get("actions")
    statuses = [row.get("status") for row in actions] if isinstance(actions, list) and all(isinstance(row, dict) for row in actions) else []
    effect = _json(root / "mutation/mutation_effectiveness.json")
    restoration = _json(root / "mutation/restoration_record.json")
    replay = _json(root / "mutation/standalone_replay.json")
    return {
        "attempted": any(status in {"ATTEMPTED", "COMMAND_ACCEPTED", "FAILED"} for status in statuses),
        "command_accepted": bool(statuses) and all(status == "COMMAND_ACCEPTED" for status in statuses),
        "effective": effect.get("status") == "MUTATION_EFFECTIVE",
        "restoration_status": restoration.get("status", "NOT_COMPLETED"),
        "standalone_replay_status": replay.get("status", "NOT_COMPLETED"),
    }


def terminalize_x6_r1_failure(
    root: Path,
    *,
    terminal_phase: str,
    last_successful_phase: str,
    error: BaseException,
    cleanup_status: str,
) -> dict[str, Any]:
    """Write once, atomically; never create scientific acceptance artifacts."""
    path = root / "validation/terminal_lifecycle_v1.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    state = _state(root)
    baseline_after = _json(root / "validation/baseline_after.json")
    artifacts = _inventory(root)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "release_id": "X6_R1_PACKET_LOSS",
        "terminal_lifecycle_status": "DIAGNOSTIC_NON_AUTHORITATIVE",
        "pilot_authorization": "PILOT_CONSUMED" if (root / "mutation/action_journal.json").is_file() else "PILOT_NOT_CONSUMED",
        "terminal_phase": terminal_phase,
        "last_successful_phase": last_successful_phase,
        "error": {"type": type(error).__name__, "message": str(error)},
        "cleanup_status": cleanup_status,
        "baseline_before_status": "BASELINE_VALID" if (root / "validation/baseline_before.json").is_file() else "NOT_COMPLETED",
        "baseline_after_status": baseline_after.get("status", "NOT_COMPLETED"),
        "mutation": {"attempted": state["attempted"], "command_accepted": state["command_accepted"], "effective": state["effective"]},
        "restoration": {"recorded": (root / "mutation/restoration_record.json").is_file(), "status": state["restoration_status"], "standalone_replay_recorded": (root / "mutation/standalone_replay.json").is_file(), "standalone_replay_status": state["standalone_replay_status"]},
        "artifacts": artifacts,
        "missing_expected_artifacts": [item for item in EXPECTED_ACCEPTANCE_ARTIFACTS if not (root / item).is_file()],
        "created_at_utc": utc_now(),
        "provenance": "POST_FAILURE_TERMINALIZATION_NOT_RUNTIME_ACCEPTANCE",
    }
    write_json_atomic(path, payload)
    return payload
