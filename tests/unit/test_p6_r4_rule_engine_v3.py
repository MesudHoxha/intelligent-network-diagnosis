import inspect
import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.contracts.evidence_v3 import EVIDENCE_V3_FEATURE_NAMES
from src.rules.rule_engine_v3 import (
    RULE_IDS,
    SIGNATURES,
    diagnose_evidence_v3,
)


RAW_SHA = "a" * 64


def valid_evidence() -> dict[str, object]:
    features = deepcopy(SIGNATURES["no_fault"])
    return {
        "schema_version": 3,
        "topology_id": "TOP_01",
        "collected_at_utc": "2026-08-10T08:00:00+00:00",
        "direction": "hosta_to_hostb",
        "source_node": "hosta",
        "route_observer_node": "r1",
        "transit_node": "r2",
        "source_address": "10.10.1.10",
        "source_prefix": "10.10.1.0/24",
        "destination_address": "10.10.2.10",
        "destination_prefix": "10.10.2.0/24",
        "source_expected_gateway_address": "10.10.1.1",
        "source_default_gateway_on_source": "10.10.1.1",
        "expected_next_hop": "10.10.12.2",
        "route_next_hop_on_observer": "10.10.12.2",
        "observer_egress_interface": "eth2",
        "observer_egress_oper_state": "up",
        "flow_protocol": "icmp",
        "flow_source_port": None,
        "flow_destination_port": None,
        "policy_backend": "iptables",
        "policy_table": "filter",
        "policy_chain": "FORWARD",
        "matching_block_rule_id": None,
        "features": features,
        "availability": {
            name: "observed" for name in EVIDENCE_V3_FEATURE_NAMES
        },
        "probes": {
            name: {
                "producer": f"{name}_probe",
                "status": "completed",
                "raw_artifact": f"raw/v3/{name}.json",
                "raw_artifact_sha256": RAW_SHA,
            }
            for name in EVIDENCE_V3_FEATURE_NAMES
        },
    }


def evidence_for(fault_type: str) -> dict[str, object]:
    evidence = valid_evidence()
    evidence["features"] = deepcopy(SIGNATURES[fault_type])
    if fault_type == "wrong_default_gateway":
        evidence["source_default_gateway_on_source"] = "10.10.1.254"
    elif fault_type == "interface_down":
        evidence["observer_egress_oper_state"] = "down"
        evidence["route_next_hop_on_observer"] = None
        availability = evidence["availability"]
        probes = evidence["probes"]
        assert isinstance(availability, dict)
        assert isinstance(probes, dict)
        for name in (
            "route_next_hop_matches_expected",
            "route_next_hop_reachable_from_observer",
        ):
            availability[name] = "structurally_unavailable"
            probes[name] = {
                "producer": f"{name}_probe",
                "status": "not_applicable",
                "raw_artifact": None,
                "raw_artifact_sha256": None,
            }
    elif fault_type == "acl_block":
        evidence["matching_block_rule_id"] = "IND-P6-R4-ACL-TOP01"
    elif fault_type == "missing_static_route":
        evidence["route_next_hop_on_observer"] = None
        availability = evidence["availability"]
        probes = evidence["probes"]
        assert isinstance(availability, dict)
        assert isinstance(probes, dict)
        for name in (
            "route_next_hop_matches_expected",
            "route_next_hop_reachable_from_observer",
        ):
            availability[name] = "structurally_unavailable"
            probes[name] = {
                "producer": f"{name}_probe",
                "status": "not_applicable",
                "raw_artifact": None,
                "raw_artifact_sha256": None,
            }
    elif fault_type == "wrong_next_hop":
        evidence["route_next_hop_on_observer"] = "10.10.12.254"
    return evidence


@pytest.mark.parametrize(
    ("fault_type", "location"),
    [
        ("wrong_default_gateway", "hosta"),
        ("interface_down", "r1"),
        ("acl_block", "r1"),
    ],
)
def test_new_fault_signatures_use_only_evidence(
    fault_type: str,
    location: str,
) -> None:
    diagnosis = diagnose_evidence_v3(evidence_for(fault_type))

    assert diagnosis["status"] == "DIAGNOSIS_PRODUCED"
    assert diagnosis["diagnosis"]["fault_type"] == fault_type
    assert diagnosis["diagnosis"]["location"] == location
    assert diagnosis["matched_rules"] == [RULE_IDS[fault_type]]


def test_sorted_json_round_trip_uses_frozen_feature_order() -> None:
    evidence = json.loads(
        json.dumps(evidence_for("wrong_default_gateway"), sort_keys=True)
    )

    diagnosis = diagnose_evidence_v3(evidence)

    assert diagnosis["status"] == "DIAGNOSIS_PRODUCED"
    assert diagnosis["diagnosis"]["fault_type"] == (
        "wrong_default_gateway"
    )
    assert tuple(
        item.split("=", 1)[0]
        for item in diagnosis["supporting_evidence"]
    ) == EVIDENCE_V3_FEATURE_NAMES


@pytest.mark.parametrize(
    "fault_type",
    ["no_fault", "missing_static_route", "wrong_next_hop"],
)
def test_complete_six_class_signatures_remain_unique(
    fault_type: str,
) -> None:
    diagnosis = diagnose_evidence_v3(evidence_for(fault_type))

    if fault_type == "no_fault":
        assert diagnosis["status"] == "NO_FAULT_DETECTED"
    else:
        assert diagnosis["diagnosis"]["fault_type"] == fault_type
    assert diagnosis["matched_rules"] == [RULE_IDS[fault_type]]


def test_absent_route_classes_are_separated_by_link_evidence() -> None:
    missing = diagnose_evidence_v3(
        evidence_for("missing_static_route")
    )
    interface = diagnose_evidence_v3(evidence_for("interface_down"))

    assert missing["diagnosis"]["fault_type"] == "missing_static_route"
    assert interface["diagnosis"]["fault_type"] == "interface_down"
    assert SIGNATURES["missing_static_route"][
        "observer_egress_interface_oper_up"
    ] is True
    assert SIGNATURES["interface_down"][
        "observer_egress_interface_oper_up"
    ] is False


def test_rule_signatures_match_frozen_taxonomy_plan() -> None:
    plan = json.loads(
        Path(
            "plans/taxonomies/P6_EXTENDED_FAULT_TAXONOMY_V1.json"
        ).read_text(encoding="utf-8")
    )
    planned = {
        item["fault_type"]: {
            name: (
                True
                if value == "true"
                else False
                if value == "false"
                else None
            )
            for name, value in item["expected_signature"].items()
        }
        for item in plan["taxonomy"]["classes"]
    }

    assert SIGNATURES == planned
    assert len({tuple(signature.values()) for signature in SIGNATURES.values()}) == 6


def test_collection_unavailable_returns_insufficient_evidence() -> None:
    evidence = valid_evidence()
    evidence["features"]["flow_blocked_by_policy"] = None
    evidence["availability"]["flow_blocked_by_policy"] = (
        "collection_unavailable"
    )
    evidence["probes"]["flow_blocked_by_policy"]["status"] = "failed"

    diagnosis = diagnose_evidence_v3(evidence)

    assert diagnosis["status"] == "INSUFFICIENT_EVIDENCE"
    assert diagnosis["diagnosis"] is None
    assert diagnosis["missing_evidence"] == ["flow_blocked_by_policy"]


def test_unexpected_complete_vector_does_not_guess() -> None:
    evidence = valid_evidence()
    evidence["features"]["source_expected_gateway_reachable"] = False

    diagnosis = diagnose_evidence_v3(evidence)

    assert diagnosis["status"] == "NO_RULE_MATCH"
    assert diagnosis["diagnosis"] is None


def test_rule_entry_point_has_no_label_or_ground_truth_input() -> None:
    parameters = inspect.signature(diagnose_evidence_v3).parameters

    assert tuple(parameters) == ("evidence",)
    source = Path("src/rules/rule_engine_v3.py").read_text(
        encoding="utf-8"
    )
    assert "ground_truth" not in source
    assert "expected_signature" not in source
