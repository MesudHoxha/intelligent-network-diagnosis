import json
from pathlib import Path
from typing import Sequence

import pytest

from src.collection.evidence_collector_v3 import (
    collect_evidence_v3,
    load_observation_profile_v2,
)
from src.contracts.evidence_v3 import EVIDENCE_V3_FEATURE_NAMES
from src.contracts.observation_profile_v2 import ObservationProfileV2
from src.verification.healthy_evidence_v3 import (
    EXPECTED_RAW_ARTIFACTS,
    HealthyEvidenceV3VerificationError,
    verify_healthy_evidence_v3,
)


SCENARIO_PATH = Path(
    "scenarios/routing/N0_NORMAL_OPERATION_P6_TOP01.yml"
)
TIMESTAMP = "2026-08-06T12:00:00+00:00"


class HealthyExecutor:
    def __init__(self, profile: ObservationProfileV2) -> None:
        self.profile = profile

    def __call__(
        self,
        container: str,
        command: Sequence[str],
    ) -> dict[str, object]:
        arguments = list(command)
        stdout = ""
        if arguments[:4] == ["ip", "-j", "route", "show"]:
            if arguments[4:] == ["default"]:
                stdout = json.dumps([{
                    "dst": "default",
                    "gateway": self.profile.source_gateway_address,
                    "dev": "eth1",
                }])
            else:
                stdout = json.dumps([{
                    "dst": self.profile.destination_prefix,
                    "gateway": self.profile.expected_next_hop,
                    "dev": self.profile.observer_egress_interface,
                }])
        elif arguments[:4] == ["ip", "-j", "link", "show"]:
            stdout = json.dumps([{
                "ifname": self.profile.observer_egress_interface,
                "operstate": "UP",
            }])
        elif arguments[0] == "iptables":
            stdout = "-P FORWARD ACCEPT\n"
        elif arguments[0] == "ping":
            stdout = "healthy ping"
        else:
            raise AssertionError(f"Unexpected command: {arguments}")
        return {
            "command": ["docker", "exec", container, *arguments],
            "return_code": 0,
            "stdout": stdout,
            "stderr": "",
            "timestamp_utc": TIMESTAMP,
        }


@pytest.fixture
def healthy_runtime(tmp_path: Path) -> tuple[Path, Path]:
    profile = load_observation_profile_v2(SCENARIO_PATH)
    collect_evidence_v3(
        tmp_path,
        profile,
        executor=HealthyExecutor(profile),
    )
    return tmp_path, SCENARIO_PATH


def test_reviewed_profile_and_toolchain_declarations() -> None:
    profile = load_observation_profile_v2(SCENARIO_PATH)

    assert profile.schema_version == 2
    assert profile.topology_id == "TOP_01"
    assert profile.source_node == "hosta"
    assert profile.source_gateway_address == "10.10.1.1"
    assert profile.observer_egress_interface == "eth2"
    assert profile.flow_protocol == "icmp"

    dockerfile = Path("labs/images/ind-linux/Dockerfile").read_text(
        encoding="utf-8"
    )
    profile_setup = Path(
        "labs/topologies/top01_routed/scripts/"
        "prepare_p6_r3_profile.sh"
    ).read_text(encoding="utf-8")
    assert "        iptables \\\n" in dockerfile
    normalized_setup = " ".join(
        profile_setup.replace("\\\n", " ").split()
    )
    assert (
        'ip route replace default via "$EXPECTED_GATEWAY" '
        'dev "$SOURCE_INTERFACE"'
        in normalized_setup
    )


def test_accepts_complete_healthy_runtime_artifacts(
    healthy_runtime: tuple[Path, Path],
) -> None:
    experiment_directory, scenario_path = healthy_runtime

    summary = verify_healthy_evidence_v3(
        experiment_directory,
        scenario_path,
    )

    assert summary["status"] == "P6_R3_HEALTHY_EVIDENCE_V3_VERIFIED"
    assert summary["feature_count"] == len(EVIDENCE_V3_FEATURE_NAMES)
    assert summary["observed_feature_count"] == 10
    assert summary["raw_artifact_count"] == 9
    assert set(summary["raw_artifact_sha256"]) == (
        EXPECTED_RAW_ARTIFACTS
    )


def test_rejects_nonhealthy_observed_feature(
    healthy_runtime: tuple[Path, Path],
) -> None:
    experiment_directory, scenario_path = healthy_runtime
    evidence_path = experiment_directory / "parsed/evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["features"]["destination_reachable"] = False
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        HealthyEvidenceV3VerificationError,
        match="healthy signature",
    ):
        verify_healthy_evidence_v3(experiment_directory, scenario_path)


def test_rejects_tampered_raw_artifact(
    healthy_runtime: tuple[Path, Path],
) -> None:
    experiment_directory, scenario_path = healthy_runtime
    raw_path = experiment_directory / (
        "raw/v3/source_destination_ping_v3.json"
    )
    raw_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(
        HealthyEvidenceV3VerificationError,
        match="SHA-256 mismatch",
    ):
        verify_healthy_evidence_v3(experiment_directory, scenario_path)


def test_rejects_collector_status_count_drift(
    healthy_runtime: tuple[Path, Path],
) -> None:
    experiment_directory, scenario_path = healthy_runtime
    status_path = experiment_directory / "collector_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["probe_artifact_count"] = 8
    status_path.write_text(
        json.dumps(status, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        HealthyEvidenceV3VerificationError,
        match="probe_artifact_count",
    ):
        verify_healthy_evidence_v3(experiment_directory, scenario_path)
