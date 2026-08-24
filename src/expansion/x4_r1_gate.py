from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from jsonschema import Draft202012Validator

from src.contracts.expansion import validate_topology_context_v1
from src.expansion.x4_dhcp_server_unavailable import load_dhcp_server_unavailable_scenario
from src.expansion.x4_gate import verify_x4_gate


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path("plans/expansion/X4_R1_DHCP_SERVER_UNAVAILABLE_V1.json")
SCHEMA = Path("schemas/x4_r1_dhcp_server_unavailable_gate_v1.schema.json")
SIGNATURE = {"dhcp_server_reachable": False, "dhcp_lease_obtained": False, "dhcp_lease_matches_expected_scope": False, "dns_server_reachable": True, "dns_query_succeeds": True, "dns_answer_matches_expected": True, "service_process_running": True, "service_port_reachable": True, "service_flow_blocked_by_policy": False}


def verify_x4_r1_gate(repository_root: Path) -> dict[str, object]:
    root = Path(repository_root); manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8")); schema = json.loads((root / SCHEMA).read_text(encoding="utf-8")); errors = list(Draft202012Validator(schema).iter_errors(manifest))
    if errors: raise ValueError("X4-R1 schema validation failed: " + errors[0].message)
    if verify_x4_gate(root)["track"]["next_release"] != "X4_R1_DHCP_SERVER_UNAVAILABLE": raise ValueError("X4-R0 parent boundary drifted.")
    if manifest["source_boundary"] != {"parent_commit": "f23f08cd6ef019b3cc0b4fd2c16f3a2609370cb7", "extension_policy": "APPEND_ONLY", "runtime_inherited": False}: raise ValueError("X4-R1 append-only parent boundary drifted.")
    if manifest["slice"]["signature"] != SIGNATURE: raise ValueError("X4-R1 D1 signature drifted.")
    binding = load_dhcp_server_unavailable_scenario(root / manifest["slice"]["scenario_path"]); context = json.loads((root / manifest["slice"]["topology_context_path"]).read_text(encoding="utf-8")); validate_topology_context_v1(context, repository_root=root)
    if binding.topology_context_id != context["context_id"] or context["observation_roles"] != {"source": "client", "destination": "dhcp_server", "observers": ["observer"]}: raise ValueError("X4-R1 must bind a distinct DHCP-flow context.")
    if manifest["topology_runtime"]["image"] != "ind-x4-dhcp:0.2" or "ind-linux:0.1" not in (root / "labs/images/ind-x4-dhcp/Dockerfile").read_text(encoding="utf-8"): raise ValueError("X4-R1 versioned image boundary drifted.")
    if "ICMP" not in manifest["slice"]["dhcp_endpoint_semantics"] or "collection_unavailable" not in manifest["slice"]["negative_lease_semantics"]: raise ValueError("X4-R1 DHCP evidence semantics drifted.")
    bindings = manifest.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 18 or len({row.get("path") for row in bindings}) != 18: raise ValueError("X4-R1 requires 18 unique hash bindings.")
    for row in bindings:
        path = root / str(row.get("path"))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row.get("sha256"): raise ValueError("X4-R1 source binding drifted: " + str(row.get("path")))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repository-root", type=Path, default=Path.cwd()); manifest = verify_x4_r1_gate(parser.parse_args().repository_root)
    print("x4_r0_gate=VERIFIED\nx4_r1_gate=VERIFIED\nd1_signature=FALSE_FALSE_FALSE_TRUE_TRUE_TRUE_TRUE_TRUE_FALSE_PASS\ndhcp_context=CLIENT_TO_DHCP_SERVER_PASS\nendpoint_semantics=DHCP_PROTOCOL_NOT_ICMP_PASS\nnext_release=" + manifest["track"]["next_release"]); return 0


if __name__ == "__main__": raise SystemExit(main())
