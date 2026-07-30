from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import yaml

from src.contracts.observation_profile import (
    ObservationProfile,
    validate_observation_profile,
)


def run_command(command: Sequence[str]) -> dict[str, object]:
    """Execute a command and return a structured result."""
    process = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=False,
    )

    return {
        "command": list(command),
        "return_code": process.returncode,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def docker_exec(
    container: str,
    command: Sequence[str],
) -> dict[str, object]:
    return run_command(
        ["docker", "exec", container, *command]
    )


def ping_result(container: str, address: str) -> dict[str, object]:
    return docker_exec(
        container,
        ["ping", "-c", "2", "-W", "1", address],
    )


def route_result(container: str, prefix: str) -> dict[str, object]:
    return docker_exec(
        container,
        ["ip", "route", "show", prefix],
    )


def ping_succeeded(result: dict[str, object]) -> bool | None:
    return_code = result["return_code"]

    if return_code == 0:
        return True

    if return_code == 1:
        return False

    return None


def route_exists(result: dict[str, object]) -> bool | None:
    if result["return_code"] != 0:
        return None

    return bool(str(result["stdout"]).strip())


def route_next_hop(
    result: dict[str, object],
) -> str | None:
    if result["return_code"] != 0:
        return None

    fields = str(result["stdout"]).split()

    for index, field in enumerate(fields[:-1]):
        if field == "via":
            return fields[index + 1]

    return None


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def collect_evidence(
    output_directory: Path,
    profile: ObservationProfile,
) -> dict[str, object]:
    r1_route_to_hostb = route_result(
        profile.route_observer_container,
        profile.destination_prefix,
    )

    raw_results = {
        "hosta_ping_gateway": ping_result(
            profile.source_container,
            profile.source_gateway_address,
        ),
        "hosta_ping_hostb": ping_result(
            profile.source_container,
            profile.destination_address,
        ),
        "r1_route_to_hostb": r1_route_to_hostb,
        "r1_ping_r2": ping_result(
            profile.route_observer_container,
            profile.expected_next_hop,
        ),
        "r2_ping_hostb": ping_result(
            profile.transit_container,
            profile.destination_address,
        ),
    }

    configured_next_hop = route_next_hop(
        r1_route_to_hostb
    )

    if configured_next_hop is not None:
        raw_results[
            "r1_ping_configured_next_hop"
        ] = ping_result(
            profile.route_observer_container,
            configured_next_hop,
        )

    for probe_name, result in raw_results.items():
        write_json(
            output_directory
            / "raw"
            / f"{probe_name}.json",
            result,
        )

    evidence = {
        "schema_version": 1,
        "topology_id": "TOP_01",
        "collected_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_gateway_reachable": ping_succeeded(
            raw_results["hosta_ping_gateway"]
        ),
        "destination_reachable": ping_succeeded(
            raw_results["hosta_ping_hostb"]
        ),
        "route_to_destination_exists_on_r1": route_exists(
            raw_results["r1_route_to_hostb"]
        ),
        "route_next_hop_on_r1": configured_next_hop,
        "route_next_hop_reachable_from_r1": (
            ping_succeeded(
                raw_results[
                    "r1_ping_configured_next_hop"
                ]
            )
            if "r1_ping_configured_next_hop"
            in raw_results
            else None
        ),
        "transit_next_hop_reachable": ping_succeeded(
            raw_results["r1_ping_r2"]
        ),
        "destination_reachable_from_r2": ping_succeeded(
            raw_results["r2_ping_hostb"]
        ),
    }

    write_json(
        output_directory / "parsed" / "evidence.json",
        evidence,
    )

    collector_status = {
        "collector": "TOP01EvidenceCollector",
        "status": "COLLECTION_COMPLETED",
        "probe_count": len(raw_results),
        "output_directory": str(output_directory),
    }

    write_json(
        output_directory / "collector_status.json",
        collector_status,
    )

    return evidence


def load_observation_profile(
    scenario_path: Path,
) -> ObservationProfile:
    document = yaml.safe_load(
        scenario_path.read_text(encoding="utf-8")
    )

    if not isinstance(document, dict):
        raise ValueError(
            "Scenario document must be a YAML object."
        )

    scenario = document.get("scenario")

    if not isinstance(scenario, dict):
        raise ValueError(
            "Scenario document does not contain 'scenario'."
        )

    return validate_observation_profile(scenario)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect diagnostic evidence from TOP-01."
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory where evidence will be stored.",
    )

    parser.add_argument(
        "--scenario",
        type=Path,
        required=True,
        help=(
            "Scenario YAML that supplies Observation Profile v1."
        ),
    )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    profile = load_observation_profile(
        arguments.scenario
    )
    evidence = collect_evidence(
        arguments.output,
        profile,
    )

    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
