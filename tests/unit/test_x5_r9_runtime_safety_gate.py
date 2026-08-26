from pathlib import Path
import json
import subprocess

from src.expansion.x5_r9_gate import verify_x5_r9_gate
from src.fault_injection.phase6_common import write_json_atomic
from src.orchestration.x5_r9_c5_runtime_safety_revalidation_runner import _new_journal, _standalone_replay
ROOT=Path(__file__).resolve().parents[2]
def test_x5_r9_requires_crash_safe_c5_lifecycle()->None:
 plan=verify_x5_r9_gate(ROOT);assert plan["slice"]["signature"]=={"ospf_adjacency_full":True,"ospf_route_advertised":False,"ospf_route_installed":False,"route_filter_allows_prefix":False};assert plan["acceptance"]["standalone_replay_required"] is True


def test_x5_r9_standalone_replay_uses_bounded_wrapper_and_preserves_provenance(tmp_path: Path) -> None:
    (tmp_path / "mutation").mkdir()
    seen: dict[str, object] = {}

    def bounded(command: list[str], *, timeout_seconds: float, cwd: Path) -> subprocess.CompletedProcess[str]:
        seen.update({"command": command, "timeout_seconds": timeout_seconds, "cwd": cwd})
        return subprocess.CompletedProcess(command, 0, '{"status":"RECOVERY_APPLIED"}', "")

    result = _standalone_replay(tmp_path, bounded_runner=bounded)
    persisted = json.loads((tmp_path / "mutation/standalone_replay_record.json").read_text())
    assert seen["timeout_seconds"] == 20.0 and seen["command"] == result["command"]
    assert result["status"] == "STANDALONE_REPLAY_APPLIED"
    assert persisted["started_at_utc"] and persisted["completed_at_utc"]


def test_x5_r9_standalone_replay_timeout_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "mutation").mkdir()
    result = _standalone_replay(tmp_path, bounded_runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 124, "", "timeout"))
    assert result["status"] == "STANDALONE_REPLAY_FAILED" and result["failure_kind"] == "TIMEOUT"


def test_x5_r9_durable_recovery_state_is_json_readable_by_a_new_process_boundary(tmp_path: Path) -> None:
    mutation = tmp_path / "mutation"
    mutation.mkdir()
    intent = {"target": "r3:attached_prefix_list:X5-R5-C5-TARGET"}
    write_json_atomic(mutation / "mutation_journal.json", _new_journal(intent))
    recovered = json.loads((mutation / "mutation_journal.json").read_text())
    assert recovered["actions"][0]["status"] == "PLANNED" and recovered["events"][0]["detail"] == "durable_before_forward_command"
