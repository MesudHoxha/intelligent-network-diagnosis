from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.fault_injection.common import (
    CommandResult,
    FaultInjectionError,
    docker_exec,
    ping_succeeds,
    route_exists,
    write_json,
)


@dataclass(frozen=True)
class InjectionRecord:
    scenario_id: str
    fault_type: str
    target_container: str
    target_node: str
    destination_prefix: str
    correct_next_hop: str
    wrong_next_hop: str
    timestamp_utc: str
    preconditions_passed: bool
    injection_applied: bool
    postconditions_passed: bool
    status: str


def route_uses_next_hop(
    container: str,
    prefix: str,
    next_hop: str,
) -> bool:
    result: CommandResult = docker_exec(
        container,
        ["ip", "route", "show", prefix],
    )

    if result.return_code != 0:
        return False

    for line in result.stdout.splitlines():
        fields = line.split()

        if not fields or fields[0] != prefix:
            continue

        for index, field in enumerate(fields[:-1]):
            if (
                field == "via"
                and fields[index + 1] == next_hop
            ):
                return True

    return False


def inject_wrong_next_hop(
    scenario_path: Path,
    output_directory: Path,
) -> InjectionRecord:
    document = yaml.safe_load(
        scenario_path.read_text(encoding="utf-8")
    )
    scenario = document["scenario"]
    fault = scenario["fault"]
    parameters = fault["parameters"]

    scenario_id = str(scenario["id"])
    target_node = str(fault["target_node"])
    container = str(fault["target_container"])
    prefix = str(parameters["destination_prefix"])
    correct_next_hop = str(
        parameters["correct_next_hop"]
    )
    wrong_next_hop = str(
        parameters["wrong_next_hop"]
    )
    egress_interface = str(
        parameters["egress_interface"]
    )

    preconditions = {
        "route_exists_before_injection": route_exists(
            container,
            prefix,
        ),
        "correct_next_hop_present_before_injection": (
            route_uses_next_hop(
                container,
                prefix,
                correct_next_hop,
            )
        ),
        "baseline_end_to_end_connectivity": ping_succeeds(
            "clab-top01-hosta",
            "10.10.2.10",
        ),
        "correct_next_hop_reachable": ping_succeeds(
            container,
            correct_next_hop,
        ),
        "wrong_next_hop_unreachable": not ping_succeeds(
            container,
            wrong_next_hop,
        ),
    }

    preconditions_passed = all(preconditions.values())

    write_json(
        output_directory / "preconditions.json",
        preconditions,
    )

    if not preconditions_passed:
        record = InjectionRecord(
            scenario_id=scenario_id,
            fault_type="wrong_next_hop",
            target_container=container,
            target_node=target_node,
            destination_prefix=prefix,
            correct_next_hop=correct_next_hop,
            wrong_next_hop=wrong_next_hop,
            timestamp_utc=datetime.now(
                timezone.utc
            ).isoformat(),
            preconditions_passed=False,
            injection_applied=False,
            postconditions_passed=False,
            status="INVALID_BASELINE",
        )
        write_json(
            output_directory / "injection_record.json",
            asdict(record),
        )
        raise FaultInjectionError(
            "Preconditions failed. Fault injection "
            "was not attempted."
        )

    replacement = docker_exec(
        container,
        [
            "ip",
            "route",
            "replace",
            prefix,
            "via",
            wrong_next_hop,
            "dev",
            egress_interface,
            "onlink",
        ],
        check=True,
    )

    postconditions = {
        "route_present_after_injection": route_exists(
            container,
            prefix,
        ),
        "wrong_next_hop_present_after_injection": (
            route_uses_next_hop(
                container,
                prefix,
                wrong_next_hop,
            )
        ),
        "correct_next_hop_absent_after_injection": (
            not route_uses_next_hop(
                container,
                prefix,
                correct_next_hop,
            )
        ),
        "end_to_end_connectivity_fails": not ping_succeeds(
            "clab-top01-hosta",
            "10.10.2.10",
        ),
        "local_gateway_remains_reachable": ping_succeeds(
            "clab-top01-hosta",
            "10.10.1.1",
        ),
        "transit_neighbor_remains_reachable": (
            ping_succeeds(
                container,
                correct_next_hop,
            )
        ),
        "wrong_next_hop_remains_unreachable": (
            not ping_succeeds(
                container,
                wrong_next_hop,
            )
        ),
    }

    postconditions_passed = all(postconditions.values())

    write_json(
        output_directory / "postconditions.json",
        postconditions,
    )

    status = (
        "FAULT_CONFIRMED"
        if postconditions_passed
        else "FAULT_NOT_EFFECTIVE"
    )

    record = InjectionRecord(
        scenario_id=scenario_id,
        fault_type="wrong_next_hop",
        target_container=container,
        target_node=target_node,
        destination_prefix=prefix,
        correct_next_hop=correct_next_hop,
        wrong_next_hop=wrong_next_hop,
        timestamp_utc=datetime.now(
            timezone.utc
        ).isoformat(),
        preconditions_passed=True,
        injection_applied=(
            replacement.return_code == 0
        ),
        postconditions_passed=postconditions_passed,
        status=status,
    )

    write_json(
        output_directory / "injection_record.json",
        asdict(record),
    )
    write_json(
        output_directory / "ground_truth.json",
        scenario["ground_truth"],
    )

    if not postconditions_passed:
        raise FaultInjectionError(
            "The route was changed, but the expected "
            "fault effects were not fully confirmed."
        )

    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Inject and validate the wrong-next-hop fault."
        )
    )
    parser.add_argument(
        "--scenario",
        type=Path,
        default=Path(
            "scenarios/routing/"
            "C2_WRONG_NEXT_HOP.yml"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        record = inject_wrong_next_hop(
            args.scenario,
            args.output,
        )
    except FaultInjectionError as error:
        print(f"[ERROR] {error}")
        return 1

    print(json.dumps(asdict(record), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
