"""Fixed read-only predecessor validation for accounting, never admission."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import sys
import tempfile

from src.orchestration.x6_r1_5_1_contract import canonical, digest, load, require
from src.runtime.subprocesses import run_capture
from src.orchestration.x6_r1_5_3_epoch import normalized_kernel

ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_COMMIT = "47b809efa55c9485b37cb73eaf6762d6026a96a6"
SUPPORTED_TREE = "684d9098fba178591852c28bdb5638cad1dee86a"
SUPPORTED_CONTRACT = "2e6ea92cb329088c981f03fdebb4a206def53eb8a19321458e531b9641e0e9a3"
SUPPORTED_INVENTORY = "c1ff4d276705936111b12c918cad7a387d44369859b828ca13c7e28a5dba2c2c"


def validate_original_source(source):
    """Verify a fixed Git tree and all dependencies, never a caller-selected import."""
    required = {"git_commit", "git_tree", "implementation_root", "executable_inventory",
                "executable_inventory_sha256", "clean"}
    require(isinstance(source, dict) and set(source) == required, "historical source schema")
    require(source["git_commit"] == SUPPORTED_COMMIT and source["git_tree"] == SUPPORTED_TREE
            and source["clean"] is True, "unsupported historical source")
    location = source["implementation_root"]
    require(isinstance(location, str) and Path(location).is_absolute()
            and str(Path(location)) == location and ".." not in Path(location).parts,
            "historical implementation location")

    def git(*args):
        result = run_capture(["git", *args], cwd=ROOT, timeout_seconds=30)
        result.check_returncode()
        return result.stdout

    require(git("rev-parse", SUPPORTED_COMMIT + "^{tree}").strip() == SUPPORTED_TREE,
            "historical Git tree substitution")
    inventory = []
    for entry in git("ls-tree", "-rz", "--full-tree", SUPPORTED_COMMIT).split("\0"):
        if not entry:
            continue
        metadata, relative = entry.split("\t", 1)
        mode, kind, object_id = metadata.split()
        require(kind == "blob" and mode in {"100644", "100755"}, "unsupported historical tree entry")
        path = ROOT / relative
        require(path.is_file() and not path.is_symlink(), "historical validator dependency absent")
        data = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(blob == object_id and ("100755" if path.stat().st_mode & 0o111 else "100644") == mode,
                "historical validator/dependency bytes or mode changed")
        historical_path = Path(location) / relative
        require(historical_path.is_file() and not historical_path.is_symlink()
                and historical_path.read_bytes() == data
                and ("100755" if historical_path.stat().st_mode & 0o111 else "100644") == mode,
                "recorded historical implementation bytes or mode changed")
        inventory.append({"path": relative, "sha256": digest(data), "mode": mode})
    inventory.sort(key=lambda row: row["path"])
    require(source["executable_inventory"] == inventory and
            source["executable_inventory_sha256"] == digest(canonical(inventory)),
            "historical executable inventory substitution")
    return source


@contextmanager
def _original_read_pass(root, source, extra_roots=()):
    """Populate the original per-pass cache only after independent tree validation.

    No validator or identity function is replaced. This adapter owns historical
    identity validation and before/after evidence checks instead of live identity.
    """
    from src.expansion import x6_r1_5_2_materialized_verifier as original
    validate_original_source(source)
    require(original._VERIFY_PASS.get() is None, "foreign historical verification context")
    root = Path(root).resolve()
    roots = {root, *[Path(p).resolve() for p in extra_roots]}
    fingerprints = {p: original._evidence_fingerprint(p) for p in roots}
    state = {"root": root, "fingerprint": fingerprints[root], "raw": {}, "slots": {},
             "cleanup": {}, "events": {}, "stages": {}, "models": {}, "source": source}
    token = original._VERIFY_PASS.set(state)
    try:
        yield
        require(all(original._evidence_fingerprint(p) == v for p, v in fingerprints.items()),
                "historical evidence changed during reconstruction")
        validate_original_source(source)
    finally:
        original._VERIFY_PASS.reset(token)


def accounting_epoch(path, campaign_root, *, observed_drift=False):
    from src.orchestration.x6_r1_5_3_reconstruction import validated
    value = load(path)
    roots = [Path(path).parent, Path(value["readiness_root"])]
    if value.get("schema_version") == 1:
        roots.append(Path(value["source"]["implementation_root"]))
    return validated(campaign_root, "accounting-epoch", {
        "epoch": value, "file_sha256": digest(Path(path).read_bytes()),
        "observed_drift": observed_drift},
        lambda: _accounting_epoch_once(path, campaign_root, observed_drift=observed_drift),
        external_roots=roots)


def _accounting_epoch_once(path, campaign_root, *, observed_drift=False):
    value = load(path)
    if value.get("schema_version") == 2:
        from src.orchestration.x6_r1_5_3_contract import validate_epoch
        return validate_epoch(path, campaign_root, allow_observed_drift=observed_drift)
    require(type(value.get("schema_version")) is int and value["schema_version"] == 1,
            "unsupported accounting epoch schema")
    validated = _original_process("epoch", campaign_root, value["source"],
                                  path=str(path), observed_drift=observed_drift)
    normalized_kernel(validated["kernel_and_module"], allow_ineligible=observed_drift)
    return validated


def accounting_context(value):
    """Project already raw-validated evidence without replacing its epoch identity."""
    if value.get("schema_version") == 2:
        from src.orchestration.x6_r1_5_3_contract import epoch_context
        return epoch_context(value)
    require(value.get("schema_version") == 1, "unsupported accounting context schema")
    result = {name: value[name] for name in
              ("stage", "source", "boot_id", "runtime_bindings", "host_identity", "tools")}
    result["kernel_and_module"] = normalized_kernel(value["kernel_and_module"], allow_ineligible=True)
    return result


def accounting_slot(root, slot):
    from src.orchestration.x6_r1_5_3_contract import require_accepted_slot
    from src.orchestration.x6_r1_5_3_durable import read_events
    require_accepted_slot(slot)
    events = read_events(root, "slot", slot["slot_id"])
    require(events, "accounting slot events absent")
    auth = events[0].get("evidence", {}).get("authorization")
    if auth is None or auth.get("record_kind") == "X6_R1_5_3_CAMPAIGN_SLOT_AUTHORIZATION_V1":
        from src.expansion.x6_r1_5_3_materialized_verifier import verify_slot
        return verify_slot(root, slot)
    require(auth.get("record_kind") == "X6_R1_5_2_CAMPAIGN_SLOT_AUTHORIZATION_V1"
            and auth.get("campaign_contract_sha256") == SUPPORTED_CONTRACT
            and auth.get("inventory_sha256") == SUPPORTED_INVENTORY,
            "unsupported historical slot validator selection")
    require(slot["stage"] == "DEVELOPMENT" and events[-1]["state"] == "TERMINAL"
            and events[-1]["evidence"].get("classification") == "SLOT_COMPLETE",
            "unsupported historical slot outcome")
    from src.orchestration.x6_r1_5_2_contract import authorization_digest
    authorization_digest(auth)
    source = validate_original_source(auth["source"])
    epoch = load(auth["epoch"]["path"])
    require(epoch.get("schema_version") == 1 and epoch.get("source") == source,
            "historical slot/epoch source disagreement")
    result = _original_process("slot", root, source, slot=slot)
    require(result.get("cleanup_verified") is True and "row" in result,
            "historical completed slot cleanup/measurement reconstruction")
    accounting_epoch(auth["epoch"]["path"], root)
    return result


def _original_process(kind, root, source, **fields):
    """Use a fixed worker and bounded subprocess, without shared-module mutation."""
    validate_original_source(source)
    request = {"kind": kind, "campaign_root": str(Path(root).resolve()),
               "source": source, **fields}
    with tempfile.TemporaryDirectory(prefix="x6-r153-read-only-history-") as directory:
        path = Path(directory) / "request.json"
        path.write_bytes(canonical(request)); path.chmod(0o600)
        result = run_capture([sys.executable, "-B", str(Path(__file__).resolve()),
                              "--original-read-only", str(path)], cwd=ROOT,
                             timeout_seconds=600)
        require(result.returncode == 0, "original read-only validation failed: " + result.stderr)
        value = json.loads(result.stdout)
    validate_original_source(source)
    return value


def _worker(path):
    request = load(path)
    require(request.get("kind") in {"epoch", "slot"}, "unsupported historical read action")
    expected = {"kind", "campaign_root", "source"} | (
        {"path", "observed_drift"} if request["kind"] == "epoch" else {"slot"})
    require(set(request) == expected, "historical read request schema")
    source = validate_original_source(request["source"])
    # The full source tree was checked against the one supported Git object.
    # Only fixed predecessor modules are imported, in a separate interpreter.
    # Never modify ROOT or validator functions in the live accounting process.
    for name in list(sys.modules):
        if name == "src" or name.startswith("src."):
            del sys.modules[name]
    sys.path.insert(0, source["implementation_root"])
    from src.orchestration import x6_r1_5_2_contract as original_contract
    from src.expansion import x6_r1_5_2_materialized_verifier as original
    require(original_contract.CONTRACT_PROPOSAL_SHA256 == SUPPORTED_CONTRACT and
            original_contract.INVENTORY_SHA256 == SUPPORTED_INVENTORY,
            "historical validator contract substitution")
    for module, relative in ((original_contract,"src/orchestration/x6_r1_5_2_contract.py"),
                             (original,"src/expansion/x6_r1_5_2_materialized_verifier.py")):
        require(Path(module.__file__).resolve() == Path(source["implementation_root"]) / relative,
                "historical validator selection substitution")
    root = request["campaign_root"]
    if request["kind"] == "epoch":
        epoch = load(request["path"])
        require(epoch.get("source") == source, "historical epoch request source")
        with _original_read_pass(root,source,[Path(request["path"]).parent,
                                               Path(epoch["readiness_root"])]):
            value = original_contract.validate_epoch(request["path"],root,
                allow_observed_drift=request["observed_drift"])
    else:
        original_contract.require_accepted_slot(request["slot"])
        from src.orchestration.x6_r1_5_2_durable import read_events
        auth = read_events(root,"slot",request["slot"]["slot_id"])[0]["evidence"]["authorization"]
        require(auth["source"] == source, "historical slot request source")
        epoch = load(auth["epoch"]["path"])
        with _original_read_pass(root,source,[Path(auth["epoch"]["path"]).parent,
                                               Path(epoch["readiness_root"])]):
            value = original.verify_slot(root,request["slot"])
    print(canonical(value).decode())


if __name__ == "__main__":
    require(len(sys.argv) == 3 and sys.argv[1] == "--original-read-only",
            "historical worker supports read-only validation only")
    _worker(sys.argv[2])
