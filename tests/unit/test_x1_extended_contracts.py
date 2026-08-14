from __future__ import annotations

import ast
import copy
import json
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.collection.modular_registry import (
    CollectorRegistry,
    CollectorSpec,
    ModularCollectorRegistryError,
    build_x1_registry,
)
from src.contracts.evidence_v3 import EVIDENCE_V3_FEATURE_NAMES
from src.contracts.expansion import (
    ExpansionContractError,
    SCHEMA_PATHS,
    validate_dataset_row_v4,
    validate_diagnosis_result_v2,
    validate_evidence_mask_plan_v2,
    validate_evidence_v4,
    validate_feature_catalog_v1,
    validate_feature_vector_v2,
    validate_topology_context_v1,
)
from src.expansion.evidence_v3_adapter import (
    adapt_evidence_v3_to_v4,
    project_feature_vector_v2,
)
from src.expansion.x1_gate import (
    EXPECTED_CONTRACTS,
    EXPECTED_DOMAIN_COUNTS,
    EXPECTED_RUNTIME_FLAGS,
    X1GateError,
    validate_x1_manifest,
    verify_x1_gate,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    ROOT / "plans/expansion/X1_EXTENDED_CONTRACTS_MODULAR_COLLECTION_V1.json"
)
MANIFEST_SCHEMA_PATH = (
    ROOT / "schemas/x1_extended_contracts_modular_collection_v1.schema.json"
)
CATALOG_PATH = ROOT / "plans/expansion/X1_FEATURE_CATALOG_V1.json"
MASK_PLAN_PATH = ROOT / "plans/expansion/X1_EVIDENCE_MASK_PLAN_V2.json"
SHA256 = "a" * 64


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def valid_evidence_v3() -> dict[str, object]:
    features = {
        name: (False if name == "flow_blocked_by_policy" else True)
        for name in EVIDENCE_V3_FEATURE_NAMES
    }
    availability = {name: "observed" for name in EVIDENCE_V3_FEATURE_NAMES}
    probes = {
        name: {
            "producer": "synthetic_probe",
            "status": "completed",
            "raw_artifact": f"raw/{name}.json",
            "raw_artifact_sha256": SHA256,
        }
        for name in EVIDENCE_V3_FEATURE_NAMES
    }
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
        "features": features,
        "availability": availability,
        "probes": probes,
    }


def valid_topology_context() -> dict[str, object]:
    return {
        "schema_version": 1,
        "context_id": "top01_baseline",
        "topology_id": "TOP_01",
        "variant_id": "baseline",
        "nodes": [
            {
                "node_id": "hosta",
                "role": "host",
                "runtime_target": "hosta",
                "capabilities": ["ipv4_addressing"],
            },
            {
                "node_id": "hostb",
                "role": "host",
                "runtime_target": "hostb",
                "capabilities": ["ipv4_addressing"],
            },
            {
                "node_id": "r1",
                "role": "router",
                "runtime_target": "r1",
                "capabilities": ["ipv4_addressing", "ospf"],
            },
        ],
        "links": [
            {
                "link_id": "hosta_r1",
                "kind": "routed",
                "endpoints": [
                    {"node_id": "hosta", "interface": "eth1"},
                    {"node_id": "r1", "interface": "eth1"},
                ],
                "expected_vlans": [],
                "native_vlan": None,
            }
        ],
        "observation_roles": {
            "source": "hosta",
            "destination": "hostb",
            "observers": ["r1"],
        },
        "capabilities": ["ipv4_addressing", "ospf"],
    }


def adapted_evidence() -> dict[str, object]:
    return adapt_evidence_v3_to_v4(
        valid_evidence_v3(),
        evidence_id="evidence-v3-adapted",
        topology_context_id="top01_baseline",
        source_artifact_sha256=SHA256,
        feature_catalog=_load(CATALOG_PATH),
        repository_root=ROOT,
    )


def projected_vector() -> dict[str, object]:
    return project_feature_vector_v2(
        adapted_evidence(),
        vector_id="vector-v2-adapted",
        evidence_sha256=SHA256,
        feature_catalog_sha256="b" * 64,
        feature_catalog=_load(CATALOG_PATH),
        repository_root=ROOT,
    )


def test_all_x1_json_schemas_are_valid_draft_2020_12() -> None:
    paths = [MANIFEST_SCHEMA_PATH, *(ROOT / path for path in SCHEMA_PATHS.values())]
    for path in paths:
        Draft202012Validator.check_schema(_load(path))


def test_x1_manifest_and_tracked_gate_verify() -> None:
    manifest = _load(MANIFEST_PATH)
    validate_x1_manifest(manifest, _load(MANIFEST_SCHEMA_PATH))
    verified = verify_x1_gate(ROOT)
    assert verified["status"] == "ACCEPTED_CONTRACT_ONLY"
    assert verified["track"]["next_milestone"] == "X2_ADDRESSING_VERTICAL_SLICES"


def test_x1_contract_family_is_exact_and_versioned() -> None:
    contracts = _load(MANIFEST_PATH)["contracts"]
    assert tuple(row["contract_id"] for row in contracts) == EXPECTED_CONTRACTS
    assert not {row["schema_path"] for row in contracts} & {
        "schemas/evidence_v3.schema.json",
        "schemas/dataset_row_v3.schema.json",
    }


def test_feature_catalog_has_exact_baseline_and_planned_counts() -> None:
    catalog = _load(CATALOG_PATH)
    index = validate_feature_catalog_v1(catalog, repository_root=ROOT)
    assert len(index) == 39
    assert Counter(row["lifecycle"] for row in index.values()) == {
        "FROZEN_BASELINE": 10,
        "PLANNED_EXTENSION": 29,
    }
    assert Counter(row["domain"] for row in index.values()) == EXPECTED_DOMAIN_COUNTS


def test_frozen_evidence_v3_feature_ids_are_preserved_exactly() -> None:
    index = validate_feature_catalog_v1(_load(CATALOG_PATH), repository_root=ROOT)
    baseline = tuple(
        feature_id
        for feature_id, row in index.items()
        if row["lifecycle"] == "FROZEN_BASELINE"
    )
    assert baseline == EVIDENCE_V3_FEATURE_NAMES


def test_mask_plan_preserves_p6_masks_and_covers_only_catalog_features() -> None:
    validate_evidence_mask_plan_v2(
        _load(MASK_PLAN_PATH),
        _load(CATALOG_PATH),
        repository_root=ROOT,
    )


def test_registry_is_design_only_and_covers_every_catalog_feature_once() -> None:
    index = validate_feature_catalog_v1(_load(CATALOG_PATH), repository_root=ROOT)
    registry = build_x1_registry(index)
    assert len(registry.specs) == 7
    assert registry.uncovered_features == ()
    assert not any(spec.runtime_authorized for spec in registry.specs)
    assert {spec.implementation_status for spec in registry.specs} == {
        "ADAPTER_ONLY",
        "DESIGN_ONLY",
    }


def test_registry_rejects_duplicate_feature_ownership() -> None:
    registry = CollectorRegistry(["feature_a"])
    registry.register(
        CollectorSpec("collector_a", 1, "addressing", ("feature_a",), (), "DESIGN_ONLY")
    )
    with pytest.raises(ModularCollectorRegistryError, match="multiple"):
        registry.register(
            CollectorSpec(
                "collector_b", 1, "addressing", ("feature_a",), (), "DESIGN_ONLY"
            )
        )


def test_registry_planning_is_deterministic_and_reports_capability_gaps() -> None:
    index = validate_feature_catalog_v1(_load(CATALOG_PATH), repository_root=ROOT)
    registry = build_x1_registry(index)
    plan = registry.plan(
        ["access_vlan_matches_expected", "source_address_matches_expected"],
        ["ipv4_addressing"],
    )
    assert plan.collector_keys == ("addressing_state_collector:v1",)
    assert plan.capability_gaps == {
        "l2_vlan_state_collector:v1": ("l2_vlan",)
    }
    assert plan.runtime_authorized is False


def test_topology_context_validates_cross_references() -> None:
    validate_topology_context_v1(valid_topology_context(), repository_root=ROOT)


def test_topology_context_rejects_unknown_role_node() -> None:
    context = valid_topology_context()
    context["observation_roles"]["destination"] = "missing"
    with pytest.raises(ExpansionContractError, match="roles"):
        validate_topology_context_v1(context, repository_root=ROOT)


def test_read_only_v3_adapter_preserves_source_and_all_ten_features() -> None:
    source = valid_evidence_v3()
    before = copy.deepcopy(source)
    result = adapt_evidence_v3_to_v4(
        source,
        evidence_id="evidence-v3-adapted",
        topology_context_id="top01_baseline",
        source_artifact_sha256=SHA256,
        feature_catalog=_load(CATALOG_PATH),
        repository_root=ROOT,
    )
    assert source == before
    assert tuple(result["observations"]) == EVIDENCE_V3_FEATURE_NAMES
    assert result["compatibility"] == {
        "origin": "read_only_v3_adapter",
        "source_schema_version": 3,
        "source_artifact_sha256": SHA256,
    }


def test_v3_adapter_requires_source_artifact_hash() -> None:
    with pytest.raises(ExpansionContractError, match="SHA-256"):
        adapt_evidence_v3_to_v4(
            valid_evidence_v3(),
            evidence_id="evidence-v3-adapted",
            topology_context_id="top01_baseline",
            source_artifact_sha256="not-a-hash",
            feature_catalog=_load(CATALOG_PATH),
            repository_root=ROOT,
        )


def test_evidence_v4_rejects_unknown_feature() -> None:
    evidence = adapted_evidence()
    evidence["observations"]["unknown_feature"] = copy.deepcopy(
        next(iter(evidence["observations"].values()))
    )
    with pytest.raises(ExpansionContractError):
        validate_evidence_v4(
            evidence,
            _load(CATALOG_PATH),
            repository_root=ROOT,
        )


def test_feature_vector_projection_is_unmasked_and_hash_bound() -> None:
    vector = projected_vector()
    validate_feature_vector_v2(vector, _load(CATALOG_PATH), repository_root=ROOT)
    assert vector["mask_id"] is None
    assert tuple(vector["values"]) == EVIDENCE_V3_FEATURE_NAMES
    assert vector["provenance"]["evidence_sha256"] == SHA256


def test_feature_vector_rejects_value_type_drift() -> None:
    vector = projected_vector()
    vector["values"]["destination_reachable"]["value"] = "yes"
    with pytest.raises(ExpansionContractError, match="type"):
        validate_feature_vector_v2(vector, _load(CATALOG_PATH), repository_root=ROOT)


def test_dataset_row_v4_is_single_fault_and_quality_bound() -> None:
    vector = projected_vector()
    row = {
        "schema_version": 4,
        "sample_id": "experiment-x1",
        "metadata": {
            "experiment_id": "experiment-x1",
            "scenario_id": "healthy-adapted",
            "variant_id": "baseline",
            "split_group_id": "group-x1",
            "topology_context_id": "top01_baseline",
            "collected_at_utc": "2026-08-14T08:00:00+00:00",
        },
        "feature_vector": vector,
        "labels": {
            "truth_model": "single_fault",
            "fault_type": "no_fault",
            "fault_category": None,
            "fault_location": None,
            "affected_resource": None,
        },
        "quality": {
            "experiment_completed": True,
            "collector_completed": True,
            "baseline_before_valid": True,
            "baseline_after_valid": True,
            "observed_feature_count": 10,
            "unavailable_feature_count": 0,
            "masked_missing_count": 0,
        },
        "provenance": {
            "source_evidence_sha256": SHA256,
            "topology_context_sha256": "c" * 64,
            "feature_catalog_sha256": "b" * 64,
            "evidence_mask_plan_id": None,
        },
    }
    validate_dataset_row_v4(row, _load(CATALOG_PATH), repository_root=ROOT)
    row["labels"]["truth_model"] = "multiple_fault"
    with pytest.raises(ExpansionContractError):
        validate_dataset_row_v4(row, _load(CATALOG_PATH), repository_root=ROOT)


def test_diagnosis_result_v2_supports_objective_ranked_single_fault_output() -> None:
    first = {
        "fault_type": "missing_static_route",
        "score": 0.8,
        "location": "r1",
        "affected_resource": "10.10.2.0/24",
    }
    result = {
        "schema_version": 2,
        "result_id": "diagnosis-x1",
        "input_vector_id": "vector-v2-adapted",
        "method": "hybrid_v2",
        "truth_model": "single_fault",
        "status": "diagnosed",
        "prediction": first,
        "ranked_candidates": [
            first,
            {
                "fault_type": "wrong_next_hop",
                "score": 0.2,
                "location": "r1",
                "affected_resource": "10.10.2.0/24",
            },
        ],
        "evidence_assessment": {
            "completeness_ratio": 1.0,
            "conflict_detected": False,
            "missing_domains": [],
        },
        "explanation_refs": ["rule-route-missing"],
    }
    validate_diagnosis_result_v2(result, repository_root=ROOT)


def test_diagnosis_result_v2_rejects_unsorted_candidates() -> None:
    result = {
        "schema_version": 2,
        "result_id": "diagnosis-x1",
        "input_vector_id": "vector-v2-adapted",
        "method": "ml_v2",
        "truth_model": "single_fault",
        "status": "diagnosed",
        "prediction": {
            "fault_type": "a",
            "score": 0.2,
            "location": None,
            "affected_resource": None,
        },
        "ranked_candidates": [
            {"fault_type": "a", "score": 0.2, "location": None, "affected_resource": None},
            {"fault_type": "b", "score": 0.8, "location": None, "affected_resource": None},
        ],
        "evidence_assessment": {
            "completeness_ratio": 1.0,
            "conflict_detected": False,
            "missing_domains": [],
        },
        "explanation_refs": [],
    }
    with pytest.raises(ExpansionContractError, match="descending"):
        validate_diagnosis_result_v2(result, repository_root=ROOT)


@pytest.mark.parametrize(
    "mutation",
    ["runtime", "class_order", "multiple_fault", "p9"],
)
def test_x1_manifest_fails_closed_on_boundary_drift(mutation: str) -> None:
    manifest = _load(MANIFEST_PATH)
    if mutation == "runtime":
        manifest["runtime_authorization"]["network_mutation"] = True
    elif mutation == "class_order":
        manifest["compatibility"]["frozen_class_order"].reverse()
    elif mutation == "multiple_fault":
        manifest["truth_boundaries"]["dataset_row_v4"] = "MULTIPLE_FAULT"
    else:
        manifest["track"]["phase9_status"] = "RESUMED"
    with pytest.raises(X1GateError):
        validate_x1_manifest(manifest)


def test_x1_runtime_authorization_is_exactly_all_false() -> None:
    authorization = _load(MANIFEST_PATH)["runtime_authorization"]
    assert tuple(authorization) == EXPECTED_RUNTIME_FLAGS
    assert not any(authorization.values())


def test_registry_and_adapter_import_no_execution_or_model_modules() -> None:
    for relative_path in (
        "src/collection/modular_registry.py",
        "src/expansion/evidence_v3_adapter.py",
    ):
        tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        forbidden = (
            "subprocess",
            "docker",
            "joblib",
            "sklearn",
            "src.runtime",
            "src.fault_injection",
            "src.orchestration",
        )
        assert not any(
            module == prefix or module.startswith(prefix + ".")
            for module in imported_modules
            for prefix in forbidden
        )


def test_adapter_contains_no_file_write_api() -> None:
    source = (ROOT / "src/expansion/evidence_v3_adapter.py").read_text(
        encoding="utf-8"
    )
    assert ".write_text(" not in source
    assert ".write_bytes(" not in source
    assert "open(" not in source
