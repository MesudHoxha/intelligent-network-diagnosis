import json
from pathlib import Path

import pytest

from src.batch.runner import (
    BatchRunnerError,
    run_batch,
)
from src.dataset.contract import FEATURE_NAMES
from src.orchestration.experiment_runner import (
    build_experiment_id,
)


SCENARIO_NAMES = (
    "N0_NORMAL_OPERATION",
    "C1_MISSING_STATIC_ROUTE",
    "C2_WRONG_NEXT_HOP",
)


def prepare_repository(
    tmp_path: Path,
) -> Path:
    scenario_directory = (
        tmp_path / "scenarios" / "routing"
    )
    scenario_directory.mkdir(
        parents=True
    )

    for name in SCENARIO_NAMES:
        (
            scenario_directory / f"{name}.yml"
        ).write_text(
            "schema_version: 1\nscenario: {}\n",
            encoding="utf-8",
        )

    plan_path = (
        tmp_path
        / "plans"
        / "batches"
        / "B0_TEST.yml"
    )
    plan_path.parent.mkdir(
        parents=True
    )
    plan_path.write_text(
        """
schema_version: 1
batch:
  id: B0_TEST
  description: Isolated batch runner test
  execution:
    order: listed
    failure_policy: stop
  entries:
    - entry_id: n0
      scenario_path: scenarios/routing/N0_NORMAL_OPERATION.yml
      repetitions: 1
    - entry_id: c1
      scenario_path: scenarios/routing/C1_MISSING_STATIC_ROUTE.yml
      repetitions: 1
    - entry_id: c2
      scenario_path: scenarios/routing/C2_WRONG_NEXT_HOP.yml
      repetitions: 1
""".lstrip(),
        encoding="utf-8",
    )

    return plan_path


def valid_row(
    sample_id: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "sample_id": sample_id,
        "metadata": {
            "experiment_id": sample_id,
        },
        "features": {
            name: "true"
            for name in FEATURE_NAMES
        },
        "labels": {},
        "quality": {},
    }


def run_arguments(
    tmp_path: Path,
    plan_path: Path,
    *,
    batch_run_id: str,
) -> dict[str, object]:
    return {
        "plan_path": plan_path,
        "repository_root": tmp_path,
        "output_root": Path("data/raw"),
        "processed_root": Path(
            "data/processed"
        ),
        "metadata_root": Path(
            "data/metadata"
        ),
        "baseline_validator": Path(
            "validator.sh"
        ),
        "batch_run_id": batch_run_id,
    }


def test_runs_in_listed_order_and_aggregates_jsonl(
    tmp_path: Path,
) -> None:
    plan_path = prepare_repository(tmp_path)
    calls: list[str] = []

    def fake_executor(
        *,
        scenario_path: Path,
        output_root: Path,
        baseline_validator: Path,
    ) -> dict[str, object]:
        del baseline_validator

        calls.append(
            scenario_path.name
        )
        sequence_number = len(calls)
        experiment_id = (
            f"experiment-{sequence_number}"
        )
        experiment_directory = (
            output_root / experiment_id
        )
        experiment_directory.mkdir(
            parents=True
        )

        return {
            "status": "COMPLETED",
            "experiment_id": experiment_id,
            "experiment_directory": str(
                experiment_directory
            ),
        }

    result = run_batch(
        **run_arguments(
            tmp_path,
            plan_path,
            batch_run_id="batch-run-001",
        ),
        experiment_executor=fake_executor,
        dataset_row_builder=lambda path: (
            valid_row(path.name)
        ),
    )

    assert calls == [
        "N0_NORMAL_OPERATION.yml",
        "C1_MISSING_STATIC_ROUTE.yml",
        "C2_WRONG_NEXT_HOP.yml",
    ]
    assert result["status"] == "COMPLETED"
    assert (
        result["planned_experiment_count"]
        == 3
    )
    assert (
        result["completed_experiment_count"]
        == 3
    )
    assert result["dataset_row_count"] == 3
    assert [
        record["sequence_number"]
        for record in result["experiments"]
    ] == [1, 2, 3]

    dataset_path = Path(
        result["dataset_path"]
    )
    rows = [
        json.loads(line)
        for line in dataset_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert [
        row["sample_id"]
        for row in rows
    ] == [
        "experiment-1",
        "experiment-2",
        "experiment-3",
    ]

    stored_result = json.loads(
        (
            tmp_path
            / "data"
            / "metadata"
            / "batch-run-001.json"
        ).read_text(encoding="utf-8")
    )

    assert stored_result == result


def test_failure_policy_stop_stops_after_first_error(
    tmp_path: Path,
) -> None:
    plan_path = prepare_repository(tmp_path)
    calls: list[str] = []

    def failing_executor(
        *,
        scenario_path: Path,
        output_root: Path,
        baseline_validator: Path,
    ) -> dict[str, object]:
        del baseline_validator

        calls.append(
            scenario_path.name
        )

        if len(calls) == 2:
            raise RuntimeError(
                "simulated experiment failure"
            )

        experiment_id = "experiment-1"
        experiment_directory = (
            output_root / experiment_id
        )
        experiment_directory.mkdir(
            parents=True
        )

        return {
            "status": "COMPLETED",
            "experiment_id": experiment_id,
            "experiment_directory": str(
                experiment_directory
            ),
        }

    with pytest.raises(
        BatchRunnerError,
        match="sequence 2",
    ):
        run_batch(
            **run_arguments(
                tmp_path,
                plan_path,
                batch_run_id=(
                    "batch-run-failure"
                ),
            ),
            experiment_executor=(
                failing_executor
            ),
            dataset_row_builder=lambda path: (
                valid_row(path.name)
            ),
        )

    assert calls == [
        "N0_NORMAL_OPERATION.yml",
        "C1_MISSING_STATIC_ROUTE.yml",
    ]

    stored_result = json.loads(
        (
            tmp_path
            / "data"
            / "metadata"
            / "batch-run-failure.json"
        ).read_text(encoding="utf-8")
    )

    assert stored_result["status"] == "FAILED"
    assert (
        stored_result[
            "completed_experiment_count"
        ]
        == 1
    )
    assert (
        stored_result[
            "failed_sequence_number"
        ]
        == 2
    )
    assert (
        stored_result["error"]["type"]
        == "RuntimeError"
    )
    assert not (
        tmp_path
        / "data"
        / "processed"
        / "batch-run-failure.jsonl"
    ).exists()


def test_rejects_duplicate_sample_ids(
    tmp_path: Path,
) -> None:
    plan_path = prepare_repository(tmp_path)
    call_count = 0

    def executor(
        *,
        scenario_path: Path,
        output_root: Path,
        baseline_validator: Path,
    ) -> dict[str, object]:
        nonlocal call_count
        del scenario_path
        del baseline_validator

        call_count += 1
        experiment_directory = (
            output_root
            / f"directory-{call_count}"
        )
        experiment_directory.mkdir(
            parents=True
        )

        return {
            "status": "COMPLETED",
            "experiment_id": "duplicate",
            "experiment_directory": str(
                experiment_directory
            ),
        }

    with pytest.raises(BatchRunnerError):
        run_batch(
            **run_arguments(
                tmp_path,
                plan_path,
                batch_run_id=(
                    "batch-run-duplicate"
                ),
            ),
            experiment_executor=executor,
            dataset_row_builder=lambda _: (
                valid_row("duplicate")
            ),
        )

    stored_result = json.loads(
        (
            tmp_path
            / "data"
            / "metadata"
            / "batch-run-duplicate.json"
        ).read_text(encoding="utf-8")
    )

    assert stored_result["status"] == "FAILED"
    assert (
        "Duplicate dataset sample_id"
        in stored_result["error"]["message"]
    )
    assert call_count == 2


def test_rejects_non_completed_experiment(
    tmp_path: Path,
) -> None:
    plan_path = prepare_repository(tmp_path)
    builder_called = False

    def executor(
        *,
        scenario_path: Path,
        output_root: Path,
        baseline_validator: Path,
    ) -> dict[str, object]:
        del scenario_path
        del output_root
        del baseline_validator

        return {
            "status": "FAILED",
        }

    def builder(
        _: Path,
    ) -> dict[str, object]:
        nonlocal builder_called
        builder_called = True
        return valid_row("unexpected")

    with pytest.raises(BatchRunnerError):
        run_batch(
            **run_arguments(
                tmp_path,
                plan_path,
                batch_run_id=(
                    "batch-run-incomplete"
                ),
            ),
            experiment_executor=executor,
            dataset_row_builder=builder,
        )

    assert builder_called is False


def test_revalidates_rows_from_builder(
    tmp_path: Path,
) -> None:
    plan_path = prepare_repository(tmp_path)

    def executor(
        *,
        scenario_path: Path,
        output_root: Path,
        baseline_validator: Path,
    ) -> dict[str, object]:
        del scenario_path
        del baseline_validator

        experiment_directory = (
            output_root / "experiment-1"
        )
        experiment_directory.mkdir(
            parents=True
        )

        return {
            "status": "COMPLETED",
            "experiment_id": "experiment-1",
            "experiment_directory": str(
                experiment_directory
            ),
        }

    with pytest.raises(BatchRunnerError):
        run_batch(
            **run_arguments(
                tmp_path,
                plan_path,
                batch_run_id=(
                    "batch-run-invalid-row"
                ),
            ),
            experiment_executor=executor,
            dataset_row_builder=lambda _: {
                "invalid": True,
            },
        )

    stored_result = json.loads(
        (
            tmp_path
            / "data"
            / "metadata"
            / "batch-run-invalid-row.json"
        ).read_text(encoding="utf-8")
    )

    assert stored_result["status"] == "FAILED"
    assert (
        stored_result["error"]["type"]
        == "DatasetContractError"
    )


def test_refuses_to_overwrite_dataset_output(
    tmp_path: Path,
) -> None:
    plan_path = prepare_repository(tmp_path)
    dataset_path = (
        tmp_path
        / "data"
        / "processed"
        / "existing-run.jsonl"
    )
    dataset_path.parent.mkdir(
        parents=True
    )
    dataset_path.write_text(
        "existing\n",
        encoding="utf-8",
    )
    executor_called = False

    def executor(**kwargs):
        nonlocal executor_called
        del kwargs
        executor_called = True
        return {}

    with pytest.raises(
        BatchRunnerError,
        match="already exists",
    ):
        run_batch(
            **run_arguments(
                tmp_path,
                plan_path,
                batch_run_id="existing-run",
            ),
            experiment_executor=executor,
        )

    assert executor_called is False
    assert dataset_path.read_text(
        encoding="utf-8"
    ) == "existing\n"


def test_experiment_ids_are_unique(
) -> None:
    identifiers = {
        build_experiment_id(
            "C1_MISSING_STATIC_ROUTE"
        )
        for _ in range(100)
    }

    assert len(identifiers) == 100
    assert all(
        identifier.startswith(
            "c1_missing_static_route-"
        )
        for identifier in identifiers
    )
