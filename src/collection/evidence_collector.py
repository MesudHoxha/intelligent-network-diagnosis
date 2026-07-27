from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


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


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def collect_evidence(output_directory: Path) -> dict[str, object]:
    raw_results = {
        "hosta_ping_gateway": ping_result(
            "clab-top01-hosta",
            "10.10.1.1",
        ),
        "hosta_ping_hostb": ping_result(
            "clab-top01-hosta",
            "10.10.2.10",
        ),
        "r1_route_to_hostb": route_result(
            "clab-top01-r1",
            "10.10.2.0/24",
        ),
        "r1_ping_r2": ping_result(
            "clab-top01-r1",
            "10.10.12.2",
        ),
        "r2_ping_hostb": ping_result(
            "clab-top01-r2",
            "10.10.2.10",
        ),
    }

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

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    evidence = collect_evidence(arguments.output)

    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
