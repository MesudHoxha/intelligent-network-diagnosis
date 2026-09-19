"""Append-only R1.4.1 correction gate with R1.4 in its published context."""
from __future__ import annotations
import io
import json
import sys
import tarfile
from src.expansion.x6_r1_3_7_gate import FROZEN_DIAGNOSTIC_NODES, _detached_snapshot
from src.orchestration.x6_r1_4_1_contract import ROOT, PREDECESSOR, RELEASE, HISTORICAL_VECTOR, digest, require
from src.runtime.subprocesses import run_capture

PLAN = "plans/expansion/X6_R1_4_1_AUTHORIZATION_COMMITMENT_AND_BOOT_RECOVERY_CORRECTION_V1.json"


def verify_source(*, historical=True):
    plan = json.loads((ROOT / PLAN).read_text())
    require(plan["release_id"] == RELEASE and plan["predecessor"] == PREDECESSOR, "successor boundary")
    require(plan["historical_authorization"] == HISTORICAL_VECTOR and all(v is False for v in plan["historical_authorization"].values()), "historical vector")
    require(plan["runtime_authorization_artifact"] == "ABSENT" and plan["authorization_template"] == "NON_EXECUTABLE", "source correction cannot authorize runtime")
    require(plan["diagnostic_nodes"] == list(FROZEN_DIAGNOSTIC_NODES), "diagnostic partition widened")
    for row in plan["source_bindings"]:
        path = ROOT / row["path"]
        require(path.is_file() and not path.is_symlink() and digest(path.read_bytes()) == row["sha256"], "successor binding drift: " + row["path"])
    listing = run_capture(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", PREDECESSOR], timeout_seconds=30)
    require(listing.returncode == 0, "predecessor inventory unavailable: " + listing.stderr)
    import subprocess
    try:
        raw = subprocess.check_output(["git", "-C", str(ROOT), "archive", PREDECESSOR], timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise ValueError("predecessor archive unavailable") from error
    with tarfile.open(fileobj=io.BytesIO(raw)) as tree:
        for member in tree.getmembers():
            if member.isfile():
                require((ROOT / member.name).read_bytes() == tree.extractfile(member).read(), "protected historical file changed: " + member.name)
    if historical:
        with _detached_snapshot(ROOT, PREDECESSOR, receipts=[]) as snapshot:
            result = run_capture([sys.executable, "-c", "from src.expansion.x6_r1_4_gate import verify_source; verify_source()"], cwd=snapshot, timeout_seconds=1800)
            require(result.returncode == 0, "historical R1.4 gate failed in exact snapshot: " + result.stderr)
    return {"release_id": RELEASE, "source_only": True, "authorization": "0/10_FALSE", "historical_files_preserved": len(listing.stdout.splitlines()), "diagnostics": 6, "runtime_authorization": "ABSENT"}


if __name__ == "__main__":
    print(json.dumps(verify_source(), sort_keys=True))
