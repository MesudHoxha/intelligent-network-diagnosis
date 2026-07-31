from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from src.batch.plan import expand_batch_plan
from src.campaign.plan import (
    CampaignPlanError,
    load_campaign_plan,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_PLAN_PATH = (
    REPOSITORY_ROOT
    / "plans"
    / "campaigns"
    / "P2_ROUTING_5CTX_V1.yml"
)
EXPECTED_FAULT_TYPES = (
    "no_fault",
    "missing_static_route",
    "wrong_next_hop",
)
EXPECTED_GROUPS = {
    "G01": "CTX_G01_TOP01_LINEAR_2R",
    "G02": "CTX_G02_TOP02_CHAIN_3R",
    "G03": "CTX_G03_TOP02_BRANCH_MID",
    "G04": "CTX_G04_TOP02_DUAL_TRANSIT",
    "G05": "CTX_G05_TOP03_ASYMMETRIC_RETURN",
}


def read_yaml(path: Path) -> dict[str, object]:
    document = yaml.safe_load(
        path.read_text(encoding="utf-8")
    )
    assert isinstance(document, dict)
    return document


def prepare_repository(tmp_path: Path) -> Path:
    for directory in (
        "labs",
        "plans",
        "scenarios",
    ):
        shutil.copytree(
            REPOSITORY_ROOT / directory,
            tmp_path / directory,
        )

    return tmp_path


def write_yaml(
    path: Path,
    document: dict[str, object],
) -> None:
    path.write_text(
        yaml.safe_dump(
            document,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_campaign_plan_freezes_exact_matrix_and_counts() -> None:
    plan = load_campaign_plan(
        CAMPAIGN_PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )

    assert plan.schema_version == 1
    assert plan.campaign_id == "P2_ROUTING_5CTX_V1"
    assert plan.execution_order == "listed"
    assert plan.failure_policy == "stop"
    assert plan.dataset_row_schema_version == 2
    assert plan.expected_fault_types == (
        EXPECTED_FAULT_TYPES
    )
    assert (
        plan.repetitions_per_class_context
        == 2
    )
    assert plan.expected_row_count == 30
    assert len(plan.contexts) == 5
    assert {
        context.group_slot: context.split_group_id
        for context in plan.contexts
    } == EXPECTED_GROUPS
    assert sum(
        len(expand_batch_plan(context.batch_plan))
        for context in plan.contexts
    ) == 30


def test_campaign_plan_matches_json_schema() -> None:
    schema = json.loads(
        (
            REPOSITORY_ROOT
            / "schemas"
            / "dataset_campaign_plan_v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    document = read_yaml(CAMPAIGN_PLAN_PATH)

    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(
            schema
        ).iter_errors(document),
        key=lambda error: list(error.path),
    )

    assert errors == []


def test_every_context_batch_has_exact_class_order_and_repetitions(
) -> None:
    plan = load_campaign_plan(
        CAMPAIGN_PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )

    for context in plan.contexts:
        experiments = expand_batch_plan(
            context.batch_plan
        )

        assert len(experiments) == 6
        assert [
            experiment.repetition_index
            for experiment in experiments
        ] == [1, 2, 1, 2, 1, 2]

        observed_fault_types = []
        for entry in context.batch_plan.entries:
            scenario = read_yaml(
                REPOSITORY_ROOT
                / entry.scenario_path
            )["scenario"]
            assert isinstance(scenario, dict)
            ground_truth = scenario["ground_truth"]
            assert isinstance(ground_truth, dict)
            observed_fault_types.append(
                ground_truth["fault_type"]
            )

        assert tuple(observed_fault_types) == (
            EXPECTED_FAULT_TYPES
        )


def test_g01_uses_new_complete_context_bindings_without_relabelling_history(
) -> None:
    historical_names = (
        "N0_NORMAL_OPERATION.yml",
        "C1_MISSING_STATIC_ROUTE.yml",
        "C2_WRONG_NEXT_HOP.yml",
    )
    campaign_names = (
        "N0_NORMAL_OPERATION_G01_TOP01_LINEAR_2R.yml",
        "C1_MISSING_STATIC_ROUTE_G01_TOP01_LINEAR_2R.yml",
        "C2_WRONG_NEXT_HOP_G01_TOP01_LINEAR_2R.yml",
    )
    routing_root = (
        REPOSITORY_ROOT / "scenarios" / "routing"
    )

    for historical_name, campaign_name in zip(
        historical_names,
        campaign_names,
        strict=True,
    ):
        historical = read_yaml(
            routing_root / historical_name
        )["scenario"]
        campaign = read_yaml(
            routing_root / campaign_name
        )["scenario"]

        assert isinstance(historical, dict)
        assert isinstance(campaign, dict)
        assert "split_group_id" not in historical
        assert campaign["split_group_id"] == (
            "CTX_G01_TOP01_LINEAR_2R"
        )
        assert campaign["topology"] == (
            historical["topology"]
        )
        assert campaign["observation"] == (
            historical["observation"]
        )
        assert campaign["ground_truth"] == (
            historical["ground_truth"]
        )


def test_split_allocation_is_frozen_as_deterministic_3_1_1(
) -> None:
    plan = load_campaign_plan(
        CAMPAIGN_PLAN_PATH,
        repository_root=REPOSITORY_ROOT,
    )

    assert plan.split.seed == 20260730
    assert plan.split.ratios == {
        "train": 0.6,
        "validation": 0.2,
        "test": 0.2,
    }
    assert (
        plan.split.expected_group_allocation
        == {
            "train": (
                "CTX_G03_TOP02_BRANCH_MID",
                "CTX_G04_TOP02_DUAL_TRANSIT",
                "CTX_G05_TOP03_ASYMMETRIC_RETURN",
            ),
            "validation": (
                "CTX_G01_TOP01_LINEAR_2R",
            ),
            "test": (
                "CTX_G02_TOP02_CHAIN_3R",
            ),
        }
    )


def test_rejects_declared_row_count_mismatch(
    tmp_path: Path,
) -> None:
    root = prepare_repository(tmp_path)
    path = (
        root
        / "plans"
        / "campaigns"
        / "P2_ROUTING_5CTX_V1.yml"
    )
    document = read_yaml(path)
    campaign = document["campaign"]
    assert isinstance(campaign, dict)
    dataset = campaign["dataset"]
    assert isinstance(dataset, dict)
    dataset["expected_row_count"] = 29
    write_yaml(path, document)

    with pytest.raises(
        CampaignPlanError,
        match="produce 30 rows",
    ):
        load_campaign_plan(
            path,
            repository_root=root,
        )


def test_rejects_context_batch_with_wrong_repetition_count(
    tmp_path: Path,
) -> None:
    root = prepare_repository(tmp_path)
    batch_path = (
        root
        / "plans"
        / "batches"
        / "P2_G03_CAMPAIGN.yml"
    )
    document = read_yaml(batch_path)
    batch = document["batch"]
    assert isinstance(batch, dict)
    entries = batch["entries"]
    assert isinstance(entries, list)
    assert isinstance(entries[1], dict)
    entries[1]["repetitions"] = 1
    write_yaml(batch_path, document)

    with pytest.raises(
        CampaignPlanError,
        match="must use 2 repetitions",
    ):
        load_campaign_plan(
            root
            / "plans"
            / "campaigns"
            / "P2_ROUTING_5CTX_V1.yml",
            repository_root=root,
        )


def test_rejects_scenario_role_binding_mismatch(
    tmp_path: Path,
) -> None:
    root = prepare_repository(tmp_path)
    scenario_path = (
        root
        / "scenarios"
        / "routing"
        / "N0_NORMAL_OPERATION_TOP02_BRANCH.yml"
    )
    document = read_yaml(scenario_path)
    scenario = document["scenario"]
    assert isinstance(scenario, dict)
    observation = scenario["observation"]
    assert isinstance(observation, dict)
    observation["transit_node"] = "r3"
    write_yaml(scenario_path, document)

    with pytest.raises(
        CampaignPlanError,
        match="transit_node",
    ):
        load_campaign_plan(
            root
            / "plans"
            / "campaigns"
            / "P2_ROUTING_5CTX_V1.yml",
            repository_root=root,
        )


def test_rejects_declared_split_allocation_mismatch(
    tmp_path: Path,
) -> None:
    root = prepare_repository(tmp_path)
    path = (
        root
        / "plans"
        / "campaigns"
        / "P2_ROUTING_5CTX_V1.yml"
    )
    document = read_yaml(path)
    campaign = document["campaign"]
    assert isinstance(campaign, dict)
    split = campaign["split"]
    assert isinstance(split, dict)
    allocation = split[
        "expected_group_allocation"
    ]
    assert isinstance(allocation, dict)
    validation = allocation["validation"]
    test = allocation["test"]
    allocation["validation"] = test
    allocation["test"] = validation
    write_yaml(path, document)

    with pytest.raises(
        CampaignPlanError,
        match=(
            "does not match the deterministic "
            "split contract"
        ),
    ):
        load_campaign_plan(
            path,
            repository_root=root,
        )
