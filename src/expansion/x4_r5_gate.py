from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.contracts.expansion import validate_topology_context_v1
from src.expansion.x4_r4_gate import verify_x4_r4_gate
from src.expansion.x4_firewall_service_block import load_firewall_service_block_scenario
from src.rules.service_security_rule_engine_x4_r5 import D5_SIGNATURE

MANIFEST = Path("plans/expansion/X4_R5_FIREWALL_SERVICE_BLOCK_V1.json")
SCHEMA = Path("schemas/x4_r5_firewall_service_block_gate_v1.schema.json")

def verify_x4_r5_gate(repository_root: Path) -> dict[str, object]:
    root = Path(repository_root); manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8")); schema = json.loads((root / SCHEMA).read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors: raise ValueError("X4-R5 schema validation failed: " + errors[0].message)
    if verify_x4_r4_gate(root)["track"]["next_release"] != "X4_R5_FIREWALL_SERVICE_BLOCK": raise ValueError("X4-R4 parent boundary drifted.")
    frozen = json.loads((root / "plans/expansion/X4_R0_DHCP_DNS_SERVICE_SECURITY_RUNTIME_GATE_V1.json").read_text(encoding="utf-8"))["dhcp_dns_service_security_scope"][4]
    if frozen["implementation_release"] != "X4_R5_FIREWALL_SERVICE_BLOCK" or frozen["fault_type"] != "firewall_service_block" or frozen["fault_signature"] != D5_SIGNATURE: raise ValueError("Frozen X4-R0 D5 boundary drifted.")
    binding = load_firewall_service_block_scenario(root / manifest["slice"]["scenario_path"]); context = json.loads((root / manifest["slice"]["topology_context_path"]).read_text(encoding="utf-8")); validate_topology_context_v1(context, repository_root=root)
    if context["observation_roles"] != {"source": "client", "destination": "app_server", "observers": ["observer"]} or binding.topology_context_id != context["context_id"]: raise ValueError("X4-R5 application-flow provenance drifted.")
    topology = (root / manifest["topology_runtime"]["topology_path"]).read_text(encoding="utf-8")
    if manifest["slice"]["signature"] != D5_SIGNATURE or manifest["slice"]["preserved_rules"] != ["R_X4_SERVICE_SECURITY_001", "R_X4_SERVICE_SECURITY_002", "R_X4_SERVICE_SECURITY_003", "R_X4_SERVICE_SECURITY_004"]: raise ValueError("X4-R5 combined rule boundary drifted.")
    if "image: ind-x4-dhcp:0.2" not in topology or "cap-add: [NET_ADMIN]" not in topology or "X4-R5-SERVICE-BLOCK" not in manifest["slice"]["firewall_semantics"]: raise ValueError("X4-R5 topology/firewall tooling boundary drifted.")
    flags = manifest["runtime_authorization"]
    if any(flags[name] is not False for name in ("dataset_generation", "model_fit_or_selection", "estimator_deserialization", "metric_calculation", "report_only_test_access", "multiple_fault_execution")): raise ValueError("X4-R5 scientific boundary drifted.")
    return manifest

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repository-root", type=Path, default=Path.cwd()); manifest = verify_x4_r5_gate(parser.parse_args().repository_root)
    print("x4_r5_gate=VERIFIED"); return 0
if __name__ == "__main__": raise SystemExit(main())
