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
    load_phase6_scenario,
    ping_check,
    require_new_mutation_output,
    require_restorable_record,
    utc_now,
    write_json_atomic,
)


FAULT_TYPE = "wrong_default_gateway"


def _parameters(binding) -> tuple[str, str, str]:
    correct_gateway = binding.parameters.get("correct_gateway")
    wrong_gateway = binding.parameters.get("wrong_gateway")
    source_interface = binding.parameters.get("source_interface")
    if (
        correct_gateway != binding.profile.source_gateway_address
        or not isinstance(wrong_gateway, str)
        or not isinstance(source_interface, str)
        or not source_interface
    ):
        raise Phase6FaultInjectionError(
            "wrong_default_gateway parameters are incomplete or drifted."
        )
    return correct_gateway, wrong_gateway, source_interface


def _preconditions(
    binding,
    executor: Phase6Executor,
) -> dict[str, dict[str, object]]:
    correct_gateway, wrong_gateway, source_interface = _parameters(binding)
    profile = binding.profile
    return {
        "default_route_uses_expected_gateway": default_route_check(
            executor,
            profile.source_container,
            gateway=correct_gateway,
            interface=source_interface,
        ),
        "observed_flow_uses_expected_default_gateway": (
            effective_route_check(
                executor,
                profile.source_container,
                profile.destination_address,
                gateway=correct_gateway,
                interface=source_interface,
            )
        ),
        "expected_gateway_reachable": ping_check(
            executor,
            profile.source_container,
            correct_gateway,
            expected=True,
        ),
        "wrong_gateway_unreachable": ping_check(
            executor,
            profile.source_container,
            wrong_gateway,
            expected=False,
        ),
        "baseline_destination_reachable": ping_check(
            executor,
            profile.source_container,
            profile.destination_address,
            expected=True,
        ),
    }


def _fault_postconditions(
    binding,
    executor: Phase6Executor,
) -> dict[str, dict[str, object]]:
    correct_gateway, wrong_gateway, source_interface = _parameters(binding)
    profile = binding.profile
    return {
        "default_route_uses_wrong_gateway": default_route_check(
            executor,
            profile.source_container,
            gateway=wrong_gateway,
            interface=source_interface,
        ),
        "observed_flow_uses_wrong_default_gateway": effective_route_check(
            executor,
            profile.source_container,
            profile.destination_address,
            gateway=wrong_gateway,
            interface=source_interface,
        ),
        "expected_gateway_remains_reachable": ping_check(
            executor,
            profile.source_container,
            correct_gateway,
            expected=True,
        ),
        "wrong_gateway_remains_unreachable": ping_check(
            executor,
            profile.source_container,
            wrong_gateway,
            expected=False,
        ),
        "destination_reachability_fails": ping_check(
            executor,
            profile.source_container,
            profile.destination_address,
            expected=False,
        ),
    }


def inject_wrong_default_gateway(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = docker_exec_result,
) -> dict[str, object]:
    binding = load_phase6_scenario(scenario_path, FAULT_TYPE)
    output_directory = Path(output_directory)
    require_new_mutation_output(output_directory)
    correct_gateway, wrong_gateway, source_interface = _parameters(binding)
    started = utc_now()
    preconditions = _preconditions(binding, executor)
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
            "wrong_default_gateway preconditions failed; no mutation "
            "was attempted."
        )

    command = execute_checked(
        executor,
        binding.profile.source_container,
        [
            "ip",
            "route",
            "replace",
            "default",
            "via",
            wrong_gateway,
            "dev",
            source_interface,
            "onlink",
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
            "wrong_default_gateway mutation command failed."
        )

    postconditions = _fault_postconditions(binding, executor)
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
            restore_wrong_default_gateway(
                scenario_path,
                output_directory,
                executor=executor,
            )
        except Phase6FaultInjectionError as restoration_error:
            raise Phase6FaultInjectionError(
                "wrong_default_gateway postconditions failed and exact "
                "restoration also failed."
            ) from restoration_error
        raise Phase6FaultInjectionError(
            "wrong_default_gateway postconditions failed; the applied "
            "mutation was restored."
        )
    return record


def restore_wrong_default_gateway(
    scenario_path: Path,
    output_directory: Path,
    *,
    executor: Phase6Executor = docker_exec_result,
) -> dict[str, object]:
    binding = load_phase6_scenario(scenario_path, FAULT_TYPE)
    output_directory = Path(output_directory)
    if (output_directory / "restoration_record.json").exists():
        raise Phase6FaultInjectionError(
            "wrong_default_gateway restoration was already recorded."
        )
    require_restorable_record(output_directory, binding)
    correct_gateway, wrong_gateway, source_interface = _parameters(binding)
    profile = binding.profile
    started = utc_now()
    preconditions = {
        "exact_injected_default_route_present": default_route_check(
            executor,
            profile.source_container,
            gateway=wrong_gateway,
            interface=source_interface,
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
        profile.source_container,
        [
            "ip",
            "route",
            "replace",
            "default",
            "via",
            correct_gateway,
            "dev",
            source_interface,
        ],
    )
    postconditions = {
        "expected_default_route_restored": default_route_check(
            executor,
            profile.source_container,
            gateway=correct_gateway,
            interface=source_interface,
        ),
        "observed_flow_uses_restored_default_gateway": effective_route_check(
            executor,
            profile.source_container,
            profile.destination_address,
            gateway=correct_gateway,
            interface=source_interface,
        ),
        "expected_gateway_reachable": ping_check(
            executor,
            profile.source_container,
            correct_gateway,
            expected=True,
        ),
        "destination_reachability_restored": ping_check(
            executor,
            profile.source_container,
            profile.destination_address,
            expected=True,
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
            "wrong_default_gateway exact restoration was not confirmed."
        )
    return record
