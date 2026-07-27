from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_EVIDENCE = [
    "source_gateway_reachable",
    "destination_reachable",
    "route_to_destination_exists_on_r1",
    "transit_next_hop_reachable",
    "destination_reachable_from_r2",
]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Evidence file does not exist: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Evidence document must be a JSON object.")

    return data


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def diagnose(evidence: dict[str, Any]) -> dict[str, Any]:
    missing_evidence = [
        key
        for key in REQUIRED_EVIDENCE
        if key not in evidence or evidence[key] is None
    ]

    base_result: dict[str, Any] = {
        "schema_version": 1,
        "method": "rule_based",
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "topology_id": evidence.get("topology_id"),
    }

    if missing_evidence:
        return {
            **base_result,
            "status": "INSUFFICIENT_EVIDENCE",
            "diagnosis": None,
            "matched_rules": [],
            "missing_evidence": missing_evidence,
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "recommendation": (
                "Collect the missing diagnostic evidence before "
                "producing a definitive diagnosis."
            ),
        }

    normal_operation = (
        evidence["source_gateway_reachable"] is True
        and evidence["destination_reachable"] is True
        and evidence["route_to_destination_exists_on_r1"] is True
        and evidence["transit_next_hop_reachable"] is True
        and evidence["destination_reachable_from_r2"] is True
    )

    if normal_operation:
        return {
            **base_result,
            "status": "NO_FAULT_DETECTED",
            "diagnosis": None,
            "matched_rules": ["R_BASELINE_001"],
            "rule_support_score": 1.0,
            "score_interpretation": (
                "Deterministic rule support, not a calibrated "
                "probability."
            ),
            "supporting_evidence": [
                "HostA reaches its local gateway.",
                "HostA reaches HostB end-to-end.",
                "R1 contains a route toward the HostB network.",
                "R1 reaches the transit next-hop R2.",
                "R2 reaches HostB.",
            ],
            "contradicting_evidence": [],
            "recommendation": (
                "No routing fault was detected by the current "
                "rule set."
            ),
        }

    missing_route_on_r1 = (
        evidence["source_gateway_reachable"] is True
        and evidence["destination_reachable"] is False
        and evidence["route_to_destination_exists_on_r1"] is False
        and evidence["transit_next_hop_reachable"] is True
        and evidence["destination_reachable_from_r2"] is True
    )

    if missing_route_on_r1:
        return {
            **base_result,
            "status": "DIAGNOSIS_PRODUCED",
            "diagnosis": {
                "category": "routing",
                "fault_type": "missing_static_route",
                "location": "r1",
                "affected_prefix": "10.10.2.0/24",
            },
            "matched_rules": ["R_ROUTING_001"],
            "rule_support_score": 1.0,
            "score_interpretation": (
                "Deterministic rule support, not a calibrated "
                "probability."
            ),
            "supporting_evidence": [
                "HostA reaches its local gateway R1.",
                "HostA does not reach HostB end-to-end.",
                "R1 does not contain a route toward 10.10.2.0/24.",
                "R1 still reaches the transit next-hop R2.",
                "R2 still reaches HostB.",
            ],
            "contradicting_evidence": [],
            "recommendation": (
                "Inspect the routing table on R1 and configure a "
                "valid route toward 10.10.2.0/24 through the "
                "appropriate next-hop."
            ),
        }

    return {
        **base_result,
        "status": "UNDETERMINED",
        "diagnosis": None,
        "matched_rules": [],
        "supporting_evidence": [],
        "contradicting_evidence": [],
        "recommendation": (
            "The current evidence does not match any implemented "
            "diagnostic rule. Additional rules or evidence are "
            "required."
        ),
    }


def run_rule_engine(experiment_directory: Path) -> dict[str, Any]:
    evidence_path = (
        experiment_directory / "parsed" / "evidence.json"
    )
    output_path = (
        experiment_directory
        / "diagnosis"
        / "rule_based.json"
    )

    evidence = read_json(evidence_path)
    result = diagnose(evidence)

    write_json(output_path, result)

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run rule-based diagnosis on collected evidence."
        )
    )

    parser.add_argument(
        "--experiment-dir",
        type=Path,
        required=True,
        help=(
            "Experiment directory containing parsed/evidence.json."
        ),
    )

    return parser


def main() -> int:
    arguments = build_parser().parse_args()

    try:
        result = run_rule_engine(arguments.experiment_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"[ERROR] {error}")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
