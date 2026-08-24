from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.contracts.expansion import validate_topology_context_v1
from src.expansion.x4_r3_gate import verify_x4_r3_gate
from src.expansion.x4_wrong_dns_record import load_wrong_dns_record_scenario
from src.rules.service_security_rule_engine_x4_r1 import SIGNATURE as D1_SIGNATURE
from src.rules.service_security_rule_engine_x4_r2 import D2_SIGNATURE
from src.rules.service_security_rule_engine_x4_r3 import D3_SIGNATURE
from src.rules.service_security_rule_engine_x4_r4 import D4_SIGNATURE


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path("plans/expansion/X4_R4_WRONG_DNS_RECORD_V1.json")
SCHEMA = Path("schemas/x4_r4_wrong_dns_record_gate_v1.schema.json")


def verify_x4_r4_gate(repository_root: Path) -> dict[str, object]:
    root = Path(repository_root); manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8")); schema = json.loads((root / SCHEMA).read_text(encoding="utf-8")); errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors: raise ValueError("X4-R4 schema validation failed: " + errors[0].message)
    if verify_x4_r3_gate(root)["track"]["next_release"] != "X4_R4_WRONG_DNS_RECORD": raise ValueError("X4-R3 parent/alias boundary drifted.")
    if manifest["source_boundary"] != {"parent_commit": "b9a6ad97a9605f2237a08d300bbfbab07870e465", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}: raise ValueError("X4-R4 append-only parent boundary drifted.")
    frozen = json.loads((root / "plans/expansion/X4_R0_DHCP_DNS_SERVICE_SECURITY_RUNTIME_GATE_V1.json").read_text(encoding="utf-8")); d4 = frozen["dhcp_dns_service_security_scope"][3]
    if d4["implementation_release"] != "X4_R4_WRONG_DNS_RECORD" or d4["fault_type"] != "wrong_dns_record" or d4["fault_signature"] != D4_SIGNATURE: raise ValueError("Frozen X4-R0 D4 identity/signature drifted.")
    slice_ = manifest["slice"]
    if slice_["signature"] != D4_SIGNATURE or slice_["preserved_rules"] != ["R_X4_SERVICE_SECURITY_001", "R_X4_SERVICE_SECURITY_002", "R_X4_SERVICE_SECURITY_003"]: raise ValueError("X4-R4 D1-D4 combined-rule boundary drifted.")
    binding = load_wrong_dns_record_scenario(root / slice_["scenario_path"]); context = json.loads((root / slice_["topology_context_path"]).read_text(encoding="utf-8")); validate_topology_context_v1(context, repository_root=root)
    if binding.topology_context_id != context["context_id"] or context["observation_roles"] != {"source": "client", "destination": "dns_server", "observers": ["observer"]}: raise ValueError("X4-R4 must reuse the accepted DNS-flow context.")
    runtime = manifest["topology_runtime"]
    topology_text = (root / runtime["topology_path"]).read_text(encoding="utf-8")
    if runtime["image"] != "ind-x4-dhcp:0.2" or runtime["topology_path"] != binding.scenario["topology"]["file"] or "/etc/x4-dns/dnsmasq.conf" not in topology_text: raise ValueError("X4-R4 accepted image/direct-config topology boundary drifted.")
    if "norecurse" not in slice_["dns_semantics"] or "collection_unavailable" not in slice_["dns_semantics"] or slice_["controlled_record"] != {"expected_line": binding.expected_record_line, "wrong_line": binding.controlled_wrong_record_line}: raise ValueError("X4-R4 DNS evidence semantics drifted.")
    flags = manifest["runtime_authorization"]
    if any(flags[name] is not False for name in ("dataset_generation", "model_fit_or_selection", "estimator_deserialization", "metric_calculation", "report_only_test_access", "multiple_fault_execution")): raise ValueError("X4-R4 scientific authorization boundary drifted.")
    bindings = manifest.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 20 or len({row.get("path") for row in bindings}) != 20: raise ValueError("X4-R4 requires 20 unique hash bindings.")
    for row in bindings:
        path = root / str(row.get("path"))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.get("sha256"): raise ValueError("X4-R4 source binding drifted: " + str(row.get("path")))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repository-root", type=Path, default=Path.cwd()); manifest = verify_x4_r4_gate(parser.parse_args().repository_root)
    print("x4_r0_gate=VERIFIED\nx4_r1_gate=VERIFIED\nx4_r2_gate=VERIFIED\nx4_r3_gate=VERIFIED\nx4_r4_gate=VERIFIED\nd1_d3_rules=PRESERVED\nd4_signature=TRUE_TRUE_TRUE_TRUE_TRUE_FALSE_TRUE_TRUE_FALSE_PASS\ndns_context=CLIENT_TO_DNS_SERVER_REUSED_PASS\nimage=ind-x4-dhcp:0.2_PASS\nnext_release=" + manifest["track"]["next_release"])
    return 0


if __name__ == "__main__": raise SystemExit(main())
