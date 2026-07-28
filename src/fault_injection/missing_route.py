from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.fault_injection.common import (
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
    next_hop: str
    timestamp_utc: str
    preconditions_passed: bool
    injection_applied: bool
    postconditions_passed: bool
    status: str


def inject_missing_route(
    scenario_path: Path,
    output_directory: Path,
) -> InjectionRecord:
    scenario_document = yaml.safe_load(
        scenario_path.read_text(encoding="utf-8")
    )
    scenario = scenario_document["scenario"]
    fault = scenario["fault"]
    parameters = fault["parameters"]

    scenario_id = str(scenario["id"])
    container = str(fault["target_container"])
    target_node = str(fault["target_node"])
    prefix = str(parameters["destination_prefix"])
    next_hop = str(parameters["next_hop"])

    preconditions = {
        "route_exists_before_injection": route_exists(container, prefix),
        "baseline_end_to_end_connectivity": ping_succeeds(
            "clab-top01-hosta",
            "10.10.2.10",
        ),
        "next_hop_reachable": ping_succeeds(container, next_hop),
    }

    preconditions_passed = all(preconditions.values())

    write_json(
        output_directory / "preconditions.json",
        preconditions,
    )

    if not preconditions_passed:
        record = InjectionRecord(
            scenario_id=scenario_id,
            fault_type="missing_static_route",
            target_container=container,
            target_node=target_node,
            destination_prefix=prefix,
            next_hop=next_hop,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
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
            "Preconditions failed. Fault injection was not attempted."
        )

    removal = docker_exec(
        container,
        ["ip", "route", "del", prefix, "via", next_hop],
        check=True,
    )

    postconditions = {
        "route_absent_after_injection": not route_exists(
            container,
            prefix,
        ),
        "end_to_end_connectivity_fails": not ping_succeeds(
            "clab-top01-hosta",
            "10.10.2.10",
        ),
        "local_gateway_remains_reachable": ping_succeeds(
            "clab-top01-hosta",
            "10.10.1.1",
        ),
        "transit_next_hop_remains_reachable": ping_succeeds(
            container,
            next_hop,
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
        fault_type="missing_static_route",
        target_container=container,
        target_node=target_node,
        destination_prefix=prefix,
        next_hop=next_hop,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        preconditions_passed=True,
        injection_applied=removal.return_code == 0,
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
            "The route was changed, but the expected fault effects "
            "were not fully confirmed."
        )

    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inject and validate the missing-route PoC fault."
    )
    parser.add_argument(
        "--scenario",
        type=Path,
        default=Path(
            "scenarios/routing/C1_MISSING_STATIC_ROUTE.yml"
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
        record = inject_missing_route(
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
