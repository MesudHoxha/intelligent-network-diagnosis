from __future__ import annotations

from pathlib import Path

from src.fault_injection.phase6_common import (
    Phase6Executor,
    Phase6FaultInjectionError,
    all_checks_pass,
    build_record,
    docker_exec_result,
    execute_checked,
    interface_state_check,
    load_phase6_scenario,
    observer_route_absent_check,
    observer_route_check,
    ping_check,
    require_new_mutation_output,
    require_restorable_record,
    utc_now,
    write_json_atomic,
)


FAULT_TYPE = "interface_down"


def _interface(binding) -> str:
    interface = binding.parameters.get("interface")
    if interface != binding.profile.observer_egress_interface:
        raise Phase6FaultInjectionError(
            "interface_down target interface drifted from the profile."
        )
    return str(interface)


def _baseline_routes(binding) -> tuple[tuple[str, str], ...]:
    routes = binding.parameters.get("baseline_routes")
    if not isinstance(routes, list) or not routes:
        raise Phase6FaultInjectionError(
            "interface_down requires explicit baseline_routes."
        )
    normalized: list[tuple[str, str]] = []
    for route in routes:
        if (
            not isinstance(route, dict)
            or set(route) != {"prefix", "next_hop"}
            or not isinstance(route.get("prefix"), str)
            or not isinstance(route.get("next_hop"), str)
        ):
            raise Phase6FaultInjectionError(
                "interface_down baseline_routes drifted from the "
                "reviewed binding."
            )
        normalized.append((route["prefix"], route["next_hop"]))
    if len(set(normalized)) != len(normalized):
        raise Phase6FaultInjectionError(
            "interface_down baseline_routes contains duplicates."
        )
    selected_route = (
        binding.profile.destination_prefix,
        binding.profile.expected_next_hop,
    )
    if selected_route not in normalized:
        raise Phase6FaultInjectionError(
            "interface_down baseline_routes omits the selected route."
        )
    return tuple(normalized)


def _baseline_route_checks(
    binding,
    executor: Phase6Executor,
) -> dict[str, dict[str, object]]:
    profile = binding.profile
    interface = _interface(binding)
    checks: dict[str, dict[str, object]] = {}
    for index, (prefix, next_hop) in enumerate(
        _baseline_routes(binding),
        start=1,
    ):
        checks[f"baseline_route_{index:02d}"] = (
            observer_route_check(
                executor,
                profile.route_observer_container,
                prefix,
                next_hop=next_hop,
                interface=interface,
            )
        )
    return checks


def _fault_route_absence_checks(
    binding,
    executor: Phase6Executor,
) -> dict[str, dict[str, object]]:
    profile = binding.profile
    return {
        f"kernel_removed_baseline_route_{index:02d}": (
            observer_route_absent_check(
                executor,
                profile.route_observer_container,
                prefix,
            )
        )
        for index, (prefix, _next_hop) in enumerate(
            _baseline_routes(binding),
            start=1,
        )
    }


def _replace_baseline_routes(
    binding,
    executor: Phase6Executor,
) -> list[dict[str, object]]:
    profile = binding.profile
    interface = _interface(binding)
    results: list[dict[str, object]] = []
    for prefix, next_hop in _baseline_routes(binding):
        arguments = [
            "ip",
            "route",
            "replace",
            prefix,
            "via",
            next_hop,
            "dev",
            interface,
        ]
        results.append(
            execute_checked(
                executor,
                profile.route_observer_container,
                arguments,
            )
        )
    return results


def _healthy_checks(
    binding,
    executor: Phase6Executor,
) -> dict[str, dict[str, object]]:
    profile = binding.profile
    interface = _interface(binding)
    checks = {
        "observer_egress_interface_up": interface_state_check(
            executor,
            profile.route_observer_container,
            interface,
            expected_up=True,
        ),
        "expected_next_hop_reachable": ping_check(
            executor,
            profile.route_observer_container,
            profile.expected_next_hop,
            expected=True,
        ),
        "baseline_destination_reachable": ping_check(
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
    checks.update(_baseline_route_checks(binding, executor))
    return checks


def _fault_checks(
    binding,
    executor: Phase6Executor,
) -> dict[str, dict[str, object]]:
    profile = binding.profile
    interface = _interface(binding)
    checks = {
        "observer_egress_interface_down": interface_state_check(
            executor,
            profile.route_observer_container,
            interface,
            expected_up=False,
        ),
        "expected_next_hop_unreachable": ping_check(
            executor,
            profile.route_observer_container,
            profile.expected_next_hop,
            expected=False,
        ),
        "destination_reachability_fails": ping_check(
            executor,
            profile.source_container,
            profile.destination_address,
            expected=False,
        ),
        "transit_destination_remains_reachable": ping_check(
            executor,
            profile.transit_container,
            profile.destination_address,
            expected=True,
        ),
    }
    checks.update(_fault_route_absence_checks(binding, executor))
    return checks


def inject_interface_down(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = docker_exec_result,
) -> dict[str, object]:
    binding = load_phase6_scenario(scenario_path, FAULT_TYPE)
    output_directory = Path(output_directory)
    require_new_mutation_output(output_directory)
    interface = _interface(binding)
    started = utc_now()
    preconditions = _healthy_checks(binding, executor)
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
            "interface_down preconditions failed; no mutation was "
            "attempted."
        )
    command = execute_checked(
        executor,
        binding.profile.route_observer_container,
        ["ip", "link", "set", "dev", interface, "down"],
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
            "interface_down mutation command failed."
        )
    postconditions = _fault_checks(binding, executor)
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
    record["kernel_route_side_effect"] = {
        "expected": "baseline_routes_absent_while_interface_down",
        "baseline_route_count": len(_baseline_routes(binding)),
    }
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
            restore_interface_down(
                scenario_path,
                output_directory,
                executor=executor,
            )
        except Phase6FaultInjectionError as restoration_error:
            raise Phase6FaultInjectionError(
                "interface_down postconditions failed and exact "
                "restoration also failed."
            ) from restoration_error
        raise Phase6FaultInjectionError(
            "interface_down postconditions failed; the applied mutation "
            "was restored."
        )
    return record


def restore_interface_down(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = docker_exec_result,
) -> dict[str, object]:
    binding = load_phase6_scenario(scenario_path, FAULT_TYPE)
    output_directory = Path(output_directory)
    if (output_directory / "restoration_record.json").exists():
        raise Phase6FaultInjectionError(
            "interface_down restoration was already recorded."
        )
    require_restorable_record(output_directory, binding)
    interface = _interface(binding)
    profile = binding.profile
    started = utc_now()
    preconditions = {
        "exact_injected_interface_state_present": interface_state_check(
            executor,
            profile.route_observer_container,
            interface,
            expected_up=False,
        ),
    }
    preconditions.update(_fault_route_absence_checks(binding, executor))
    command = execute_checked(
        executor,
        profile.route_observer_container,
        ["ip", "link", "set", "dev", interface, "up"],
    )
    route_restoration_commands = _replace_baseline_routes(
        binding,
        executor,
    )
    postconditions = _healthy_checks(binding, executor)
    restored = (
        preconditions["exact_injected_interface_state_present"][
            "passed"
        ]
        is True
        and command["return_code"] == 0
        and all(
            result["return_code"] == 0
            for result in route_restoration_commands
        )
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
        "route_restoration_commands": route_restoration_commands,
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
            "interface_down exact restoration was not confirmed."
        )
    return record
