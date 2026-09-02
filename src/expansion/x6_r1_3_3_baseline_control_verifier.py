"""Independent raw-control verifier for a future X6-R1.3.3 baseline run tree."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any, Mapping
from src.expansion.x6_r1_3_2_baseline_execution_provenance_correction import verify_materialized_baseline_execution_manifest
from src.orchestration.x6_r1_3_3_baseline_only_runner import RELEASE_ID, safe_relative

class X6R133VerifierError(ValueError): pass
def _fail(s: str) -> None: raise X6R133VerifierError("X6-R1.3.3: " + s)
def _sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()

def _read(root: Path, ref: Mapping[str, object]) -> object:
    if set(ref) != {"path", "sha256"} or not isinstance(ref.get("path"), str) or not isinstance(ref.get("sha256"), str): _fail("artifact reference malformed")
    p = root / safe_relative(str(ref["path"]))
    if not p.is_file() or p.is_symlink() or _sha(p.read_bytes()) != ref["sha256"]: _fail("missing, unsafe, or rehashed raw artifact")
    try: return json.loads(p.read_text())
    except json.JSONDecodeError as e: raise X6R133VerifierError("X6-R1.3.3: raw artifact is not JSON") from e

def verify_raw_controls(value: Mapping[str, Any], *, run_root: Path) -> dict[str, bool]:
    required = {"qdisc_before", "qdisc_after", "filters_before", "filters_after", "counters", "cleanup", "replay", "authorization_ledger"}
    if set(value) != required: _fail("complete raw control inventory required")
    rows = {name: _read(Path(run_root), value[name]) for name in required}
    for name in ("qdisc_before", "qdisc_after"):
        if rows[name] != {"interface": "clab-x6r1-r2:eth2", "qdisc": {"kind": "noqueue", "handle": "0:", "children": []}}: _fail("qdisc control is not exact noqueue")
    for name in ("filters_before", "filters_after"):
        if rows[name] != {"interface": "clab-x6r1-r2:eth2", "filters": []}: _fail("filter control is not empty")
    counters = rows["counters"]
    if not isinstance(counters, list) or len(counters) < 2: _fail("counter continuity inventory incomplete")
    previous = None
    for row in counters:
        if not isinstance(row, dict) or set(row) != {"interface", "monotonic_ns", "rx_packets", "tx_packets"} or row["interface"] != "clab-x6r1-r2:eth2": _fail("counter row malformed")
        now = (row["monotonic_ns"], row["rx_packets"], row["tx_packets"])
        if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in now) or previous is not None and any(a < b for a,b in zip(now, previous)): _fail("counter reset/wrap/ordering detected")
        previous = now
    if rows["cleanup"] != {"owned_processes": [], "containers": [], "namespaces": [], "temporary_resources": []}: _fail("cleanup raw evidence shows leftover owned resource")
    if rows["replay"] != {"new_process": True, "status": "IDEMPOTENT_RECOVERY_CONFIRMED"}: _fail("standalone replay evidence invalid")
    ledger = rows["authorization_ledger"]
    if not isinstance(ledger, dict) or ledger.get("state") != "CONSUMED" or not ledger.get("authorization_id") or not ledger.get("authorization_sha256"): _fail("authorization consumption evidence invalid")
    return {"qdisc_filter_state_valid": True, "counter_continuity_valid": True, "cleanup_valid": True, "replay_valid": True, "authorization_consumed": True}

def verify_future_baseline_run(value: Mapping[str, Any], *, run_root: Path, repository_root: Path, expected_source_identity: Mapping[str, object]) -> dict[str, object]:
    if set(value) != {"release_id", "execution_manifest", "raw_controls", "terminal"} or value.get("release_id") != RELEASE_ID: _fail("run envelope identity drift")
    base = verify_materialized_baseline_execution_manifest(value["execution_manifest"], repository_root=repository_root, run_root=run_root, expected_source_identity=expected_source_identity)
    controls = verify_raw_controls(value["raw_controls"], run_root=run_root)
    terminal = value["terminal"]
    if not isinstance(terminal, dict) or any(terminal.get(k) is not v for k,v in controls.items() if k != "authorization_consumed"): _fail("summary booleans are not independently derived")
    return {**base, **controls}
