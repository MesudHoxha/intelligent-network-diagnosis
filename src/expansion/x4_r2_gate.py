from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.contracts.expansion import validate_topology_context_v1
from src.expansion.x4_dhcp_pool_misconfiguration import load_dhcp_pool_misconfiguration_scenario
from src.expansion.x4_r1_gate import SIGNATURE as D1_SIGNATURE, verify_x4_r1_gate
from src.rules.service_security_rule_engine_x4_r2 import D2_SIGNATURE


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path("plans/expansion/X4_R2_DHCP_POOL_MISCONFIGURATION_V1.json")
SCHEMA = Path("schemas/x4_r2_dhcp_pool_misconfiguration_gate_v1.schema.json")


def verify_x4_r2_gate(repository_root: Path) -> dict[str, object]:
    root = Path(repository_root); manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8")); schema = json.loads((root / SCHEMA).read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors: raise ValueError("X4-R2 schema validation failed: " + errors[0].message)
    if verify_x4_r1_gate(root)["track"]["next_release"] != "X4_R2_DHCP_POOL_MISCONFIGURATION": raise ValueError("X4-R1 parent boundary drifted.")
    if manifest["source_boundary"] != {"parent_commit": "00219ffd947cf4a7c8723c0341d6efdce9654ed4", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}: raise ValueError("X4-R2 append-only parent boundary drifted.")
    slice_ = manifest["slice"]
    if slice_["signature"] != D2_SIGNATURE or slice_["preserved_d1_signature"] != D1_SIGNATURE or slice_["preserved_d1_rule_id"] != "R_X4_SERVICE_SECURITY_001": raise ValueError("X4-R2 exact D2/D1 signature boundary drifted.")
    binding = load_dhcp_pool_misconfiguration_scenario(root / slice_["scenario_path"])
    context = json.loads((root / slice_["topology_context_path"]).read_text(encoding="utf-8")); validate_topology_context_v1(context, repository_root=root)
    if binding.topology_context_id != context["context_id"] or context["observation_roles"] != {"source": "client", "destination": "dhcp_server", "observers": ["observer"]}: raise ValueError("X4-R2 must bind the accepted DHCP-flow context.")
    runtime = manifest["topology_runtime"]
    if runtime["image"] != "ind-x4-dhcp:0.2" or runtime["topology_path"] != binding.scenario["topology"]["file"]: raise ValueError("X4-R2 accepted image/topology boundary drifted.")
    if "not ICMP" not in slice_["evidence_semantics"] or "collection_unavailable" not in slice_["evidence_semantics"]: raise ValueError("X4-R2 Evidence v4 semantics drifted.")
    if binding.expected_pool_line not in (root / runtime["topology_path"]).read_text(encoding="utf-8"): raise ValueError("X4-R2 expected DHCP pool is not bound to the accepted topology.")
    flags = manifest["runtime_authorization"]
    if any(flags[name] is not False for name in ("dataset_generation", "model_fit_or_selection", "estimator_deserialization", "metric_calculation", "report_only_test_access", "multiple_fault_execution")): raise ValueError("X4-R2 scientific authorization boundary drifted.")
    bindings = manifest.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 20 or len({row.get("path") for row in bindings}) != 20: raise ValueError("X4-R2 requires 20 unique hash bindings.")
    for row in bindings:
        path = root / str(row.get("path"))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.get("sha256"): raise ValueError("X4-R2 source binding drifted: " + str(row.get("path")))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repository-root", type=Path, default=Path.cwd()); manifest = verify_x4_r2_gate(parser.parse_args().repository_root)
    print("x4_r0_gate=VERIFIED\nx4_r1_gate=VERIFIED\nx4_r2_gate=VERIFIED\nd1_signature=PRESERVED\nd2_signature=TRUE_FALSE_FALSE_TRUE_TRUE_TRUE_TRUE_TRUE_FALSE_PASS\ndhcp_context=CLIENT_TO_DHCP_SERVER_REUSED_PASS\nimage=ind-x4-dhcp:0.2_PASS\nnext_release=" + manifest["track"]["next_release"])
    return 0


if __name__ == "__main__": raise SystemExit(main())
