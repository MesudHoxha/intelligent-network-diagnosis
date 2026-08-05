from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from src.batch.plan import expand_batch_plan
from src.campaign.plan import (
    CampaignContext,
    DatasetCampaignPlan,
    load_campaign_plan,
)
from src.campaign.runner import (
    CampaignRunnerError,
    load_fingerprint_manifest,
    normalized_bundle_sha256,
    run_campaign,
)
from src.dataset.contract import FEATURE_NAMES


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_PLAN_PATH = Path(
    "plans/campaigns/P2_ROUTING_5CTX_V1.yml"
)
FINGERPRINT_PATH = Path(
    "plans/campaigns/"
    "P2_ROUTING_5CTX_V1.fingerprints.json"
)


def make_row(
    context: CampaignContext,
    fault_type: str,
    repetition: int,
    *,
    wrong_binding: bool = False,
) -> dict[str, Any]:
    sample_id = (
        f"sample-{context.group_slot.lower()}-"
        f"{fault_type}-{repetition}"
    )
    is_normal = fault_type == "no_fault"
    features = {
        name: "true"
        for name in FEATURE_NAMES
    }

    if fault_type == "missing_static_route":
        features.update({
            "destination_reachable": "false",
            (
                "route_to_destination_exists_on_observer"
            ): "false",
            (
                "route_next_hop_present_on_observer"
            ): "false",
            (
                "route_next_hop_reachable_from_observer"
            ): "unavailable",
        })
    elif fault_type == "wrong_next_hop":
        features.update({
            "destination_reachable": "false",
            (
                "route_next_hop_reachable_from_observer"
            ): "false",
        })

    return {
        "schema_version": 2,
        "sample_id": sample_id,
        "metadata": {
            "experiment_id": sample_id,
            "scenario_id": (
                f"{fault_type}_{context.group_slot}"
            ),
            "variant_id": "canonical",
            "split_group_id": (
                context.split_group_id
            ),
            "topology_id": context.topology_id,
            "direction": context.direction,
            "route_observer_node": (
                "wrong-observer"
                if wrong_binding
                else context.route_observer_node
            ),
            "transit_node": context.transit_node,
            "collected_at_utc": (
                "2026-08-01T12:00:00+00:00"
            ),
        },
        "features": features,
        "labels": {
            "fault_category": (
                None if is_normal else "routing"
            ),
            "fault_type": fault_type,
            "fault_location": (
                None
                if is_normal
                else context.route_observer_node
            ),
            "affected_prefix": (
                None if is_normal else "10.0.0.0/24"
            ),
        },
        "quality": {
            "experiment_completed": True,
            "collector_completed": True,
            "baseline_before_valid": True,
            "baseline_after_valid": True,
            "unavailable_feature_count": sum(
                value == "unavailable"
                for value in features.values()
            ),
        },
    }


class FakeBatchExecutor:
    def __init__(
        self,
        campaign_plan: DatasetCampaignPlan,
        *,
        fail_slot: str | None = None,
        wrong_binding_slot: str | None = None,
        wrong_evaluation_slot: str | None = None,
        unexpected_unavailable_slot: str | None = None,
    ) -> None:
        self.campaign_plan = campaign_plan
        self.fail_slot = fail_slot
        self.wrong_binding_slot = wrong_binding_slot
        self.wrong_evaluation_slot = (
            wrong_evaluation_slot
        )
        self.unexpected_unavailable_slot = (
            unexpected_unavailable_slot
        )
        self.calls: list[str] = []

    def __call__(
        self,
        *,
        plan_path: Path,
        repository_root: Path,
        output_root: Path,
        processed_root: Path,
        metadata_root: Path,
        baseline_validator: Path,
        batch_run_id: str,
    ) -> dict[str, Any]:
        del repository_root, baseline_validator

        context = next(
            item
            for item in self.campaign_plan.contexts
            if item.batch_plan_path == plan_path
        )
        self.calls.append(context.group_slot)

        if context.group_slot == self.fail_slot:
            raise RuntimeError("synthetic batch failure")

        planned = expand_batch_plan(
            context.batch_plan
        )
        labels = [
            fault_type
            for fault_type
            in self.campaign_plan.expected_fault_types
            for _ in range(
                self.campaign_plan.
                repetitions_per_class_context
            )
        ]
        rows: list[dict[str, Any]] = []
        experiments: list[dict[str, Any]] = []

        for index, (
            planned_experiment,
            fault_type,
        ) in enumerate(
            zip(planned, labels, strict=True),
            start=1,
        ):
            repetition = (
                planned_experiment.repetition_index
            )
            row = make_row(
                context,
                fault_type,
                repetition,
                wrong_binding=(
                    context.group_slot
                    == self.wrong_binding_slot
                    and index == 1
                ),
            )
            if (
                context.group_slot
                == self.unexpected_unavailable_slot
                and index == 1
            ):
                row["features"][
                    "source_gateway_reachable"
                ] = "unavailable"
                row["quality"][
                    "unavailable_feature_count"
                ] += 1
            sample_id = row["sample_id"]
            experiment_directory = (
                output_root / sample_id
            )
            evaluation_directory = (
                experiment_directory / "evaluation"
            )
            evaluation_directory.mkdir(
                parents=True,
                exist_ok=False,
            )
            (
                experiment_directory / "row.json"
            ).write_text(
                json.dumps(row),
                encoding="utf-8",
            )
            exact_match = not (
                context.group_slot
                == self.wrong_evaluation_slot
                and index == 1
            )
            (
                evaluation_directory
                / "rule_based.json"
            ).write_text(
                json.dumps({
                    "metrics": {
                        "exact_match": exact_match,
                        "affected_prefix_correct": True,
                    }
                }),
                encoding="utf-8",
            )

            rows.append(row)
            experiments.append({
                "sequence_number": index,
                "entry_id": (
                    planned_experiment.entry_id
                ),
                "scenario_path": (
                    planned_experiment.
                    scenario_path.as_posix()
                ),
                "repetition_index": repetition,
                "experiment_id": sample_id,
                "experiment_directory": str(
                    experiment_directory
                ),
                "sample_id": sample_id,
                "status": "COMPLETED",
            })

        processed_root.mkdir(
            parents=True,
            exist_ok=True,
        )
        metadata_root.mkdir(
            parents=True,
            exist_ok=True,
        )
        dataset_path = (
            processed_root / f"{batch_run_id}.jsonl"
        )
        dataset_path.write_text(
            "".join(
                json.dumps(
                    row,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
                for row in rows
            ),
            encoding="utf-8",
        )
        result_path = (
            metadata_root / f"{batch_run_id}.json"
        )

        result = {
            "schema_version": 1,
            "batch_run_id": batch_run_id,
            "batch_id": context.batch_plan.batch_id,
            "plan_path": plan_path.as_posix(),
            "failure_policy": "stop",
            "status": "COMPLETED",
            "planned_experiment_count": 6,
            "completed_experiment_count": 6,
            "dataset_row_count": 6,
            "dataset_row_schema_version": 2,
            "dataset_path": str(dataset_path),
            "batch_result_path": str(result_path),
            "experiments": experiments,
        }
        result_path.write_text(
            json.dumps(result),
            encoding="utf-8",
        )
        return result


class FakeCommandExecutor:
    def __init__(
        self,
        *,
        fail_deploy_pattern: str | None = None,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail_deploy_pattern = (
            fail_deploy_pattern
        )

    def __call__(
        self,
        command: Sequence[str],
        cwd: Path,
    ) -> dict[str, Any]:
        del cwd
        self.calls.append(tuple(command))
        should_fail = (
            self.fail_deploy_pattern is not None
            and len(command) >= 5
            and command[:3]
            == ["sudo", "containerlab", "deploy"]
            and self.fail_deploy_pattern in command[-1]
        )
        return {
            "return_code": 1 if should_fail else 0,
            "stdout": "",
            "stderr": (
                "synthetic deploy failure"
                if should_fail
                else ""
            ),
        }


def row_builder(path: Path) -> dict[str, Any]:
    value = json.loads(
        (path / "row.json").read_text(
            encoding="utf-8"
        )
    )
    assert isinstance(value, dict)
    return value


def run_arguments(
    tmp_path: Path,
) -> dict[str, Any]:
    return {
        "plan_path": CAMPAIGN_PLAN_PATH,
        "fingerprint_manifest_path": (
            FINGERPRINT_PATH
        ),
        "repository_root": REPOSITORY_ROOT,
        "output_root": tmp_path / "raw",
        "processed_root": tmp_path / "processed",
        "metadata_root": tmp_path / "metadata",
        "reports_root": tmp_path / "reports",
        "campaign_run_id": "campaign-test-001",
    }


def test_fingerprint_manifest_binds_all_five_contexts() -> None:
    campaign_plan = load_campaign_plan(
        CAMPAIGN_PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )
    records = load_fingerprint_manifest(
        REPOSITORY_ROOT / FINGERPRINT_PATH,
        campaign_plan=campaign_plan,
        repository_root=REPOSITORY_ROOT,
    )

    assert list(records) == [
        "G01",
        "G02",
        "G03",
        "G04",
        "G05",
    ]
    assert records["G01"]["actual_sha256"] == (
        "208d92f8d355462ff1a4631ebf4ca1e2"
        "c9cf8b61900d6084bff8b87d2c09c8ea"
    )
    assert records["G05"]["actual_sha256"] == (
        "6bd4de9818ba0c3b589e5a17cf47553f"
        "523fc743d6feb12334bd525ea79ca870"
    )


def test_normalized_fingerprint_is_path_and_content_bound(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("alpha\r\n", encoding="utf-8")
    second.write_text("beta\n", encoding="utf-8")

    original = normalized_bundle_sha256(
        [first, second],
        repository_root=tmp_path,
    )
    first.write_text("alpha\n", encoding="utf-8")
    assert normalized_bundle_sha256(
        [second, first],
        repository_root=tmp_path,
    ) == original
    second.write_text("changed\n", encoding="utf-8")
    assert normalized_bundle_sha256(
        [first, second],
        repository_root=tmp_path,
    ) != original


def test_complete_campaign_merges_audits_and_splits(
    tmp_path: Path,
) -> None:
    campaign_plan = load_campaign_plan(
        CAMPAIGN_PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )
    batch = FakeBatchExecutor(campaign_plan)
    commands = FakeCommandExecutor()
    progress: list[str] = []

    result = run_campaign(
        **run_arguments(tmp_path),
        command_executor=commands,
        batch_executor=batch,
        row_builder=row_builder,
        progress=progress.append,
    )

    assert result["status"] == "COMPLETED"
    assert batch.calls == [
        "G01",
        "G02",
        "G03",
        "G04",
        "G05",
    ]
    assert result["completed_context_count"] == 5
    assert result["completed_experiment_count"] == 30
    assert result["dataset_row_count"] == 30
    assert result["merged_dataset"]["row_count"] == 30
    assert result["merged_dataset"]["quality"][
        "unavailable_feature_count"
    ] == 10
    assert result["merged_dataset"]["quality"][
        "unavailable_feature_counts_by_fault_type"
    ] == {
        "no_fault": 0,
        "missing_static_route": 10,
        "wrong_next_hop": 0,
    }
    assert result["merged_dataset"]["quality"][
        "expected_unavailable_features_by_fault_type"
    ] == {
        "no_fault": [],
        "missing_static_route": [
            "route_next_hop_reachable_from_observer",
        ],
        "wrong_next_hop": [],
    }
    assert result["rule_audit"] == {
        "path": str(
            tmp_path
            / "reports"
            / "campaign-test-001-rule-audit.json"
        ),
        "record_count": 30,
        "exact_match_count": 30,
        "affected_prefix_correct_count": 30,
    }
    assert {
        name: (
            partition["row_count"],
            partition["group_count"],
        )
        for name, partition
        in result["split"]["partitions"].items()
    } == {
        "train": (18, 3),
        "validation": (6, 1),
        "test": (6, 1),
    }
    assert result["split"][
        "no_cross_partition_group"
    ] is True
    assert all(
        context["cleanup_verified"] is True
        for context in result["contexts"]
    )
    assert progress[-1] == (
        "[complete] campaign 30/30 accepted"
    )
    rule_audit = json.loads(
        Path(result["rule_audit"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    assert [
        record["campaign_sequence_number"]
        for record in rule_audit["records"]
    ] == list(range(1, 31))

    deploy_commands = [
        command
        for command in commands.calls
        if command[:3]
        == ("sudo", "containerlab", "deploy")
    ]
    destroy_commands = [
        command
        for command in commands.calls
        if command[:3]
        == ("sudo", "containerlab", "destroy")
    ]
    assert len(deploy_commands) == 5
    assert len(destroy_commands) == 5


def test_completed_result_matches_formal_schema(
    tmp_path: Path,
) -> None:
    campaign_plan = load_campaign_plan(
        CAMPAIGN_PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )
    result = run_campaign(
        **run_arguments(tmp_path),
        command_executor=FakeCommandExecutor(),
        batch_executor=FakeBatchExecutor(
            campaign_plan
        ),
        row_builder=row_builder,
    )
    schema = json.loads(
        (
            REPOSITORY_ROOT
            / "schemas"
            / "campaign_result_v1.schema.json"
        ).read_text(encoding="utf-8")
    )

    Draft202012Validator.check_schema(schema)
    errors = list(
        Draft202012Validator(schema).iter_errors(
            result
        )
    )
    assert errors == []


def test_failure_stops_before_next_context_and_keeps_cleanup(
    tmp_path: Path,
) -> None:
    campaign_plan = load_campaign_plan(
        CAMPAIGN_PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )
    batch = FakeBatchExecutor(
        campaign_plan,
        fail_slot="G02",
    )
    commands = FakeCommandExecutor()

    with pytest.raises(
        CampaignRunnerError,
        match="synthetic batch failure",
    ):
        run_campaign(
            **run_arguments(tmp_path),
            command_executor=commands,
            batch_executor=batch,
            row_builder=row_builder,
        )

    assert batch.calls == ["G01", "G02"]
    result = json.loads(
        (
            tmp_path
            / "metadata"
            / "campaign-test-001.campaign.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"] == "FAILED"
    assert result["completed_context_count"] == 1
    assert result["failed_context"] == "G02"
    assert result["contexts"][1][
        "cleanup_verified"
    ] is True
    assert not (
        tmp_path
        / "processed"
        / "campaign-test-001.jsonl"
    ).exists()
    assert not (
        tmp_path
        / "processed"
        / "campaign-test-001-split"
    ).exists()


@pytest.mark.parametrize(
    ("option", "message"),
    [
        (
            {"wrong_binding_slot": "G03"},
            "invalid metadata.route_observer_node",
        ),
        (
            {"wrong_evaluation_slot": "G03"},
            "is not an exact rule match",
        ),
    ],
)
def test_context_semantic_audit_blocks_campaign(
    tmp_path: Path,
    option: dict[str, str],
    message: str,
) -> None:
    campaign_plan = load_campaign_plan(
        CAMPAIGN_PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )

    with pytest.raises(
        CampaignRunnerError,
        match=message,
    ):
        run_campaign(
            **run_arguments(tmp_path),
            command_executor=FakeCommandExecutor(),
            batch_executor=FakeBatchExecutor(
                campaign_plan,
                **option,
            ),
            row_builder=row_builder,
        )

    result = json.loads(
        (
            tmp_path
            / "metadata"
            / "campaign-test-001.campaign.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"] == "FAILED"
    assert result["completed_context_count"] == 2
    assert result["failed_context"] == "G03"


def test_unexpected_unavailable_feature_blocks_campaign(
    tmp_path: Path,
) -> None:
    campaign_plan = load_campaign_plan(
        CAMPAIGN_PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )

    with pytest.raises(
        CampaignRunnerError,
        match="invalid unavailable features",
    ):
        run_campaign(
            **run_arguments(tmp_path),
            command_executor=FakeCommandExecutor(),
            batch_executor=FakeBatchExecutor(
                campaign_plan,
                unexpected_unavailable_slot="G02",
            ),
            row_builder=row_builder,
        )

    result = json.loads(
        (
            tmp_path
            / "metadata"
            / "campaign-test-001.campaign.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"] == "FAILED"
    assert result["failed_context"] == "G02"


def test_fingerprint_mismatch_stops_before_any_command(
    tmp_path: Path,
) -> None:
    document = json.loads(
        (
            REPOSITORY_ROOT / FINGERPRINT_PATH
        ).read_text(encoding="utf-8")
    )
    document["contexts"][0]["sha256"] = "0" * 64
    changed_path = tmp_path / "fingerprints.json"
    changed_path.write_text(
        json.dumps(document),
        encoding="utf-8",
    )
    commands = FakeCommandExecutor()

    arguments = run_arguments(tmp_path)
    arguments["fingerprint_manifest_path"] = (
        changed_path
    )

    with pytest.raises(
        CampaignRunnerError,
        match="G01 artifact fingerprint mismatch",
    ):
        run_campaign(
            **arguments,
            command_executor=commands,
        )

    assert commands.calls == []
    assert not (tmp_path / "metadata").exists()


def test_existing_campaign_output_is_never_overwritten(
    tmp_path: Path,
) -> None:
    metadata_root = tmp_path / "metadata"
    metadata_root.mkdir()
    existing_path = (
        metadata_root
        / "campaign-test-001.campaign.json"
    )
    existing_path.write_text(
        "preserve-me\n",
        encoding="utf-8",
    )

    with pytest.raises(
        CampaignRunnerError,
        match="campaign result already exists",
    ):
        run_campaign(
            **run_arguments(tmp_path),
            command_executor=FakeCommandExecutor(),
        )

    assert existing_path.read_text(
        encoding="utf-8"
    ) == "preserve-me\n"


def test_partial_deploy_failure_attempts_exact_cleanup(
    tmp_path: Path,
) -> None:
    campaign_plan = load_campaign_plan(
        CAMPAIGN_PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )
    commands = FakeCommandExecutor(
        fail_deploy_pattern="top02_chain",
    )

    with pytest.raises(
        CampaignRunnerError,
        match="synthetic deploy failure",
    ):
        run_campaign(
            **run_arguments(tmp_path),
            command_executor=commands,
            batch_executor=FakeBatchExecutor(
                campaign_plan
            ),
            row_builder=row_builder,
        )

    g02_destroy = [
        command
        for command in commands.calls
        if command[:3]
        == ("sudo", "containerlab", "destroy")
        and "top02_chain" in command[-2]
    ]
    assert len(g02_destroy) == 1
