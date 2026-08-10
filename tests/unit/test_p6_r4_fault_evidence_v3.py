import json
from pathlib import Path
from typing import Sequence

import pytest

from src.collection.evidence_collector_v3 import (
    collect_evidence_v3,
    load_observation_profile_v2,
)
from src.verification.fault_evidence_v3 import (
    FaultEvidenceV3VerificationError,
    verify_fault_evidence_v3,
)


TIMESTAMP = "2026-08-10T08:00:00+00:00"
SCENARIOS = {
    "wrong_default_gateway": Path(
        "scenarios/routing/C3_WRONG_DEFAULT_GATEWAY_P6_TOP01.yml"
    ),
    "interface_down": Path(
        "scenarios/routing/C4_INTERFACE_DOWN_P6_TOP01.yml"
    ),
    "acl_block": Path(
        "scenarios/routing/C5_ACL_BLOCK_P6_TOP01.yml"
    ),
}


class FaultExecutor:
    def __init__(self, fault_type: str, profile) -> None:
        self.fault_type = fault_type
        self.profile = profile

    def __call__(
        self,
        container: str,
        command: Sequence[str],
    ) -> dict[str, object]:
        arguments = list(command)
        return_code = 0
        stdout = ""
        if arguments[:4] == ["ip", "-j", "route", "show"]:
            if arguments[4:] == ["default"]:
                gateway = (
                    "10.10.1.254"
                    if self.fault_type == "wrong_default_gateway"
                    else self.profile.source_gateway_address
                )
                stdout = json.dumps([{
                    "dst": "default",
                    "gateway": gateway,
                    "dev": "eth1",
                }])
            else:
                stdout = json.dumps(
                    []
                    if self.fault_type == "interface_down"
                    else [{
                        "dst": self.profile.destination_prefix,
                        "gateway": self.profile.expected_next_hop,
                        "dev": self.profile.observer_egress_interface,
                    }]
                )
        elif arguments[:4] == ["ip", "-j", "link", "show"]:
            stdout = json.dumps([{
                "ifname": self.profile.observer_egress_interface,
                "operstate": (
                    "DOWN"
                    if self.fault_type == "interface_down"
                    else "UP"
                ),
            }])
        elif arguments[0] == "iptables":
            stdout = "-P FORWARD ACCEPT\n"
            if self.fault_type == "acl_block":
                stdout += (
                    "-A FORWARD -s 10.10.1.10/32 "
                    "-d 10.10.2.10/32 -p icmp -m comment "
                    "--comment IND-P6-R4-ACL-TOP01 -j DROP\n"
                )
        elif arguments[0] == "ping":
            destination = arguments[-1]
            failed = (
                container == self.profile.source_container
                and destination == self.profile.destination_address
            ) or (
                self.fault_type == "interface_down"
                and container == self.profile.route_observer_container
                and destination == self.profile.expected_next_hop
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
def test_accepts_three_complete_fault_runtime_signatures(
    tmp_path: Path,
    fault_type: str,
) -> None:
    scenario_path = SCENARIOS[fault_type]
    profile = load_observation_profile_v2(scenario_path)
    experiment = tmp_path / fault_type
    collect_evidence_v3(
        experiment,
        profile,
        executor=FaultExecutor(fault_type, profile),
    )

    summary = verify_fault_evidence_v3(experiment, scenario_path)

    assert summary["status"] == "P6_R4_FAULT_EVIDENCE_V3_VERIFIED"
    assert summary["fault_type"] == fault_type
    assert summary["feature_count"] == 10
    expected_structural = 2 if fault_type == "interface_down" else 0
    assert summary["observed_feature_count"] == 10 - expected_structural
    assert summary["structural_unavailable_count"] == expected_structural
    assert summary["raw_artifact_count"] == (
        8 if fault_type == "interface_down" else 9
    )

    evidence = json.loads(
        (experiment / "parsed/evidence.json").read_text(
            encoding="utf-8"
        )
    )
    if fault_type == "interface_down":
        assert evidence["route_next_hop_on_observer"] is None
        for name in (
            "route_next_hop_matches_expected",
            "route_next_hop_reachable_from_observer",
        ):
            assert evidence["features"][name] is None
            assert evidence["availability"][name] == (
                "structurally_unavailable"
            )
            assert evidence["probes"][name]["raw_artifact"] is None


def test_rejects_tampered_fault_raw_artifact(tmp_path: Path) -> None:
    fault_type = "acl_block"
    scenario_path = SCENARIOS[fault_type]
    profile = load_observation_profile_v2(scenario_path)
    collect_evidence_v3(
        tmp_path,
        profile,
        executor=FaultExecutor(fault_type, profile),
    )
    raw_path = tmp_path / "raw/v3/observer_forward_policy_v3.json"
    raw_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(
        FaultEvidenceV3VerificationError,
        match="SHA-256 mismatch",
    ):
        verify_fault_evidence_v3(tmp_path, scenario_path)
