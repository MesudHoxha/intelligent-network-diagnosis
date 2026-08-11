from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import pytest

from src.collection.evidence_collector_v3 import (
    collect_evidence_v3,
    load_observation_profile_v2,
)
from src.dataset.contract_v3 import build_dataset_row_v3
from src.fault_injection.phase6_registry import (
    PHASE6_INJECTORS,
    PHASE6_RESTORERS,
)
from src.fault_injection.phase6_route_faults import (
    inject_missing_static_route,
    inject_wrong_next_hop_v3,
    restore_missing_static_route,
    restore_wrong_next_hop_v3,
)
from src.orchestration.phase6_experiment_runner import run_phase6_experiment
from src.verification.fault_evidence_v3 import verify_fault_evidence_v3


TIMESTAMP = "2026-08-10T08:00:00+00:00"
SCENARIOS = {
    "missing_static_route": Path(
        "scenarios/phase6/E01_C1_MISSING_STATIC_ROUTE.yml"
    ),
    "wrong_next_hop": Path("scenarios/phase6/E01_C2_WRONG_NEXT_HOP.yml"),
}


class RouteFaultLab:
    def __init__(self) -> None:
        self.default_gateway = "10.10.1.1"
        self.expected_next_hop = "10.10.12.2"
        self.wrong_next_hop = "10.10.12.254"
        self.route: tuple[str, str] | None = (self.expected_next_hop, "eth2")
        self.mutations: list[list[str]] = []

    def _destination_reachable(self) -> bool:
        return self.route == (self.expected_next_hop, "eth2")

    def __call__(
        self, container: str, command: Sequence[str]
    ) -> dict[str, object]:
        arguments = list(command)
        return_code = 0
        stdout = ""
        stderr = ""
        if arguments == ["ip", "-j", "route", "show", "default"]:
            stdout = json.dumps(
                [
                    {
                        "dst": "default",
                        "gateway": self.default_gateway,
                        "dev": "eth1",
                    }
                ]
            )
        elif arguments[:4] == ["ip", "-j", "route", "get"]:
            stdout = json.dumps(
                [
                    {
                        "dst": arguments[4],
                        "gateway": self.default_gateway,
                        "dev": "eth1",
                    }
                ]
            )
        elif arguments[:5] == ["ip", "-j", "route", "show", "exact"]:
            stdout = json.dumps(
                []
                if self.route is None
                else [
                    {
                        "dst": arguments[5],
                        "gateway": self.route[0],
                        "dev": self.route[1],
                    }
                ]
            )
        elif arguments[:4] == ["ip", "-j", "link", "show"]:
            stdout = json.dumps([{"ifname": "eth2", "operstate": "UP"}])
        elif arguments[0] == "ping":
            destination = arguments[-1]
            if container == "clab-top01-hosta":
                reachable = (
                    True
                    if destination == self.default_gateway
                    else self._destination_reachable()
                )
            elif container == "clab-top01-r1":
                reachable = destination == self.expected_next_hop
            else:
                reachable = True
            return_code = 0 if reachable else 1
            stdout = "reachable" if reachable else ""
        elif arguments[0] == "iptables":
            stdout = "-P FORWARD ACCEPT\n"
        elif arguments[:4] == ["ip", "route", "del", "10.10.2.0/24"]:
            if self.route != (self.expected_next_hop, "eth2"):
                return_code = 2
                stderr = "exact route not found"
            else:
                self.route = None
            self.mutations.append(arguments)
        elif arguments[:4] == ["ip", "route", "replace", "10.10.2.0/24"]:
            self.route = (arguments[5], arguments[7])
            self.mutations.append(arguments)
        else:
            raise AssertionError(f"Unexpected command: {arguments}")
        return {
            "command": ["docker", "exec", container, *arguments],
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "timestamp_utc": TIMESTAMP,
        }


@pytest.mark.parametrize(
    ("fault_type", "injector", "restorer"),
    [
        (
            "missing_static_route",
            inject_missing_static_route,
            restore_missing_static_route,
        ),
        ("wrong_next_hop", inject_wrong_next_hop_v3, restore_wrong_next_hop_v3),
    ],
)
def test_route_fault_injection_and_exact_restoration(
    tmp_path: Path, fault_type: str, injector, restorer
) -> None:
    lab = RouteFaultLab()
    output = tmp_path / fault_type
    injection = injector(SCENARIOS[fault_type], output, executor=lab)
    assert injection["status"] == "FAULT_CONFIRMED"
    assert injection["mutation_applied"] is True
    assert not lab._destination_reachable()

    restoration = restorer(SCENARIOS[fault_type], output, executor=lab)
    assert restoration["status"] == "RESTORATION_CONFIRMED"
    assert lab.route == (lab.expected_next_hop, "eth2")
    assert lab._destination_reachable()


def test_phase6_registry_uses_versioned_route_faults() -> None:
    assert PHASE6_INJECTORS["missing_static_route"] is inject_missing_static_route
    assert PHASE6_INJECTORS["wrong_next_hop"] is inject_wrong_next_hop_v3
    assert PHASE6_RESTORERS["missing_static_route"] is restore_missing_static_route
    assert PHASE6_RESTORERS["wrong_next_hop"] is restore_wrong_next_hop_v3


class RouteEvidenceExecutor:
    def __init__(self, fault_type: str, profile) -> None:
        self.fault_type = fault_type
        self.profile = profile

    def __call__(
        self, container: str, command: Sequence[str]
    ) -> dict[str, object]:
        arguments = list(command)
        return_code = 0
        stdout = ""
        if arguments[:4] == ["ip", "-j", "route", "show"]:
            if arguments[4:] == ["default"]:
                stdout = json.dumps(
                    [
                        {
                            "dst": "default",
                            "gateway": self.profile.source_gateway_address,
                            "dev": "eth1",
                        }
                    ]
                )
            elif self.fault_type == "missing_static_route":
                stdout = "[]"
            else:
                stdout = json.dumps(
                    [
                        {
                            "dst": self.profile.destination_prefix,
                            "gateway": "10.10.12.254",
                            "dev": self.profile.observer_egress_interface,
                        }
                    ]
                )
        elif arguments[:4] == ["ip", "-j", "link", "show"]:
            stdout = json.dumps(
                [
                    {
                        "ifname": self.profile.observer_egress_interface,
                        "operstate": "UP",
                    }
                ]
            )
        elif arguments[0] == "iptables":
            stdout = "-P FORWARD ACCEPT\n"
        elif arguments[0] == "ping":
            destination = arguments[-1]
            failed = (
                container == self.profile.source_container
                and destination == self.profile.destination_address
            ) or (
                self.fault_type == "wrong_next_hop"
                and container == self.profile.route_observer_container
                and destination == "10.10.12.254"
            )
            return_code = 1 if failed else 0
            stdout = "" if failed else "reachable"
        else:
            raise AssertionError(f"Unexpected command: {arguments}")
        return {
            "command": ["docker", "exec", container, *arguments],
            "return_code": return_code,
            "stdout": stdout,
            "stderr": "",
            "timestamp_utc": TIMESTAMP,
        }


@pytest.mark.parametrize("fault_type", tuple(SCENARIOS))
def test_evidence_v3_verifier_accepts_c1_and_c2(
    tmp_path: Path, fault_type: str
) -> None:
    scenario_path = SCENARIOS[fault_type]
    profile = load_observation_profile_v2(scenario_path)
    experiment = tmp_path / fault_type
    collect_evidence_v3(
        experiment,
        profile,
        executor=RouteEvidenceExecutor(fault_type, profile),
    )
    summary = verify_fault_evidence_v3(experiment, scenario_path)
    assert summary["status"] == "P6_R5_FAULT_EVIDENCE_V3_VERIFIED"
    assert summary["fault_type"] == fault_type
    assert summary["structural_unavailable_count"] == (
        2 if fault_type == "missing_static_route" else 0
    )
    assert summary["raw_artifact_count"] == (
        8 if fault_type == "missing_static_route" else 9
    )


@pytest.mark.parametrize(
    ("scenario_path", "fault_type"),
    [
        (Path("scenarios/phase6/E01_N0_NO_FAULT.yml"), "no_fault"),
        (SCENARIOS["missing_static_route"], "missing_static_route"),
    ],
)
def test_phase6_experiment_runner_builds_clean_dataset_row_v3(
    tmp_path: Path,
    scenario_path: Path,
    fault_type: str,
) -> None:
    lab = RouteFaultLab()

    def baseline(_path: Path) -> dict[str, object]:
        return {
            "command": ["bash", "validate_baseline.sh"],
            "return_code": 0,
            "stdout": "baseline ok\n",
            "stderr": "",
            "timestamp_utc": TIMESTAMP,
        }

    def collector(directory: Path, profile):
        return collect_evidence_v3(directory, profile, executor=lab)

    def injector(_fault_type: str, scenario: Path, output: Path):
        return inject_missing_static_route(scenario, output, executor=lab)

    def restorer(_fault_type: str, scenario: Path, output: Path):
        return restore_missing_static_route(scenario, output, executor=lab)

    result = run_phase6_experiment(
        scenario_path,
        tmp_path / "raw",
        Path("validate_baseline.sh"),
        baseline_validator=baseline,
        fault_injector=injector,
        fault_restorer=restorer,
        evidence_collector=collector,
        experiment_id=f"experiment-{fault_type}",
    )
    experiment = Path(result["experiment_directory"])
    row = build_dataset_row_v3(experiment)
    assert result["status"] == "COMPLETED"
    assert result["diagnosis_created"] is False
    assert result["prediction_created"] is False
    assert result["metric_created"] is False
    assert row["schema_version"] == 3
    assert row["labels"]["fault_type"] == fault_type
    assert row["provenance"]["mask_id"] is None
    assert not any(
        (experiment / name).exists()
        for name in ("diagnosis", "prediction", "evaluation", "metrics")
    )
