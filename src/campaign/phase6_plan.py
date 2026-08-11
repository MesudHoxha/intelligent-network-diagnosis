from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from src.batch.plan import BatchPlan, expand_batch_plan, load_batch_plan
from src.collection.evidence_collector_v3 import load_observation_profile_v2
from src.fault_injection.phase6_common import load_phase6_scenario


class Phase6CampaignPlanError(ValueError):
    """Raised when the frozen P6-R5 campaign plan drifts."""


CLASS_ORDER = (
    "no_fault",
    "missing_static_route",
    "wrong_next_hop",
    "wrong_default_gateway",
    "interface_down",
    "acl_block",
)
SLOT_GROUPS = {
    "E01": "CTX_P6_E01_TOP01_LINEAR_SOURCE_EDGE",
    "E02": "CTX_P6_E02_TOP02_CHAIN_OBSERVER_EDGE",
    "E03": "CTX_P6_E03_TOP02_BRANCH_TARGET_ARM",
    "E04": "CTX_P6_E04_TOP02_DUAL_TRANSIT_SELECTED_ARM",
    "E05": "CTX_P6_E05_TOP03_ASYMMETRIC_FORWARD",
    "E06": "CTX_P6_E06_TOP04_FILTER_BOUNDARY",
}
EXPLICIT_ALLOCATION = {
    "train": (SLOT_GROUPS["E01"], SLOT_GROUPS["E03"], SLOT_GROUPS["E05"]),
    "validation": (SLOT_GROUPS["E04"],),
    "test": (SLOT_GROUPS["E02"], SLOT_GROUPS["E06"]),
}
EXPECTED_ROWS = {"train": 36, "validation": 12, "test": 24}


@dataclass(frozen=True)
class Phase6Context:
    group_slot: str
    topology_id: str
    split_group_id: str
    topology_file: Path
    baseline_validator: Path
    batch_plan_path: Path
    direction: str
    source_node: str
    route_observer_node: str
    transit_node: str
    batch_plan: BatchPlan


@dataclass(frozen=True)
class Phase6CampaignPlan:
    campaign_id: str
    expected_fault_types: tuple[str, ...]
    repetitions_per_class_context: int
    expected_row_count: int
    contexts: tuple[Phase6Context, ...]
    split_allocation: dict[str, tuple[str, ...]]
    split_expected_rows: dict[str, int]


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Phase6CampaignPlanError(f"{label} must be an object.")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise Phase6CampaignPlanError(
            f"{label} keys drifted: expected={sorted(expected)}, "
            f"observed={sorted(value)}."
        )


def _relative_file(
    value: object,
    *,
    repository_root: Path,
    prefix: str,
    suffixes: set[str],
    executable: bool = False,
) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise Phase6CampaignPlanError("Campaign file path is invalid.")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.parts[0] != prefix:
        raise Phase6CampaignPlanError(
            f"Campaign file must remain inside {prefix}/: {value}"
        )
    resolved = (repository_root / path).resolve()
    try:
        resolved.relative_to(repository_root)
    except ValueError as error:
        raise Phase6CampaignPlanError("Campaign file escapes the repository.") from error
    if not resolved.is_file() or resolved.suffix not in suffixes:
        raise Phase6CampaignPlanError(f"Campaign file is missing: {value}")
    if executable and not os.access(resolved, os.X_OK):
        raise Phase6CampaignPlanError(f"Campaign validator is not executable: {value}")
    return path


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise Phase6CampaignPlanError(f"Cannot read YAML: {path}") from error
    return _mapping(value, str(path))


def _validate_topology_profile(
    *,
    repository_root: Path,
    context: Phase6Context,
    scenario: dict[str, Any],
) -> None:
    topology = _read_yaml(repository_root / context.topology_file)
    topology_body = _mapping(topology.get("topology"), "topology")
    nodes = _mapping(topology_body.get("nodes"), "topology.nodes")
    observation = _mapping(scenario.get("observation"), "scenario.observation")
    source = _mapping(nodes.get(context.source_node), "topology source node")
    observer = _mapping(
        nodes.get(context.route_observer_node), "topology observer node"
    )
    source_exec = source.get("exec")
    observer_exec = observer.get("exec")
    if not isinstance(source_exec, list) or not isinstance(observer_exec, list):
        raise Phase6CampaignPlanError(
            f"{context.group_slot} topology nodes require exec lists."
        )
    source_commands = tuple(str(item) for item in source_exec)
    observer_commands = tuple(str(item) for item in observer_exec)
    expected_default = (
        "ip route replace default via "
        f"{observation['source_gateway_address']} dev eth1"
    )
    if expected_default not in source_commands:
        raise Phase6CampaignPlanError(
            f"{context.group_slot} source does not use the reviewed default route."
        )
    destination_prefix = str(observation["destination_prefix"])
    if any(
        command.startswith(f"ip route replace {destination_prefix} ")
        for command in source_commands
    ):
        raise Phase6CampaignPlanError(
            f"{context.group_slot} source-specific route would mask C3."
        )
    expected_route_fragment = (
        f"ip route replace {destination_prefix} via "
        f"{observation['expected_next_hop']}"
    )
    if not any(
        command.startswith(expected_route_fragment) for command in observer_commands
    ):
        raise Phase6CampaignPlanError(
            f"{context.group_slot} observer lacks the exact healthy route."
        )


def _validate_context_scenarios(
    *,
    repository_root: Path,
    context: Phase6Context,
    seen_scenario_ids: set[str],
    acl_rule_tags: set[str],
) -> None:
    entries = context.batch_plan.entries
    if len(entries) != len(CLASS_ORDER):
        raise Phase6CampaignPlanError(
            f"{context.group_slot} must contain six scenario entries."
        )
    observed_labels: list[str] = []
    canonical_observation: dict[str, Any] | None = None
    first_scenario: dict[str, Any] | None = None
    for entry, expected_fault_type in zip(entries, CLASS_ORDER, strict=True):
        if entry.repetitions != 2:
            raise Phase6CampaignPlanError(
                f"{context.group_slot} entries must use two repetitions."
            )
        scenario_path = repository_root / entry.scenario_path
        document = _read_yaml(scenario_path)
        scenario = _mapping(document.get("scenario"), "scenario")
        profile = load_observation_profile_v2(scenario_path)
        scenario_id = scenario.get("id")
        ground_truth = _mapping(scenario.get("ground_truth"), "ground_truth")
        fault_type = ground_truth.get("fault_type")
        if not isinstance(scenario_id, str) or scenario_id in seen_scenario_ids:
            raise Phase6CampaignPlanError("Scenario IDs must be non-empty and unique.")
        seen_scenario_ids.add(scenario_id)
        if fault_type != expected_fault_type:
            raise Phase6CampaignPlanError(
                f"{context.group_slot} class order drifted at {entry.entry_id}."
            )
        observed_labels.append(fault_type)
        topology = _mapping(scenario.get("topology"), "scenario.topology")
        expected_bindings = {
            "topology.id": (topology.get("id"), context.topology_id),
            "topology.file": (
                topology.get("file"),
                context.topology_file.as_posix(),
            ),
            "split_group_id": (
                scenario.get("split_group_id"),
                context.split_group_id,
            ),
            "direction": (profile.direction, context.direction),
            "source_node": (profile.source_node, context.source_node),
            "route_observer_node": (
                profile.route_observer_node,
                context.route_observer_node,
            ),
            "transit_node": (profile.transit_node, context.transit_node),
        }
        for name, (observed, expected) in expected_bindings.items():
            if observed != expected:
                raise Phase6CampaignPlanError(
                    f"{context.group_slot} {name} must be {expected!r}."
                )
        observation = _mapping(scenario.get("observation"), "observation")
        if canonical_observation is None:
            canonical_observation = observation
            first_scenario = scenario
        elif observation != canonical_observation:
            raise Phase6CampaignPlanError(
                f"{context.group_slot} scenarios do not share one observation binding."
            )
        if expected_fault_type == "no_fault":
            if scenario.get("kind") != "normal" or "fault" in scenario:
                raise Phase6CampaignPlanError(
                    f"{context.group_slot} no_fault scenario is not clean normal."
                )
        else:
            binding = load_phase6_scenario(scenario_path, expected_fault_type)
            if expected_fault_type == "acl_block":
                tag = binding.parameters.get("rule_tag")
                if not isinstance(tag, str) or tag in acl_rule_tags:
                    raise Phase6CampaignPlanError(
                        "Phase 6 ACL rule tags must be unique."
                    )
                acl_rule_tags.add(tag)
            if expected_fault_type == "interface_down":
                routes = binding.parameters.get("baseline_routes")
                expected_route = {
                    "prefix": profile.destination_prefix,
                    "next_hop": profile.expected_next_hop,
                }
                if not isinstance(routes, list) or expected_route not in routes:
                    raise Phase6CampaignPlanError(
                        f"{context.group_slot} C4 must bind the selected "
                        "baseline route."
                    )
    if tuple(observed_labels) != CLASS_ORDER or first_scenario is None:
        raise Phase6CampaignPlanError(
            f"{context.group_slot} does not contain the frozen class order."
        )
    _validate_topology_profile(
        repository_root=repository_root,
        context=context,
        scenario=first_scenario,
    )


def load_phase6_campaign_plan(
    plan_path: Path,
    *,
    repository_root: Path | None = None,
) -> Phase6CampaignPlan:
    root = (repository_root or Path.cwd()).resolve()
    resolved_plan = plan_path if plan_path.is_absolute() else root / plan_path
    document = _read_yaml(resolved_plan.resolve())
    _exact_keys(document, {"schema_version", "campaign"}, "plan")
    if document["schema_version"] != 1:
        raise Phase6CampaignPlanError("Phase 6 Campaign Plan version must be 1.")
    campaign = _mapping(document["campaign"], "campaign")
    _exact_keys(
        campaign,
        {"id", "description", "execution", "dataset", "split", "contexts"},
        "campaign",
    )
    if campaign["id"] != "P6_EXTENDED_6CLASS_6CTX_V1":
        raise Phase6CampaignPlanError("Unexpected Phase 6 campaign id.")
    execution = _mapping(campaign["execution"], "execution")
    if execution != {"order": "listed", "failure_policy": "stop"}:
        raise Phase6CampaignPlanError("Phase 6 campaign must be listed/fail-stop.")
    dataset = _mapping(campaign["dataset"], "dataset")
    expected_dataset = {
        "evidence_schema_version": 3,
        "row_schema_version": 3,
        "expected_fault_types": list(CLASS_ORDER),
        "repetitions_per_class_context": 2,
        "expected_row_count": 72,
    }
    if dataset != expected_dataset:
        raise Phase6CampaignPlanError("Phase 6 dataset contract drifted.")
    split = _mapping(campaign["split"], "split")
    allocation = _mapping(split.get("expected_group_allocation"), "allocation")
    parsed_allocation = {
        name: tuple(allocation.get(name, ())) for name in ("train", "validation", "test")
    }
    if (
        split.get("algorithm") != "explicit_complete_context_v1"
        or parsed_allocation != EXPLICIT_ALLOCATION
        or split.get("expected_rows") != EXPECTED_ROWS
        or split.get("test_use") != "report_only_after_p6_r6_freeze"
    ):
        raise Phase6CampaignPlanError("Frozen explicit split contract drifted.")

    raw_contexts = campaign["contexts"]
    if not isinstance(raw_contexts, list) or len(raw_contexts) != 6:
        raise Phase6CampaignPlanError("Phase 6 requires exactly six contexts.")
    contexts: list[Phase6Context] = []
    seen_scenario_ids: set[str] = set()
    acl_rule_tags: set[str] = set()
    for index, raw_context in enumerate(raw_contexts):
        context_data = _mapping(raw_context, f"contexts[{index}]")
        _exact_keys(
            context_data,
            {
                "group_slot",
                "topology_id",
                "split_group_id",
                "topology_file",
                "baseline_validator",
                "batch_plan",
                "observation",
            },
            f"contexts[{index}]",
        )
        slot = context_data["group_slot"]
        if slot != f"E0{index + 1}" or context_data["split_group_id"] != SLOT_GROUPS[slot]:
            raise Phase6CampaignPlanError("Phase 6 context slot/group order drifted.")
        observation = _mapping(context_data["observation"], "context observation")
        _exact_keys(
            observation,
            {"direction", "source_node", "route_observer_node", "transit_node"},
            "context observation",
        )
        topology_file = _relative_file(
            context_data["topology_file"],
            repository_root=root,
            prefix="labs",
            suffixes={".yml", ".yaml"},
        )
        baseline_validator = _relative_file(
            context_data["baseline_validator"],
            repository_root=root,
            prefix="labs",
            suffixes={".sh"},
            executable=True,
        )
        batch_plan_path = _relative_file(
            context_data["batch_plan"],
            repository_root=root,
            prefix="plans",
            suffixes={".yml", ".yaml"},
        )
        batch_plan = load_batch_plan(root / batch_plan_path, repository_root=root)
        context = Phase6Context(
            group_slot=slot,
            topology_id=str(context_data["topology_id"]),
            split_group_id=str(context_data["split_group_id"]),
            topology_file=topology_file,
            baseline_validator=baseline_validator,
            batch_plan_path=batch_plan_path,
            direction=str(observation["direction"]),
            source_node=str(observation["source_node"]),
            route_observer_node=str(observation["route_observer_node"]),
            transit_node=str(observation["transit_node"]),
            batch_plan=batch_plan,
        )
        if len(expand_batch_plan(batch_plan)) != 12:
            raise Phase6CampaignPlanError(f"{slot} must expand to 12 experiments.")
        _validate_context_scenarios(
            repository_root=root,
            context=context,
            seen_scenario_ids=seen_scenario_ids,
            acl_rule_tags=acl_rule_tags,
        )
        contexts.append(context)

    if len(acl_rule_tags) != 6:
        raise Phase6CampaignPlanError("Six unique ACL tags are required.")
    return Phase6CampaignPlan(
        campaign_id="P6_EXTENDED_6CLASS_6CTX_V1",
        expected_fault_types=CLASS_ORDER,
        repetitions_per_class_context=2,
        expected_row_count=72,
        contexts=tuple(contexts),
        split_allocation=parsed_allocation,
        split_expected_rows=dict(EXPECTED_ROWS),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the frozen P6-R5 plan.")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    arguments = parser.parse_args()
    try:
        plan = load_phase6_campaign_plan(
            arguments.plan,
            repository_root=arguments.repository_root,
        )
    except Exception as error:
        print(f"[ERROR] {error}")
        return 1
    print(
        json.dumps(
            {
                "campaign_id": plan.campaign_id,
                "contexts": [
                    {**asdict(context), "batch_plan": context.batch_plan.batch_id}
                    for context in plan.contexts
                ],
                "expected_row_count": plan.expected_row_count,
                "split": plan.split_allocation,
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
