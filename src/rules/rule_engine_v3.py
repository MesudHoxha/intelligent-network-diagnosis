from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.contracts.evidence import EvidenceContractError
from src.contracts.evidence_v3 import (
    EVIDENCE_V3_FEATURE_NAMES,
    validate_evidence_v3,
)


class RuleEngineV3Error(RuntimeError):
    """Raised when Evidence v3 cannot be diagnosed safely."""


SIGNATURES: dict[str, dict[str, bool | None]] = {
    "no_fault": {
        "source_expected_gateway_reachable": True,
        "source_default_gateway_matches_expected": True,
        "destination_reachable": True,
        "route_to_destination_exists_on_observer": True,
        "route_next_hop_matches_expected": True,
        "route_next_hop_reachable_from_observer": True,
        "expected_next_hop_reachable_from_observer": True,
        "observer_egress_interface_oper_up": True,
        "destination_reachable_from_transit": True,
        "flow_blocked_by_policy": False,
    },
    "missing_static_route": {
        "source_expected_gateway_reachable": True,
        "source_default_gateway_matches_expected": True,
        "destination_reachable": False,
        "route_to_destination_exists_on_observer": False,
        "route_next_hop_matches_expected": None,
        "route_next_hop_reachable_from_observer": None,
        "expected_next_hop_reachable_from_observer": True,
        "observer_egress_interface_oper_up": True,
        "destination_reachable_from_transit": True,
        "flow_blocked_by_policy": False,
    },
    "wrong_next_hop": {
        "source_expected_gateway_reachable": True,
        "source_default_gateway_matches_expected": True,
        "destination_reachable": False,
        "route_to_destination_exists_on_observer": True,
        "route_next_hop_matches_expected": False,
        "route_next_hop_reachable_from_observer": False,
        "expected_next_hop_reachable_from_observer": True,
        "observer_egress_interface_oper_up": True,
        "destination_reachable_from_transit": True,
        "flow_blocked_by_policy": False,
    },
    "wrong_default_gateway": {
        "source_expected_gateway_reachable": True,
        "source_default_gateway_matches_expected": False,
        "destination_reachable": False,
        "route_to_destination_exists_on_observer": True,
        "route_next_hop_matches_expected": True,
        "route_next_hop_reachable_from_observer": True,
        "expected_next_hop_reachable_from_observer": True,
        "observer_egress_interface_oper_up": True,
        "destination_reachable_from_transit": True,
        "flow_blocked_by_policy": False,
    },
    "interface_down": {
        "source_expected_gateway_reachable": True,
        "source_default_gateway_matches_expected": True,
        "destination_reachable": False,
        "route_to_destination_exists_on_observer": False,
        "route_next_hop_matches_expected": None,
        "route_next_hop_reachable_from_observer": None,
        "expected_next_hop_reachable_from_observer": False,
        "observer_egress_interface_oper_up": False,
        "destination_reachable_from_transit": True,
        "flow_blocked_by_policy": False,
    },
    "acl_block": {
        "source_expected_gateway_reachable": True,
        "source_default_gateway_matches_expected": True,
        "destination_reachable": False,
        "route_to_destination_exists_on_observer": True,
        "route_next_hop_matches_expected": True,
        "route_next_hop_reachable_from_observer": True,
        "expected_next_hop_reachable_from_observer": True,
        "observer_egress_interface_oper_up": True,
        "destination_reachable_from_transit": True,
        "flow_blocked_by_policy": True,
    },
}

RULE_IDS = {
    "no_fault": "R_P6_BASELINE_001",
    "missing_static_route": "R_P6_ROUTING_001",
    "wrong_next_hop": "R_P6_ROUTING_002",
    "wrong_default_gateway": "R_P6_ROUTING_003",
    "interface_down": "R_P6_LINK_001",
    "acl_block": "R_P6_POLICY_001",
}

CATEGORIES = {
    "missing_static_route": "routing",
    "wrong_next_hop": "routing",
    "wrong_default_gateway": "routing",
    "interface_down": "link",
    "acl_block": "access_control",
}


def _base(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "method": "rule_based_v3",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "topology_id": evidence["topology_id"],
        "direction": evidence["direction"],
    }


def _location(evidence: dict[str, Any], fault_type: str) -> str:
    if fault_type == "wrong_default_gateway":
        return str(evidence["source_node"])
    return str(evidence["route_observer_node"])


def diagnose_evidence_v3(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    try:
        validate_evidence_v3(evidence)
    except EvidenceContractError as error:
        raise RuleEngineV3Error(
            f"Invalid Evidence v3: {error}"
        ) from error
    features = {
        name: evidence["features"][name]
        for name in EVIDENCE_V3_FEATURE_NAMES
    }
    availability = evidence["availability"]

    unavailable = [
        name
        for name in EVIDENCE_V3_FEATURE_NAMES
        if availability[name] != "observed"
        and not (
            features[name] is None
            and availability[name] == "structurally_unavailable"
        )
    ]
    if unavailable:
        return {
            **_base(evidence),
            "status": "INSUFFICIENT_EVIDENCE",
            "diagnosis": None,
            "matched_rules": [],
            "missing_evidence": unavailable,
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "recommendation": (
                "Collect the unavailable Evidence v3 features before "
                "producing a definitive diagnosis."
            ),
        }

    matches = [
        fault_type
        for fault_type, signature in SIGNATURES.items()
        if features == signature
    ]
    if len(matches) != 1:
        return {
            **_base(evidence),
            "status": "NO_RULE_MATCH",
            "diagnosis": None,
            "matched_rules": [],
            "missing_evidence": [],
            "supporting_evidence": [],
            "contradicting_evidence": [
                "The observed ten-feature vector does not match one "
                "unique frozen Phase 6 rule signature."
            ],
            "recommendation": (
                "Review the raw probe artifacts; do not infer a class "
                "from an incomplete or unexpected signature."
            ),
        }

    fault_type = matches[0]
    if fault_type == "no_fault":
        return {
            **_base(evidence),
            "status": "NO_FAULT_DETECTED",
            "diagnosis": None,
            "matched_rules": [RULE_IDS[fault_type]],
            "rule_support_score": 1.0,
            "score_interpretation": (
                "Exact deterministic signature support, not a "
                "calibrated probability."
            ),
            "supporting_evidence": [
                "The complete Evidence v3 vector matches the frozen "
                "healthy signature."
            ],
            "contradicting_evidence": [],
            "recommendation": (
                "No controlled Phase 6 fault was detected by the "
                "current rule set."
            ),
        }

    return {
        **_base(evidence),
        "status": "DIAGNOSIS_PRODUCED",
        "diagnosis": {
            "category": CATEGORIES[fault_type],
            "fault_type": fault_type,
            "location": _location(evidence, fault_type),
            "affected_prefix": evidence["destination_prefix"],
        },
        "matched_rules": [RULE_IDS[fault_type]],
        "rule_support_score": 1.0,
        "score_interpretation": (
            "Exact deterministic signature support, not a calibrated "
            "probability."
        ),
        "supporting_evidence": [
            f"{name}={str(value).lower() if value is not None else 'unavailable'}"
            for name, value in features.items()
        ],
        "contradicting_evidence": [],
        "recommendation": (
            "Inspect and restore the configuration on the diagnosed "
            "role, then revalidate the complete healthy baseline."
        ),
    }


def read_evidence(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuleEngineV3Error(
            f"Cannot read Evidence v3: {path}"
        ) from error
    if not isinstance(value, dict):
        raise RuleEngineV3Error("Evidence v3 must be a JSON object.")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose one Evidence v3 artifact with frozen rules."
    )
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        result = diagnose_evidence_v3(
            read_evidence(arguments.evidence)
        )
    except (RuleEngineV3Error, OSError, ValueError) as error:
        print(f"[ERROR] {error}")
        return 1
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
