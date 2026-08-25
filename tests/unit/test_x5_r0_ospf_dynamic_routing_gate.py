from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.contracts.expansion import validate_topology_context_v1
from src.expansion import x5_gate
from src.expansion.x5_gate import EXPECTED_FEATURE_IDS, EXPECTED_FAULTS, EXPECTED_RELEASES, EXPECTED_SIGNATURES, X5GateError, _validate_topology, validate_x5_manifest, verify_x5_gate


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "plans/expansion/X5_R0_OSPF_DYNAMIC_ROUTING_RUNTIME_GATE_V1.json"
SCHEMA = ROOT / "schemas/x5_ospf_dynamic_routing_runtime_gate_v1.schema.json"
TOPOLOGY = ROOT / "labs/topologies/x5_r1_ospf_dynamic_routing/topology_context_v1.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_x5_r0_schema_manifest_and_repository_gate_verify() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA))
    validate_x5_manifest(_load(MANIFEST), _load(SCHEMA))
    verified = verify_x5_gate(ROOT)
    assert verified["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verified["track"]["next_release"] == "X5_R1_OSPF_ADJACENCY_FAILURE"


def test_x5_scope_features_and_signatures_are_exact_and_disjoint() -> None:
    manifest = _load(MANIFEST)
    slices = manifest["ospf_dynamic_routing_scope"]
    assert tuple((row["fault_code"], row["fault_type"], row["implementation_release"]) for row in slices) == EXPECTED_FAULTS
    assert tuple(tuple(row["required_feature_ids"]) for row in slices) == (EXPECTED_FEATURE_IDS, EXPECTED_FEATURE_IDS)
    assert all(row["fault_signature"] == EXPECTED_SIGNATURES[row["fault_type"]] for row in slices)
    assert len({tuple(sorted(row["fault_signature"].items())) for row in slices}) == 2


def test_ospf_direct_state_separates_adjacency_from_policy_suppression() -> None:
    adjacency, filtering = EXPECTED_SIGNATURES["dynamic_routing_adjacency_failure"], EXPECTED_SIGNATURES["route_filtering_or_advertisement_problem"]
    assert adjacency["ospf_adjacency_full"] is False and adjacency["route_filter_allows_prefix"] is True
    assert filtering["ospf_adjacency_full"] is True and filtering["route_filter_allows_prefix"] is False
    assert adjacency["ospf_route_installed"] is filtering["ospf_route_installed"] is False


def test_topology_and_release_controls_are_exact() -> None:
    context = _load(TOPOLOGY)
    validate_topology_context_v1(context, repository_root=ROOT)
    _validate_topology(context)
    manifest = _load(MANIFEST)
    assert tuple(row["release_id"] for row in manifest["release_sequence"]) == EXPECTED_RELEASES
    assert manifest["feature_boundary"]["collector_binding"]["collector_id"] == "ospf_state_collector"
    assert "STATIC_ROUTE_OVERRIDE_CONTROL" in manifest["topology_design"]["required_raw_observations"]


def test_design_only_boundary_and_hash_bindings_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _load(MANIFEST)
    assert not any(manifest["runtime_authorization"].values())
    assert manifest["acceptance"]["new_runtime_executed"] is False
    for row in manifest["source_bindings"]:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    changed = copy.deepcopy(manifest)
    changed["runtime_authorization"]["network_mutation"] = True
    with pytest.raises(X5GateError):
        validate_x5_manifest(changed, _load(SCHEMA))
    changed = copy.deepcopy(manifest)
    changed["ospf_dynamic_routing_scope"][1]["fault_signature"] = copy.deepcopy(changed["ospf_dynamic_routing_scope"][0]["fault_signature"])
    with pytest.raises(X5GateError):
        validate_x5_manifest(changed, _load(SCHEMA))
    changed = copy.deepcopy(manifest)
    changed["source_bindings"][0]["sha256"] = "0" * 64
    original_load = x5_gate._load_json
    monkeypatch.setattr(x5_gate, "_load_json", lambda path: changed if path == ROOT / x5_gate.MANIFEST_PATH else original_load(path))
    with pytest.raises(X5GateError):
        verify_x5_gate(ROOT)
