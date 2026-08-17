from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Sequence

import pytest

from src.collection.addressing_state_collector import (
    build_feature_vector_v2,
    collect_wrong_ip_evidence_v4,
)
from src.contracts.expansion import (
    validate_diagnosis_result_v2,
    validate_evidence_v4,
    validate_feature_vector_v2,
    validate_topology_context_v1,
)
from src.expansion.x2_addressing import X2AddressingError, load_wrong_ip_scenario
from src.fault_injection.phase6_common import utc_now
from src.fault_injection.wrong_ip_address import (
    inject_wrong_ip_address,
    restore_wrong_ip_address,
)
from src.orchestration.x2_addressing_experiment_runner import run_x2_r1_experiment
from src.rules.addressing_rule_engine_v2 import diagnose_wrong_ip_v2


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/expansion/X2_R1_WRONG_IP_ADDRESS.yml"
CATALOG = ROOT / "plans/expansion/X1_FEATURE_CATALOG_V1.json"
CONTEXT = ROOT / "labs/topologies/x2_r1_addressing/topology_context_v1.json"


class FakeNetwork:
    def __init__(self) -> None:
        self.address = "10.20.1.10"
        self.prefix_length = 24
        self.route_present = True
        self.raise_after_mutation = False

    def _result(
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

    def __call__(
        self,
        container: str,
        command: Sequence[str],
    ) -> dict[str, object]:
        parts = list(command)
        if parts[:6] == ["ip", "-j", "-4", "addr", "show", "dev"]:
            payload = [
                {
                    "ifname": parts[6],
                    "addr_info": [
                        {
                            "family": "inet",
                            "local": self.address,
                            "prefixlen": self.prefix_length,
                        }
                    ],
                }
            ]
            return self._result(container, command, stdout=json.dumps(payload))
        if parts == ["ip", "-j", "route", "show", "default"]:
            payload = (
                [{"dst": "default", "gateway": "10.20.1.1", "dev": "eth1"}]
                if self.route_present
                else []
            )
            return self._result(container, command, stdout=json.dumps(payload))
        if parts[:1] == ["ping"]:
            address = parts[-1]
            reachable = (
                address in {"10.20.1.1", "10.20.2.10"}
                or (
                    container == "clab-x2r1-r1"
                    and address == self.address
                    and self.address == "10.20.1.11"
                )
            )
            return self._result(container, command, return_code=0 if reachable else 1)
        if parts[:2] == ["sh", "-c"] and "ip neigh flush" in parts[2]:
            payload = [
                {
                    "dst": "10.20.1.11",
                    "lladdr": "02:00:00:00:01:11",
                    "state": "REACHABLE",
                }
            ]
            return self._result(container, command, stdout=json.dumps(payload))
        if parts[:3] == ["sh", "-eu", "-c"]:
            shell = parts[3]
            if "ip addr del 10.20.1.10/24" in shell:
                self.address = "10.20.1.11"
                self.route_present = True
                if self.raise_after_mutation:
                    self.raise_after_mutation = False
                    raise RuntimeError("simulated crash after real mutation")
                return self._result(container, command)
            if "ip addr del 10.20.1.11/24" in shell:
                self.address = "10.20.1.10"
                self.route_present = True
                return self._result(container, command)
        raise AssertionError(f"Unexpected command: {container} {parts}")


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_scenario_freezes_disjoint_wrong_ip_identity() -> None:
    binding = load_wrong_ip_scenario(SCENARIO)
    assert binding.expected_interface == "10.20.1.10/24"
    assert binding.wrong_interface == "10.20.1.11/24"
    assert binding.expected_prefix == "10.20.1.0/24"
    assert binding.expected_gateway == "10.20.1.1"


def test_topology_context_is_real_and_contract_valid() -> None:
    context = _load(CONTEXT)
    validate_topology_context_v1(context, repository_root=ROOT)
    assert context["context_id"] == "x2_top_01_addressing_context_v1"
    assert context["capabilities"] == [
        "ipv4_addressing",
        "active_neighbor_probe",
    ]


def test_injection_and_restoration_are_exact_and_idempotent(tmp_path: Path) -> None:
    network = FakeNetwork()
    mutation = tmp_path / "mutation"
    injection = inject_wrong_ip_address(SCENARIO, mutation, executor=network)
    assert injection["status"] == "FAULT_CONFIRMED"
    assert network.address == "10.20.1.11"
    restoration = restore_wrong_ip_address(SCENARIO, mutation, executor=network)
    assert restoration["status"] == "RESTORATION_CONFIRMED"
    assert network.address == "10.20.1.10"
    assert restore_wrong_ip_address(SCENARIO, mutation, executor=network) == restoration


def test_exception_after_real_mutation_triggers_best_effort_restoration(
    tmp_path: Path,
) -> None:
    network = FakeNetwork()
    network.raise_after_mutation = True
    mutation = tmp_path / "mutation"
    with pytest.raises(Exception, match="executor raised an exception"):
        inject_wrong_ip_address(SCENARIO, mutation, executor=network)
    assert network.address == "10.20.1.10"
    assert (mutation / "recovery_intent.json").is_file()
    restoration = _load(mutation / "restoration_record.json")
    assert restoration["status"] == "RESTORATION_CONFIRMED"
    assert not (mutation / "injection_record.json").exists()


def test_restorer_rejects_unjournaled_calls(tmp_path: Path) -> None:
    with pytest.raises(X2AddressingError, match="durable recovery intent"):
        restore_wrong_ip_address(SCENARIO, tmp_path / "mutation", executor=FakeNetwork())


def test_native_evidence_v4_has_real_hash_bound_provenance(tmp_path: Path) -> None:
    network = FakeNetwork()
    mutation = tmp_path / "mutation"
    inject_wrong_ip_address(SCENARIO, mutation, executor=network)
    evidence = collect_wrong_ip_evidence_v4(tmp_path, SCENARIO, executor=network)
    catalog = _load(CATALOG)
    validate_evidence_v4(evidence, catalog, repository_root=ROOT)
    observed = evidence["observations"]
    assert observed["source_address_matches_expected"]["value"] is False
    assert observed["source_prefix_matches_expected"]["value"] is True
    assert observed["source_default_route_present"]["value"] is True
    assert observed["duplicate_address_detected"]["value"] is False
    assert (
        observed["duplicate_address_mac_churn_detected"]["availability"]
        == "not_requested"
    )
    for artifact in evidence["collector_runs"][0]["raw_artifacts"]:
        path = tmp_path / artifact["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    restore_wrong_ip_address(SCENARIO, mutation, executor=network)


def test_feature_vector_and_rule_produce_only_wrong_ip(tmp_path: Path) -> None:
    network = FakeNetwork()
    mutation = tmp_path / "mutation"
    inject_wrong_ip_address(SCENARIO, mutation, executor=network)
    evidence = collect_wrong_ip_evidence_v4(tmp_path, SCENARIO, executor=network)
    vector = build_feature_vector_v2(tmp_path, evidence)
    validate_feature_vector_v2(vector, _load(CATALOG), repository_root=ROOT)
    diagnosis = diagnose_wrong_ip_v2(
        vector,
        source_node="hosta",
        affected_resource="eth1",
    )
    validate_diagnosis_result_v2(diagnosis, repository_root=ROOT)
    assert diagnosis["status"] == "diagnosed"
    assert diagnosis["prediction"]["fault_type"] == "wrong_ip_address"
    assert diagnosis["ranked_candidates"] == [diagnosis["prediction"]]
    restore_wrong_ip_address(SCENARIO, mutation, executor=network)


def test_rule_abstains_on_wrong_mask_confounder(tmp_path: Path) -> None:
    network = FakeNetwork()
    mutation = tmp_path / "mutation"
    inject_wrong_ip_address(SCENARIO, mutation, executor=network)
    evidence = collect_wrong_ip_evidence_v4(tmp_path, SCENARIO, executor=network)
    vector = build_feature_vector_v2(tmp_path, evidence)
    conflicting = copy.deepcopy(vector)
    conflicting["values"]["source_address_matches_expected"]["value"] = True
    conflicting["values"]["source_prefix_matches_expected"]["value"] = False
    diagnosis = diagnose_wrong_ip_v2(
        conflicting,
        source_node="hosta",
        affected_resource="eth1",
    )
    assert diagnosis["status"] == "abstained"
    assert diagnosis["prediction"] is None
    restore_wrong_ip_address(SCENARIO, mutation, executor=network)


def test_rule_reports_insufficient_evidence_without_guessing(tmp_path: Path) -> None:
    network = FakeNetwork()
    mutation = tmp_path / "mutation"
    inject_wrong_ip_address(SCENARIO, mutation, executor=network)
    evidence = collect_wrong_ip_evidence_v4(tmp_path, SCENARIO, executor=network)
    vector = build_feature_vector_v2(tmp_path, evidence)
    missing = copy.deepcopy(vector)
    missing["values"]["duplicate_address_detected"] = {
        "value": None,
        "availability": "collection_unavailable",
    }
    diagnosis = diagnose_wrong_ip_v2(
        missing,
        source_node="hosta",
        affected_resource="eth1",
    )
    assert diagnosis["status"] == "insufficient_evidence"
    assert diagnosis["prediction"] is None
    restore_wrong_ip_address(SCENARIO, mutation, executor=network)


def test_orchestrator_runs_diagnosis_then_restores_baseline(tmp_path: Path) -> None:
    network = FakeNetwork()

    def baseline(_: Path) -> dict[str, object]:
        return {
            "command": ["bash", "fake"],
            "return_code": 0 if network.address == "10.20.1.10" else 1,
            "stdout": "",
            "stderr": "",
            "timestamp_utc": utc_now(),
        }

    result = run_x2_r1_experiment(
        SCENARIO,
        tmp_path / "experiments",
        ROOT / "unused.sh",
        baseline_validator=baseline,
        fault_injector=lambda scenario, output: inject_wrong_ip_address(
            scenario, output, executor=network
        ),
        fault_restorer=lambda scenario, output: restore_wrong_ip_address(
            scenario, output, executor=network
        ),
        evidence_collector=lambda output, scenario: collect_wrong_ip_evidence_v4(
            output, scenario, executor=network
        ),
        experiment_id="x2-r1-unit-cycle",
    )
    assert result["status"] == "COMPLETED"
    assert result["baseline_valid_after"] is True
    assert result["restoration_confirmed"] is True
    assert result["diagnosis_created"] is True
    assert result["dataset_row_created"] is False
    assert result["model_operation_performed"] is False
    assert network.address == "10.20.1.10"

