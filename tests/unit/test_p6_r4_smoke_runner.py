import json
from pathlib import Path

import pytest

from src.orchestration import phase6_smoke_runner as runner
from src.orchestration.phase6_smoke_runner import (
    Phase6SmokeRunnerError,
    run_phase6_smoke,
)


SCENARIO = Path(
    "scenarios/routing/C3_WRONG_DEFAULT_GATEWAY_P6_TOP01.yml"
)
HEALTHY_SCENARIO = Path(
    "scenarios/routing/N0_NORMAL_OPERATION_P6_TOP01.yml"
)
BASELINE = Path(
    "labs/topologies/top01_routed/scripts/validate_baseline.sh"
)


def install_fakes(monkeypatch, *, diagnosis_fails: bool = False):
    calls: list[str] = []

    def baseline(_path: Path) -> dict[str, object]:
        calls.append("baseline")
        return {"return_code": 0}

    def inject(_fault_type, _scenario, output):
        calls.append("inject")
        output.mkdir(parents=True)
        record = {
            "mutation_applied": True,
            "status": "FAULT_CONFIRMED",
        }
        (output / "injection_record.json").write_text(
            json.dumps(record),
            encoding="utf-8",
        )
        return record

    def restore(_fault_type, _scenario, output):
        calls.append("restore")
        record = {"status": "RESTORATION_CONFIRMED"}
        (output / "restoration_record.json").write_text(
            json.dumps(record),
            encoding="utf-8",
        )
        return record

    def collect(output, _profile):
        calls.append("collect")
        (output / "parsed").mkdir(parents=True)
        (output / "parsed/evidence.json").write_text(
            "{}\n",
            encoding="utf-8",
        )
        return {}

    def fault_verify(_output, _scenario):
        calls.append("fault_verify")
        return {
            "status": "P6_R4_FAULT_EVIDENCE_V3_VERIFIED",
            "evidence_sha256": "a" * 64,
            "raw_artifact_count": 9,
        }

    def diagnose(_evidence):
        calls.append("diagnose")
        if diagnosis_fails:
            raise RuntimeError("synthetic diagnosis failure")
        return {
            "method": "rule_based_v3",
            "status": "DIAGNOSIS_PRODUCED",
            "matched_rules": ["R_P6_ROUTING_003"],
            "diagnosis": {
                "fault_type": "wrong_default_gateway",
                "location": "hosta",
                "affected_prefix": "10.10.2.0/24",
            },
        }

    def healthy_verify(_output, _scenario):
        calls.append("healthy_verify")
        return {
            "status": "P6_R3_HEALTHY_EVIDENCE_V3_VERIFIED",
            "evidence_sha256": "b" * 64,
        }

    monkeypatch.setattr(runner, "inject_fault", inject)
    monkeypatch.setattr(runner, "restore_fault", restore)
    monkeypatch.setattr(runner, "collect_evidence_v3", collect)
    monkeypatch.setattr(runner, "verify_fault_evidence_v3", fault_verify)
    monkeypatch.setattr(runner, "diagnose_evidence_v3", diagnose)
    monkeypatch.setattr(runner, "verify_healthy_evidence_v3", healthy_verify)
    return calls, baseline


def test_smoke_runner_restores_and_reverifies_healthy_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, baseline = install_fakes(monkeypatch)

    summary = run_phase6_smoke(
        SCENARIO,
        HEALTHY_SCENARIO,
        tmp_path / "smoke",
        BASELINE,
        baseline_validator=baseline,
    )

    assert summary["status"] == "P6_R4_NEW_CLASS_SMOKE_VERIFIED"
    assert summary["rule_exact_match"] is True
    assert summary["restoration_status"] == "RESTORATION_CONFIRMED"
    assert calls == [
        "baseline",
        "inject",
        "collect",
        "fault_verify",
        "diagnose",
        "restore",
        "baseline",
        "collect",
        "healthy_verify",
    ]


def test_smoke_runner_restores_before_reporting_fault_gate_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, baseline = install_fakes(
        monkeypatch,
        diagnosis_fails=True,
    )

    with pytest.raises(
        Phase6SmokeRunnerError,
        match="exact restoration",
    ):
        run_phase6_smoke(
            SCENARIO,
            HEALTHY_SCENARIO,
            tmp_path / "smoke",
            BASELINE,
            baseline_validator=baseline,
        )

    assert "restore" in calls
    assert calls.count("baseline") == 2
    assert calls[-1] == "healthy_verify"
