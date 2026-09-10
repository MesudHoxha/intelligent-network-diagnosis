"""Append-only successor source gate, with historical gates in their own context."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from src.expansion.x6_r1_3_7_gate import FROZEN_DIAGNOSTIC_NODES, _detached_snapshot
from src.orchestration.x6_r1_3_8_contract import ROOT, PREDECESSOR, RELEASE, HISTORICAL_VECTOR, digest, require
from src.runtime.subprocesses import run_capture

PLAN = "plans/expansion/X6_R1_3_8_BASELINE_PRODUCTION_LIFECYCLE_CORRECTION_V1.json"

def verify_source(*, historical=True):
    plan = json.loads((ROOT / PLAN).read_text())
    require(plan["release_id"] == RELEASE and plan["predecessor"] == PREDECESSOR, "successor boundary")
    require(plan["historical_authorization"] == HISTORICAL_VECTOR and all(v is False for v in plan["historical_authorization"].values()), "historical vector")
    require(plan["runtime_authorization_artifact"] == "ABSENT", "source correction cannot authorize runtime")
    require(plan["diagnostic_nodes"] == list(FROZEN_DIAGNOSTIC_NODES), "diagnostic partition widened")
    for row in plan["source_bindings"]:
        path = ROOT / row["path"]
        require(path.is_file() and not path.is_symlink() and digest(path.read_bytes()) == row["sha256"], "successor binding drift: " + row["path"])
    old_paths = subprocess.check_output(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", PREDECESSOR], text=True, timeout=30).splitlines()
    # A batch Git archive avoids invoking one subprocess per historical file.
    import io, tarfile
    archive = subprocess.check_output(["git", "-C", str(ROOT), "archive", PREDECESSOR], timeout=30)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for member in tree.getmembers():
            if member.isfile():
                require((ROOT/member.name).read_bytes() == tree.extractfile(member).read(), "protected historical file changed: " + member.name)
    if historical:
        with _detached_snapshot(ROOT, PREDECESSOR, receipts=[]) as snapshot:
            result = run_capture([sys.executable, "-c", "from src.expansion.x6_r1_3_7_gate import verify_x6_r1_3_7; verify_x6_r1_3_7()"], cwd=snapshot, timeout_seconds=900)
            require(result.returncode == 0, "historical R1.3.7 gate failed in exact snapshot: " + result.stderr)
    return {"release_id": RELEASE, "source_only": True, "authorization": "0/10_FALSE", "historical_files_preserved": len(old_paths), "diagnostics": 6, "runtime_authorization": "ABSENT"}

if __name__ == "__main__":
    print(json.dumps(verify_source(), sort_keys=True))
