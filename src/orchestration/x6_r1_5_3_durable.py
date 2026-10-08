"""Durable, hash-chained campaign and non-slot action accounting."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path

from src.orchestration.x6_r1_5_1_contract import canonical, digest, load, require
from src.orchestration.x6_r1_5_1_durable import fsync_directory, save, stamp, process_identity
from src.orchestration.x6_r1_5_3_contract import ACTION_FINAL, SLOT_FINAL, validate_transition


def lock_campaign(root):
    path = Path(root) / ".campaign.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    require(os.fstat(fd).st_uid == os.getuid(), "foreign campaign lock")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _events(root, kind, identity):
    return Path(root) / "accounting" / kind / identity


def read_events(root, kind, identity):
    directory = _events(root, kind, identity)
    from src.expansion.x6_r1_5_3_materialized_verifier import _VERIFY_PASS
    from copy import deepcopy
    state=_VERIFY_PASS.get();key=(kind,identity)
    if state is not None:
        require(Path(root).resolve()==state["root"],"cross-campaign event cache")
        if key in state["events"]:return deepcopy(state["events"][key])
    rows = []
    for index, path in enumerate(sorted(directory.glob("*.json")), 1):
        row = load(path)
        require(path.name == f"{index:06d}.json" and row["index"] == index, "event index")
        require(row["identity"] == identity and row["kind"] == kind, "event identity")
        previous = None if index == 1 else rows[-1]["event_sha256"]
        require(row["previous_sha256"] == previous, "event chain")
        unsigned = dict(row); claimed = unsigned.pop("event_sha256")
        require(claimed == digest(canonical(unsigned)), "event digest")
        current = ("AUTHORIZED_UNRESERVED" if kind == "action" else "SCHEDULED") if not rows else rows[-1]["state"]
        require(row.get("schema_version") == 1 and row.get("from_state") == current, "event transition origin")
        validate_transition(current, row["state"], action=kind == "action")
        require(type(row.get("at", {}).get("monotonic_ns")) is int and row["at"].get("boot_id"), "event clock binding")
        if rows and row["at"]["boot_id"] == rows[-1]["at"]["boot_id"]:
            require(row["at"]["monotonic_ns"] >= rows[-1]["at"]["monotonic_ns"], "event clock reversal")
        rows.append(row)
    if state is not None:state["events"][key]=deepcopy(rows)
    return rows


def append_event(root, kind, identity, target, *, evidence=None, action=False):
    from src.expansion.x6_r1_5_3_materialized_verifier import _VERIFY_PASS
    require(_VERIFY_PASS.get() is None,"event publication during read-only verification")
    rows = read_events(root, kind, identity)
    current = ("AUTHORIZED_UNRESERVED" if action else "SCHEDULED") if not rows else rows[-1]["state"]
    validate_transition(current, target, action=action)
    row = {
        "schema_version": 1, "kind": kind, "identity": identity,
        "index": len(rows) + 1, "previous_sha256": None if not rows else rows[-1]["event_sha256"],
        "from_state": current, "state": target, "evidence": evidence or {}, "at": stamp(),
    }
    row["event_sha256"] = digest(canonical(row))
    save(_events(root, kind, identity) / f"{row['index']:06d}.json", row, exclusive=True)
    return row


def reserve_action(root, authorization, *, action):
    ledger = Path(root) / "action-ledger" / authorization["record_kind"] / (authorization["authorization_id"] + ".reservation.json")
    require(not ledger.exists(), "action authorization already reserved")
    if action in {"freeze-development","evaluate"}:
        require(not any(ledger.parent.glob("*.reservation.json")),"canonical single action already reserved")
    started=stamp()
    row = {"authorization": authorization, "authorization_sha256": authorization["authorization_sha256"], "action": action, "state": "RESERVED_UNDECIDED", "started": started,"process":process_identity(),
           "history":[{"from_state":"AUTHORIZED_UNRESERVED","state":"RESERVED_UNDECIDED","at":started}]}
    row["ledger_sha256"]=digest(canonical(row))
    save(ledger, row, exclusive=True)
    unsigned=dict(row); claimed=unsigned.pop("ledger_sha256"); require(claimed==digest(canonical(unsigned)),"action ledger digest")
    row["durable_observed"] = stamp(); row.pop("ledger_sha256"); row["ledger_sha256"]=digest(canonical(row)); save(ledger, row)
    return ledger, row


def commit_action_authorization(root, authorization, *, action, validate_at_commit, observe=stamp):
    """Reserve once, then decide authorization using an observation after reservation fsync."""
    lock = lock_campaign(root)
    try:
        ledger, row = reserve_action(root, authorization, action=action)
        try:
            # Reconstruct potentially expensive prerequisites before observing the
            # single permission decision. The returned checker applies validity
            # at that observation, after reservation durability and preparation.
            checker = validate_at_commit(None)
            observed = observe()
            checker(observed)
        except BaseException as error:
            row = advance_action(ledger, row, "REJECTED_SPENT", commitment_observation=locals().get("observed"),
                                 error_type=type(error).__name__, detail=str(error))
            raise
        row = advance_action(ledger, row, "ADMITTED", decision="AUTHORIZED_ACTION_ENTRY",
                             commitment_observation=observed)
        row = advance_action(ledger, row, "CONSUMED", consumed=observe())
        return ledger, row, lock
    except BaseException:
        os.close(lock)
        raise


def advance_action(ledger, row, state, **evidence):
    unsigned=dict(row); claimed=unsigned.pop("ledger_sha256"); require(claimed==digest(canonical(unsigned)),"action ledger digest")
    validate_transition(row["state"], state, action=True)
    old=row["state"]; at=stamp(); row = {**row, "state": state, **evidence, "at": at,
        "history":[*row["history"],{"from_state":old,"state":state,"at":at}]}
    row.pop("ledger_sha256"); row["ledger_sha256"]=digest(canonical(row))
    save(ledger, row)
    return row


def publish_bundle(staging, output, files, *, validate=None):
    """Publish a prevalidated bundle; manifest and state event are commit-last."""
    staging, output = Path(staging), Path(output)
    require(not output.exists(), "canonical output exists")
    staging.mkdir(parents=True, exist_ok=False)
    inventory = []
    for relative, value in files.items():
        rel=Path(relative)
        require(not rel.is_absolute() and ".." not in rel.parts and rel.parts and rel.as_posix()==relative and relative!="publication-manifest.json","unsafe publication artifact path")
        path = staging / relative
        save(path, value, exclusive=True)
        inventory.append({"path": relative, "sha256": digest(path.read_bytes())})
    manifest = {"schema_version": 1, "inventory": sorted(inventory, key=lambda x: x["path"])}
    manifest["inventory_sha256"] = digest(canonical(manifest["inventory"]))
    save(staging / "publication-manifest.json", manifest, exclusive=True)
    require(callable(validate), "bundle lacks independent prepublication validation")
    validate(staging)
    os.replace(staging, output); fsync_directory(output.parent)
    return manifest


def verify_terminal_accounting(root, identities):
    result = {}
    for identity in identities:
        rows = read_events(root, "slot", identity)
        require(rows and rows[-1]["state"] in SLOT_FINAL, "slot lacks final accounting")
        result[identity] = rows[-1]
    return result


def verify_action_ledger(root, action, *, require_published=True, authorization_id=None):
    from src.orchestration.x6_r1_5_3_contract import ACTIONS
    directory=Path(root)/"action-ledger"/ACTIONS[action]
    paths=([directory/(authorization_id+".reservation.json")] if authorization_id else sorted(directory.glob("*.reservation.json")))
    paths=[path for path in paths if path.is_file()]
    require(len(paths)==1,"missing or ambiguous action reservation")
    row=load(paths[0]); unsigned=dict(row); claimed=unsigned.pop("ledger_sha256")
    require(claimed==digest(canonical(unsigned)) and row["action"]==action,"action ledger integrity")
    history=row.get("history",[]); require(history and history[0]["state"]=="RESERVED_UNDECIDED","action history")
    for left,right in zip(history,history[1:]):
        require(left["state"]==right["from_state"],"action history chain")
        validate_transition(right["from_state"],right["state"],action=True)
    require(history[0].get("from_state")=="AUTHORIZED_UNRESERVED","action initial transition")
    for event in history:
        point=event.get("at",{})
        require(set(point)=={"monotonic_ns","utc","boot_id"} and type(point["monotonic_ns"]) is int and point["monotonic_ns"]>=0 and point["boot_id"],"action history timestamp schema")
    for left,right in zip(history,history[1:]):
        if left["at"]["boot_id"]==right["at"]["boot_id"]:require(left["at"]["monotonic_ns"]<=right["at"]["monotonic_ns"],"action history clock reversal")
    require(history[-1]["state"]==row["state"],"action head contradiction")
    from src.orchestration.x6_r1_5_3_contract import authorization_digest,validate_action_authorization
    auth=row["authorization"]
    from src.expansion.x6_r1_5_3_materialized_verifier import _verify_source_snapshot
    _verify_source_snapshot(auth["source"])
    require(row["authorization_sha256"]==authorization_digest(auth),"action authorization integrity")
    validate_action_authorization(auth,action=action,campaign_root=root,source=auth["source"],input_inventory_sha256=auth["input_inventory_sha256"],prior_state_sha256=auth["prior_state_sha256"],now_ns=auth["issued_ns"],boot_id=auth["boot_id"])
    process=row.get("process")
    require(isinstance(process,dict) and set(process)=={"pid","start_ticks","boot_id"} and type(process["pid"]) is int and process["pid"]>0 and str(process["start_ticks"]).isdigit() and process["boot_id"]==row["started"]["boot_id"],"action process identity")
    commitment=row.get("commitment_observation")
    if any(event["state"]=="ADMITTED" for event in history):
        require(row.get("decision")=="AUTHORIZED_ACTION_ENTRY" and isinstance(commitment,dict),"action positive commitment absent")
        validate_action_authorization(auth,action=action,campaign_root=root,source=auth["source"],
            input_inventory_sha256=auth["input_inventory_sha256"],prior_state_sha256=auth["prior_state_sha256"],
            now_ns=commitment["monotonic_ns"],boot_id=commitment["boot_id"])
        require(row["durable_observed"]["boot_id"]==row["started"]["boot_id"] and type(row["durable_observed"]["monotonic_ns"]) is int and commitment["boot_id"]==row["started"]["boot_id"] and
                commitment["monotonic_ns"]>=row["durable_observed"]["monotonic_ns"],"action decision precedes durable reservation")
    elif row["state"] not in {"RESERVED_UNDECIDED","REJECTED_SPENT"}:
        require(False,"action state lacks positive authorization commitment")
    if any(event["state"]=="CONSUMED" for event in history):
        consumed=row.get("consumed",{})
        require(type(consumed.get("monotonic_ns")) is int and consumed.get("boot_id")==commitment["boot_id"] and consumed["monotonic_ns"]>=commitment["monotonic_ns"],"action consumption timestamp contradiction")
    if require_published: require(row["state"]=="PUBLISHED","action publication incomplete")
    return row


def reject_not_run_artifacts(root, slot, state):
    if state.startswith("NOT_RUN_"):
        run = Path(root) / "slots" / slot["run_id"]
        require(not run.exists(), "NOT_RUN slot has fabricated run artifacts")

