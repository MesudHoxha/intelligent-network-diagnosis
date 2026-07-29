from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from src.batch.plan import (
    BatchPlanError,
    expand_batch_plan,
    load_batch_plan,
)


def valid_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "batch": {
            "id": "TEST_BATCH",
            "description": "Test batch plan.",
            "execution": {
                "order": "listed",
                "failure_policy": "stop",
            },
            "entries": [
                {
                    "entry_id": "normal",
                    "scenario_path": (
                        "scenarios/routing/N0.yml"
                    ),
                    "repetitions": 2,
                },
                {
                    "entry_id": "missing_route",
                    "scenario_path": (
                        "scenarios/routing/C1.yml"
                    ),
                    "repetitions": 1,
                },
            ],
        },
    }


def prepare_repository(
    root: Path,
    document: dict[str, object] | None = None,
) -> Path:
    scenario_directory = (
        root / "scenarios" / "routing"
    )
    scenario_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    for name in ("N0.yml", "C1.yml"):
        (scenario_directory / name).write_text(
            "scenario:\n  id: TEST\n",
            encoding="utf-8",
        )

    plan_path = (
        root / "plans" / "batches" / "test.yml"
    )
    plan_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    plan_path.write_text(
        yaml.safe_dump(
            (
                valid_document()
                if document is None
                else document
            ),
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return plan_path


def test_load_batch_plan_reads_valid_contract(
    tmp_path: Path,
) -> None:
    plan_path = prepare_repository(tmp_path)

    plan = load_batch_plan(
        plan_path,
        repository_root=tmp_path,
    )

    assert plan.schema_version == 1
    assert plan.batch_id == "TEST_BATCH"
    assert plan.execution_order == "listed"
    assert plan.failure_policy == "stop"
    assert len(plan.entries) == 2
    assert plan.entries[0].repetitions == 2


def test_expand_batch_plan_is_deterministic(
    tmp_path: Path,
) -> None:
    plan = load_batch_plan(
        prepare_repository(tmp_path),
        repository_root=tmp_path,
    )

    experiments = expand_batch_plan(plan)

    assert [
        (
            item.sequence_number,
            item.entry_id,
            item.repetition_index,
        )
        for item in experiments
    ] == [
        (1, "normal", 1),
        (2, "normal", 2),
        (3, "missing_route", 1),
    ]


def test_rejects_duplicate_entry_ids(
    tmp_path: Path,
) -> None:
    document = valid_document()
    entries = document["batch"]["entries"]
    entries[1]["entry_id"] = "normal"

    plan_path = prepare_repository(
        tmp_path,
        document,
    )

    with pytest.raises(
        BatchPlanError,
        match="Duplicate entry_id",
    ):
        load_batch_plan(
            plan_path,
            repository_root=tmp_path,
        )


def test_rejects_duplicate_scenario_paths(
    tmp_path: Path,
) -> None:
    document = valid_document()
    entries = document["batch"]["entries"]
    entries[1]["scenario_path"] = (
        "scenarios/routing/N0.yml"
    )

    plan_path = prepare_repository(
        tmp_path,
        document,
    )

    with pytest.raises(
        BatchPlanError,
        match="Duplicate scenario_path",
    ):
        load_batch_plan(
            plan_path,
            repository_root=tmp_path,
        )


def test_rejects_path_traversal(
    tmp_path: Path,
) -> None:
    document = valid_document()
    document["batch"]["entries"][0][
        "scenario_path"
    ] = "scenarios/../outside.yml"

    plan_path = prepare_repository(
        tmp_path,
        document,
    )

    with pytest.raises(
        BatchPlanError,
        match="must not contain",
    ):
        load_batch_plan(
            plan_path,
            repository_root=tmp_path,
        )


def test_rejects_missing_scenario_file(
    tmp_path: Path,
) -> None:
    document = valid_document()
    document["batch"]["entries"][0][
        "scenario_path"
    ] = "scenarios/routing/MISSING.yml"

    plan_path = prepare_repository(
        tmp_path,
        document,
    )

    with pytest.raises(
        BatchPlanError,
        match="does not exist",
    ):
        load_batch_plan(
            plan_path,
            repository_root=tmp_path,
        )


@pytest.mark.parametrize(
    "invalid_repetitions",
    [0, True, 1001],
)
def test_rejects_invalid_repetition_count(
    tmp_path: Path,
    invalid_repetitions: object,
) -> None:
    document = deepcopy(valid_document())
    document["batch"]["entries"][0][
        "repetitions"
    ] = invalid_repetitions

    plan_path = prepare_repository(
        tmp_path,
        document,
    )

    with pytest.raises(
        BatchPlanError,
        match="integer from 1 to 1000",
    ):
        load_batch_plan(
            plan_path,
            repository_root=tmp_path,
        )


def test_rejects_more_than_1000_entries(
    tmp_path: Path,
) -> None:
    document = valid_document()
    template = document["batch"]["entries"][0]

    document["batch"]["entries"] = [
        {
            "entry_id": f"entry_{index}",
            "scenario_path": template["scenario_path"],
            "repetitions": 1,
        }
        for index in range(1001)
    ]

    plan_path = prepare_repository(
        tmp_path,
        document,
    )

    with pytest.raises(
        BatchPlanError,
        match="at most 1000 entries",
    ):
        load_batch_plan(
            plan_path,
            repository_root=tmp_path,
        )
