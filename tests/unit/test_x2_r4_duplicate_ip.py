from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Sequence

import pytest

from src.collection.addressing_state_collector import build_feature_vector_v2
from src.collection.duplicate_ip_state_collector import collect_duplicate_ip_evidence_v4
from src.expansion.x2_addressing import X2AddressingError
from src.expansion.x2_duplicate_ip import load_duplicate_ip_scenario
from src.fault_injection.duplicate_ip import inject_duplicate_ip, restore_duplicate_ip
from src.fault_injection.phase6_common import utc_now
from src.orchestration.x2_duplicate_ip_experiment_runner import run_x2_r4_experiment
from src.rules.addressing_rule_engine_x2_r4 import diagnose_addressing_v2

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/expansion/X2_R4_DUPLICATE_IP.yml"


class FakeNetwork:
    def __init__(self) -> None:
        self.claimant = False
        self.raise_after_mutation = False

    def result(self, container: str, command: Sequence[str], rc: int = 0, stdout: str = "", stderr: str = "") -> dict[str, object]:
        return {"command": ["docker", "exec", container, *command], "return_code": rc, "stdout": stdout, "stderr": stderr, "timestamp_utc": utc_now()}

    def __call__(self, container: str, command: Sequence[str]) -> dict[str, object]:
        parts = list(command)
        if parts[:6] == ["ip", "-j", "-4", "addr", "show", "dev"]:
            return self.result(container, command, stdout=json.dumps([{"ifname": parts[6], "addr_info": [{"family": "inet", "local": "10.20.1.10", "prefixlen": 24}]}]))
        if parts == ["ip", "-j", "route", "show", "default"]:
            return self.result(container, command, stdout=json.dumps([{"dst": "default", "gateway": "10.20.1.1", "dev": "eth1"}]))
        if parts[:2] == ["sh", "-c"] and parts[2].startswith("ip -j addr"):
            return self.result(container, command, stdout=(json.dumps([{"addr_info": [{"local": "10.20.1.10"}]}]) if self.claimant else ""))
        if parts[:3] == ["sh", "-eu", "-c"]:
            if "ip link add x2r4dup0" in parts[3]:
                self.claimant = True
                if self.raise_after_mutation:
                    self.raise_after_mutation = False
                    raise RuntimeError("simulated crash after mutation")
            elif "ip link del x2r4dup0" in parts[3]:
                self.claimant = False
            return self.result(container, command)
        if parts[:3] == ["ip", "netns", "exec"]:
            output = "ARP, Reply 10.20.1.10 is-at 02:42:0A:14:01:10\nARP, Reply 10.20.1.10 is-at 02:42:0A:14:01:EE\n"
            return self.result(container, command, stdout=output)
        raise AssertionError(f"unexpected command: {container} {parts}")


class MissingCaptureNetwork(FakeNetwork):
    def __call__(self, container: str, command: Sequence[str]) -> dict[str, object]:
        if list(command)[:3] == ["ip", "netns", "exec"]:
            return self.result(container, command, rc=127, stderr="tcpdump unavailable")
        return super().__call__(container, command)


def fault_vector(tmp_path: Path, network: FakeNetwork) -> dict[str, object]:
    inject_duplicate_ip(SCENARIO, tmp_path / "mutation", executor=network)
    evidence = collect_duplicate_ip_evidence_v4(tmp_path, SCENARIO, executor=network)
    return build_feature_vector_v2(tmp_path, evidence)


def test_scenario_binds_exact_duplicate_identity() -> None:
    binding = load_duplicate_ip_scenario(SCENARIO)
    assert binding.topology_id == "X2_TOP_01_ADDRESSING"
    assert binding.expected_interface == "10.20.1.10/24"
    assert binding.duplicate_mac == "02:42:0a:14:01:ee"


def test_injection_and_idempotent_restoration(tmp_path: Path) -> None:
    network = FakeNetwork()
    mutation = tmp_path / "mutation"
    assert inject_duplicate_ip(SCENARIO, mutation, executor=network)["status"] == "FAULT_CONFIRMED"
    assert network.claimant is True
    first = restore_duplicate_ip(SCENARIO, mutation, executor=network)
    assert first["status"] == "RESTORATION_CONFIRMED"
    assert network.claimant is False
    assert restore_duplicate_ip(SCENARIO, mutation, executor=network) == first


def test_crash_after_mutation_restores(tmp_path: Path) -> None:
    network = FakeNetwork(); network.raise_after_mutation = True
    with pytest.raises(Exception, match="executor raised an exception"):
        inject_duplicate_ip(SCENARIO, tmp_path / "mutation", executor=network)
    assert network.claimant is False


def test_unjournaled_restoration_rejected(tmp_path: Path) -> None:
    with pytest.raises(X2AddressingError, match="durable recovery intent"):
        restore_duplicate_ip(SCENARIO, tmp_path / "mutation", executor=FakeNetwork())


def test_evidence_requires_active_and_temporal_signals(tmp_path: Path) -> None:
    network = FakeNetwork(); vector = fault_vector(tmp_path, network)
    values = vector["values"]
    assert values["duplicate_address_detected"]["value"] is True
    assert values["duplicate_address_mac_churn_detected"]["value"] is True
    restore_duplicate_ip(SCENARIO, tmp_path / "mutation", executor=network)


def test_rule_diagnoses_exact_duplicate_signature(tmp_path: Path) -> None:
    network = FakeNetwork(); vector = fault_vector(tmp_path, network)
    result = diagnose_addressing_v2(vector, source_node="hosta", affected_resource="eth1")
    assert result["prediction"]["fault_type"] == "duplicate_ip"
    assert result["explanation_refs"] == ["rule:R_X2_ADDRESSING_004"]
    restore_duplicate_ip(SCENARIO, tmp_path / "mutation", executor=network)


@pytest.mark.parametrize("feature", ["duplicate_address_detected", "duplicate_address_mac_churn_detected"])
def test_one_positive_duplicate_signal_is_not_enough(tmp_path: Path, feature: str) -> None:
    network = FakeNetwork(); vector = fault_vector(tmp_path, network)
    incomplete = copy.deepcopy(vector)
    incomplete["values"][feature]["value"] = False
    assert diagnose_addressing_v2(incomplete, source_node="hosta", affected_resource="eth1")["status"] == "abstained"
    restore_duplicate_ip(SCENARIO, tmp_path / "mutation", executor=network)


def test_missing_temporal_evidence_is_insufficient(tmp_path: Path) -> None:
    network = FakeNetwork(); vector = fault_vector(tmp_path, network)
    missing = copy.deepcopy(vector)
    missing["values"]["duplicate_address_mac_churn_detected"] = {"value": None, "availability": "collection_unavailable"}
    assert diagnose_addressing_v2(missing, source_node="hosta", affected_resource="eth1")["status"] == "insufficient_evidence"
    restore_duplicate_ip(SCENARIO, tmp_path / "mutation", executor=network)


def test_missing_capture_tool_is_collection_unavailable(tmp_path: Path) -> None:
    network = MissingCaptureNetwork()
    inject_duplicate_ip(SCENARIO, tmp_path / "mutation", executor=network)
    evidence = collect_duplicate_ip_evidence_v4(tmp_path, SCENARIO, executor=network)
    values = evidence["observations"]
    assert values["duplicate_address_detected"]["availability"] == "collection_unavailable"
    assert values["duplicate_address_detected"]["value"] is None
    vector = build_feature_vector_v2(tmp_path, evidence)
    assert diagnose_addressing_v2(vector, source_node="hosta", affected_resource="eth1")["status"] == "insufficient_evidence"
    restore_duplicate_ip(SCENARIO, tmp_path / "mutation", executor=network)


def test_wrong_ip_signature_remains_preserved(tmp_path: Path) -> None:
    network = FakeNetwork(); vector = fault_vector(tmp_path, network)
    values = vector["values"]
    values["source_address_matches_expected"]["value"] = False
    values["source_prefix_matches_expected"]["value"] = True
    values["source_default_route_present"]["value"] = True
    values["duplicate_address_detected"]["value"] = False
    values["duplicate_address_mac_churn_detected"]["value"] = False
    assert diagnose_addressing_v2(vector, source_node="hosta", affected_resource="eth1")["prediction"]["fault_type"] == "wrong_ip_address"
    restore_duplicate_ip(SCENARIO, tmp_path / "mutation", executor=network)


def test_orchestrator_completes_and_restores(tmp_path: Path) -> None:
    network = FakeNetwork()

    def baseline(_: Path) -> dict[str, object]:
        return {"command": ["bash", "fake"], "return_code": 0 if not network.claimant else 1, "stdout": "", "stderr": "", "timestamp_utc": utc_now()}

    result = run_x2_r4_experiment(
        SCENARIO, tmp_path / "runs", ROOT / "unused.sh",
        baseline_validator=baseline,
        fault_injector=lambda scenario, output: inject_duplicate_ip(scenario, output, executor=network),
        fault_restorer=lambda scenario, output: restore_duplicate_ip(scenario, output, executor=network),
        evidence_collector=lambda output, scenario: collect_duplicate_ip_evidence_v4(output, scenario, executor=network),
        experiment_id="x2-r4-unit-cycle",
    )
    assert result["status"] == "COMPLETED"
    assert result["release_id"] == "X2_R4_DUPLICATE_IP"
    assert result["topology_id"] == "X2_TOP_01_ADDRESSING"
    assert result["restoration_confirmed"] is True
    assert network.claimant is False
