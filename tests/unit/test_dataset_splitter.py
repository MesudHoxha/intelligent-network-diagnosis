import json
from pathlib import Path

import pytest

from src.dataset.contract import (
    FEATURE_NAMES,
    FEATURE_NAMES_V1,
)
from src.dataset.splitter import (
    DatasetSplitError,
    PARTITION_NAMES,
    plan_group_aware_split,
    write_group_aware_split,
)


FAULT_TYPES = (
    "no_fault",
    "missing_static_route",
    "wrong_next_hop",
)


def make_row(
    label: str,
    group_number: int,
    repetition: int = 1,
) -> dict[str, object]:
    sample_id = (
        f"{label}-{group_number}-{repetition}"
    )

    return {
        "schema_version": 2,
        "sample_id": sample_id,
        "metadata": {
            "experiment_id": sample_id,
            "scenario_id": label,
            "variant_id": (
                f"independent-{group_number}"
            ),
            "split_group_id": (
                f"{label}-group-{group_number}"
            ),
            "topology_id": "TOP_02",
            "direction": "client_to_server",
            "route_observer_node": "edge1",
            "transit_node": "core1",
            "collected_at_utc": (
                "2026-07-30T12:00:00+00:00"
            ),
        },
        "features": {
            name: "true"
            for name in FEATURE_NAMES
        },
        "labels": {
            "fault_category": (
                None
                if label == "no_fault"
                else "routing"
            ),
            "fault_type": label,
            "fault_location": (
                None
                if label == "no_fault"
                else "edge1"
            ),
            "affected_prefix": (
                None
                if label == "no_fault"
                else "10.20.2.0/24"
            ),
        },
        "quality": {
            "experiment_completed": True,
            "collector_completed": True,
            "baseline_before_valid": True,
            "baseline_after_valid": True,
            "unavailable_feature_count": 0,
        },
    }


def valid_rows(
    *,
    groups_per_class: int = 3,
    repetitions: int = 2,
) -> list[dict[str, object]]:
    return [
        make_row(
            label,
            group_number,
            repetition,
        )
        for label in FAULT_TYPES
        for group_number in range(
            1,
            groups_per_class + 1,
        )
        for repetition in range(
            1,
            repetitions + 1,
        )
    ]


def sample_assignments(
    result,
) -> dict[str, str]:
    return {
        row["sample_id"]: partition_name
        for partition_name, rows
        in result.partitions.items()
        for row in rows
    }


def test_groups_do_not_cross_partitions_and_all_classes_are_covered(
) -> None:
    result = plan_group_aware_split(
        valid_rows()
    )
    observed_groups: dict[str, str] = {}

    assert (
        result.manifest[
            "source_dataset_schema_version"
        ]
        == 2
    )

    for partition_name, rows in (
        result.partitions.items()
    ):
        assert {
            row["labels"]["fault_type"]
            for row in rows
        } == set(FAULT_TYPES)

        for row in rows:
            group_id = row[
                "metadata"
            ]["split_group_id"]

            assert observed_groups.setdefault(
                group_id,
                partition_name,
            ) == partition_name


def test_split_is_deterministic_when_input_order_changes(
) -> None:
    rows = valid_rows(
        groups_per_class=5
    )

    first = plan_group_aware_split(
        rows,
        seed=123,
    )
    second = plan_group_aware_split(
        list(reversed(rows)),
        seed=123,
    )

    assert (
        sample_assignments(first)
        == sample_assignments(second)
    )

    for label in FAULT_TYPES:
        assert [
            first.manifest[
                "partitions"
            ][partition_name][
                "class_group_counts"
            ][label]
            for partition_name
            in PARTITION_NAMES
        ] == [3, 1, 1]


def test_rejects_p1_like_class_group_structure(
) -> None:
    with pytest.raises(
        DatasetSplitError,
        match=(
            "missing_static_route=1, "
            "no_fault=1, "
            "wrong_next_hop=1"
        ),
    ):
        plan_group_aware_split(
            valid_rows(
                groups_per_class=1
            )
        )


def test_infeasible_split_creates_no_output(
    tmp_path: Path,
) -> None:
    source_path = (
        tmp_path / "p1-like.jsonl"
    )
    output_directory = (
        tmp_path / "split"
    )

    source_path.write_text(
        "".join(
            json.dumps(row) + "\n"
            for row in valid_rows(
                groups_per_class=1
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        DatasetSplitError,
        match="Insufficient independent",
    ):
        write_group_aware_split(
            source_path,
            output_directory,
        )

    assert (
        output_directory.exists()
        is False
    )


def test_rejects_group_with_multiple_labels(
) -> None:
    rows = valid_rows()
    rows[-1]["metadata"][
        "split_group_id"
    ] = (
        rows[0]["metadata"][
            "split_group_id"
        ]
    )

    with pytest.raises(
        DatasetSplitError,
        match="exactly one fault_type",
    ):
        plan_group_aware_split(rows)


def test_rejects_duplicate_sample_id(
) -> None:
    rows = valid_rows()
    duplicate_id = rows[0]["sample_id"]

    rows[-1]["sample_id"] = duplicate_id
    rows[-1]["metadata"][
        "experiment_id"
    ] = duplicate_id

    with pytest.raises(
        DatasetSplitError,
        match="Duplicate sample_id",
    ):
        plan_group_aware_split(rows)


def test_rejects_missing_split_group_id(
) -> None:
    rows = valid_rows()
    rows[-1]["metadata"][
        "split_group_id"
    ] = ""

    with pytest.raises(
        DatasetSplitError,
        match=(
            "metadata.split_group_id"
        ),
    ):
        plan_group_aware_split(rows)


def test_rejects_mixed_dataset_row_versions(
) -> None:
    rows = valid_rows()
    canonical = rows[0]

    rows[0] = {
        "schema_version": 1,
        "sample_id": canonical["sample_id"],
        "metadata": {
            name: canonical["metadata"][name]
            for name in (
                "experiment_id",
                "scenario_id",
                "variant_id",
                "split_group_id",
                "topology_id",
                "collected_at_utc",
            )
        },
        "features": {
            name: "true"
            for name in FEATURE_NAMES_V1
        },
        "labels": canonical["labels"],
        "quality": canonical["quality"],
    }

    with pytest.raises(
        DatasetSplitError,
        match="cannot mix",
    ):
        plan_group_aware_split(rows)


@pytest.mark.parametrize(
    "ratios",
    [
        (0.6, 0.2, 0.3),
        (0.8, 0.2, 0.0),
        (float("nan"), 0.5, 0.5),
    ],
)
def test_rejects_invalid_ratios(
    ratios: tuple[
        float,
        float,
        float,
    ],
) -> None:
    with pytest.raises(
        DatasetSplitError
    ):
        plan_group_aware_split(
            valid_rows(),
            train_ratio=ratios[0],
            validation_ratio=ratios[1],
            test_ratio=ratios[2],
        )


def test_writes_manifest_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    source_path = (
        tmp_path / "source.jsonl"
    )
    output_directory = (
        tmp_path / "split"
    )

    source_path.write_text(
        "".join(
            json.dumps(row) + "\n"
            for row in valid_rows()
        ),
        encoding="utf-8",
    )

    manifest = write_group_aware_split(
        source_path,
        output_directory,
    )

    assert (
        manifest["source_row_count"]
        == 18
    )

    for partition_name in (
        PARTITION_NAMES
    ):
        assert (
            output_directory
            / f"{partition_name}.jsonl"
        ).is_file()

    assert (
        output_directory
        / "split_manifest.json"
    ).is_file()

    with pytest.raises(
        DatasetSplitError,
        match="already exists",
    ):
        write_group_aware_split(
            source_path,
            output_directory,
        )
