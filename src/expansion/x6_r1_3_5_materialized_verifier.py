"""Independent, non-mutating verifier for a future R1.3.5 run tree."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from src.orchestration.x6_r1_3_5_baseline_provenance import RELEASE_ID, X6R135Error, canonical_bytes, derive_source_identity, safe_relative, sha256, verify_command_inventory, verify_recovery
from src.orchestration.x6_r1_3_3_baseline_only_runner import WINDOW_IDS
from src.collection.x6_r0_3_pre_runtime_validation import NUMERIC_FEATURES, build_threshold_manifest, canonical_threshold_manifest_bytes
from src.orchestration import x6_r1_3_5_authorization as b1

# R1.3.5 is source-only preparation.  It never derives or accepts a runtime
# qualification terminal, including when one is asserted in an input artifact.
TERMINAL = {"UNSTABLE", "COLLECTION_UNAVAILABLE", "ENVIRONMENT_INELIGIBLE", "INTERRUPTED", "CLEANUP_FAILED", "VERIFICATION_FAILED"}


def _fail(message: str) -> None:
    raise X6R135Error("X6-R1.3.5 verifier: " + message)


def _read(root: Path, relative: str) -> Mapping[str, object]:
    path = root / safe_relative(relative)
    if not path.is_file() or path.is_symlink(): _fail("required artifact missing or unsafe: " + relative)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping): _fail("artifact object required: " + relative)
    return value

def verify_thirty_window_artifacts(root: Path, *, run_id: str, authorization_id: str) -> dict[str, object]:
    """Verify complete ordered source-test or future-run window wiring."""
    records = verify_command_inventory(root, run_id=run_id, authorization_id=authorization_id)
    by_path = {"raw/commands/%05d-%s.json" % (row["order"], row["command_name"]): row for row in records}
    rows=[]; previous=-1
    for index, window_id in enumerate(WINDOW_IDS):
        value=_read(root, "raw/windows/"+window_id+".json")
        if value.get("window_id") != window_id or not isinstance(value.get("features"), Mapping) or set(value["features"]) != set(NUMERIC_FEATURES): _fail("window inventory/order/feature drift")
        timing=value.get("timing")
        if not isinstance(timing, Mapping) or timing.get("actual_start_ns") != index*25_000_000_000 or timing.get("actual_end_ns") != index*25_000_000_000+20_000_000_000 or (index and timing["actual_start_ns"] < previous+5_000_000_000): _fail("window timing or ordering drift")
        previous=timing["actual_end_ns"]
        raw=value.get("raw")
        refs=raw.get("command_references") if isinstance(raw, Mapping) else None
        if not isinstance(refs, Mapping) or len(refs) != 14: _fail("per-window command linkage missing")
        for reference in refs.values():
            if not isinstance(reference, Mapping) or not isinstance(reference.get("path"), str) or reference["path"] not in by_path: _fail("cross-run or missing command reference")
            command=by_path[reference["path"]]
            if command["window_id"] != window_id or sha256((root/reference["path"]).read_bytes()) != reference.get("sha256"): _fail("window command hash/identity substitution")
        rows.append(value)
    manifest_path=root/"state/threshold_manifest.json"; freeze=_read(root,"state/threshold_freeze.json")
    if not manifest_path.is_file(): _fail("threshold manifest missing")
    manifest=json.loads(manifest_path.read_text())
    expected=build_threshold_manifest({f:[row["features"][f] for row in rows[:10]] for f in NUMERIC_FEATURES},topology_context_id="X6_TOP_01_CONTROLLED_PERFORMANCE_PATH",traffic_context_id="X6_R1_BASELINE_ONLY_QUALIFICATION")
    if manifest != expected or freeze.get("after_window_id") != "C10" or freeze.get("before_window_id") != "C11" or freeze.get("manifest_sha256") != manifest.get("sha256") or freeze.get("byte_sha256") != sha256(manifest_path.read_bytes()): _fail("C01-C10 threshold freeze drift")
    return {"windows":30,"threshold_frozen_before_c11":True,"qualified":False}

def verify_artifact_inventory(root: Path) -> dict[str, object]:
    root=Path(root); inventory=_read(root,"state/artifact_inventory.json"); rows=inventory.get("artifacts")
    if not isinstance(rows,list) or not rows: _fail("artifact inventory missing")
    declared={};
    for row in rows:
        if not isinstance(row,Mapping) or set(row)!={"path","sha256"} or not isinstance(row["path"],str) or not isinstance(row["sha256"],str): _fail("inventory row malformed")
        path=safe_relative(row["path"])
        if path == "state/artifact_inventory.json" or path in declared: _fail("inventory self-substitution or duplicate path")
        target=root/path
        if not target.is_file() or target.is_symlink() or sha256(target.read_bytes()) != row["sha256"]: _fail("inventory artifact hash/path drift")
        declared[path]=row["sha256"]
    actual={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and not p.is_symlink() and p.relative_to(root).as_posix() != "state/artifact_inventory.json"}
    if actual != set(declared): _fail("inventory missing or unexpected artifact")
    required={"state/command_inventory.json","state/threshold_manifest.json","state/threshold_freeze.json"}|{"raw/windows/"+w+".json" for w in WINDOW_IDS}
    if not required <= actual: _fail("required lifecycle inventory incomplete")
    canonical=sha256(canonical_bytes(rows)); return {"artifact_count":len(actual),"inventory_sha256":canonical}

def derive_raw_controls(records: list[Mapping[str, object]]) -> dict[str, object]:
    """Derive healthy controls only from hash-validated command stdout."""
    def rows(name: str) -> list[Mapping[str, object]]: return [r for r in records if r.get("command_name") == name]
    required=("qdisc","filters","r2_tx","r3_rx","r2_speed","r3_speed","processes","namespaces","cleanup")
    if any(not rows(name) for name in required) or any(r.get("return_code") != 0 or r.get("timed_out") or r.get("interrupted") for r in records): _fail("missing or failed raw control command")
    for row in rows("qdisc"):
        try: value=json.loads(str(row["stdout"]))
        except json.JSONDecodeError: _fail("malformed qdisc output")
        if not isinstance(value,list) or len(value)!=1 or value[0].get("kind")!="noqueue" or value[0].get("handle")!="0:": _fail("qdisc drift or unexpected child")
    for row in rows("filters"):
        try: value=json.loads(str(row["stdout"]))
        except json.JSONDecodeError: _fail("malformed filter output")
        if value != []: _fail("unexpected filter or police state")
    def number(row: Mapping[str,object]) -> int:
        try: value=int(str(row["stdout"]).strip())
        except ValueError: _fail("malformed counter/speed output")
        if value < 0: _fail("negative counter/speed output")
        return value
    for name in ("r2_tx","r3_rx"):
        values=[number(r) for r in rows(name)]
        if any(b<a for a,b in zip(values,values[1:])): _fail("counter reset or cross-window substitution")
    speeds=[number(r) for r in rows("r2_speed")+rows("r3_speed")]
    if not speeds or any(v<=0 for v in speeds) or len(set(speeds))!=1: _fail("interface speed drift or mismatch")
    for name in ("processes","namespaces"):
        text="\n".join(str(r["stdout"]) for r in rows(name)).lower()
        if "clab-x6" in text or "x6r1" in text or "iperf3" in text: _fail("residual owned runtime resource")
    cleanup=rows("cleanup")[-1]
    if any(int(r["started_monotonic_ns"]) < int(cleanup["completed_monotonic_ns"]) for r in rows("qdisc")[-1:]+rows("filters")[-1:]+rows("processes")[-1:]+rows("namespaces")[-1:]): _fail("final observation precedes cleanup")
    return {"qdisc_filter_state":"STRUCTURAL_ZERO_NOQUEUE","counter_continuity":True,"speed_mbps":speeds[0],"cleanup_valid":True,"final_drift_absent":True}

def derive_checkpoint_a_terminal(root: Path, *, run_id: str, authorization_id: str) -> dict[str, object]:
    """Derive only Checkpoint-A evidence status; it can never qualify."""
    try:
        lifecycle=verify_thirty_window_artifacts(root,run_id=run_id,authorization_id=authorization_id)
        inventory=verify_artifact_inventory(root)
        controls=derive_raw_controls(verify_command_inventory(root,run_id=run_id,authorization_id=authorization_id))
    except X6R135Error as error:
        status="CLEANUP_FAILED" if "cleanup" in str(error).lower() else "VERIFICATION_FAILED"
        return {"terminal_status":status,"detail":str(error),"qualified":False,"checkpoint_b_required":True}
    return {"terminal_status":"PROSPECTIVE_COMPLETE_CHECKPOINT_B_REQUIRED","detail":"authorization ledger and distinct-process replay remain required","qualified":False,"checkpoint_b_required":True,"lifecycle":lifecycle,"inventory":inventory,"controls":controls}

def verify_b1_artifacts(root: Path, *, run_id: str, output_root: str, identity: Mapping[str,object]) -> dict[str,object]:
    root=Path(root); auth=_read(root,"state/authorization.json")
    b1.validate(auth,identity=identity,output_root=output_root,now_ns=int(auth.get("issued_ns",0)))
    ledger=_read(root,"state/authorization_ledger.json"); b1.verify_ledger(ledger,authorization=auth,run_id=run_id,output_root=output_root,identity=identity)
    transitions=[_read(root,"state/transition-%03d.json"%i) for i in range(1,6)]
    records=verify_command_inventory(root,run_id=run_id,authorization_id=str(auth["authorization_id"]))
    first=min([int(r["started_monotonic_ns"]) for r in records] or [10**18])
    b1.verify_transitions(transitions,run_id=run_id,authorization=auth,first_action_ns=first)
    verify_artifact_inventory(root)
    return {"authorization_id":auth["authorization_id"],"b1_valid":True}

def derive_b1_terminal(root: Path, *, run_id: str, output_root: str, identity: Mapping[str,object]) -> dict[str,object]:
    try: result=verify_b1_artifacts(root,run_id=run_id,output_root=output_root,identity=identity)
    except X6R135Error as error: return {"terminal_status":"VERIFICATION_FAILED","detail":str(error),"qualified":False}
    return {"terminal_status":"PROSPECTIVE_COMPLETE_RECOVERY_REPLAY_REQUIRED","qualified":False,"b1":result}

def verify_b2_artifacts(root: Path, *, run_id: str, authorization_id: str) -> dict[str,object]:
    root=Path(root); journal=_read(root,"state/action_journal.json"); recovery=_read(root,"state/recovery.json")
    if journal.get("run_id")!=run_id or journal.get("authorization_id")!=authorization_id or recovery.get("run_id")!=run_id or recovery.get("authorization_id")!=authorization_id: _fail("cross-run recovery identity")
    original,replayed=recovery.get("original_pid"),recovery.get("recovery_pid")
    if original != journal.get("original_pid") or not isinstance(original,int) or not isinstance(replayed,int) or original<=0 or replayed<=0 or original==replayed: _fail("forged or same-process recovery PID")
    first,last=recovery.get("recovery_first_order"),recovery.get("recovery_last_order")
    if not isinstance(first,int) or not isinstance(last,int) or first<=0 or last<first or not isinstance(recovery.get("replay_count"),int) or recovery["replay_count"]<=0:
        _fail("recovery ordering metadata malformed")
    rows=verify_command_inventory(root,run_id=run_id,authorization_id=authorization_id)
    span=[row for row in rows if first <= int(row["order"]) <= last]
    expected=("processes","namespaces","qdisc","filters","cleanup","processes","namespaces","qdisc","filters")
    if len(span)!=len(expected) or tuple(str(row["command_name"]) for row in span)!=expected or any(row.get("phase")!="recovery" or row.get("parent_action_id")!="recovery" for row in span):
        _fail("recovery command ordering or identity drift")
    cleanup=span[4]
    if any(int(row["started_monotonic_ns"]) < int(cleanup["completed_monotonic_ns"]) for row in span[5:]):
        _fail("recovery final observation precedes cleanup")
    if cleanup.get("return_code") != 0 or cleanup.get("timed_out") or cleanup.get("interrupted"):
        _fail("recovery cleanup command failed")
    if any(row.get("return_code") != 0 or row.get("timed_out") or row.get("interrupted") for row in span):
        _fail("recovery command evidence is incomplete or failed")
    controls=derive_raw_controls(rows)
    inventory=verify_artifact_inventory(root)
    required={"state/action_journal.json","state/recovery.json","state/artifact_inventory.json"}
    # The inventory verifier deliberately excludes its own file; all other B2
    # artifacts must be present and byte-hash-bound.
    declared={row["path"] for row in _read(root,"state/artifact_inventory.json")["artifacts"]}
    if not {"state/action_journal.json","state/recovery.json"} <= declared:
        _fail("recovery artifact absent from rebuilt inventory")
    return {"distinct_process":True,"replay_count":recovery["replay_count"],"controls":controls,"inventory":inventory}

def derive_final_source_contract_terminal(root: Path, *, run_id: str, output_root: str, identity: Mapping[str,object]) -> dict[str,object]:
    b1_result=derive_b1_terminal(root,run_id=run_id,output_root=output_root,identity=identity)
    if b1_result["terminal_status"]!="PROSPECTIVE_COMPLETE_RECOVERY_REPLAY_REQUIRED": return b1_result
    try: b2=verify_b2_artifacts(root,run_id=run_id,authorization_id=str(b1_result["b1"]["authorization_id"]))
    except X6R135Error as error: return {"terminal_status":"CLEANUP_FAILED" if "cleanup" in str(error).lower() else "VERIFICATION_FAILED","detail":str(error),"qualified":False}
    return {"terminal_status":"R1.3.5_SOURCE_CONTRACT_COMPLETE_FOR_AUTHORIZATION_REVIEW","qualified":False,"b2":b2}


def verify_materialized_attempt(run_root: Path, *, repository_root: Path) -> dict[str, object]:
    """Derive only a terminal result; never trust a runner's qualification flag."""
    root = Path(run_root)
    auth = _read(root, "state/authorization.json")
    required_auth = {"schema_version", "authorization_id", "scope", "maximum_attempts", "source_identity", "bindings", "mutation_prohibited", "runtime_enabled", "authorization_sha256"}
    if set(auth) != required_auth or auth.get("schema_version") != 1 or auth.get("scope") != "BASELINE_ONLY_QUALIFICATION" or auth.get("maximum_attempts") != 1 or auth.get("mutation_prohibited") is not True or auth.get("runtime_enabled") is not True or not isinstance(auth.get("authorization_id"), str): _fail("authorization schema/scope drift")
    unsigned = dict(auth); digest = unsigned.pop("authorization_sha256")
    if not isinstance(digest, str) or digest != sha256(canonical_bytes(unsigned)): _fail("authorization hash drift")
    actual = derive_source_identity(repository_root)
    if auth.get("source_identity") != actual: _fail("authorization source identity differs from independently derived identity")
    provenance = _read(root, "state/provenance.json")
    required_provenance = {"kernel", "kernel_config", "module", "python", "ip", "tc", "ethtool", "ping", "iperf3", "docker", "containerlab", "git", "image"}
    if provenance.get("release_id") != RELEASE_ID or provenance.get("identity") != actual or provenance.get("source_test_only") is not False or set(provenance.get("command_records", {})) != required_provenance:
        _fail("full independently collected provenance is missing or synthetic")
    ledger = _read(root, "state/authorization_ledger.json")
    journal = _read(root, "state/action_journal.json")
    if ledger.get("authorization_id") != auth["authorization_id"] or ledger.get("authorization_sha256") != digest or ledger.get("state") != "CONSUMED" or not isinstance(ledger.get("consumed_monotonic_ns"), int): _fail("authorization ledger is invalid")
    if journal.get("authorization_id") != auth["authorization_id"] or journal.get("state") != "CONSUMED_BEFORE_STATEFUL_ACTION" or journal.get("run_id") != ledger.get("run_id"): _fail("journal/ledger ordering identity drift")
    rows = verify_command_inventory(root, run_id=str(ledger["run_id"]), authorization_id=str(auth["authorization_id"]))
    if not rows or any(row["return_code"] != 0 or row["timed_out"] or row["interrupted"] for row in rows): _fail("command lifecycle has a failed or incomplete command")
    first = min(int(row["started_monotonic_ns"]) for row in rows)
    if int(ledger["consumed_monotonic_ns"]) > first: _fail("authorization was consumed after a stateful command")
    by_id = {str(row["record_id"]): row for row in rows}
    for reference in provenance["command_records"].values():
        if not isinstance(reference, Mapping) or not isinstance(reference.get("path"), str): _fail("provenance command reference malformed")
        if not any(str(row["record_id"]) in reference["path"] or str(row["command_name"]) in reference["path"] for row in rows): _fail("provenance command is absent from inventory")
    inventory = _read(root, "state/artifact_inventory.json")
    artifacts = inventory.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts: _fail("complete artifact inventory required")
    seen: set[str] = set()
    for row in artifacts:
        if not isinstance(row, Mapping) or set(row) != {"path", "sha256"} or not isinstance(row["path"], str) or not isinstance(row["sha256"], str): _fail("artifact inventory row malformed")
        relative = safe_relative(row["path"])
        if relative in seen: _fail("duplicate artifact inventory path")
        seen.add(relative); path = root / relative
        if not path.is_file() or path.is_symlink() or sha256(path.read_bytes()) != row["sha256"]: _fail("artifact inventory hash drift")
    recovery = _read(root, "state/recovery.json")
    replay = verify_recovery(root, original_pid=int(recovery.get("original_pid", 0)), recovery_pid=int(recovery.get("recovery_pid", 0)), run_id=str(ledger["run_id"]), authorization_id=str(auth["authorization_id"]))
    terminal = _read(root, "terminal/verifier_terminal.json")
    requested = terminal.get("status")
    if requested not in TERMINAL: _fail("unsupported verifier terminal")
    return {"release_id": RELEASE_ID, "authorization_valid": True, "authorization_consumed_before_commands": True, "source_identity_valid": True, "artifact_inventory_valid": True, "recovery": replay, "terminal_status": requested, "qualified": False}
