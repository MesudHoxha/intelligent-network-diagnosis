from __future__ import annotations

from pathlib import Path

from src.fault_injection.phase6_common import (
    Phase6Executor,
    Phase6FaultInjectionError,
    all_checks_pass,
    build_record,
    default_route_check,
    docker_exec_result,
    effective_route_check,
    execute_checked,
    interface_state_check,
    load_confirmed_restoration,
    load_phase6_scenario,
    observer_route_absent_check,
    observer_route_check,
    ping_check,
    require_new_mutation_output,
    require_restorable_record,
    utc_now,
    write_recovery_intent,
    write_json_atomic,
)


MISSING_ROUTE = "missing_static_route"
WRONG_NEXT_HOP = "wrong_next_hop"


def _healthy_checks(binding, executor: Phase6Executor):
    profile = binding.profile
    return {
        "source_default_gateway_is_expected": default_route_check(
            executor,
            profile.source_container,
            gateway=profile.source_gateway_address,
            interface="eth1",
        ),
        "selected_flow_uses_expected_gateway": effective_route_check(
            executor,
            profile.source_container,
            profile.destination_address,
            gateway=profile.source_gateway_address,
            interface="eth1",
        ),
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
        "destination_reachable": ping_check(
            executor,
            profile.source_container,
            profile.destination_address,
            expected=True,
        ),
        "transit_destination_reachable": ping_check(
            executor,
            profile.transit_container,
            profile.destination_address,
            expected=True,
        ),
    }


def _fault_common_checks(binding, executor: Phase6Executor):
    profile = binding.profile
    return {
        "source_default_gateway_is_expected": default_route_check(
            executor,
            profile.source_container,
            gateway=profile.source_gateway_address,
            interface="eth1",
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
        "destination_reachability_fails": ping_check(
            executor,
            profile.source_container,
            profile.destination_address,
            expected=False,
        ),
        "transit_destination_reachable": ping_check(
            executor,
            profile.transit_container,
            profile.destination_address,
            expected=True,
        ),
    }


def _write_failed_injection(
    binding,
    output_directory: Path,
    *,
    started: str,
    preconditions,
    mutation_command,
    status: str,
) -> None:
    write_json_atomic(
        output_directory / "injection_record.json",
        build_record(
            binding,
            started_at_utc=started,
            completed_at_utc=utc_now(),
            preconditions=preconditions,
            mutation_command=mutation_command,
            postconditions={},
            status=status,
        ),
    )


def inject_missing_static_route(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = docker_exec_result,
) -> dict[str, object]:
    binding = load_phase6_scenario(scenario_path, MISSING_ROUTE)
    output_directory = Path(output_directory)
    require_new_mutation_output(output_directory)
    profile = binding.profile
    started = utc_now()
    preconditions = _healthy_checks(binding, executor)
    write_json_atomic(output_directory / "preconditions.json", preconditions)
    if not all_checks_pass(preconditions):
        _write_failed_injection(
            binding,
            output_directory,
            started=started,
            preconditions=preconditions,
            mutation_command=None,
            status="INVALID_BASELINE",
        )
        raise Phase6FaultInjectionError(
            "missing_static_route preconditions failed; no mutation was attempted."
        )

    write_recovery_intent(output_directory, binding)

    command = execute_checked(
        executor,
        profile.route_observer_container,
        [
            "ip",
            "route",
            "del",
            profile.destination_prefix,
            "via",
            profile.expected_next_hop,
            "dev",
            profile.observer_egress_interface,
        ],
    )
    if command["return_code"] != 0:
        _write_failed_injection(
            binding,
            output_directory,
            started=started,
            preconditions=preconditions,
            mutation_command=command,
            status="MUTATION_COMMAND_FAILED",
        )
        raise Phase6FaultInjectionError(
            "missing_static_route mutation command failed."
        )

    postconditions = {
        "observer_destination_route_absent": observer_route_absent_check(
            executor,
            profile.route_observer_container,
            profile.destination_prefix,
        ),
        **_fault_common_checks(binding, executor),
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
    write_json_atomic(output_directory / "injection_record.json", record)
    write_json_atomic(
        output_directory / "ground_truth.json",
        binding.scenario["ground_truth"],
    )
    if not confirmed:
        try:
            restore_missing_static_route(
                scenario_path,
                output_directory,
                executor=executor,
            )
        except Phase6FaultInjectionError as restoration_error:
            raise Phase6FaultInjectionError(
                "missing_static_route postconditions and restoration failed."
            ) from restoration_error
        raise Phase6FaultInjectionError(
            "missing_static_route postconditions failed; mutation was restored."
        )
    return record


def restore_missing_static_route(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = docker_exec_result,
) -> dict[str, object]:
    binding = load_phase6_scenario(scenario_path, MISSING_ROUTE)
    output_directory = Path(output_directory)
    existing = load_confirmed_restoration(output_directory, binding)
    if existing is not None:
        return existing
    require_restorable_record(output_directory, binding)
    profile = binding.profile
    started = utc_now()
    preconditions = {
        "exact_destination_route_absent": observer_route_absent_check(
            executor,
            profile.route_observer_container,
            profile.destination_prefix,
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
    }
    command = execute_checked(
        executor,
        profile.route_observer_container,
        [
            "ip",
            "route",
            "replace",
            profile.destination_prefix,
            "via",
            profile.expected_next_hop,
            "dev",
            profile.observer_egress_interface,
        ],
    )
    postconditions = _healthy_checks(binding, executor)
    restored = command["return_code"] == 0 and all_checks_pass(postconditions)
    record = {
        "schema_version": 1,
        "scenario_id": binding.scenario["id"],
        "scenario_sha256": binding.sha256,
        "fault_type": MISSING_ROUTE,
        "target_node": binding.fault["target_node"],
        "target_container": binding.fault["target_container"],
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "preconditions": preconditions,
        "restoration_command": command,
        "postconditions": postconditions,
        "status": (
            "RESTORATION_CONFIRMED" if restored else "RESTORATION_NOT_CONFIRMED"
        ),
    }
    write_json_atomic(output_directory / "restoration_record.json", record)
    if not restored:
        raise Phase6FaultInjectionError(
            "missing_static_route exact restoration was not confirmed."
        )
    return record


def inject_wrong_next_hop_v3(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = docker_exec_result,
) -> dict[str, object]:
    binding = load_phase6_scenario(scenario_path, WRONG_NEXT_HOP)
    output_directory = Path(output_directory)
    require_new_mutation_output(output_directory)
    profile = binding.profile
    wrong_next_hop = str(binding.parameters["wrong_next_hop"])
    wrong_interface = str(binding.parameters["egress_interface"])
    started = utc_now()
    preconditions = {
        **_healthy_checks(binding, executor),
        "wrong_next_hop_unreachable": ping_check(
            executor,
            profile.route_observer_container,
            wrong_next_hop,
            expected=False,
        ),
    }
    write_json_atomic(output_directory / "preconditions.json", preconditions)
    if not all_checks_pass(preconditions):
        _write_failed_injection(
            binding,
            output_directory,
            started=started,
            preconditions=preconditions,
            mutation_command=None,
            status="INVALID_BASELINE",
        )
        raise Phase6FaultInjectionError(
            "wrong_next_hop preconditions failed; no mutation was attempted."
        )

    write_recovery_intent(output_directory, binding)

    command = execute_checked(
        executor,
        profile.route_observer_container,
        [
            "ip",
            "route",
            "replace",
            profile.destination_prefix,
            "via",
            wrong_next_hop,
            "dev",
            wrong_interface,
            "onlink",
        ],
    )
    if command["return_code"] != 0:
        _write_failed_injection(
            binding,
            output_directory,
            started=started,
            preconditions=preconditions,
            mutation_command=command,
            status="MUTATION_COMMAND_FAILED",
        )
        raise Phase6FaultInjectionError("wrong_next_hop mutation command failed.")

    postconditions = {
        "observer_route_uses_wrong_next_hop": observer_route_check(
            executor,
            profile.route_observer_container,
            profile.destination_prefix,
            next_hop=wrong_next_hop,
            interface=wrong_interface,
        ),
        "wrong_next_hop_unreachable": ping_check(
            executor,
            profile.route_observer_container,
            wrong_next_hop,
            expected=False,
        ),
        **_fault_common_checks(binding, executor),
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
    write_json_atomic(output_directory / "injection_record.json", record)
    write_json_atomic(
        output_directory / "ground_truth.json",
        binding.scenario["ground_truth"],
    )
    if not confirmed:
        try:
            restore_wrong_next_hop_v3(
                scenario_path,
                output_directory,
                executor=executor,
            )
        except Phase6FaultInjectionError as restoration_error:
            raise Phase6FaultInjectionError(
                "wrong_next_hop postconditions and restoration failed."
            ) from restoration_error
        raise Phase6FaultInjectionError(
            "wrong_next_hop postconditions failed; mutation was restored."
        )
    return record


def restore_wrong_next_hop_v3(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = docker_exec_result,
) -> dict[str, object]:
    binding = load_phase6_scenario(scenario_path, WRONG_NEXT_HOP)
    output_directory = Path(output_directory)
    existing = load_confirmed_restoration(output_directory, binding)
    if existing is not None:
        return existing
    require_restorable_record(output_directory, binding)
    profile = binding.profile
    wrong_next_hop = str(binding.parameters["wrong_next_hop"])
    wrong_interface = str(binding.parameters["egress_interface"])
    started = utc_now()
    preconditions = {
        "exact_wrong_route_present": observer_route_check(
            executor,
            profile.route_observer_container,
            profile.destination_prefix,
            next_hop=wrong_next_hop,
            interface=wrong_interface,
        ),
        "wrong_next_hop_unreachable": ping_check(
            executor,
            profile.route_observer_container,
            wrong_next_hop,
            expected=False,
        ),
    }
    command = execute_checked(
        executor,
        profile.route_observer_container,
        [
            "ip",
            "route",
            "replace",
            profile.destination_prefix,
            "via",
            profile.expected_next_hop,
            "dev",
            profile.observer_egress_interface,
        ],
    )
    postconditions = _healthy_checks(binding, executor)
    restored = command["return_code"] == 0 and all_checks_pass(postconditions)
    record = {
        "schema_version": 1,
        "scenario_id": binding.scenario["id"],
        "scenario_sha256": binding.sha256,
        "fault_type": WRONG_NEXT_HOP,
        "target_node": binding.fault["target_node"],
        "target_container": binding.fault["target_container"],
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "preconditions": preconditions,
        "restoration_command": command,
        "postconditions": postconditions,
        "status": (
            "RESTORATION_CONFIRMED" if restored else "RESTORATION_NOT_CONFIRMED"
        ),
    }
    write_json_atomic(output_directory / "restoration_record.json", record)
    if not restored:
        raise Phase6FaultInjectionError(
            "wrong_next_hop exact restoration was not confirmed."
        )
    return record
