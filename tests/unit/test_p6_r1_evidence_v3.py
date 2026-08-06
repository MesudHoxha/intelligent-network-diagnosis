import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.contracts.evidence import EvidenceContractError
from src.contracts.evidence_v3 import (
    EVIDENCE_V3_FEATURE_NAMES,
    validate_evidence_v3,
    validate_evidence_versioned,
)
from src.planning.fault_taxonomy import FEATURE_ORDER


RAW_SHA = "a" * 64


def valid_evidence_v3() -> dict[str, object]:
    features = {
        name: (False if name == "flow_blocked_by_policy" else True)
        for name in EVIDENCE_V3_FEATURE_NAMES
    }
    availability = {
        name: "observed" for name in EVIDENCE_V3_FEATURE_NAMES
    }
    probes = {
        name: {
            "producer": "synthetic_probe",
            "status": "completed",
            "raw_artifact": f"raw/{name}.json",
            "raw_artifact_sha256": RAW_SHA,
        }
        for name in EVIDENCE_V3_FEATURE_NAMES
    }
    return {
        "schema_version": 3,
        "topology_id": "TOP_01",
        "collected_at_utc": "2026-08-06T08:00:00+00:00",
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
        "availability": availability,
        "probes": probes,
    }


def nested(
    evidence: dict[str, object],
    field_name: str,
) -> dict[str, object]:
    value = evidence[field_name]
    assert isinstance(value, dict)
    return value


def test_feature_order_matches_frozen_p6_plan() -> None:
    assert EVIDENCE_V3_FEATURE_NAMES == FEATURE_ORDER


def test_accepts_complete_evidence_v3() -> None:
    validate_evidence_v3(valid_evidence_v3())


def test_json_schema_accepts_complete_evidence_v3() -> None:
    schema = json.loads(
        Path("schemas/evidence_v3.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(valid_evidence_v3())


def test_versioned_dispatch_accepts_evidence_v3() -> None:
    validate_evidence_versioned(valid_evidence_v3())


def test_versioned_dispatch_preserves_evidence_v2() -> None:
    evidence_v2 = {
        "schema_version": 2,
        "topology_id": "TOP_01",
        "collected_at_utc": "2026-08-06T08:00:00+00:00",
        "direction": "hosta_to_hostb",
        "route_observer_node": "r1",
        "transit_node": "r2",
        "destination_address": "10.10.2.10",
        "destination_prefix": "10.10.2.0/24",
        "source_gateway_reachable": True,
        "destination_reachable": True,
        "route_to_destination_exists_on_observer": True,
        "route_next_hop_on_observer": "10.10.12.2",
        "route_next_hop_reachable_from_observer": True,
        "expected_next_hop_reachable_from_observer": True,
        "destination_reachable_from_transit": True,
    }

    validate_evidence_versioned(evidence_v2)


def test_accepts_structurally_unavailable_route_family() -> None:
    evidence = valid_evidence_v3()
    nested(evidence, "features")[
        "route_to_destination_exists_on_observer"
    ] = False
    evidence["route_next_hop_on_observer"] = None
    for name in (
        "route_next_hop_matches_expected",
        "route_next_hop_reachable_from_observer",
    ):
        nested(evidence, "features")[name] = None
        nested(evidence, "availability")[name] = (
            "structurally_unavailable"
        )
        nested(evidence, "probes")[name] = {
            "producer": "synthetic_probe",
            "status": "not_applicable",
            "raw_artifact": None,
            "raw_artifact_sha256": None,
        }

    validate_evidence_v3(evidence)


def test_accepts_collection_unavailable_with_failure_artifact() -> None:
    evidence = valid_evidence_v3()
    feature_name = "flow_blocked_by_policy"
    nested(evidence, "features")[feature_name] = None
    nested(evidence, "availability")[feature_name] = (
        "collection_unavailable"
    )
    nested(evidence, "probes")[feature_name]["status"] = "failed"

    validate_evidence_v3(evidence)


def test_rejects_structural_reason_outside_route_dependency() -> None:
    evidence = valid_evidence_v3()
    feature_name = "destination_reachable"
    nested(evidence, "features")[feature_name] = None
    nested(evidence, "availability")[feature_name] = (
        "structurally_unavailable"
    )
    nested(evidence, "probes")[feature_name] = {
        "producer": "synthetic_probe",
        "status": "not_applicable",
        "raw_artifact": None,
        "raw_artifact_sha256": None,
    }

    with pytest.raises(
        EvidenceContractError,
        match="cannot be structurally unavailable",
    ):
        validate_evidence_v3(evidence)


def test_rejects_installed_gateway_outside_source_prefix() -> None:
    evidence = valid_evidence_v3()
    evidence["source_default_gateway_on_source"] = "10.20.1.1"

    with pytest.raises(
        EvidenceContractError,
        match="must belong to source_prefix",
    ):
        validate_evidence_v3(evidence)


def test_rejects_null_feature_marked_observed() -> None:
    evidence = valid_evidence_v3()
    nested(evidence, "features")["destination_reachable"] = None

    with pytest.raises(
        EvidenceContractError,
        match="must be boolean when availability is observed",
    ):
        validate_evidence_v3(evidence)


def test_rejects_structural_unavailability_with_raw_artifact() -> None:
    evidence = valid_evidence_v3()
    feature_name = "route_next_hop_matches_expected"
    nested(evidence, "features")[feature_name] = None
    nested(evidence, "availability")[feature_name] = (
        "structurally_unavailable"
    )
    nested(evidence, "probes")[feature_name]["status"] = (
        "not_applicable"
    )

    with pytest.raises(
        EvidenceContractError,
        match="cannot claim a raw artifact",
    ):
        validate_evidence_v3(evidence)


@pytest.mark.parametrize(
    ("field_name", "new_value", "message"),
    [
        (
            "source_default_gateway_on_source",
            "10.10.1.254",
            "source_default_gateway_matches_expected",
        ),
        (
            "route_next_hop_on_observer",
            "10.10.12.254",
            "route_next_hop_matches_expected",
        ),
        (
            "observer_egress_oper_state",
            "down",
            "observer_egress_interface_oper_up",
        ),
        (
            "matching_block_rule_id",
            "IND-P6-ACL-001",
            "flow_blocked_by_policy",
        ),
    ],
)
def test_rejects_derived_feature_drift(
    field_name: str,
    new_value: object,
    message: str,
) -> None:
    evidence = valid_evidence_v3()
    evidence[field_name] = new_value

    with pytest.raises(EvidenceContractError, match=message):
        validate_evidence_v3(evidence)


def test_rejects_missing_route_without_structural_semantics() -> None:
    evidence = valid_evidence_v3()
    nested(evidence, "features")[
        "route_to_destination_exists_on_observer"
    ] = False
    evidence["route_next_hop_on_observer"] = None
    nested(evidence, "features")[
        "route_next_hop_matches_expected"
    ] = False

    with pytest.raises(
        EvidenceContractError,
        match="structural unavailability",
    ):
        validate_evidence_v3(evidence)


def test_rejects_unexpected_ground_truth_field() -> None:
    evidence = valid_evidence_v3()
    evidence["fault_type"] = "acl_block"

    with pytest.raises(
        EvidenceContractError,
        match="Unexpected Evidence v3 fields",
    ):
        validate_evidence_v3(evidence)


def test_rejects_unexpected_predictor() -> None:
    evidence = valid_evidence_v3()
    nested(evidence, "features")["scenario_id"] = "leakage"

    with pytest.raises(
        EvidenceContractError,
        match="ten-feature whitelist",
    ):
        validate_evidence_v3(evidence)


def test_rejects_unnormalized_raw_artifact_path() -> None:
    evidence = valid_evidence_v3()
    nested(evidence, "probes")["destination_reachable"][
        "raw_artifact"
    ] = "../ground_truth.json"

    with pytest.raises(
        EvidenceContractError,
        match="normalized relative path",
    ):
        validate_evidence_v3(evidence)


def test_dispatch_rejects_unknown_version() -> None:
    evidence = deepcopy(valid_evidence_v3())
    evidence["schema_version"] = 4

    with pytest.raises(
        EvidenceContractError,
        match="Unsupported evidence schema_version",
    ):
        validate_evidence_versioned(evidence)
