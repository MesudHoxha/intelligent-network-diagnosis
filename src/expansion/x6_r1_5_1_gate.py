"""Append-only source gate for the R1.5.1 postmortem successor."""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile

from src.expansion.x6_r1_3_7_gate import FROZEN_DIAGNOSTIC_NODES, _detached_snapshot
from src.orchestration.x6_r1_5_1_contract import (
    FREEZE_RECORD_SHA256,
    HISTORICAL_VECTOR,
    PREDECESSOR,
    RELEASE,
    ROOT,
    accepted_manifest,
    digest,
    require,
)
from src.runtime.subprocesses import run_capture

PLAN = "plans/expansion/X6_R1_5_1_POSTMORTEM_CORRECTION_SOURCE_ONLY_V1.json"
PROPOSAL = "plans/expansion/X6_R1_5_1_POSTMORTEM_CORRECTION_REVIEW_PROPOSAL_V1.json"
PROPOSAL_SHA256 = "c908748d102511f201f9d06e79e50022ffddd33ec4582624e2a3f5f353810f92"
PROPOSAL_HANDOFF = "docs/HANDOFF_X6_R1_5_1_POSTMORTEM_CORRECTION_REVIEW.md"
PROPOSAL_HANDOFF_SHA256 = "7bbe8a4ff85651f96c3bb758988af098c4e5cfc5606f06f2e371833416db7645"


def verify_source(*, historical: bool = True) -> dict[str, object]:
    plan = json.loads((ROOT / PLAN).read_text(encoding="utf-8"))
    require(plan["release_id"] == RELEASE and plan["predecessor"] == PREDECESSOR, "successor boundary")
    require(plan["accepted_proposal_sha256"] == PROPOSAL_SHA256, "accepted proposal binding")
    require(digest((ROOT / PROPOSAL).read_bytes()) == PROPOSAL_SHA256, "review proposal drift")
    require(plan["accepted_proposal_handoff_sha256"] == PROPOSAL_HANDOFF_SHA256, "proposal handoff binding")
    require(digest((ROOT / PROPOSAL_HANDOFF).read_bytes()) == PROPOSAL_HANDOFF_SHA256, "proposal handoff drift")
    require(plan["freeze_record_sha256"] == FREEZE_RECORD_SHA256, "freeze binding")
    accepted_manifest()
    require(plan["historical_authorization"] == HISTORICAL_VECTOR and all(v is False for v in HISTORICAL_VECTOR.values()), "historical vector")
    require(plan["runtime_authorization_artifact"] == "ABSENT", "source successor cannot authorize runtime")
    require(plan["diagnostic_nodes"] == list(FROZEN_DIAGNOSTIC_NODES), "diagnostic partition widened")
    require(plan["pre_fault_role"] == "VALIDATION_ONLY_NEVER_CALIBRATION", "pre-fault calibration prohibited")
    require(plan["fault_assessment"]["persistence"] == "COMMIT_LAST", "fault assessment persistence")
    require(plan["diagnostic_abstention"]["overall_acceptance"] is False, "abstention cannot accept")
    require(plan["numeric_semantics"]["rounding"] == "ROUND_HALF_EVEN_SIX_PLACES", "numeric semantics")
    for row in plan["source_bindings"]:
        path = ROOT / row["path"]
        require(path.is_file() and not path.is_symlink(), "successor source missing: " + row["path"])
        require(digest(path.read_bytes()) == row["sha256"], "successor binding drift: " + row["path"])
        actual_mode = "100755" if path.stat().st_mode & 0o111 else "100644"
        require(actual_mode == row["mode"], "successor mode drift: " + row["path"])
    production = (ROOT / "src/orchestration/x6_r1_5_1_production_path.py").read_text(encoding="utf-8")
    verifier = (ROOT / "src/expansion/x6_r1_5_1_materialized_verifier.py").read_text(encoding="utf-8")
    require("build_threshold_manifest" not in production + verifier, "runtime threshold rebuilding is reachable")
    listing = run_capture(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", PREDECESSOR], timeout_seconds=30)
    require(listing.returncode == 0, "predecessor inventory unavailable: " + listing.stderr)
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
            result = run_capture(
                [sys.executable, "-c", "from src.expansion.x6_r1_5_gate import verify_source; verify_source()"],
                cwd=snapshot,
                timeout_seconds=1800,
            )
            require(result.returncode == 0, "historical R1.4.1 gate failed in exact snapshot: " + result.stderr)
    return {
        "release_id": RELEASE,
        "source_only": True,
        "authorization": "0/10_FALSE",
        "runtime_authorization": "ABSENT",
        "historical_files_preserved": len(listing.stdout.splitlines()),
        "diagnostics": len(FROZEN_DIAGNOSTIC_NODES),
        "threshold_role": "IMMUTABLE_ACCEPTED_MANIFEST_CONSUMPTION",
        "fault_assessment": "COMMIT_LAST_INDEPENDENT_RECONSTRUCTION",
        "diagnostic_abstention": "RESTORATION_ALLOWED_OVERALL_ACCEPTANCE_FALSE",
    }


if __name__ == "__main__":
    print(json.dumps(verify_source(), sort_keys=True))
