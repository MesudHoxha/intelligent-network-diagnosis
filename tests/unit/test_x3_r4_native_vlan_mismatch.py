from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Sequence

import pytest

from src.collection.l2_vlan_state_collector_v4 import build_l2_vlan_feature_vector_v2, collect_native_vlan_mismatch_evidence_v4
from src.expansion.x3_native_vlan_mismatch import X3NativeVlanMismatchError, load_native_vlan_mismatch_scenario
from src.fault_injection.native_vlan_mismatch import inject_native_vlan_mismatch, restore_native_vlan_mismatch
from src.fault_injection.phase6_common import utc_now
from src.orchestration.x3_native_vlan_mismatch_experiment_runner import recover_x3_r4_experiment, run_x3_r4_experiment
from src.rules.l2_vlan_rule_engine_x3_r4 import diagnose_l2_vlan_x3_r4_v2


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/expansion/X3_R4_NATIVE_VLAN_MISMATCH.yml"
HOSTC_MAC = "02:42:0a:1e:63:0a"


class FakeNetwork:
    def __init__(self) -> None:
        self.faulted = False
        self.raise_after_mutation = False

    def result(self, container: str, command: Sequence[str], *, return_code: int = 0, stdout: str = "", stderr: str = "") -> dict[str, object]:
        return {"command": ["docker", "exec", container, *command], "return_code": return_code, "stdout": stdout, "stderr": stderr, "timestamp_utc": utc_now()}

    def vlans(self, container: str) -> list[dict[str, object]]:
        native = ([{"vlan": 10, "flags": []}, {"vlan": 99, "flags": []}, {"vlan": 98, "flags": ["PVID", "Egress Untagged"]}] if self.faulted and container.endswith("sw1") else [{"vlan": 10, "flags": []}, {"vlan": 99, "flags": ["PVID", "Egress Untagged"]}])
        return [{"ifname": "eth1", "vlans": [{"vlan": 10, "flags": ["PVID", "Egress Untagged"]}]}, {"ifname": "eth2", "vlans": [{"vlan": 99, "flags": ["PVID", "Egress Untagged"]}]}, {"ifname": "eth3", "vlans": native}]

    def __call__(self, container: str, command: Sequence[str]) -> dict[str, object]:
        parts = list(command)
        if parts[:4] == ["bridge", "-j", "vlan", "show"]:
            rows = self.vlans(container)
            if parts[4:5] == ["dev"]: rows = [row for row in rows if row["ifname"] == parts[5]]
            return self.result(container, command, stdout=json.dumps(rows))
        if parts[:4] == ["bridge", "-j", "fdb", "show"]:
            rows = [{"mac": HOSTC_MAC, "ifname": "eth2", "vlan": 99, "state": "reachable"}] if container.endswith("sw1") else []
            return self.result(container, command, stdout=json.dumps(rows))
        if parts[:5] == ["ip", "-j", "link", "show", "dev"]:
            mac = HOSTC_MAC if container.endswith("hostc") else "02:42:00:00:00:01"
            return self.result(container, command, stdout=json.dumps([{"ifname": parts[5], "address": mac, "flags": ["BROADCAST", "MULTICAST", "UP", "LOWER_UP"]}]))
        if parts[:1] == ["ping"]:
            broken_native = container.endswith("hostc") and self.faulted
            return self.result(container, command, return_code=1 if broken_native else 0)
        if parts[:3] == ["sh", "-eu", "-c"]:
            shell = parts[3]
            if "vid 98 pvid untagged" in shell:
                self.faulted = True
                if self.raise_after_mutation:
                    self.raise_after_mutation = False
                    raise RuntimeError("simulated crash after native mutation")
            if "bridge vlan add dev eth3 vid 99 pvid untagged" in shell:
                self.faulted = False
            return self.result(container, command)
        raise AssertionError(f"Unexpected command: {container} {parts}")


def _fault_evidence(tmp_path: Path, network: FakeNetwork) -> dict[str, object]:
    inject_native_vlan_mismatch(SCENARIO, tmp_path / "mutation", executor=network)
    return collect_native_vlan_mismatch_evidence_v4(tmp_path, SCENARIO, executor=network)


def test_native_scenario_uses_distinct_hostc_hostd_context() -> None:
    binding = load_native_vlan_mismatch_scenario(SCENARIO)
    assert binding.topology_context_id == "x3_top_01_l2_vlan_native_flow_context_v1"
    assert (binding.source_node, binding.destination_node) == ("hostc", "hostd")
    assert (binding.expected_vlan, binding.mismatched_native_vlan, binding.tagged_control_vlan) == (99, 98, 10)


def test_injection_restoration_and_evidence_keep_tagged_control_healthy(tmp_path: Path) -> None:
    network = FakeNetwork()
    injection = inject_native_vlan_mismatch(SCENARIO, tmp_path / "mutation", executor=network)
    assert injection["status"] == "FAULT_CONFIRMED" and network.faulted is True
    assert injection["postconditions"]["native_flow_is_broken"]["passed"] is True
    assert injection["postconditions"]["tagged_control_flow_remains_healthy"]["passed"] is True
    evidence = collect_native_vlan_mismatch_evidence_v4(tmp_path, SCENARIO, executor=network)
    assert {name: row["value"] for name, row in evidence["observations"].items()} == {"access_vlan_matches_expected": True, "vlan_exists_on_target": True, "vlan_allowed_on_trunk": True, "native_vlan_matches_peer": False, "fdb_location_matches_expected": True}
    assert evidence["observation_path"]["source_node"] == "hostc"
    assert evidence["collector_runs"][0]["collector_version"] == 4
    for artifact in evidence["collector_runs"][0]["raw_artifacts"]:
        assert hashlib.sha256((tmp_path / artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
    restored = restore_native_vlan_mismatch(SCENARIO, tmp_path / "mutation", executor=network)
    assert restored["status"] == "RESTORATION_CONFIRMED" and network.faulted is False
    assert restore_native_vlan_mismatch(SCENARIO, tmp_path / "mutation", executor=network) == restored


def test_exact_rule_preserves_previous_signatures_and_rejects_incomplete_evidence(tmp_path: Path) -> None:
    network = FakeNetwork(); evidence = _fault_evidence(tmp_path, network)
    vector = build_l2_vlan_feature_vector_v2(tmp_path, evidence)
    diagnosis = diagnose_l2_vlan_x3_r4_v2(vector, location_node="sw1", affected_resource="eth3:native-vlan")
    assert diagnosis["prediction"]["fault_type"] == "native_vlan_mismatch"
    prior = copy.deepcopy(vector); prior["values"]["native_vlan_matches_peer"]["value"] = True; prior["values"]["vlan_allowed_on_trunk"]["value"] = False
    assert diagnose_l2_vlan_x3_r4_v2(prior, location_node="sw1", affected_resource="eth3:vlan10")["prediction"]["fault_type"] == "vlan_not_allowed_on_trunk"
    incomplete = copy.deepcopy(vector); incomplete["values"]["fdb_location_matches_expected"]["availability"] = "collection_unavailable"; incomplete["values"]["fdb_location_matches_expected"]["value"] = None
    assert diagnose_l2_vlan_x3_r4_v2(incomplete, location_node="sw1", affected_resource="eth3:native-vlan")["status"] == "insufficient_evidence"
    restore_native_vlan_mismatch(SCENARIO, tmp_path / "mutation", executor=network)


def test_durable_crash_recovery_and_orchestrator_lifecycle(tmp_path: Path) -> None:
    network = FakeNetwork(); network.raise_after_mutation = True
    with pytest.raises(Exception, match="executor raised an exception"):
        inject_native_vlan_mismatch(SCENARIO, tmp_path / "crash", executor=network)
    assert network.faulted is False and (tmp_path / "crash/recovery_intent.json").is_file()
    def baseline(_: Path) -> dict[str, object]:
        return {"command": ["bash", "fake"], "return_code": 0 if not network.faulted else 1, "stdout": "", "stderr": "", "timestamp_utc": utc_now()}
    result = run_x3_r4_experiment(SCENARIO, tmp_path / "runs", ROOT / "unused.sh", baseline_validator=baseline, fault_injector=lambda s, o: inject_native_vlan_mismatch(s, o, executor=network), fault_restorer=lambda s, o: restore_native_vlan_mismatch(s, o, executor=network), evidence_collector=lambda o, s: collect_native_vlan_mismatch_evidence_v4(o, s, executor=network), experiment_id="x3-r4-unit")
    assert result["status"] == "COMPLETED" and result["baseline_valid_after"] is True
    assert recover_x3_r4_experiment(SCENARIO, Path(str(result["experiment_directory"])), ROOT / "unused.sh", baseline_validator=baseline, fault_restorer=lambda s, o: restore_native_vlan_mismatch(s, o, executor=network))["status"] == "RECOVERY_CONFIRMED"


def test_unjournaled_restoration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(X3NativeVlanMismatchError, match="durable recovery intent"):
        restore_native_vlan_mismatch(SCENARIO, tmp_path / "missing", executor=FakeNetwork())
