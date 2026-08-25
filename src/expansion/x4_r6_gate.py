from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Mapping

from jsonschema import Draft202012Validator, FormatChecker
from src.expansion.x4_gate import verify_x4_gate
from src.expansion.x4_r5_gate import verify_x4_r5_gate

ROOT = Path(__file__).resolve().parents[2]
PLAN = Path("plans/expansion/X4_R6_DHCP_DNS_SERVICE_SECURITY_CLOSEOUT_V1.json")
PLAN_SCHEMA = Path("schemas/x4_r6_dhcp_dns_service_security_closeout_v1.schema.json")
RECEIPT_SCHEMA = Path("schemas/x4_r6_dhcp_dns_service_security_evidence_receipt_v1.schema.json")
EXPECTED_PARENT = "4df8d3ed62fcff0c860d46a7109f3ae09314acac"
SHA256 = re.compile(r"[0-9a-f]{64}")
FEATURES = ("dhcp_server_reachable", "dhcp_lease_obtained", "dhcp_lease_matches_expected_scope", "dns_server_reachable", "dns_query_succeeds", "dns_answer_matches_expected", "service_process_running", "service_port_reachable", "service_flow_blocked_by_policy")
EXPECTED_SLICES = {
 "X4_R1_DHCP_SERVER_UNAVAILABLE": ("dhcp_server_unavailable", "R_X4_SERVICE_SECURITY_001", (False,False,False,True,True,True,True,True,False), "x4_top_01_dhcp_dns_service_security_dhcp_flow_context_v1"),
 "X4_R2_DHCP_POOL_MISCONFIGURATION": ("dhcp_pool_misconfiguration", "R_X4_SERVICE_SECURITY_002", (True,False,False,True,True,True,True,True,False), "x4_top_01_dhcp_dns_service_security_dhcp_flow_context_v1"),
 "X4_R3_DNS_SERVICE_DOWN": ("dns_service_down", "R_X4_SERVICE_SECURITY_003", (True,True,True,True,False,False,False,False,False), "x4_top_01_dhcp_dns_service_security_dns_flow_context_v1"),
 "X4_R4_WRONG_DNS_RECORD": ("wrong_dns_record", "R_X4_SERVICE_SECURITY_004", (True,True,True,True,True,False,True,True,False), "x4_top_01_dhcp_dns_service_security_dns_flow_context_v1"),
 "X4_R5_FIREWALL_SERVICE_BLOCK": ("firewall_service_block", "R_X4_SERVICE_SECURITY_005", (True,True,True,True,True,True,True,False,True), "x4_top_01_dhcp_dns_service_security_context_v1"),
}
REQUIRED = {"manifest.json", "mutation/recovery_intent.json", "mutation/injection_record.json", "mutation/restoration_record.json", "parsed/evidence_v4.json", "parsed/feature_vector_v2.json", "diagnosis/diagnosis_result_v2.json", "validation/baseline_before.json", "validation/baseline_after.json"}

class X4R6CloseoutError(ValueError): pass

def _load(path: Path, label: str) -> dict[str, object]:
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error: raise X4R6CloseoutError("Cannot read " + label + ": " + str(path)) from error
    if not isinstance(value, dict): raise X4R6CloseoutError(label + " must be a JSON object.")
    return value
def _validate(value: Mapping[str, object], schema: Path, label: str) -> None:
    errors = list(Draft202012Validator(_load(schema, label + " schema"), format_checker=FormatChecker()).iter_errors(value))
    if errors: raise X4R6CloseoutError(label + " schema validation failed: " + errors[0].message)
def _canonical(value: object, label: str) -> str:
    if not isinstance(value, str) or not value: raise X4R6CloseoutError(label + " path is invalid.")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != value: raise X4R6CloseoutError(label + " path is not canonical: " + value)
    return value
def _digest(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def _tree(rows: list[Mapping[str, object]]) -> str: return hashlib.sha256("".join(sorted(str(row["sha256"]) + "  " + str(row["path"]) + chr(10) for row in rows)).encode()).hexdigest()

def verify_x4_r6_source_gate(repository_root: Path = ROOT) -> dict[str, object]:
    root = Path(repository_root); plan = _load(root / PLAN, "X4-R6 closeout plan"); _validate(plan, root / PLAN_SCHEMA, "X4-R6 closeout plan")
    if plan.get("source_boundary") != {"parent_commit": EXPECTED_PARENT, "extension_policy": "APPEND_ONLY", "runtime_inherited": False}: raise X4R6CloseoutError("X4-R6 parent boundary drifted.")
    flags = plan.get("runtime_authorization")
    if not isinstance(flags, Mapping) or len(flags) != 10 or any(flags.values()): raise X4R6CloseoutError("X4-R6 authorization must be 10/10 false.")
    bindings = plan.get("source_bindings")
    if not isinstance(bindings, list) or len(bindings) != 24: raise X4R6CloseoutError("X4-R6 requires exactly 24 source bindings.")
    seen = set()
    for row in bindings:
        if not isinstance(row, Mapping): raise X4R6CloseoutError("X4-R6 source binding is invalid.")
        relative = _canonical(row.get("path"), "source binding")
        if relative in seen or not SHA256.fullmatch(str(row.get("sha256", ""))): raise X4R6CloseoutError("X4-R6 source binding is duplicate or unhashed.")
        seen.add(relative); path = root / relative
        if not path.is_file() or path.is_symlink() or _digest(path) != row["sha256"]: raise X4R6CloseoutError("X4-R6 source binding drifted: " + relative)
    slices = plan.get("accepted_slices")
    observed = {row.get("release_id"): (row.get("fault_type"), row.get("rule_id"), tuple(row.get("expected_signature", {}).get(name) for name in FEATURES), row.get("topology_context_id")) for row in slices if isinstance(row, Mapping)} if isinstance(slices, list) else {}
    if observed != EXPECTED_SLICES or len({value[2] for value in observed.values()}) != 5: raise X4R6CloseoutError("X4-R6 D1-D5 signatures drifted or are not disjoint.")
    if plan.get("d3_release_alias") != {"canonical_release": "X4_R3_DNS_SERVICE_DOWN", "compatibility_alias": "X4_R3_DNS_SERVICE_UNAVAILABLE", "mapping": "ONE_TO_ONE_SAME_SLICE"}: raise X4R6CloseoutError("X4-R6 D3 alias boundary drifted.")
    if verify_x4_gate(root)["status"] != "ACCEPTED_DESIGN_ONLY" or verify_x4_r5_gate(root)["status"] != "IMPLEMENTED_RUNTIME_SLICE": raise X4R6CloseoutError("An X4 parent gate is not accepted.")
    if plan.get("image_boundary") != {"image": "ind-x4-dhcp:0.2", "accepted_image_modified": False}: raise X4R6CloseoutError("X4-R6 image boundary drifted.")
    return plan

def verify_x4_r6_receipt(receipt_path: Path, *, repository_root: Path = ROOT, schema_root: Path | None = None, verify_materialized: bool = False) -> dict[str, object]:
    root = Path(repository_root); receipt = _load(Path(receipt_path), "X4-R6 evidence receipt"); _validate(receipt, (Path(schema_root) if schema_root else root) / RECEIPT_SCHEMA, "X4-R6 evidence receipt")
    if receipt.get("evidence_kind") != "REPRODUCIBILITY_REVALIDATION_NOT_ORIGINAL_ACCEPTANCE_ARCHIVE": raise X4R6CloseoutError("X4-R6 receipt must not claim recovered original acceptance evidence.")
    runs = receipt.get("runs"); observed = {}
    if not isinstance(runs, list): raise X4R6CloseoutError("X4-R6 receipt runs are invalid.")
    for run in runs:
        if not isinstance(run, Mapping): raise X4R6CloseoutError("X4-R6 receipt run is invalid.")
        release = str(run.get("release_id")); expected = EXPECTED_SLICES.get(release)
        if expected is None or (run.get("fault_type"), run.get("rule_id"), run.get("topology_context_id")) != (expected[0], expected[1], expected[3]): raise X4R6CloseoutError("X4-R6 receipt identity drifted: " + release)
        artifacts = run.get("artifacts"); relative = _canonical(run.get("relative_run_path"), "runtime evidence")
        if not isinstance(artifacts, list): raise X4R6CloseoutError("X4-R6 receipt artifacts are invalid.")
        paths = {_canonical(row.get("path"), "runtime artifact") for row in artifacts if isinstance(row, Mapping)}
        if len(paths) != len(artifacts) or not REQUIRED.issubset(paths) or _tree(artifacts) != run.get("run_tree_sha256"): raise X4R6CloseoutError("X4-R6 receipt tree drifted: " + release)
        if verify_materialized:
            run_root = root / relative
            for artifact in artifacts:
                path = run_root / str(artifact["path"])
                if not path.is_file() or path.is_symlink() or path.stat().st_size != artifact["size_bytes"] or _digest(path) != artifact["sha256"]: raise X4R6CloseoutError("X4-R6 materialized artifact drifted: " + release + "/" + str(artifact["path"]))
        observed[release] = expected
    if observed != EXPECTED_SLICES: raise X4R6CloseoutError("X4-R6 receipt does not cover exact D1-D5 releases.")
    return receipt

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repository-root", type=Path, default=ROOT); parser.add_argument("--receipt", type=Path); parser.add_argument("--verify-materialized", action="store_true"); args = parser.parse_args()
    plan = verify_x4_r6_source_gate(args.repository_root); print("x4_r6_source_gate=VERIFIED")
    if args.receipt: print("evidence_receipt=" + str(len(verify_x4_r6_receipt(args.receipt, repository_root=args.repository_root, verify_materialized=args.verify_materialized)["runs"])) + "/5_REVALIDATION_HASH_BOUND_PASS")
    print("next_release=" + str(plan["track"]["next_release"])); return 0
if __name__ == "__main__": raise SystemExit(main())
