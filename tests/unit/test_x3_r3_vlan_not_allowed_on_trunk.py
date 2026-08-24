from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Sequence

import pytest

from src.collection.l2_vlan_state_collector_v3 import (
    build_l2_vlan_feature_vector_v2,
    collect_vlan_not_allowed_on_trunk_evidence_v4,
)
from src.expansion.x3_vlan_not_allowed_on_trunk import (
    X3VlanNotAllowedOnTrunkError,
    is_tagged,
    load_vlan_not_allowed_on_trunk_scenario,
)
from src.fault_injection.phase6_common import utc_now
from src.fault_injection.vlan_not_allowed_on_trunk import (
    inject_vlan_not_allowed_on_trunk,
    restore_vlan_not_allowed_on_trunk,
)
from src.orchestration.x3_vlan_not_allowed_on_trunk_experiment_runner import (
    recover_x3_r3_experiment,
    run_x3_r3_experiment,
)
from src.rules.l2_vlan_rule_engine_x3_r3 import diagnose_l2_vlan_x3_r3_v2


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/expansion/X3_R3_VLAN_NOT_ALLOWED_ON_TRUNK.yml"
HOSTA_MAC = "02:42:0a:1e:0a:0a"


class FakeNetwork:
    def __init__(self) -> None:
        self.faulted = False
        self.raise_after_mutation = False

    def result(
        self,
        container: str,
        command: Sequence[str],
        *,
        return_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ) -> dict[str, object]:
        return {
            "command": ["docker", "exec", container, *command],
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "timestamp_utc": utc_now(),
        }

    def vlan_rows(self, container: str) -> list[dict[str, object]]:
        trunk_blocked = self.faulted and container.endswith("sw1")
        return [
            {
                "ifname": "eth1",
                "vlans": [{"vlan": 10, "flags": ["PVID", "Egress Untagged"]}],
            },
            {
                "ifname": "eth2",
                "vlans": [
                    {"vlan": 99, "flags": ["PVID", "Egress Untagged"]}
                ],
            },
            {
                "ifname": "eth3",
                "vlans": (
                    [{"vlan": 99, "flags": ["PVID", "Egress Untagged"]}]
                    if trunk_blocked
                    else [
                        {"vlan": 10, "flags": []},
                        {"vlan": 99, "flags": ["PVID", "Egress Untagged"]},
                    ]
                ),
            },
        ]

    def __call__(self, container: str, command: Sequence[str]) -> dict[str, object]:
        parts = list(command)
        if parts[:4] == ["bridge", "-j", "vlan", "show"]:
            rows = self.vlan_rows(container)
            if parts[4:5] == ["dev"]:
                rows = [row for row in rows if row["ifname"] == parts[5]]
            return self.result(container, command, stdout=json.dumps(rows))
        if parts[:4] == ["bridge", "-j", "fdb", "show"]:
            rows = (
                [
                    {
                        "mac": HOSTA_MAC,
                        "ifname": "eth1",
                        "vlan": 10,
                        "state": "reachable",
                    }
                ]
                if container.endswith("sw1")
                else []
            )
            return self.result(container, command, stdout=json.dumps(rows))
        if parts[:5] == ["ip", "-j", "link", "show", "dev"]:
            interface = parts[5]
            address = HOSTA_MAC if container.endswith("hosta") else "02:42:00:00:00:01"
            rows = [
                {
                    "ifname": interface,
                    "address": address,
                    "flags": ["BROADCAST", "MULTICAST", "UP", "LOWER_UP"],
                }
            ]
            return self.result(container, command, stdout=json.dumps(rows))
        if parts[:1] == ["ping"]:
            reachable = not (container.endswith("hosta") and self.faulted)
            return self.result(container, command, return_code=0 if reachable else 1)
        if parts == ["bridge", "vlan", "del", "dev", "eth3", "vid", "10"]:
            self.faulted = True
            if self.raise_after_mutation:
                self.raise_after_mutation = False
                raise RuntimeError("simulated crash after VLAN mutation")
            return self.result(container, command)
        if parts[:3] == ["sh", "-eu", "-c"]:
            shell = parts[3]
            if "bridge vlan add dev eth3 vid 10" in shell:
                self.faulted = False
            return self.result(container, command)
        raise AssertionError(f"Unexpected command: {container} {parts}")


class MissingFdbNetwork(FakeNetwork):
    def __call__(self, container: str, command: Sequence[str]) -> dict[str, object]:
        if list(command)[:4] == ["bridge", "-j", "fdb", "show"]:
            return self.result(container, command, return_code=127, stderr="bridge unavailable")
        return super().__call__(container, command)


def _fault_evidence(tmp_path: Path, network: FakeNetwork) -> dict[str, object]:
    inject_vlan_not_allowed_on_trunk(SCENARIO, tmp_path / "mutation", executor=network)
    return collect_vlan_not_allowed_on_trunk_evidence_v4(tmp_path, SCENARIO, executor=network)


def test_scenario_binds_exact_tagged_flow_and_vlan_identity() -> None:
    binding = load_vlan_not_allowed_on_trunk_scenario(SCENARIO)
    assert binding.topology_id == "X3_TOP_01_L2_VLAN"
    assert binding.topology_context_id == "x3_top_01_l2_vlan_context_v1"
    assert (binding.source_node, binding.destination_node) == ("hosta", "hostb")
    assert (binding.expected_vlan, binding.native_vlan) == (10, 99)
    assert binding.affected_resource == "eth3:vlan10"


def test_tagged_membership_rejects_pvid_or_untagged_flags() -> None:
    assert is_tagged({"vlan": 10, "flags": []}) is True
    assert is_tagged({"vlan": 10, "flags": ["PVID"]}) is False
    assert is_tagged({"vlan": 10, "flags": ["Egress Untagged"]}) is False
    assert is_tagged(None) is False


def test_injection_is_effective_and_restoration_is_idempotent(tmp_path: Path) -> None:
    network = FakeNetwork()
    mutation = tmp_path / "mutation"
    injection = inject_vlan_not_allowed_on_trunk(SCENARIO, mutation, executor=network)
    assert injection["status"] == "FAULT_CONFIRMED"
    assert network.faulted is True
    assert injection["postconditions"]["tagged_flow_is_broken"]["passed"] is True
    assert injection["postconditions"]["native_flow_remains_healthy"]["passed"] is True
    restoration = restore_vlan_not_allowed_on_trunk(SCENARIO, mutation, executor=network)
    assert restoration["status"] == "RESTORATION_CONFIRMED"
    assert network.faulted is False
    assert restore_vlan_not_allowed_on_trunk(SCENARIO, mutation, executor=network) == restoration


def test_crash_after_mutation_restores_from_durable_intent(tmp_path: Path) -> None:
    network = FakeNetwork()
    network.raise_after_mutation = True
    mutation = tmp_path / "mutation"
    with pytest.raises(Exception, match="executor raised an exception"):
        inject_vlan_not_allowed_on_trunk(SCENARIO, mutation, executor=network)
    assert network.faulted is False
    assert (mutation / "recovery_intent.json").is_file()
    assert json.loads((mutation / "restoration_record.json").read_text())["status"] == (
        "RESTORATION_CONFIRMED"
    )


def test_unjournaled_restoration_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(X3VlanNotAllowedOnTrunkError, match="durable recovery intent"):
        restore_vlan_not_allowed_on_trunk(SCENARIO, tmp_path / "mutation", executor=FakeNetwork())


def test_evidence_has_exact_vlan_not_allowed_on_trunk_signature_and_hashes(tmp_path: Path) -> None:
    network = FakeNetwork()
    evidence = _fault_evidence(tmp_path, network)
    values = evidence["observations"]
    assert {name: row["value"] for name, row in values.items()} == {
        "access_vlan_matches_expected": True,
        "vlan_exists_on_target": True,
        "vlan_allowed_on_trunk": False,
        "native_vlan_matches_peer": True,
        "fdb_location_matches_expected": True,
    }
    assert evidence["observation_path"] == {
        "direction": "hosta_to_hostb",
        "source_node": "hosta",
        "destination_node": "hostb",
        "observer_nodes": ["sw1", "sw2"],
    }
    assert evidence["collector_runs"][0]["collector_version"] == 3
    for artifact in evidence["collector_runs"][0]["raw_artifacts"]:
        path = tmp_path / artifact["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    active = json.loads(
        (tmp_path / "raw/v4/l2_vlan_state_collector/active_flow_probe.json").read_text()
    )
    assert active["tagged_flow"]["reachable"] is False
    assert active["native_flow"]["reachable"] is True
    restore_vlan_not_allowed_on_trunk(SCENARIO, tmp_path / "mutation", executor=network)


def test_vector_and_rule_diagnose_only_exact_signature(tmp_path: Path) -> None:
    network = FakeNetwork()
    evidence = _fault_evidence(tmp_path, network)
    vector = build_l2_vlan_feature_vector_v2(tmp_path, evidence)
    diagnosis = diagnose_l2_vlan_x3_r3_v2(
        vector, location_node="sw1", affected_resource="eth3:vlan10"
    )
    assert diagnosis["status"] == "diagnosed"
    assert diagnosis["prediction"] == {
        "fault_type": "vlan_not_allowed_on_trunk",
        "score": 1.0,
        "location": "sw1",
        "affected_resource": "eth3:vlan10",
    }
    assert diagnosis["explanation_refs"] == ["rule:R_X3_L2_VLAN_003"]
    missing = copy.deepcopy(vector)
    missing["values"]["access_vlan_matches_expected"]["value"] = False
    missing["values"]["vlan_exists_on_target"]["value"] = False
    missing["values"]["fdb_location_matches_expected"]["value"] = False
    preserved_missing = diagnose_l2_vlan_x3_r3_v2(
        missing, location_node="sw1", affected_resource="br0:vlan10"
    )
    assert preserved_missing["prediction"]["fault_type"] == "vlan_missing"
    assert preserved_missing["explanation_refs"] == ["rule:R_X3_L2_VLAN_002"]
    wrong_access = copy.deepcopy(vector)
    wrong_access["values"]["access_vlan_matches_expected"]["value"] = False
    wrong_access["values"]["vlan_allowed_on_trunk"]["value"] = True
    wrong_access["values"]["fdb_location_matches_expected"]["value"] = False
    preserved_access = diagnose_l2_vlan_x3_r3_v2(
        wrong_access, location_node="sw1", affected_resource="eth1"
    )
    assert preserved_access["prediction"]["fault_type"] == "wrong_access_vlan"
    assert preserved_access["explanation_refs"] == ["rule:R_X3_L2_VLAN_001"]
    wrong_access["values"]["native_vlan_matches_peer"]["value"] = False
    assert diagnose_l2_vlan_x3_r3_v2(
        wrong_access, location_node="sw1", affected_resource="eth1"
    )["status"] == "abstained"
    restore_vlan_not_allowed_on_trunk(SCENARIO, tmp_path / "mutation", executor=network)


def test_missing_fdb_is_insufficient_evidence(tmp_path: Path) -> None:
    network = MissingFdbNetwork()
    evidence = _fault_evidence(tmp_path, network)
    row = evidence["observations"]["fdb_location_matches_expected"]
    assert row["value"] is None
    assert row["availability"] == "collection_unavailable"
    vector = build_l2_vlan_feature_vector_v2(tmp_path, evidence)
    assert diagnose_l2_vlan_x3_r3_v2(
        vector, location_node="sw1", affected_resource="eth3:vlan10"
    )["status"] == "insufficient_evidence"
    restore_vlan_not_allowed_on_trunk(SCENARIO, tmp_path / "mutation", executor=network)


def test_orchestrator_completes_restores_and_can_replay_recovery(tmp_path: Path) -> None:
    network = FakeNetwork()

    def baseline(_: Path) -> dict[str, object]:
        return {
            "command": ["bash", "fake"],
            "return_code": 0 if not network.faulted else 1,
            "stdout": "",
            "stderr": "",
            "timestamp_utc": utc_now(),
        }

    result = run_x3_r3_experiment(
        SCENARIO,
        tmp_path / "runs",
        ROOT / "unused.sh",
        baseline_validator=baseline,
        fault_injector=lambda scenario, output: inject_vlan_not_allowed_on_trunk(
            scenario, output, executor=network
        ),
        fault_restorer=lambda scenario, output: restore_vlan_not_allowed_on_trunk(
            scenario, output, executor=network
        ),
        evidence_collector=lambda output, scenario: collect_vlan_not_allowed_on_trunk_evidence_v4(
            output, scenario, executor=network
        ),
        experiment_id="x3-r3-unit-cycle",
    )
    assert result["status"] == "COMPLETED"
    assert result["restoration_confirmed"] is True
    assert result["baseline_valid_after"] is True
    assert network.faulted is False
    recovered = recover_x3_r3_experiment(
        SCENARIO,
        Path(str(result["experiment_directory"])),
        ROOT / "unused.sh",
        baseline_validator=baseline,
        fault_restorer=lambda scenario, output: restore_vlan_not_allowed_on_trunk(
            scenario, output, executor=network
        ),
    )
    assert recovered["status"] == "RECOVERY_CONFIRMED"


def test_existing_mutation_output_is_rejected(tmp_path: Path) -> None:
    mutation = tmp_path / "mutation"
    mutation.mkdir()
    (mutation / "preconditions.json").write_text("{}", encoding="utf-8")
    with pytest.raises(X3VlanNotAllowedOnTrunkError, match="already exists"):
        inject_vlan_not_allowed_on_trunk(SCENARIO, mutation, executor=FakeNetwork())
