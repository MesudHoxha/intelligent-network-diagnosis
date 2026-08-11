from __future__ import annotations

import copy
import json
from collections.abc import Sequence
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from src.campaign.phase6_plan import (
    CLASS_ORDER,
    EXPLICIT_ALLOCATION,
    EXPECTED_ROWS,
    load_phase6_campaign_plan,
)
from src.campaign.phase6_runner import (
    Phase6CampaignRunnerError,
    load_fingerprint_manifest,
    run_phase6_campaign,
)
from src.contracts.evidence_v3 import EVIDENCE_V3_FEATURE_NAMES
from src.dataset.contract_v3 import validate_dataset_row_v3
from src.dataset.explicit_splitter_v3 import (
    ExplicitSplitV3Error,
    plan_explicit_complete_context_split_v3,
    write_explicit_complete_context_split_v3,
)
from src.fault_injection.phase6_common import load_phase6_scenario
from src.planning.fault_taxonomy import EXPECTED_SIGNATURES, FEATURE_ORDER


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = Path("plans/campaigns/P6_EXTENDED_6CLASS_6CTX_V1.yml")
FINGERPRINT_PATH = Path(
    "plans/campaigns/P6_EXTENDED_6CLASS_6CTX_V1.fingerprints.json"
)
TIMESTAMP = "2026-08-10T08:00:00+00:00"


def _row(
    *,
    sample_id: str,
    context,
    fault_type: str,
    scenario_id: str | None = None,
) -> dict[str, object]:
    signature = dict(
        zip(FEATURE_ORDER, EXPECTED_SIGNATURES[fault_type], strict=True)
    )
    availability = {
        feature_name: (
            "structurally_unavailable"
            if signature[feature_name] == "unavailable"
            else "observed"
        )
        for feature_name in EVIDENCE_V3_FEATURE_NAMES
    }
    unavailable = sum(value == "unavailable" for value in signature.values())
    row = {
        "schema_version": 3,
        "sample_id": sample_id,
        "metadata": {
            "experiment_id": sample_id,
            "scenario_id": scenario_id or f"P6_{context.group_slot}_{fault_type}",
            "variant_id": f"p6_{context.group_slot.lower()}_clean_v1",
            "split_group_id": context.split_group_id,
            "topology_id": context.topology_id,
            "direction": context.direction,
            "source_node": context.source_node,
            "route_observer_node": context.route_observer_node,
            "transit_node": context.transit_node,
            "collected_at_utc": TIMESTAMP,
        },
        "features": signature,
        "labels": {
            "fault_category": None if fault_type == "no_fault" else "routing",
            "fault_type": fault_type,
            "fault_location": None if fault_type == "no_fault" else context.route_observer_node,
            "affected_prefix": None if fault_type == "no_fault" else "10.0.0.0/24",
        },
        "quality": {
            "experiment_completed": True,
            "collector_completed": True,
            "baseline_before_valid": True,
            "baseline_after_valid": True,
            "unavailable_feature_count": unavailable,
            "structural_unavailable_count": unavailable,
            "collection_unavailable_count": 0,
            "masked_missing_count": 0,
        },
        "provenance": {
            "source_evidence_schema_version": 3,
            "source_evidence_sha256": "a" * 64,
            "feature_availability": availability,
            "mask_id": None,
        },
    }
    validate_dataset_row_v3(row)
    return row


def _rows(plan) -> list[dict[str, object]]:
    return [
        _row(
            sample_id=f"sample-{context.group_slot}-{fault_type}-{repetition}",
            context=context,
            fault_type=fault_type,
        )
        for context in plan.contexts
        for fault_type in CLASS_ORDER
        for repetition in (1, 2)
    ]


def test_phase6_plan_schema_semantics_and_fingerprints() -> None:
    schema = json.loads(
        Path("schemas/phase6_campaign_plan_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    document = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(document)

    plan = load_phase6_campaign_plan(PLAN_PATH, repository_root=ROOT)
    records = load_fingerprint_manifest(
        FINGERPRINT_PATH,
        campaign_plan=plan,
        repository_root=ROOT,
    )

    assert len(plan.contexts) == 6
    assert plan.expected_fault_types == CLASS_ORDER
    assert plan.expected_row_count == 72
    assert plan.split_allocation == EXPLICIT_ALLOCATION
    assert plan.split_expected_rows == EXPECTED_ROWS
    assert set(records) == {f"E0{index}" for index in range(1, 7)}
    assert all(len(record["files"]) == 9 for record in records.values())


def test_all_36_phase6_scenarios_are_profile_bound_and_faults_load() -> None:
    plan = load_phase6_campaign_plan(PLAN_PATH, repository_root=ROOT)
    scenario_ids: set[str] = set()
    for context in plan.contexts:
        for entry, fault_type in zip(
            context.batch_plan.entries, CLASS_ORDER, strict=True
        ):
            document = yaml.safe_load(
                (ROOT / entry.scenario_path).read_text(encoding="utf-8")
            )
            scenario = document["scenario"]
            scenario_ids.add(scenario["id"])
            assert scenario["topology"]["id"] == context.topology_id
            assert scenario["split_group_id"] == context.split_group_id
            assert scenario["ground_truth"]["fault_type"] == fault_type
            if fault_type != "no_fault":
                binding = load_phase6_scenario(ROOT / entry.scenario_path, fault_type)
                assert binding.profile.route_observer_node == context.route_observer_node
                if fault_type == "interface_down":
                    expected_route = {
                        "prefix": binding.profile.destination_prefix,
                        "next_hop": binding.profile.expected_next_hop,
                    }
                    assert "preserved_routes" not in binding.parameters
                    assert expected_route in binding.parameters["baseline_routes"]
    assert len(scenario_ids) == 36


def test_top04_is_an_explicit_forwarding_policy_boundary() -> None:
    topology = yaml.safe_load(
        Path(
            "labs/topologies/p6_e06_top04_filter_boundary/topology.clab.yml"
        ).read_text(encoding="utf-8")
    )
    nodes = topology["topology"]["nodes"]
    assert "fw1" in nodes
    assert any(
        command.startswith("iptables ") and "-P FORWARD ACCEPT" in command
        for command in nodes["fw1"]["exec"]
    )
    assert nodes["hosta"]["exec"][-1] == "ip route replace default via 10.60.1.1 dev eth1"


def test_explicit_split_is_exact_complete_context_and_seals_test(
    tmp_path: Path,
) -> None:
    plan = load_phase6_campaign_plan(PLAN_PATH, repository_root=ROOT)
    rows = _rows(plan)
    split = plan_explicit_complete_context_split_v3(
        rows,
        allocation=plan.split_allocation,
        expected_fault_types=plan.expected_fault_types,
        repetitions_per_class_context=2,
        expected_rows=plan.split_expected_rows,
    )
    assert {name: len(values) for name, values in split.partitions.items()} == {
        "train": 36,
        "validation": 12,
        "test": 24,
    }
    assert split.manifest["partitions"]["test"]["usage"] == (
        "sealed_report_only_after_p6_r6_freeze"
    )

    input_path = tmp_path / "rows.jsonl"
    input_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    output = tmp_path / "split"
    manifest = write_explicit_complete_context_split_v3(
        input_path,
        output,
        allocation=plan.split_allocation,
        expected_fault_types=plan.expected_fault_types,
        repetitions_per_class_context=2,
        expected_rows=plan.split_expected_rows,
    )
    assert manifest["no_cross_partition_group"] is True
    assert all((output / f"{name}.jsonl").is_file() for name in ("train", "validation", "test"))


def test_explicit_split_rejects_masks_and_cross_partition_groups() -> None:
    plan = load_phase6_campaign_plan(PLAN_PATH, repository_root=ROOT)
    rows = _rows(plan)
    masked = copy.deepcopy(rows)
    masked[0]["features"]["flow_blocked_by_policy"] = "unavailable"
    masked[0]["provenance"]["feature_availability"]["flow_blocked_by_policy"] = "masked_missing"
    masked[0]["provenance"]["mask_id"] = "mask_policy_state"
    masked[0]["quality"]["unavailable_feature_count"] = 1
    masked[0]["quality"]["masked_missing_count"] = 1
    with pytest.raises(ExplicitSplitV3Error, match="cannot contain masked rows"):
        plan_explicit_complete_context_split_v3(
            masked,
            allocation=plan.split_allocation,
            expected_fault_types=plan.expected_fault_types,
        )

    invalid_allocation = {name: list(values) for name, values in plan.split_allocation.items()}
    invalid_allocation["test"][0] = invalid_allocation["train"][0]
    with pytest.raises(ExplicitSplitV3Error, match="crosses partitions"):
        plan_explicit_complete_context_split_v3(
            rows,
            allocation=invalid_allocation,
            expected_fault_types=plan.expected_fault_types,
        )


class FakeCommands:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, command: Sequence[str], cwd: Path) -> dict[str, object]:
        arguments = tuple(command)
        self.commands.append(arguments)
        return {
            "command": list(arguments),
            "return_code": 0,
            "stdout": "" if arguments[:2] == ("docker", "ps") else "ok\n",
            "stderr": "",
            "timestamp_utc": TIMESTAMP,
        }


class FakeExperiments:
    def __init__(self, plan, *, fail_at: int | None = None) -> None:
        self.plan = plan
        self.fail_at = fail_at
        self.calls = 0
        self.rows: dict[Path, dict[str, object]] = {}
        self.contexts = {
            context.topology_id: context for context in plan.contexts
        }

    def run(
        self,
        scenario_path: Path,
        output_root: Path,
        baseline_validator_path: Path,
    ) -> dict[str, object]:
        self.calls += 1
        if self.calls == self.fail_at:
            raise RuntimeError("synthetic fail-stop")
        scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))["scenario"]
        context = self.contexts[scenario["topology"]["id"]]
        experiment_id = f"experiment-{self.calls:03d}"
        directory = output_root / experiment_id
        directory.mkdir(parents=True, exist_ok=False)
        fault_type = scenario["ground_truth"]["fault_type"]
        self.rows[directory.resolve()] = _row(
            sample_id=experiment_id,
            context=context,
            fault_type=fault_type,
            scenario_id=scenario["id"],
        )
        return {
            "status": "COMPLETED",
            "experiment_id": experiment_id,
            "experiment_directory": str(directory),
            "scenario_id": scenario["id"],
            "scenario_kind": scenario["kind"],
            "fault_type": fault_type,
            "topology_id": context.topology_id,
            "split_group_id": context.split_group_id,
            "evidence_schema_version": 3,
            "baseline_valid_after": True,
            "restoration_confirmed": True,
            "diagnosis_created": False,
            "prediction_created": False,
            "metric_created": False,
        }

    def build_row(self, directory: Path) -> dict[str, object]:
        return copy.deepcopy(self.rows[directory.resolve()])


def test_campaign_runner_accepts_72_rows_and_no_evaluation(tmp_path: Path) -> None:
    plan = load_phase6_campaign_plan(PLAN_PATH, repository_root=ROOT)
    commands = FakeCommands()
    experiments = FakeExperiments(plan)
    result = run_phase6_campaign(
        plan_path=PLAN_PATH,
        fingerprint_manifest_path=FINGERPRINT_PATH,
        repository_root=ROOT,
        output_root=tmp_path / "raw",
        processed_root=tmp_path / "processed",
        metadata_root=tmp_path / "metadata",
        command_executor=commands,
        experiment_executor=experiments.run,
        row_builder=experiments.build_row,
        campaign_run_id="p6-r5-test-success",
    )
    assert result["status"] == "COMPLETED"
    assert result["dataset_row_count"] == 72
    assert result["diagnosis_count"] == 0
    assert result["prediction_count"] == 0
    assert result["metric_count"] == 0
    assert result["test_partition_status"] == "SEALED_FOR_P6_R6_REPORT_ONLY"
    assert {
        name: item["row_count"]
        for name, item in result["split"]["partitions"].items()
    } == {"train": 36, "validation": 12, "test": 24}
    assert experiments.calls == 72
    assert sum(command[:3] == ("sudo", "containerlab", "deploy") for command in commands.commands) == 6
    assert sum(command[:3] == ("sudo", "containerlab", "destroy") for command in commands.commands) == 6

    schema = json.loads(
        Path("schemas/phase6_campaign_result_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(result)


def test_campaign_runner_is_fail_stop_and_still_destroys(tmp_path: Path) -> None:
    plan = load_phase6_campaign_plan(PLAN_PATH, repository_root=ROOT)
    commands = FakeCommands()
    experiments = FakeExperiments(plan, fail_at=3)
    with pytest.raises(Phase6CampaignRunnerError, match="synthetic fail-stop"):
        run_phase6_campaign(
            plan_path=PLAN_PATH,
            fingerprint_manifest_path=FINGERPRINT_PATH,
            repository_root=ROOT,
            output_root=tmp_path / "raw",
            processed_root=tmp_path / "processed",
            metadata_root=tmp_path / "metadata",
            command_executor=commands,
            experiment_executor=experiments.run,
            row_builder=experiments.build_row,
            campaign_run_id="p6-r5-test-failure",
        )
    assert experiments.calls == 3
    assert sum(command[:3] == ("sudo", "containerlab", "destroy") for command in commands.commands) == 1
    result = json.loads(
        (tmp_path / "metadata/p6-r5-test-failure.phase6-campaign.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["status"] == "FAILED"
    assert result["failed_context"] == "E01"
    assert result["split"] is None
