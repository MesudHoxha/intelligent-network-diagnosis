from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from typing import Sequence

import pytest

from src.fault_injection.phase6_route_faults import (
    inject_missing_static_route,
    restore_missing_static_route,
)
from src.ml import baseline
from src.ml.baseline import (
    ACCEPTED_MODEL_SHA256,
    ACCEPTED_SELECTION_SHA256,
    MLBaselineError,
    validate_frozen_pipeline,
)
from src.orchestration.phase6_experiment_runner import (
    Phase6ExperimentRunnerError,
    recover_phase6_experiment,
    run_phase6_experiment,
)
from src.runtime import subprocesses
from tests.unit.test_p4_r1_ml_baseline import (
    SELECTION_SCHEMA,
    freeze_pipeline,
)
from tests.unit.test_p6_r5_route_faults import RouteFaultLab


ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "scenarios/phase6/E01_C1_MISSING_STATIC_ROUTE.yml"


class PostconditionExceptionLab:
    def __init__(self) -> None:
        self.lab = RouteFaultLab()
        self.fail_next_postcondition = False

    def __call__(
        self,
        container: str,
        command: Sequence[str],
    ) -> dict[str, object]:
        arguments = list(command)
        if (
            self.fail_next_postcondition
            and arguments[:5]
            == ["ip", "-j", "route", "show", "exact"]
        ):
            self.fail_next_postcondition = False
            raise RuntimeError("synthetic exception before injection record")
        result = self.lab(container, arguments)
        if arguments[:4] == [
            "ip",
            "route",
            "del",
            "10.10.2.0/24",
        ] and result["return_code"] == 0:
            self.fail_next_postcondition = True
        return result


def test_timeout_is_bounded_and_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["docker", "ps"],
            timeout=3,
            output="partial stdout",
            stderr="partial stderr",
        )

    monkeypatch.setattr(subprocesses.subprocess, "run", timeout)
    result = subprocesses.run_capture(
        ["docker", "ps"],
        timeout_seconds=3,
    )

    assert result.returncode == 124
    assert result.stdout == "partial stdout"
    assert "partial stderr" in result.stderr
    assert "timed out after 3 seconds" in result.stderr


def test_runner_restores_when_exception_precedes_injection_record(
    tmp_path: Path,
) -> None:
    executor = PostconditionExceptionLab()

    def baseline(_path: Path) -> dict[str, object]:
        return {
            "command": ["bash", "validate_baseline.sh"],
            "return_code": 0,
            "stdout": "baseline ok\n",
            "stderr": "",
            "timestamp_utc": "2026-08-14T08:00:00+00:00",
        }

    def inject(_fault_type: str, scenario: Path, output: Path):
        return inject_missing_static_route(
            scenario,
            output,
            executor=executor,
        )

    def restore(_fault_type: str, scenario: Path, output: Path):
        return restore_missing_static_route(
            scenario,
            output,
            executor=executor,
        )

    with pytest.raises(
        Phase6ExperimentRunnerError,
        match="synthetic exception before injection record",
    ):
        run_phase6_experiment(
            SCENARIO,
            tmp_path / "experiments",
            Path("validate_baseline.sh"),
            baseline_validator=baseline,
            fault_injector=inject,
            fault_restorer=restore,
            experiment_id="partial-failure-recovery",
        )

    mutation = (
        tmp_path
        / "experiments/partial-failure-recovery/mutation"
    )
    assert (mutation / "recovery_intent.json").is_file()
    assert not (mutation / "injection_record.json").exists()
    restoration = json.loads(
        (mutation / "restoration_record.json").read_text(
            encoding="utf-8"
        )
    )
    assert restoration["status"] == "RESTORATION_CONFIRMED"
    assert executor.lab.route == (
        executor.lab.expected_next_hop,
        "eth2",
    )


def test_recovery_entry_point_restores_abandoned_intent(
    tmp_path: Path,
) -> None:
    executor = PostconditionExceptionLab()
    experiment = tmp_path / "abandoned"
    mutation = experiment / "mutation"

    with pytest.raises(
        RuntimeError,
        match="synthetic exception before injection record",
    ):
        inject_missing_static_route(
            SCENARIO,
            mutation,
            executor=executor,
        )

    assert (mutation / "recovery_intent.json").is_file()
    assert not (mutation / "injection_record.json").exists()
    assert executor.lab.route is None

    def baseline(_path: Path) -> dict[str, object]:
        return {
            "command": ["bash", "validate_baseline.sh"],
            "return_code": 0,
            "stdout": "baseline ok\n",
            "stderr": "",
            "timestamp_utc": "2026-08-14T08:00:00+00:00",
        }

    def restore(_fault_type: str, scenario: Path, output: Path):
        return restore_missing_static_route(
            scenario,
            output,
            executor=executor,
        )

    result = recover_phase6_experiment(
        SCENARIO,
        experiment,
        Path("validate_baseline.sh"),
        baseline_validator=baseline,
        fault_restorer=restore,
    )

    assert result["status"] == "RECOVERY_CONFIRMED"
    assert result["baseline_restored"] is True
    assert executor.lab.route == (
        executor.lab.expected_next_hop,
        "eth2",
    )
    assert (experiment / "recovery_replay.json").is_file()


def test_all_production_subprocess_calls_are_bounded() -> None:
    direct_calls: list[tuple[Path, ast.Call]] = []
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "subprocess"
                and node.func.attr == "run"
            ):
                direct_calls.append((path.relative_to(ROOT), node))

    assert [path.as_posix() for path, _ in direct_calls] == [
        "src/runtime/subprocesses.py"
    ]
    assert any(
        keyword.arg == "timeout"
        for keyword in direct_calls[0][1].keywords
    )


def test_model_hash_drift_stops_before_joblib_deserialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts = freeze_pipeline(tmp_path, monkeypatch)
    with artifacts["model_path"].open("ab") as file:
        file.write(b"drift")

    called = False

    def unsafe_load(_path):
        nonlocal called
        called = True
        raise AssertionError("joblib.load must not be reached")

    monkeypatch.setattr(baseline.joblib, "load", unsafe_load)
    with pytest.raises(
        MLBaselineError,
        match="Model-artifact SHA-256 drift",
    ):
        validate_frozen_pipeline(
            matrix_path=artifacts["matrix"],
            selection_path=artifacts["selection_path"],
            model_path=artifacts["model_path"],
            selection_schema_path=SELECTION_SCHEMA,
            expected_matrix_sha256=artifacts["matrix_sha256"],
            expected_selection_sha256=artifacts["selection_sha256"],
            expected_model_sha256=artifacts["model_sha256"],
        )
    assert called is False


def test_verify_selection_cli_requires_accepted_trust_hashes() -> None:
    with pytest.raises(SystemExit):
        baseline.build_parser().parse_args(
            [
                "verify-selection",
                "--matrix",
                "matrix.jsonl",
                "--selection",
                "selection.json",
                "--model",
                "model.joblib",
            ]
        )

    with pytest.raises(SystemExit):
        baseline.build_parser().parse_args(
            [
                "verify-selection",
                "--matrix",
                "matrix.jsonl",
                "--selection",
                "selection.json",
                "--model",
                "model.joblib",
                "--expected-selection-sha256",
                "0" * 64,
                "--expected-model-sha256",
                "1" * 64,
            ]
        )

    arguments = baseline.build_parser().parse_args(
        [
            "verify-selection",
            "--matrix",
            "matrix.jsonl",
            "--selection",
            "selection.json",
            "--model",
            "model.joblib",
            "--expected-selection-sha256",
            ACCEPTED_SELECTION_SHA256,
            "--expected-model-sha256",
            ACCEPTED_MODEL_SHA256,
        ]
    )
    assert arguments.expected_selection_sha256 == (
        ACCEPTED_SELECTION_SHA256
    )
    assert arguments.expected_model_sha256 == ACCEPTED_MODEL_SHA256
