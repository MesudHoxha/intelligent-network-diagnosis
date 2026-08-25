from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from uuid import uuid4

from src.collection.ospf_state_collector_x5_r2 import build_x5_r2_feature_vector, collect_x5_r2_evidence
from src.fault_injection.phase6_common import utc_now, write_json_atomic
from src.rules.ospf_rule_engine_x5_r2 import diagnose_x5_r2_route_suppression
from src.runtime.subprocesses import run_capture

ROOT = Path(__file__).resolve().parents[2]


def _run(command: list[str]) -> dict[str, object]:
    result = run_capture(command, timeout_seconds=90.0)
    return {"command": command, "return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def _ok(result: dict[str, object], message: str) -> None:
    if result["return_code"] != 0:
        raise RuntimeError(message + ": " + str(result["stderr"]))


def _await_c5_effectiveness() -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    for number in range(1, 21):
        neighbors = [_run(["docker", "exec", "clab-x5r1-" + node, "vtysh", "-c", "show ip ospf neighbor json"]) for node in ("r1", "r2", "r3")]
        route = _run(["docker", "exec", "clab-x5r1-r1", "vtysh", "-c", "show ip route 10.51.3.0/24 json"])
        policy = _run(["docker", "exec", "clab-x5r1-r3", "vtysh", "-c", "show running-config"])
        state = {"attempt": number, "all_adjacencies_full": all(item["return_code"] == 0 and "Full" in str(item["stdout"]) for item in neighbors), "prefix_not_installed": "ospf" not in str(route["stdout"]).lower(), "policy_marker_present": "X5-R2-SUPPRESS" in str(policy["stdout"]), "neighbors": neighbors, "route": route, "policy": policy}
        attempts.append(state)
        if state["all_adjacencies_full"] and state["prefix_not_installed"] and state["policy_marker_present"]:
            return {"status": "MUTATION_EFFECTIVE", "attempts": attempts}
        sleep(2)
    return {"status": "MUTATION_NOT_EFFECTIVE", "attempts": attempts}


def run_x5_r2_experiment(output_root: Path, baseline: Path, *, experiment_id: str | None = None) -> dict[str, object]:
    experiment_id = experiment_id or "x5-r2-route-filter-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex
    root = Path(output_root) / experiment_id
    root.mkdir(parents=True, exist_ok=False)
    mutation = root / "mutation"
    mutation.mkdir()
    before = _run(["bash", str(baseline)])
    write_json_atomic(root / "validation/baseline_before.json", before)
    _ok(before, "X5-R2 baseline before failed")
    intent = {"schema_version": 1, "scenario_id": "X5_R2_ROUTE_FILTERING_OR_ADVERTISEMENT_PROBLEM", "fault_type": "route_filtering_or_advertisement_problem", "target": "r3:ospf", "status": "RECOVERY_REQUIRED_IF_MUTATION_ATTEMPTED", "created_at_utc": utc_now()}
    write_json_atomic(mutation / "recovery_intent.json", intent)
    primary: BaseException | None = None
    try:
        injected = _run(["docker", "exec", "clab-x5r1-r3", "vtysh", "-c", "configure terminal", "-c", "router ospf", "-c", "no network 10.51.3.0/24 area 0"])
        policy = _run(["docker", "exec", "clab-x5r1-r3", "vtysh", "-c", "configure terminal", "-c", "ip prefix-list X5-R2-SUPPRESS seq 5 deny 10.51.3.0/24"])
        write_json_atomic(mutation / "injection_record.json", {**intent, "mutation_commands": [injected, policy], "status": "FAULT_CONFIRMED" if injected["return_code"] == 0 and policy["return_code"] == 0 else "FAULT_NOT_CONFIRMED"})
        _ok(injected, "X5-R2 OSPF advertisement suppression failed")
        _ok(policy, "X5-R2 policy marker creation failed")
        effectiveness = _await_c5_effectiveness()
        write_json_atomic(root / "mutation/mutation_effectiveness.json", effectiveness)
        if effectiveness["status"] != "MUTATION_EFFECTIVE":
            raise RuntimeError("X5-R2 mutation did not converge to healthy adjacency with suppressed prefix")
        evidence = collect_x5_r2_evidence(root, repository_root=ROOT)
        vector = build_x5_r2_feature_vector(root, evidence, repository_root=ROOT)
        diagnosis = diagnose_x5_r2_route_suppression(vector, repository_root=ROOT)
        write_json_atomic(root / "diagnosis/diagnosis_result_v2.json", diagnosis)
        if diagnosis["status"] != "diagnosed":
            raise RuntimeError("X5-R2 exact C5 rule did not diagnose")
    except BaseException as error:
        primary = error
    restored_network = _run(["docker", "exec", "clab-x5r1-r3", "vtysh", "-c", "configure terminal", "-c", "router ospf", "-c", "network 10.51.3.0/24 area 0"])
    removed_policy = _run(["docker", "exec", "clab-x5r1-r3", "vtysh", "-c", "configure terminal", "-c", "no ip prefix-list X5-R2-SUPPRESS"])
    write_json_atomic(mutation / "restoration_record.json", {**intent, "restoration_commands": [restored_network, removed_policy], "status": "RESTORATION_CONFIRMED" if restored_network["return_code"] == 0 and removed_policy["return_code"] == 0 else "RESTORATION_FAILED", "completed_at_utc": utc_now()})
    _ok(restored_network, "X5-R2 OSPF advertisement restoration failed")
    _ok(removed_policy, "X5-R2 policy-marker removal failed")
    after = _run(["bash", str(baseline)])
    write_json_atomic(root / "validation/baseline_after.json", after)
    _ok(after, "X5-R2 baseline after failed")
    if primary:
        raise primary
    write_json_atomic(root / "manifest.json", {"schema_version": 1, "release_id": "X5_R2_ROUTE_FILTERING_OR_ADVERTISEMENT_PROBLEM", "experiment_id": experiment_id, "status": "COMPLETED", "completed_at_utc": utc_now()})
    return {"status": "COMPLETED", "experiment_directory": str(root), "restoration_confirmed": True, "baseline_valid_after": True}
