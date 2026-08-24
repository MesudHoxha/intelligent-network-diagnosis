from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.contracts.expansion import validate_topology_context_v1
from src.expansion import x4_gate
from src.expansion.x4_gate import (
    EXPECTED_BASELINE_SIGNATURE,
    EXPECTED_COLLECTOR_BINDINGS,
    EXPECTED_FAULTS,
    EXPECTED_FEATURE_IDS,
    EXPECTED_FLOWS,
    EXPECTED_LINKS,
    EXPECTED_NODES,
    EXPECTED_RELEASES,
    EXPECTED_RUNTIME_FLAGS,
    EXPECTED_SAFETY_INVARIANTS,
    EXPECTED_SIGNATURES,
    X4GateError,
    _validate_topology,
    validate_x4_manifest,
    verify_x4_gate,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "plans/expansion/X4_R0_DHCP_DNS_SERVICE_SECURITY_RUNTIME_GATE_V1.json"
SCHEMA_PATH = ROOT / "schemas/x4_dhcp_dns_service_security_runtime_gate_v1.schema.json"
TOPOLOGY_PATH = ROOT / "labs/topologies/x4_r1_dhcp_dns_service/topology_context_v1.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_x4_r0_schema_manifest_and_repository_gate_verify() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA_PATH))
    validate_x4_manifest(_load(MANIFEST_PATH), _load(SCHEMA_PATH))
    verified = verify_x4_gate(ROOT)
    assert verified["status"] == "ACCEPTED_DESIGN_ONLY"
    assert verified["track"]["next_release"] == "X4_R1_DHCP_SERVER_UNAVAILABLE"


def test_x4_scope_features_and_signatures_are_exact_and_disjoint() -> None:
    manifest = _load(MANIFEST_PATH)
    slices = manifest["dhcp_dns_service_security_scope"]
    assert tuple((row["fault_code"], row["fault_type"], row["category"], row["implementation_release"]) for row in slices) == EXPECTED_FAULTS
    assert tuple(row["order"] for row in slices) == (1, 2, 3, 4, 5)
    assert manifest["baseline_signature"] == EXPECTED_BASELINE_SIGNATURE
    signatures = []
    for row in slices:
        assert row["fault_signature"] == EXPECTED_SIGNATURES[row["fault_type"]]
        assert tuple(row["required_feature_ids"]) == EXPECTED_FEATURE_IDS
        signatures.append(tuple(sorted(row["fault_signature"].items())))
    assert len(signatures) == len(set(signatures)) == 5


def test_dhcp_dns_and_service_security_are_separated_by_direct_state() -> None:
    signatures = EXPECTED_SIGNATURES
    assert signatures["dhcp_server_unavailable"]["dhcp_server_reachable"] is False
    assert signatures["dhcp_pool_misconfiguration"]["dhcp_server_reachable"] is True
    assert signatures["dns_service_down"]["dns_server_reachable"] is True
    assert signatures["dns_service_down"]["dns_query_succeeds"] is False
    assert signatures["wrong_dns_record"]["dns_query_succeeds"] is True
    assert signatures["wrong_dns_record"]["dns_answer_matches_expected"] is False
    assert signatures["firewall_service_block"]["service_process_running"] is True
    assert signatures["firewall_service_block"]["service_port_reachable"] is False
    assert signatures["firewall_service_block"]["service_flow_blocked_by_policy"] is True


def test_topology_context_and_flow_roles_are_exact() -> None:
    context = _load(TOPOLOGY_PATH)
    validate_topology_context_v1(context, repository_root=ROOT)
    _validate_topology(context)
    assert tuple((row["node_id"], row["role"]) for row in context["nodes"]) == EXPECTED_NODES
    assert tuple((row["link_id"], row["kind"], tuple(endpoint["node_id"] for endpoint in row["endpoints"])) for row in context["links"]) == EXPECTED_LINKS
    design = _load(MANIFEST_PATH)["topology_design"]
    assert tuple((row["flow_id"], row["source"], row["destination"], row["transport"], row["port"], row["classification_role"]) for row in design["flow_roles"]) == EXPECTED_FLOWS


def test_feature_ownership_release_order_and_safety_are_exact() -> None:
    manifest = _load(MANIFEST_PATH)
    boundary = manifest["feature_boundary"]
    assert tuple(boundary["required_feature_ids"]) == EXPECTED_FEATURE_IDS
    assert tuple((row["collector_id"], row["collector_version"], row["collector_status"], tuple(row["feature_ids"])) for row in boundary["collector_bindings"]) == EXPECTED_COLLECTOR_BINDINGS
    releases = manifest["release_sequence"]
    assert tuple(row["release_id"] for row in releases) == EXPECTED_RELEASES
    assert releases[0]["status"] == "ACCEPTED_DESIGN_ONLY"
    assert all(row["status"] == "PLANNED" and row["runtime_inherited"] is False for row in releases[1:])
    assert tuple(manifest["safety_invariants"]) == EXPECTED_SAFETY_INVARIANTS


def test_runtime_and_claim_boundary_remain_design_only() -> None:
    manifest = _load(MANIFEST_PATH)
    authorization = manifest["runtime_authorization"]
    assert tuple(authorization) == EXPECTED_RUNTIME_FLAGS
    assert not any(authorization.values())
    assert manifest["evidence_policy"]["effectiveness_only_evidence_not_classifier"] is True
    assert manifest["evidence_policy"]["r0_creates_empirical_evidence"] is False
    assert manifest["acceptance"]["new_runtime_executed"] is False
    assert manifest["acceptance"]["new_empirical_claim_created"] is False


def test_source_bindings_are_unique_hash_bound_and_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _load(MANIFEST_PATH)
    bindings = manifest["source_bindings"]
    assert len(bindings) == len({row["binding_id"] for row in bindings}) == len({row["path"] for row in bindings}) == 11
    for row in bindings:
        assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    changed = copy.deepcopy(manifest)
    changed["runtime_authorization"]["network_mutation"] = True
    with pytest.raises(X4GateError):
        validate_x4_manifest(changed, _load(SCHEMA_PATH))
    changed = copy.deepcopy(manifest)
    changed["dhcp_dns_service_security_scope"][1]["fault_signature"] = copy.deepcopy(changed["dhcp_dns_service_security_scope"][0]["fault_signature"])
    with pytest.raises(X4GateError):
        validate_x4_manifest(changed, _load(SCHEMA_PATH))
    changed = copy.deepcopy(manifest)
    changed["source_bindings"][0]["sha256"] = "0" * 64
    original_load = x4_gate._load_json
    monkeypatch.setattr(x4_gate, "_load_json", lambda path: changed if path == ROOT / x4_gate.MANIFEST_PATH else original_load(path))
    with pytest.raises(X4GateError):
        verify_x4_gate(ROOT)
