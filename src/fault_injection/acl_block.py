from __future__ import annotations

import shlex
from pathlib import Path

from src.collection.evidence_collector_v3 import (
    parse_matching_block_rule,
)
from src.fault_injection.phase6_common import (
    Phase6Executor,
    Phase6FaultInjectionError,
    all_checks_pass,
    build_record,
    check,
    docker_exec_result,
    execute_checked,
    interface_state_check,
    load_phase6_scenario,
    observer_route_check,
    ping_check,
    require_new_mutation_output,
    require_restorable_record,
    utc_now,
    write_json_atomic,
)


FAULT_TYPE = "acl_block"


def _rule_tag(binding) -> str:
    rule_tag = binding.parameters.get("rule_tag")
    if (
        not isinstance(rule_tag, str)
        or not rule_tag.startswith(
            binding.profile.policy_rule_tag_prefix
        )
    ):
        raise Phase6FaultInjectionError(
            "acl_block rule tag drifted from the profile."
        )
    return rule_tag


def _rule_selector(binding) -> list[str]:
    profile = binding.profile
    selector = [
        "-s",
        profile.source_address,
        "-d",
        profile.destination_address,
        "-p",
        profile.flow_protocol,
    ]
    if profile.flow_protocol in {"tcp", "udp"}:
        selector.extend(
            [
                "-m",
                profile.flow_protocol,
                "--sport",
                str(profile.flow_source_port),
                "--dport",
                str(profile.flow_destination_port),
            ]
        )
    selector.extend(
        [
            "-m",
            "comment",
            "--comment",
            _rule_tag(binding),
            "-j",
            "DROP",
        ]
    )
    return selector


def _tagged_comments(stdout: str, prefix: str) -> list[str] | None:
    comments: list[str] = []
    try:
        for raw_line in stdout.splitlines():
            tokens = shlex.split(raw_line.strip())
            indexes = [
                index
                for index, token in enumerate(tokens)
                if token == "--comment"
            ]
            if not indexes:
                continue
            if len(indexes) != 1 or indexes[0] + 1 >= len(tokens):
                return None
            comment = tokens[indexes[0] + 1]
            if comment.startswith(prefix):
                comments.append(comment)
    except ValueError:
        return None
    return comments


def _policy_check(
    binding,
    executor: Phase6Executor,
    *,
    expected_rule_tag: str | None,
) -> dict[str, object]:
    profile = binding.profile
    result = execute_checked(
        executor,
        profile.route_observer_container,
        [
            "iptables",
            "-w",
            "2",
            "-t",
            profile.policy_table,
            "-S",
            profile.policy_chain,
        ],
    )
    policy_available, matching_rule = parse_matching_block_rule(
        result,
        profile,
    )
    tagged_comments = _tagged_comments(
        str(result["stdout"]),
        profile.policy_rule_tag_prefix,
    )
    expected_comments = (
        [] if expected_rule_tag is None else [expected_rule_tag]
    )
    observed = {
        "matching_rule": matching_rule,
        "tagged_comments": tagged_comments,
    }
    return check(
        result["return_code"] == 0
        and policy_available
        and matching_rule == expected_rule_tag
        and tagged_comments == expected_comments,
        result,
        observed=observed,
    )


def _network_checks(
    binding,
    executor: Phase6Executor,
    *,
    destination_reachable: bool,
) -> dict[str, dict[str, object]]:
    profile = binding.profile
    return {
        "observer_route_uses_expected_next_hop": observer_route_check(
            executor,
            profile.route_observer_container,
            profile.destination_prefix,
            next_hop=profile.expected_next_hop,
            interface=profile.observer_egress_interface,
        ),
        "observer_egress_interface_up": interface_state_check(
            executor,
            profile.route_observer_container,
            profile.observer_egress_interface,
            expected_up=True,
        ),
        "expected_next_hop_reachable": ping_check(
            executor,
            profile.route_observer_container,
            profile.expected_next_hop,
            expected=True,
        ),
        "destination_reachability_matches_expected": ping_check(
            executor,
            profile.source_container,
            profile.destination_address,
            expected=destination_reachable,
        ),
        "transit_destination_reachable": ping_check(
            executor,
            profile.transit_container,
            profile.destination_address,
            expected=True,
        ),
    }


def inject_acl_block(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = docker_exec_result,
) -> dict[str, object]:
    binding = load_phase6_scenario(scenario_path, FAULT_TYPE)
    output_directory = Path(output_directory)
    require_new_mutation_output(output_directory)
    profile = binding.profile
    rule_tag = _rule_tag(binding)
    started = utc_now()
    preconditions = {
        "no_p6_tagged_rule_present": _policy_check(
            binding,
            executor,
            expected_rule_tag=None,
        ),
        **_network_checks(
            binding,
            executor,
            destination_reachable=True,
        ),
    }
    write_json_atomic(
        output_directory / "preconditions.json",
        preconditions,
    )
    if not all_checks_pass(preconditions):
        record = build_record(
            binding,
            started_at_utc=started,
            completed_at_utc=utc_now(),
            preconditions=preconditions,
            mutation_command=None,
            postconditions={},
            status="INVALID_BASELINE",
        )
        write_json_atomic(
            output_directory / "injection_record.json",
            record,
        )
        raise Phase6FaultInjectionError(
            "acl_block preconditions failed; no mutation was attempted."
        )
    command = execute_checked(
        executor,
        profile.route_observer_container,
        [
            "iptables",
            "-w",
            "2",
            "-t",
            profile.policy_table,
            "-I",
            profile.policy_chain,
            "1",
            *_rule_selector(binding),
        ],
    )
    if command["return_code"] != 0:
        record = build_record(
            binding,
            started_at_utc=started,
            completed_at_utc=utc_now(),
            preconditions=preconditions,
            mutation_command=command,
            postconditions={},
            status="MUTATION_COMMAND_FAILED",
        )
        write_json_atomic(
            output_directory / "injection_record.json",
            record,
        )
        raise Phase6FaultInjectionError(
            "acl_block mutation command failed."
        )
    postconditions = {
        "exact_tagged_rule_present": _policy_check(
            binding,
            executor,
            expected_rule_tag=rule_tag,
        ),
        **_network_checks(
            binding,
            executor,
            destination_reachable=False,
        ),
    }
    confirmed = all_checks_pass(postconditions)
    record = build_record(
        binding,
        started_at_utc=started,
        completed_at_utc=utc_now(),
        preconditions=preconditions,
        mutation_command=command,
        postconditions=postconditions,
        status="FAULT_CONFIRMED" if confirmed else "FAULT_NOT_CONFIRMED",
    )
    write_json_atomic(
        output_directory / "injection_record.json",
        record,
    )
    write_json_atomic(
        output_directory / "ground_truth.json",
        binding.scenario["ground_truth"],
    )
    if not confirmed:
        try:
            restore_acl_block(
                scenario_path,
                output_directory,
                executor=executor,
            )
        except Phase6FaultInjectionError as restoration_error:
            raise Phase6FaultInjectionError(
                "acl_block postconditions failed and exact restoration "
                "also failed."
            ) from restoration_error
        raise Phase6FaultInjectionError(
            "acl_block postconditions failed; the applied mutation was "
            "restored."
        )
    return record


def restore_acl_block(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = docker_exec_result,
) -> dict[str, object]:
    binding = load_phase6_scenario(scenario_path, FAULT_TYPE)
    output_directory = Path(output_directory)
    if (output_directory / "restoration_record.json").exists():
        raise Phase6FaultInjectionError(
            "acl_block restoration was already recorded."
        )
    require_restorable_record(output_directory, binding)
    profile = binding.profile
    rule_tag = _rule_tag(binding)
    started = utc_now()
    preconditions = {
        "exact_tagged_rule_present": _policy_check(
            binding,
            executor,
            expected_rule_tag=rule_tag,
        ),
        "fault_effect_still_present": ping_check(
            executor,
            profile.source_container,
            profile.destination_address,
            expected=False,
        ),
    }
    command = execute_checked(
        executor,
        profile.route_observer_container,
        [
            "iptables",
            "-w",
            "2",
            "-t",
            profile.policy_table,
            "-D",
            profile.policy_chain,
            *_rule_selector(binding),
        ],
    )
    postconditions = {
        "no_p6_tagged_rule_remains": _policy_check(
            binding,
            executor,
            expected_rule_tag=None,
        ),
        **_network_checks(
            binding,
            executor,
            destination_reachable=True,
        ),
    }
    restored = (
        all_checks_pass(preconditions)
        and command["return_code"] == 0
        and all_checks_pass(postconditions)
    )
    record = {
        "schema_version": 1,
        "scenario_id": binding.scenario["id"],
        "scenario_sha256": binding.sha256,
        "fault_type": FAULT_TYPE,
        "target_node": binding.fault["target_node"],
        "target_container": binding.fault["target_container"],
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "preconditions": preconditions,
        "restoration_command": command,
        "postconditions": postconditions,
        "status": (
            "RESTORATION_CONFIRMED"
            if restored
            else "RESTORATION_NOT_CONFIRMED"
        ),
    }
    write_json_atomic(
        output_directory / "restoration_record.json",
        record,
    )
    if not restored:
        raise Phase6FaultInjectionError(
            "acl_block exact restoration was not confirmed."
        )
    return record
