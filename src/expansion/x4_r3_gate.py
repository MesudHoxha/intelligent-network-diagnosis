from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.contracts.expansion import validate_topology_context_v1
from src.expansion.x4_dns_service_down import load_dns_service_down_scenario
from src.expansion.x4_r2_gate import verify_x4_r2_gate
from src.rules.service_security_rule_engine_x4_r1 import SIGNATURE as D1_SIGNATURE
from src.rules.service_security_rule_engine_x4_r2 import D2_SIGNATURE
from src.rules.service_security_rule_engine_x4_r3 import D3_SIGNATURE


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path("plans/expansion/X4_R3_DNS_SERVICE_DOWN_V1.json")
SCHEMA = Path("schemas/x4_r3_dns_service_down_gate_v1.schema.json")


def verify_x4_r3_gate(repository_root: Path) -> dict[str, object]:
    root = Path(repository_root); manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8")); schema = json.loads((root / SCHEMA).read_text(encoding="utf-8")); errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors: raise ValueError("X4-R3 schema validation failed: " + errors[0].message)
    if verify_x4_r2_gate(root)["track"]["next_release"] != "X4_R3_DNS_SERVICE_UNAVAILABLE": raise ValueError("X4-R2 compatibility-alias boundary drifted.")
    if manifest["source_boundary"] != {"parent_commit": "980488cebfc0000fb8bd6e19b5b7e043bf163887", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}: raise ValueError("X4-R3 append-only parent boundary drifted.")
    alias = manifest["release_alias"]
    if alias != {"canonical_release": "X4_R3_DNS_SERVICE_DOWN", "compatibility_alias": "X4_R3_DNS_SERVICE_UNAVAILABLE", "fault_type": "dns_service_down", "mapping": "ONE_TO_ONE_SAME_SLICE", "separate_runtime_artifacts_forbidden": True, "separate_scientific_claim_forbidden": True}: raise ValueError("X4-R3 canonical/alias mapping drifted.")
    frozen = json.loads((root / "plans/expansion/X4_R0_DHCP_DNS_SERVICE_SECURITY_RUNTIME_GATE_V1.json").read_text(encoding="utf-8")); d3 = frozen["dhcp_dns_service_security_scope"][2]
    if d3["implementation_release"] != alias["canonical_release"] or d3["fault_type"] != alias["fault_type"] or d3["fault_signature"] != D3_SIGNATURE: raise ValueError("Frozen X4-R0 D3 identity/signature drifted.")
    slice_ = manifest["slice"]
    if slice_["signature"] != D3_SIGNATURE or slice_["preserved_rules"] != ["R_X4_SERVICE_SECURITY_001", "R_X4_SERVICE_SECURITY_002"]: raise ValueError("X4-R3 D1/D2/D3 rule boundary drifted.")
    binding = load_dns_service_down_scenario(root / slice_["scenario_path"])
    if binding.scenario_id != alias["canonical_release"] or binding.compatibility_alias != alias["compatibility_alias"]: raise ValueError("X4-R3 scenario aliases must bind one release.")
    context = json.loads((root / slice_["topology_context_path"]).read_text(encoding="utf-8")); validate_topology_context_v1(context, repository_root=root)
    if binding.topology_context_id != context["context_id"] or context["observation_roles"] != {"source": "client", "destination": "dns_server", "observers": ["observer"]}: raise ValueError("X4-R3 must bind a distinct client-to-DNS-server context.")
    if context["context_id"] == "x4_top_01_dhcp_dns_service_security_dhcp_flow_context_v1": raise ValueError("X4-R3 cannot reuse DHCP-flow provenance.")
    runtime = manifest["topology_runtime"]
    if runtime["image"] != "ind-x4-dhcp:0.2" or runtime["topology_path"] != binding.scenario["topology"]["file"]: raise ValueError("X4-R3 accepted image/topology boundary drifted.")
    if "real dig" not in slice_["dns_semantics"] or "collection_unavailable" not in slice_["dns_semantics"]: raise ValueError("X4-R3 DNS Evidence v4 semantics drifted.")
    flags = manifest["runtime_authorization"]
    if any(flags[name] is not False for name in ("dataset_generation", "model_fit_or_selection", "estimator_deserialization", "metric_calculation", "report_only_test_access", "multiple_fault_execution")): raise ValueError("X4-R3 scientific authorization boundary drifted.")
    bindings = manifest.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 20 or len({row.get("path") for row in bindings}) != 20: raise ValueError("X4-R3 requires 20 unique hash bindings.")
    for row in bindings:
        path = root / str(row.get("path"))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.get("sha256"): raise ValueError("X4-R3 source binding drifted: " + str(row.get("path")))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repository-root", type=Path, default=Path.cwd()); manifest = verify_x4_r3_gate(parser.parse_args().repository_root)
    print("x4_r0_gate=VERIFIED\nx4_r1_gate=VERIFIED\nx4_r2_gate=VERIFIED\nx4_r3_gate=VERIFIED\ncanonical_release=X4_R3_DNS_SERVICE_DOWN\ncompatibility_alias=X4_R3_DNS_SERVICE_UNAVAILABLE_SAME_SLICE\nd1_d2_rules=PRESERVED\nd3_signature=TRUE_TRUE_TRUE_TRUE_FALSE_FALSE_FALSE_FALSE_FALSE_PASS\ndns_context=CLIENT_TO_DNS_SERVER_DISTINCT_PASS\nimage=ind-x4-dhcp:0.2_PASS\nnext_release=" + manifest["track"]["next_release"])
    return 0


if __name__ == "__main__": raise SystemExit(main())
