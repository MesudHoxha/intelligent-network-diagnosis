from __future__ import annotations

import copy
import json
from pathlib import Path

from src.collection.modular_registry import build_x1_registry
from src.contracts.evidence_v3 import EVIDENCE_V3_FEATURE_NAMES
from src.contracts.expansion import (
    validate_evidence_v4,
    validate_feature_catalog_v1,
    validate_feature_vector_v2,
)
from src.expansion.evidence_v3_adapter import (
    adapt_evidence_v3_to_v4,
    project_feature_vector_v2,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "plans/expansion/X1_FEATURE_CATALOG_V1.json"
SHA256 = "d" * 64


def _catalog() -> dict[str, object]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _evidence_v3() -> dict[str, object]:
    return {
        "schema_version": 3,
        "topology_id": "TOP_01",
        "collected_at_utc": "2026-08-14T08:00:00+00:00",
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
        "features": {
            name: (False if name == "flow_blocked_by_policy" else True)
            for name in EVIDENCE_V3_FEATURE_NAMES
        },
        "availability": {name: "observed" for name in EVIDENCE_V3_FEATURE_NAMES},
        "probes": {
            name: {
                "producer": "accepted_v3_probe",
                "status": "completed",
                "raw_artifact": f"raw/{name}.json",
                "raw_artifact_sha256": SHA256,
            }
            for name in EVIDENCE_V3_FEATURE_NAMES
        },
    }


def test_v3_adapter_to_v4_to_vector_is_read_only_and_contract_valid() -> None:
    catalog = _catalog()
    source = _evidence_v3()
    before = copy.deepcopy(source)
    evidence = adapt_evidence_v3_to_v4(
        source,
        evidence_id="integration-adapted-evidence",
        topology_context_id="top01_baseline",
        source_artifact_sha256=SHA256,
        feature_catalog=catalog,
        repository_root=ROOT,
    )
    vector = project_feature_vector_v2(
        evidence,
        vector_id="integration-vector",
        evidence_sha256="e" * 64,
        feature_catalog_sha256="f" * 64,
        feature_catalog=catalog,
        repository_root=ROOT,
    )
    assert source == before
    validate_evidence_v4(evidence, catalog, repository_root=ROOT)
    validate_feature_vector_v2(vector, catalog, repository_root=ROOT)
    assert tuple(vector["values"]) == EVIDENCE_V3_FEATURE_NAMES


def test_registry_composes_addressing_vlan_and_service_plans_without_executor() -> None:
    catalog = _catalog()
    index = validate_feature_catalog_v1(catalog, repository_root=ROOT)
    registry = build_x1_registry(index)
    plan = registry.plan(
        [
            "source_address_matches_expected",
            "access_vlan_matches_expected",
            "dns_query_succeeds",
        ],
        ["ipv4_addressing", "l2_vlan", "service_observation"],
    )
    assert plan.collector_keys == (
        "addressing_state_collector:v1",
        "l2_vlan_state_collector:v1",
        "service_state_collector:v1",
    )
    assert plan.capability_gaps == {}
    assert plan.runtime_authorized is False


def test_existing_real_infrastructure_smoke_remains_the_x1_e2e_gate() -> None:
    source = (
        ROOT / "tests/e2e/test_phase6_containerlab_smoke.py"
    ).read_text(encoding="utf-8")
    assert "IND_RUN_INFRA_E2E" in source
    assert "baseline_valid_after" in source
    assert "restoration_confirmed" in source
    assert "containerlab" in source
