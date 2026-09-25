"""Prospective one-attempt contract for the append-only future-F1 successor."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from src.collection.x6_r0_3_pre_runtime_validation import validate_threshold_manifest
from src.runtime.subprocesses import run_capture

ROOT = Path(__file__).resolve().parents[2]
PREDECESSOR = "287809ecc74bc3962de67fb903058fc6db09e899"
RELEASE = "X6_R1_5_1_POSTMORTEM_CORRECTION_SUCCESSOR"
AUTHORIZATION_RELEASE = "X6_R1_5_1_POSTMORTEM_CORRECTION_RUNTIME_AUTHORIZATION"
TRUST_MODEL = "LOCAL_OPERATOR_ACCOUNT_V1"
TOPOLOGY = "labs/topologies/x6_r1_packet_loss_r0_5/topology.clab.yml"
CONTEXT = "labs/topologies/x6_r1_packet_loss/runtime_context_v1.json"
BOOTSTRAP = "labs/topologies/x6_r1_packet_loss_r0_5/bootstrap_context_v1.json"
IMAGE = "ind-linux:0.1"
NODES = tuple("clab-x6r1-" + n for n in ("hosta", "r1", "r2", "r3", "hostb"))
WINDOW_IDS = tuple(f"B{i:02d}" for i in range(1, 11)) + tuple(f"F{i:02d}" for i in range(1, 4)) + tuple(f"R{i:02d}" for i in range(1, 4))
PHASE_BY_WINDOW = {**{name: "baseline" for name in WINDOW_IDS[:10]}, **{name: "fault" for name in WINDOW_IDS[10:13]}, **{name: "restored" for name in WINDOW_IDS[13:]}}
HISTORICAL_VECTOR = {name: False for name in ("containerlab", "measurement", "f1_revalidation", "f2", "f3", "f4", "dataset", "ml_hybrid", "api", "p9_r2")}
FREEZE_RECORD = "plans/expansion/X6_PROSPECTIVE_SUCCESSOR_PARAMETER_THRESHOLD_FREEZE_V1.json"
FREEZE_RECORD_SHA256 = "635d62272c593a6ddf6de490a96e664aa94ce3ec2ea4bba5e44a4396cfb18402"
MANIFEST_EMBEDDED_SHA256 = "0db20fccbb22f7bcde7bc5d7be0d3fd8923e32d663d59297c178dd300ce7c301"
ACCEPTED_IMAGE = {"Id": "sha256:66392daabae6054416fba5043f312bfc464bcc18246956867870e4953847ff5c", "RepoDigests": []}
SCHEDULE = {"readiness_seconds": 5, "warmup_seconds": 5, "window_duration_seconds": 20, "window_separation_seconds": 5, "cooldown_seconds": 5, "maximum_startup_skew_seconds": "0.250000", "baseline_windows": list(WINDOW_IDS[:10]), "fault_windows": list(WINDOW_IDS[10:13]), "restoration_windows": list(WINDOW_IDS[13:])}
PROHIBITIONS = ["threshold_rebuild", "threshold_retune", "selective_window_retry", "fault_or_restoration_calibration", "consumed_pilot_input", "F2", "F3", "F4", "dataset", "model", "metrics", "api", "p9_r2", "generalized_scientific_claim"]


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


def current_boot_id():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


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
        str(p.relative_to(root))
        for pattern in ("src/orchestration/x6_r1_5_1*.py", "src/expansion/x6_r1_5_1*.py", "plans/expansion/X6_R1_5_1*.json", "tests/fixtures/x6_r1_5_1_external_stub.py")
        for p in root.glob(pattern)
    })
    require(all((root / p).is_file() and not (root / p).is_symlink() for p in paths), "source missing or unsafe")
    return {"git_commit": git("rev-parse", "HEAD"), "git_tree": git("rev-parse", "HEAD^{tree}"), "files": {p: digest((root / p).read_bytes()) for p in paths}}


def accepted_manifest(root=ROOT):
    path = Path(root) / FREEZE_RECORD
    raw = path.read_bytes()
    require(digest(raw) == FREEZE_RECORD_SHA256, "accepted freeze record drift")
    record = json.loads(raw)
    require(record.get("record_id") == "X6_PROSPECTIVE_SUCCESSOR_PARAMETER_THRESHOLD_FREEZE_V1", "accepted freeze identity")
    manifest = record.get("frozen_threshold_manifest")
    require(isinstance(manifest, dict) and manifest.get("sha256") == MANIFEST_EMBEDDED_SHA256, "accepted manifest identity")
    require(manifest.get("topology_context_id") == "X6_TOP_01_CONTROLLED_PERFORMANCE_PATH" and manifest.get("traffic_context_id") == "X6_R1_BASELINE_ONLY_QUALIFICATION", "accepted manifest context")
    validate_threshold_manifest(manifest, repository_root=Path(root))
    return manifest


def frozen_contract():
    context = json.loads((ROOT / CONTEXT).read_text())
    manifest = accepted_manifest()
    return {
        "scope": "F1_PACKET_LOSS_SINGLE_FAULT",
        "maximum_attempts": 1,
        "historical_authorization": dict(HISTORICAL_VECTOR),
        "schedule": dict(SCHEDULE),
        "traffic": context["traffic"],
        "qdisc": context["qdisc"],
        "effectiveness": context["effectiveness"],
        "rule": context["rule"],
        "topology": TOPOLOGY,
        "image": IMAGE,
        "accepted_runtime_image": dict(ACCEPTED_IMAGE),
        "prohibitions": list(PROHIBITIONS),
        "threshold": {"record": FREEZE_RECORD, "record_sha256": FREEZE_RECORD_SHA256, "embedded_sha256": MANIFEST_EMBEDDED_SHA256, "canonical_sha256": digest(canonical(manifest)), "runtime_baseline_role": "VALIDATION_ONLY_NEVER_CALIBRATION"},
    }


def validate_authorization_integrity(value, *, root, run_id, source_identity, simulation=False):
    fields = {"schema_version", "record_kind", "release_id", "trust_model", "authorization_id", "scope", "source_identity", "predecessor", "output_root", "run_id", "issued_ns", "expires_ns", "boot_id", "source_test_only", "contract", "runtime_image", "authorization_sha256"}
    require(isinstance(value, dict) and set(value) == fields, "authorization schema")
    require(value["schema_version"] == 1 and value["record_kind"] == "CONCRETE_AUTHORIZATION" and value["release_id"] == AUTHORIZATION_RELEASE, "authorization release")
    require(value["trust_model"] == TRUST_MODEL, "authorization trust model")
    require(isinstance(value["authorization_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", value["authorization_id"]), "authorization ID")
    require(type(value["source_test_only"]) is bool and value["source_test_only"] == simulation, "synthetic authorization is not production authority")
    require(value["source_identity"] == source_identity and value["predecessor"] == PREDECESSOR, "authorization source identity")
    require(value["scope"] == "F1_PACKET_LOSS_SINGLE_FAULT" and canonical(value["contract"]) == canonical(frozen_contract()), "authorization contract")
    require(value["run_id"] == run_id and isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", run_id), "run identity")
    require(canonical_location(value["output_root"]) == canonical_location(str(root)), "actual output binding")
    require(type(value["issued_ns"]) is int and type(value["expires_ns"]) is int and 0 <= value["issued_ns"] <= value["expires_ns"], "authorization interval")
    require(isinstance(value["boot_id"], str) and bool(value["boot_id"]), "authorization clock epoch")
    image = value["runtime_image"]
    require(isinstance(image, dict) and set(image) == {"Id", "RepoDigests"} and isinstance(image["Id"], str) and re.fullmatch(r"sha256:[0-9a-f]{64}", image["Id"]) and isinstance(image["RepoDigests"], list) and all(isinstance(v, str) for v in image["RepoDigests"]), "runtime image identity")
    require(image == ACCEPTED_IMAGE, "runtime image outside accepted freeze scope")
    unsigned = dict(value)
    expected = unsigned.pop("authorization_sha256")
    require(expected == digest(canonical(unsigned)), "authorization digest")
    return value


def validate_new_attempt(value, *, root, run_id, source_identity, observation, simulation=False):
    validate_authorization_integrity(value, root=root, run_id=run_id, source_identity=source_identity, simulation=simulation)
    require(set(observation) == {"monotonic_ns", "utc", "boot_id"}, "live admission observation")
    require(value["issued_ns"] <= observation["monotonic_ns"] <= value["expires_ns"], "authorization validity")
    require(value["boot_id"] == observation["boot_id"] == current_boot_id(), "authorization live clock epoch")
    return value


def _point(value, message):
    require(isinstance(value, dict) and set(value) == {"monotonic_ns", "utc", "boot_id"}, message)
    require(type(value["monotonic_ns"]) is int and value["monotonic_ns"] >= 0, message)
    require(isinstance(value["utc"], str) and value["utc"].endswith("Z"), message)
    require(isinstance(value["boot_id"], str) and bool(value["boot_id"]), message)
    return value


def validate_reservation_ledger(value, ledger, *, root, run_id, source_identity, simulation=False):
    """Validate every durable reservation state without using the current boot.

    RESERVED_UNDECIDED grants no authority.  ADMITTED is the durable positive
    authorization commitment even when later consumption persistence is
    incomplete.  CONSUMED adds the durable consumption timestamp.  Historical
    monotonic observations are compared only inside the authorization's boot.
    """
    validate_authorization_integrity(value, root=root, run_id=run_id, source_identity=source_identity, simulation=simulation)
    require(isinstance(ledger, dict), "reservation ledger schema")
    require(ledger["authorization"] == value and ledger["authorization_sha256"] == value["authorization_sha256"], "commit authorization identity")
    require(ledger["authorization_id"] == value["authorization_id"] and ledger["run_id"] == run_id and ledger["output_root"] == str(canonical_location(str(root))), "commit run identity")
    process = ledger.get("process")
    require(isinstance(process, dict) and set(process) == {"pid", "start_ticks", "boot_id"}, "reservation process identity")
    require(type(process["pid"]) is int and process["pid"] > 0 and isinstance(process["start_ticks"], str) and process["start_ticks"] and process["boot_id"] == value["boot_id"], "reservation process binding")
    state = ledger.get("state")
    require(state in {"RESERVED_UNDECIDED", "REJECTED", "ADMITTED", "CONSUMED"}, "reservation state")
    base = {"authorization_sha256", "authorization_id", "run_id", "output_root", "process", "reservation", "state", "authorization"}
    expected = {
        "RESERVED_UNDECIDED": base,
        "REJECTED": base | {"admission", "rejection"},
        "ADMITTED": base | {"admission"} | ({"root_identity"} if "root_identity" in ledger else set()),
        "CONSUMED": base | {"admission", "root_identity", "consumed"},
    }[state]
    require(set(ledger) == expected, "reservation ledger fields")
    reservation = ledger.get("reservation")
    require(isinstance(reservation, dict) and set(reservation) == ({"started"} if state == "RESERVED_UNDECIDED" else {"started", "durable_observed"}), "reservation evidence")
    started = _point(reservation["started"], "reservation timestamp schema")
    require(started["boot_id"] == value["boot_id"], "reservation boot identity")
    if state == "RESERVED_UNDECIDED":
        return state
    durable = _point(reservation["durable_observed"], "reservation timestamp schema")
    require(durable["boot_id"] == value["boot_id"], "reservation boot identity")
    require(started["monotonic_ns"] <= durable["monotonic_ns"], "reservation timing order")
    admission = ledger.get("admission")
    require(isinstance(admission, dict) and set(admission) == {"decision", "observed_after_reservation"}, "admission decision evidence")
    decision = admission["observed_after_reservation"]
    require(decision == durable, "admission must use post-reservation observation")
    require(decision["boot_id"] == value["boot_id"], "committed authorization boot identity")
    if state == "REJECTED":
        require(admission["decision"] == "REJECTED_BEFORE_LIFECYCLE", "rejected reservation decision")
        rejection = ledger["rejection"]
        require(isinstance(rejection, dict) and set(rejection) == {"type", "detail", "recorded"}, "rejection evidence")
        require(isinstance(rejection["type"], str) and rejection["type"] and isinstance(rejection["detail"], str) and rejection["detail"], "rejection classification")
        recorded = _point(rejection["recorded"], "rejection timestamp schema")
        require(recorded["boot_id"] == value["boot_id"] and recorded["monotonic_ns"] >= decision["monotonic_ns"], "rejection timing/boot")
        return state
    require(admission["decision"] == "AUTHORIZED_LIFECYCLE_ENTRY", "lifecycle entry not authorized")
    require(value["issued_ns"] <= decision["monotonic_ns"] <= value["expires_ns"], "committed authorization validity")
    if "root_identity" in ledger:
        root_identity = ledger["root_identity"]
        require(isinstance(root_identity, dict) and set(root_identity) == {"device", "inode"} and all(type(root_identity[k]) is int and root_identity[k] >= 0 for k in root_identity), "run root identity")
    if state == "CONSUMED":
        consumed = _point(ledger["consumed"], "consumption timestamp schema")
        require(consumed["boot_id"] == value["boot_id"], "consumption boot identity")
        require(decision["monotonic_ns"] <= consumed["monotonic_ns"], "authorization commitment after consumption")
    return state


def validate_committed_attempt(value, ledger, *, root, run_id, source_identity, simulation=False):
    """Validate a completely consumed attempt from its original durable facts."""
    state = validate_reservation_ledger(value, ledger, root=root, run_id=run_id, source_identity=source_identity, simulation=simulation)
    require(state == "CONSUMED", "attempt is not durably consumed")
    return value


def validate_partial_attempt(value, ledger, *, root, run_id, source_identity, simulation=False):
    """Validate and classify a spent attempt whose persistence is incomplete.

    This function is read-only.  In particular it never creates a run root or
    fills in a missing run-local record after an interruption.
    """
    root = canonical_location(str(root))
    state = validate_reservation_ledger(value, ledger, root=root, run_id=run_id, source_identity=source_identity, simulation=simulation)
    exists = root.exists()
    require(not exists or (root.is_dir() and not root.is_symlink()), "unsafe partial run root")
    if state in {"RESERVED_UNDECIDED", "REJECTED"}:
        require(not exists, "run root exists before authorization commitment")
        return {
            "status": "RESERVATION_REJECTED" if state == "REJECTED" else "INTERRUPTED_BEFORE_AUTHORIZATION_COMMIT",
            "detail": "exclusive reservation is spent; lifecycle entry was never authorized",
            "ledger_state": state,
            "authorization_committed": False,
            "consumption_complete": False,
        }
    if state == "ADMITTED" and not exists:
        return {
            "status": "AUTHORIZATION_COMMITTED_CONSUMPTION_INCOMPLETE",
            "detail": "authorization commitment is durable; consumption persistence is incomplete; attempt is permanently spent",
            "ledger_state": state,
            "authorization_committed": True,
            "consumption_complete": False,
        }
    require(exists, "consumed attempt run root is absent")
    entries = list(root.rglob("*"))
    require(not any(p.is_symlink() for p in entries), "symlink in partial run root")
    files = {p.relative_to(root).as_posix() for p in entries if p.is_file()}
    root_identity = ledger.get("root_identity")
    if root_identity is None:
        require(not files, "run artifacts exist before root identity persistence")
    else:
        require(root_identity == {"device": root.stat().st_dev, "inode": root.stat().st_ino}, "run directory replaced")
    auth_path = root / "state/authorization.json"
    if auth_path.exists():
        require(root_identity is not None and load(auth_path) == value, "authorization copy contradiction")
    if state == "ADMITTED":
        require(not (root / "state/lifecycle.json").exists(), "lifecycle record exists before complete consumption")
        require(not (root / "state/consumption.json").exists(), "consumption copy contradicts admitted state")
        require(files <= {"state/authorization.json"}, "artifacts exist before complete consumption")
        return {
            "status": "AUTHORIZATION_COMMITTED_CONSUMPTION_INCOMPLETE",
            "detail": "authorization commitment is durable; consumption persistence is incomplete; attempt is permanently spent",
            "ledger_state": state,
            "authorization_committed": True,
            "consumption_complete": False,
        }
    require(root_identity is not None and auth_path.exists(), "consumed ledger lacks bound authorization copy")
    consumption_path = root / "state/consumption.json"
    if consumption_path.exists():
        require(load(consumption_path) == ledger, "consumption copy contradiction")
        lifecycle_path = root / "state/lifecycle.json"
        if lifecycle_path.exists():
            lifecycle = load(lifecycle_path)
            require(isinstance(lifecycle, dict) and set(lifecycle) == {"state", "process", "at"} and lifecycle["state"] == "CONSUMED" and lifecycle["process"] == ledger["process"], "lifecycle entry contradiction")
            lifecycle_at = _point(lifecycle["at"], "lifecycle timestamp schema")
            require(lifecycle_at["boot_id"] == value["boot_id"] and lifecycle_at["monotonic_ns"] >= ledger["consumed"]["monotonic_ns"], "lifecycle timing/boot")
        return None
    require(not (root / "state/lifecycle.json").exists(), "lifecycle record exists before consumption copy persistence")
    require(files <= {"state/authorization.json"}, "artifacts exist before consumption copy persistence")
    return {
        "status": "AUTHORIZATION_CONSUMED_RECORD_INCOMPLETE",
        "detail": "authorization and consumption are durable in the reservation ledger; run-local consumption persistence is incomplete; attempt is permanently spent",
        "ledger_state": state,
        "authorization_committed": True,
        "consumption_complete": False,
    }
