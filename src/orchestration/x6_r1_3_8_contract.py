"""Successor baseline contract; no authorization artifact or runtime side effects."""
from __future__ import annotations
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from src.orchestration.x6_r1_3_3_baseline_only_runner import WINDOW_IDS
from src.orchestration.x6_r1_3_6_production_path import HISTORICAL_VECTOR, PROHIBITIONS, SCHEDULE
from src.runtime.subprocesses import run_capture

ROOT = Path(__file__).resolve().parents[2]
PREDECESSOR = "4f62b04112f8af23ab31ab98b92e0cc54e42b5cb"
RELEASE = "X6_R1_3_8_BASELINE_PRODUCTION_LIFECYCLE_CORRECTION"
TOPOLOGY = "labs/topologies/x6_r1_packet_loss_r0_5/topology.clab.yml"
CONTEXT = "labs/topologies/x6_r1_packet_loss/runtime_context_v1.json"
BOOTSTRAP = "labs/topologies/x6_r1_packet_loss_r0_5/bootstrap_context_v1.json"
IMAGE = "ind-linux:0.1"
NODES = tuple("clab-x6r1-" + n for n in ("hosta", "r1", "r2", "r3", "hostb"))

class Invalid(ValueError):
    pass

def require(condition, message):
    if not condition:
        raise Invalid(message)

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def load(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    require(raw == canonical(value), "noncanonical or duplicate JSON members")
    return value

def canonical_location(value):
    path = Path(value)
    require(path.is_absolute(), "absolute output location required")
    require(str(path) == str(path.resolve()), "output aliases are prohibited")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink output location")
    return path

def identity(root=ROOT):
    root = Path(root)
    def git(*args):
        row = run_capture(["git", "-C", str(root), *args], timeout_seconds=30)
        require(row.returncode == 0, "Git identity command failed: " + row.stderr)
        return row.stdout.strip()
    ancestry = run_capture(["git", "-C", str(root), "merge-base", "--is-ancestor", PREDECESSOR, "HEAD"], timeout_seconds=30)
    require(ancestry.returncode == 0, "published predecessor is not an ancestor")
    paths = sorted(set(git("ls-files").splitlines()) | {
        str(p.relative_to(root)) for pattern in ("src/orchestration/x6_r1_3_8*.py", "src/expansion/x6_r1_3_8*.py", "plans/expansion/X6_R1_3_8*.json", "tests/fixtures/x6_r1_3_8_external_stub.py") for p in root.glob(pattern)
    })
    require(all((root / p).is_file() and not (root / p).is_symlink() for p in paths), "source missing or unsafe")
    return {"git_commit": git("rev-parse", "HEAD"), "git_tree": git("rev-parse", "HEAD^{tree}"), "files": {p: digest((root / p).read_bytes()) for p in paths}}

def frozen_contract():
    context = json.loads((ROOT / CONTEXT).read_text())
    return {"scope": "BASELINE_ONLY_QUALIFICATION", "maximum_attempts": 1, "historical_authorization": copy.deepcopy(HISTORICAL_VECTOR),
            "schedule": copy.deepcopy(SCHEDULE), "traffic": context["traffic"], "topology": TOPOLOGY, "image": IMAGE,
            "prohibitions": copy.deepcopy(PROHIBITIONS), "construction": list(WINDOW_IDS[:10]),
            "threshold_builder": "src.collection.x6_r0_3_pre_runtime_validation.build_threshold_manifest"}

def validate_authorization(value, *, root, run_id, source_identity, now_ns, simulation=False):
    fields = {"schema_version", "release_id", "authorization_id", "scope", "source_identity", "predecessor", "output_root", "run_id", "issued_ns", "expires_ns", "boot_id", "source_test_only", "contract", "runtime_image", "authorization_sha256"}
    require(isinstance(value, dict) and set(value) == fields, "authorization schema")
    require(value["schema_version"] == 2 and value["release_id"] == "X6_R1_4_BASELINE_ONLY_RUNTIME_AUTHORIZATION", "authorization release")
    require(isinstance(value["authorization_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", value["authorization_id"]), "authorization ID")
    require(type(value["source_test_only"]) is bool and value["source_test_only"] == simulation, "synthetic authorization is not production authority")
    require(value["source_identity"] == source_identity and value["predecessor"] == PREDECESSOR, "authorization source identity")
    require(value["scope"] == "BASELINE_ONLY_QUALIFICATION" and canonical(value["contract"]) == canonical(frozen_contract()), "authorization contract")
    require(value["run_id"] == run_id and isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", run_id), "run identity")
    require(canonical_location(value["output_root"]) == canonical_location(str(root)), "actual output binding")
    require(type(value["issued_ns"]) is int and type(value["expires_ns"]) is int and 0 <= value["issued_ns"] <= now_ns <= value["expires_ns"], "authorization validity")
    require(value["boot_id"] == Path("/proc/sys/kernel/random/boot_id").read_text().strip(), "authorization clock epoch")
    image = value["runtime_image"]
    require(isinstance(image, dict) and set(image) == {"Id", "RepoDigests"} and isinstance(image["Id"], str) and re.fullmatch(r"sha256:[0-9a-f]{64}", image["Id"]) and isinstance(image["RepoDigests"], list) and all(isinstance(v, str) for v in image["RepoDigests"]), "runtime image identity")
    unsigned = dict(value); expected = unsigned.pop("authorization_sha256")
    require(expected == digest(canonical(unsigned)), "authorization digest")
    return value
