from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.contracts.evidence import validate_evidence_v2


REQUIRED_SEMANTIC_EVIDENCE = [
    "destination_prefix",
    "source_gateway_reachable",
    "destination_reachable",
    "route_to_destination_exists_on_observer",
    "expected_next_hop_reachable_from_observer",
    "destination_reachable_from_transit",
]

NEXT_HOP_SEMANTIC_EVIDENCE = [
    "route_next_hop_on_observer",
    "route_next_hop_reachable_from_observer",
]

LEGACY_EVIDENCE_KEYS = {
    "destination_prefix": "destination_prefix",
    "source_gateway_reachable": "source_gateway_reachable",
    "destination_reachable": "destination_reachable",
    "route_to_destination_exists_on_observer": (
        "route_to_destination_exists_on_r1"
    ),
    "route_next_hop_on_observer": "route_next_hop_on_r1",
    "route_next_hop_reachable_from_observer": (
        "route_next_hop_reachable_from_r1"
    ),
    "expected_next_hop_reachable_from_observer": (
        "transit_next_hop_reachable"
    ),
    "destination_reachable_from_transit": (
        "destination_reachable_from_r2"
    ),
}

ROLE_NEUTRAL_EVIDENCE_KEYS = {
    name: name
    for name in (
        *REQUIRED_SEMANTIC_EVIDENCE,
        *NEXT_HOP_SEMANTIC_EVIDENCE,
    )
}

ROLE_CONTEXT_FIELDS = (
    "topology_id",
    "direction",
    "route_observer_node",
    "transit_node",
)


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


def adapt_evidence(
    evidence: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, str],
    list[str],
]:
    schema_version = evidence.get("schema_version", 1)

    if (
        isinstance(schema_version, bool)
        or schema_version not in {1, 2}
    ):
        raise ValueError(
            "Unsupported evidence schema_version."
        )

    if schema_version == 1:
        field_names = LEGACY_EVIDENCE_KEYS
        context_missing: list[str] = []
        route_observer_node = evidence.get(
            "route_observer_node",
            "r1",
        )
        transit_node = evidence.get(
            "transit_node",
            "r2",
        )
    else:
        field_names = ROLE_NEUTRAL_EVIDENCE_KEYS
        context_missing = [
            field
            for field in ROLE_CONTEXT_FIELDS
            if not isinstance(evidence.get(field), str)
            or not str(evidence[field]).strip()
        ]
        route_observer_node = evidence.get(
            "route_observer_node"
        )
        transit_node = evidence.get("transit_node")

    adapted = {
        semantic_name: evidence.get(source_name)
        for semantic_name, source_name
        in field_names.items()
    }
    adapted.update(
        {
            "schema_version": schema_version,
            "topology_id": evidence.get("topology_id"),
            "direction": evidence.get("direction"),
            "route_observer_node": route_observer_node,
            "transit_node": transit_node,
        }
    )

    return adapted, field_names, context_missing


def diagnose(evidence: dict[str, Any]) -> dict[str, Any]:
    (
        semantic_evidence,
        field_names,
        context_missing,
    ) = adapt_evidence(evidence)

    missing_evidence = [
        field_names[key]
        for key in REQUIRED_SEMANTIC_EVIDENCE
        if semantic_evidence[key] is None
    ]
    missing_evidence = (
        context_missing + missing_evidence
    )

    base_result: dict[str, Any] = {
        "schema_version": 1,
        "method": "rule_based",
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "topology_id": semantic_evidence.get(
            "topology_id"
        ),
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

    destination_prefix = str(
        semantic_evidence["destination_prefix"]
    )
    route_observer_node = str(
        semantic_evidence["route_observer_node"]
    )
    transit_node = str(
        semantic_evidence["transit_node"]
    )

    normal_operation = (
        semantic_evidence["source_gateway_reachable"] is True
        and semantic_evidence["destination_reachable"] is True
        and semantic_evidence[
            "route_to_destination_exists_on_observer"
        ]
        is True
        and semantic_evidence[
            "expected_next_hop_reachable_from_observer"
        ]
        is True
        and semantic_evidence[
            "destination_reachable_from_transit"
        ]
        is True
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
                "The source reaches its local gateway.",
                "The source reaches the destination end-to-end.",
                (
                    f"The route observer {route_observer_node} "
                    "contains a route toward the destination."
                ),
                (
                    f"The route observer {route_observer_node} "
                    "reaches the expected transit next-hop."
                ),
                (
                    f"The transit node {transit_node} reaches "
                    "the destination."
                ),
            ],
            "contradicting_evidence": [],
            "recommendation": (
                "No routing fault was detected by the current "
                "rule set."
            ),
        }

    missing_route_on_observer = (
        semantic_evidence["source_gateway_reachable"] is True
        and semantic_evidence["destination_reachable"] is False
        and semantic_evidence[
            "route_to_destination_exists_on_observer"
        ]
        is False
        and semantic_evidence[
            "expected_next_hop_reachable_from_observer"
        ]
        is True
        and semantic_evidence[
            "destination_reachable_from_transit"
        ]
        is True
    )

    if missing_route_on_observer:
        return {
            **base_result,
            "status": "DIAGNOSIS_PRODUCED",
            "diagnosis": {
                "category": "routing",
                "fault_type": "missing_static_route",
                "location": route_observer_node,
                "affected_prefix": destination_prefix,
            },
            "matched_rules": ["R_ROUTING_001"],
            "rule_support_score": 1.0,
            "score_interpretation": (
                "Deterministic rule support, not a calibrated "
                "probability."
            ),
            "supporting_evidence": [
                "The source reaches its local gateway.",
                "The source does not reach the destination.",
                (
                    f"The route observer {route_observer_node} "
                    "does not contain a route toward "
                    f"{destination_prefix}."
                ),
                (
                    f"The route observer {route_observer_node} "
                    "still reaches the expected transit "
                    "next-hop."
                ),
                (
                    f"The transit node {transit_node} still "
                    "reaches the destination."
                ),
            ],
            "contradicting_evidence": [],
            "recommendation": (
                "Inspect the routing table on "
                f"{route_observer_node} and configure a "
                "valid route toward "
                f"{destination_prefix} through the "
                "appropriate next-hop."
            ),
        }

    wrong_next_hop_candidate = (
        semantic_evidence["source_gateway_reachable"] is True
        and semantic_evidence["destination_reachable"] is False
        and semantic_evidence[
            "route_to_destination_exists_on_observer"
        ] is True
        and semantic_evidence[
            "expected_next_hop_reachable_from_observer"
        ]
        is True
        and semantic_evidence[
            "destination_reachable_from_transit"
        ] is True
    )

    if wrong_next_hop_candidate:
        missing_next_hop_evidence = [
            field_names[key]
            for key in NEXT_HOP_SEMANTIC_EVIDENCE
            if semantic_evidence[key] is None
        ]

        if missing_next_hop_evidence:
            return {
                **base_result,
                "status": "INSUFFICIENT_EVIDENCE",
                "diagnosis": None,
                "matched_rules": [],
                "missing_evidence": (
                    missing_next_hop_evidence
                ),
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "recommendation": (
                    "Collect the configured route next-hop and "
                    "test its reachability before classifying "
                    "the routing fault."
                ),
            }

        if (
            semantic_evidence[
                "route_next_hop_reachable_from_observer"
            ]
            is False
        ):
            observed_next_hop = str(
                semantic_evidence[
                    "route_next_hop_on_observer"
                ]
            )

            return {
                **base_result,
                "status": "DIAGNOSIS_PRODUCED",
                "diagnosis": {
                    "category": "routing",
                    "fault_type": "wrong_next_hop",
                    "location": route_observer_node,
                    "affected_prefix": destination_prefix,
                    "observed_next_hop": (
                        observed_next_hop
                    ),
                },
                "matched_rules": ["R_ROUTING_002"],
                "rule_support_score": 1.0,
                "score_interpretation": (
                    "Deterministic rule support, not a "
                    "calibrated probability."
                ),
                "supporting_evidence": [
                    "The source reaches its local gateway.",
                    "The source does not reach the destination.",
                    (
                        f"The route observer "
                        f"{route_observer_node} contains a "
                        "route toward "
                        f"{destination_prefix}."
                    ),
                    (
                        "The route-configured next-hop "
                        f"{observed_next_hop} is unreachable "
                        f"from {route_observer_node}."
                    ),
                    (
                        f"The route observer "
                        f"{route_observer_node} still reaches "
                        "the expected transit next-hop."
                    ),
                    (
                        f"The transit node {transit_node} still "
                        "reaches the destination."
                    ),
                ],
                "contradicting_evidence": [],
                "recommendation": (
                    "Inspect the static route on "
                    f"{route_observer_node} and replace "
                    f"the unreachable next-hop "
                    f"{observed_next_hop} with the verified "
                    "transit next-hop."
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

    if evidence.get("schema_version") == 2:
        validate_evidence_v2(evidence)

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
