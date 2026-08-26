from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

from src.collection.ospf_state_collector_x5_r6 import PREFIX, PREFIX_LSA_ID, _expected_lsa_present, _json_object, _policy_state, _route_installed, build_x5_r6_feature_vector, collect_x5_r6_evidence
from src.collection.ospf_state_collector_x5_r4 import capture, target_state
from src.fault_injection.phase6_common import utc_now, write_json_atomic
from src.rules.ospf_rule_engine_x5_r6 import diagnose_x5_r6_operational_policy_c5


ROOT = Path(__file__).resolve().parents[2]
NODES = "clab-x5r5c5-"


def _ok(record: dict[str, object], label: str) -> None:
    if record["return_code"] != 0: raise RuntimeError(label + ": " + str(record["stderr"]))


def _capture_image_identity() -> dict[str, object]:
    result = capture(["docker", "image", "inspect", "frrouting/frr:v8.4.1"])
    identity: dict[str, object] = {"command": result["command"], "return_code": result["return_code"], "status": "IMAGE_IDENTITY_UNAVAILABLE"}
    if result["return_code"] == 0:
        try:
            entries = json.loads(str(result["stdout"])); entry = entries[0] if isinstance(entries, list) and entries else {}
            identity.update({"status": "IMAGE_IDENTITY_RECORDED", "image_id": entry.get("Id"), "repo_digests": entry.get("RepoDigests", [])})
        except (json.JSONDecodeError, IndexError): identity["parse_error"] = "invalid_docker_image_inspect_json"
    else: identity["stderr"] = result["stderr"]
    return identity


def _state_until_effective(timeout_seconds: float = 45.0) -> dict[str, object]:
    attempts: list[dict[str, object]] = []; deadline = monotonic() + timeout_seconds
    while True:
        neighbor = capture(["docker", "exec", NODES + "r2", "vtysh", "-c", "show ip ospf neighbor json"])
        database = capture(["docker", "exec", NODES + "r1", "vtysh", "-c", "show ip ospf database json"])
        route = capture(["docker", "exec", NODES + "r1", "vtysh", "-c", "show ip route " + PREFIX + " json"])
        policy = capture(["docker", "exec", NODES + "r3", "vtysh", "-c", "show running-config"])
        parsed_neighbor, parsed_database, parsed_route = (_json_object(record, allow_empty=name == "route") for name, record in (("neighbor", neighbor), ("database", database), ("route", route)))
        state = target_state(neighbor) if parsed_neighbor is not None else {"r2_r3_full": None, "r1_r2_full": None}
        policy_state = _policy_state(str(policy.get("stdout", "")))
        values = {"target_r2_r3_full": state["r2_r3_full"] is True, "control_r1_r2_full": state["r1_r2_full"] is True, "structured_lsdb_valid": parsed_database is not None, "structured_route_valid": parsed_route is not None, "lsa_absent": parsed_database is not None and not _expected_lsa_present(parsed_database), "route_absent": parsed_route is not None and not _route_installed(parsed_route), **policy_state}
        attempts.append({"state": values, "neighbor": neighbor, "database": database, "route": route, "policy": policy})
        if all(values[name] for name in ("target_r2_r3_full", "control_r1_r2_full", "structured_lsdb_valid", "structured_route_valid", "lsa_absent", "route_absent", "attachment_present", "route_map_match_present", "active_deny_present", "baseline_permit_retained", "direct_expected_network_absent")):
            return {"status": "MUTATION_EFFECTIVE", "postcondition": values, "attempts": attempts}
        if monotonic() >= deadline: return {"status": "MUTATION_NOT_EFFECTIVE", "attempts": attempts}
        sleep(1)


def _recover() -> dict[str, object]:
    command = capture(["docker", "exec", NODES + "r3", "vtysh", "-c", "configure terminal", "-c", "no ip prefix-list X5-R5-C5-TARGET seq 1"])
    return {"recovery_command": command, "status": "RECOVERY_APPLIED" if command["return_code"] == 0 else "RECOVERY_FAILED", "completed_at_utc": utc_now()}


def run_x5_r6_experiment(output_root: Path, baseline: Path, *, experiment_id: str | None = None) -> dict[str, object]:
    experiment_id = experiment_id or "x5-r6-operational-policy-c5-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex
    root = Path(output_root) / experiment_id; root.mkdir(parents=True, exist_ok=False); mutation = root / "mutation"; mutation.mkdir()
    image = _capture_image_identity(); write_json_atomic(root / "validation/runtime_image_identity.json", image)
    before = capture(["bash", str(baseline)]); write_json_atomic(root / "validation/baseline_before.json", before); _ok(before, "X5-R6 baseline before failed")
    intent = {"schema_version": 1, "scenario_id": "X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION", "fault_type": "route_filtering_or_advertisement_problem", "target": "r3:attached_prefix_list:X5-R5-C5-TARGET", "status": "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED", "created_at_utc": utc_now()}; write_json_atomic(mutation / "recovery_intent.json", intent)
    primary: BaseException | None = None
    try:
        deny = capture(["docker", "exec", NODES + "r3", "vtysh", "-c", "configure terminal", "-c", "ip prefix-list X5-R5-C5-TARGET seq 1 deny " + PREFIX])
        write_json_atomic(mutation / "mutation_journal.json", {**intent, "actions": [{"action": "ADD_ACTIVE_DENY_CRITERION", "command": deny, "journaled_before_effectiveness": True}]})
        write_json_atomic(mutation / "injection_record.json", {**intent, "mutation_command": deny, "status": "COMMAND_ACCEPTED" if deny["return_code"] == 0 else "COMMAND_REJECTED"})
        _ok(deny, "X5-R6 attached policy deny command failed")
        effectiveness = _state_until_effective(); write_json_atomic(mutation / "mutation_effectiveness.json", effectiveness)
        if effectiveness["status"] != "MUTATION_EFFECTIVE": raise RuntimeError("X5-R6 C5 postcondition did not converge")
        evidence = collect_x5_r6_evidence(root, repository_root=ROOT); vector = build_x5_r6_feature_vector(root, evidence, repository_root=ROOT); diagnosis = diagnose_x5_r6_operational_policy_c5(vector, repository_root=ROOT); write_json_atomic(root / "diagnosis/diagnosis_result_v2.json", diagnosis)
        if diagnosis["status"] != "diagnosed": raise RuntimeError("X5-R6 exact C5 rule did not diagnose")
    except BaseException as error: primary = error
    recovery = _recover(); replay = _recover(); restoration = {**intent, "recovery": recovery, "replay": replay, "status": "RESTORATION_CONFIRMED" if recovery["status"] == replay["status"] == "RECOVERY_APPLIED" else "RESTORATION_FAILED", "completed_at_utc": utc_now()}; write_json_atomic(mutation / "restoration_record.json", restoration)
    if restoration["status"] != "RESTORATION_CONFIRMED": raise RuntimeError("X5-R6 idempotent restoration failed")
    after = capture(["bash", str(baseline)]); write_json_atomic(root / "validation/baseline_after.json", after); _ok(after, "X5-R6 baseline after failed")
    if primary: raise primary
    write_json_atomic(root / "manifest.json", {"schema_version": 1, "release_id": "X5_R6_C5_OPERATIONAL_POLICY_RUNTIME_REVALIDATION", "experiment_id": experiment_id, "status": "COMPLETED", "completed_at_utc": utc_now()})
    return {"status": "COMPLETED", "experiment_directory": str(root), "restoration_confirmed": True, "baseline_valid_after": True}
