"""Bound outer production launcher; never infer a child exit status."""
from __future__ import annotations

import argparse
import os
import sys
import time
import json
from pathlib import Path

from src.runtime.subprocesses import run_capture
from src.orchestration.x6_r1_5_1_contract import canonical, digest, load, require
from src.orchestration.x6_r1_5_1_durable import save, stamp, process_identity


def launcher_stamp():
    from src.orchestration.x6_r1_5_1_contract import current_boot_id
    return {"monotonic_ns": time.monotonic_ns(), "boot_id": current_boot_id()}


def receipt_directory(campaign_root, run_id):
    require(isinstance(run_id, str) and run_id and Path(run_id).name == run_id
            and run_id not in {".", ".."}, "unsafe launcher run identity")
    root = Path(campaign_root).resolve()
    directory = root / "launcher-receipts" / run_id
    require(not directory.is_symlink() and not directory.parent.is_symlink(), "unsafe launcher receipt directory")
    return directory


def sealed(value):
    value = dict(value)
    value["receipt_sha256"] = digest(canonical(value))
    return value


def clock_point(value):
    require(isinstance(value,dict) and set(value)=={"monotonic_ns","boot_id"}
            and type(value["monotonic_ns"]) is int and value["monotonic_ns"]>=0
            and isinstance(value["boot_id"],str) and value["boot_id"],"launcher clock schema")
    return value


def checked(path):
    require(not Path(path).is_symlink(), "symlink launcher record")
    value = load(path)
    unsigned = dict(value)
    claimed = unsigned.pop("receipt_sha256")
    require(claimed == digest(canonical(unsigned)), "launcher receipt digest")
    return value


def evidence_inventory(run):
    run = Path(run)
    if not run.exists():
        return []
    require(run.is_dir() and not run.is_symlink(), "unsafe launcher run evidence")
    rows = []
    for path in sorted(run.rglob("*")):
        require(not path.is_symlink(), "symlink launcher run evidence")
        if path.is_file():
            rows.append({"path": path.relative_to(run).as_posix(),
                         "sha256": digest(path.read_bytes())})
    return rows


def child_registration(campaign_root, auth, argv, *, synthetic):
    """Child records its own actual identity before the permission boundary."""
    directory = receipt_directory(campaign_root, auth["run_id"])
    started = checked(directory / "started.json")
    require(started["authorization_sha256"] == auth["authorization_sha256"]
            and started["source"] == auth["source"]
            and started["output_root"] == str(Path(auth["output_root"]).resolve())
            and started["synthetic"] is synthetic, "launcher/child identity mismatch")
    require(started["child_arguments"] == argv, "launcher child argv mismatch")
    require(os.getppid() == started["launcher_process"]["pid"], "launcher child parent mismatch")
    from src.orchestration.x6_r1_5_1_durable import alive
    require(alive(started["launcher_process"]), "original launcher unavailable")
    save(directory / "child.json", sealed({
        "started_sha256": digest((directory / "started.json").read_bytes()),
        "process": process_identity(), "parent_pid": os.getppid(), "registered": launcher_stamp(),
        "child_arguments": argv,
    }), exclusive=True)


def launch(campaign_root, input_path, authorization_path, *, timeout_seconds, synthetic=False):
    from src.orchestration.x6_r1_5_3_campaign import source_identity, require_production_source
    root = Path(campaign_root).resolve()
    auth = load(authorization_path)
    require(auth["source_test_only"] is synthetic, "launcher production/synthetic authority")
    source = source_identity()
    require(auth["source"] == source, "launcher actual source identity")
    if not synthetic:
        require_production_source(source)
        require(not (root / "SOURCE_TEST_ONLY.json").exists()
                and os.environ.get("X6_R1_5_1_CONTROLLED_CLOCK") != "1"
                and not os.environ.get("X6_STUB_STATE"), "synthetic production launcher")
    else:
        from src.orchestration.x6_r1_5_3_source_test import SyntheticContext
        SyntheticContext().validate(root)
    require(type(timeout_seconds) in {int, float} and 0 < timeout_seconds < float("inf"),
            "finite bounded launcher timeout required")
    directory = receipt_directory(root, auth["run_id"])
    arguments = ["run-slot", "--campaign-root", str(root), "--input",
                 str(Path(input_path).resolve()), "--authorization",
                 str(Path(authorization_path).resolve())]
    module = "src.orchestration.x6_r1_5_3_source_test" if synthetic else "src.orchestration.x6_r1_5_3_campaign"
    argv = [sys.executable, "-m", module, *arguments]
    started = sealed({
        "schema_version": 1, "run_id": auth["run_id"],
        "campaign_root": str(root), "output_root": str(Path(auth["output_root"]).resolve()),
        "authorization_sha256": auth["authorization_sha256"],
        "authorization_file_sha256": digest(Path(authorization_path).read_bytes()),
        "input": load(input_path), "input_bytes": Path(input_path).read_text(),
        "input_sha256": digest(Path(input_path).read_bytes()),
        "source": source, "argv": argv, "child_arguments": arguments,
        "cwd": source["implementation_root"], "shell": False,
        "timeout_seconds": timeout_seconds, "synthetic": synthetic,
        "launcher_process": process_identity(), "started": launcher_stamp(),
        "clock_context": "ACTUAL_HOST_MONOTONIC",
    })
    # Exclusive publication prevents replay/concurrent spawning before the child.
    save(directory / "started.json", started, exclusive=True)
    try:
        result = run_capture(argv, timeout_seconds=timeout_seconds,
                             cwd=Path(source["implementation_root"]))
        # The accepted wrapper normalizes timeout to 124 and does not expose the
        # killed child's wait status. 124 must therefore remain ambiguous.
        known = result.returncode != 124
        observation = {
            "kind": ("OBSERVED_SIGNAL" if result.returncode < 0 else "NORMAL_EXIT")
                    if known else "UNAVAILABLE_CHILD_STATUS",
            "child_return_code": result.returncode if known else None,
            "wrapper_return_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
            "stdout_sha256": digest(result.stdout.encode()),
            "stderr_sha256": digest(result.stderr.encode()),
        }
    except BaseException as error:
        observation = {"kind": "LAUNCHER_INTERRUPTED", "child_return_code": None,
                       "wrapper_return_code": None, "stdout": None, "stderr": None,
                       "error_type": type(error).__name__, "detail": str(error)}
        try:
            stop_registered_child(directory, observation)
        except Exception as stop_error:
            observation["stop"]={"kind":"OWNERSHIP_UNRESOLVED_NO_SIGNAL",
                                 "error_type":type(stop_error).__name__,"detail":str(stop_error)}
        publish_terminal(directory, auth, observation)
        raise
    publish_terminal(directory, auth, observation)
    return result.returncode


def stop_registered_child(directory, observation):
    import signal
    from src.orchestration.x6_r1_5_1_durable import alive
    path=directory/"child.json"
    if not path.exists():
        observation["stop"]={"kind":"NO_REGISTERED_CHILD"}
        return
    child=checked(path);started=checked(directory/"started.json")
    require(child["started_sha256"]==digest((directory/"started.json").read_bytes())
            and child["parent_pid"]==started["launcher_process"]["pid"]==os.getpid(),
            "interrupted launcher child ownership")
    identity=child["process"]
    if not alive(identity):
        observation["stop"]={"kind":"REGISTERED_CHILD_NOT_ALIVE","at":launcher_stamp()}
        return
    # A pinned descriptor prevents PID reuse from redirecting the signal.
    # Stored parent/argv claims alone do not establish live ownership.
    descriptor=os.pidfd_open(identity["pid"])
    try:
        stat=Path("/proc/"+str(identity["pid"])+"/stat").read_text().rsplit(")",1)[1].split()
        cmdline=Path("/proc/"+str(identity["pid"])+"/cmdline").read_bytes().split(b"\0")
        argv=[part.decode() for part in cmdline if part]
        require(stat[19]==identity["start_ticks"] and int(stat[1])==os.getpid()
                and alive(identity) and argv==started["argv"],
                "interrupted launcher live child ownership")
        signal.pidfd_send_signal(descriptor,signal.SIGTERM)
        observation["stop"]={"kind":"SIGNAL_REQUESTED_NOT_WAIT_STATUS",
                             "signal":signal.SIGTERM,"process":identity,
                             "live_parent_pid":int(stat[1]),"live_argv":argv,"at":launcher_stamp()}
    finally:
        os.close(descriptor)


def publish_terminal(directory, auth, observation):
    child = directory / "child.json"
    row = {
        "schema_version": 1, "started_sha256": digest((directory / "started.json").read_bytes()),
        "child_sha256": digest(child.read_bytes()) if child.exists() else None,
        "observed": launcher_stamp(), "status": observation,
        "run_evidence": evidence_inventory(auth["output_root"]),
    }
    save(directory / "terminal.json", sealed(row), exclusive=True)


def verify_launcher(campaign_root, auth, *, require_known=True):
    directory = receipt_directory(campaign_root, auth["run_id"])
    started = checked(directory / "started.json")
    require(started["authorization_file_sha256"] == digest(canonical(auth)), "launcher exact authorization bytes")
    require(started["input"].get("slot") == auth["slot"], "launcher input slot binding")
    require(started["input"] == json.loads(started["input_bytes"])
            and started["input_sha256"] == digest(started["input_bytes"].encode()), "launcher exact input binding")
    require(started["clock_context"] == "ACTUAL_HOST_MONOTONIC", "launcher clock provenance")
    require("synthetic_fixture_prototype_sha256" not in started or auth["source_test_only"], "synthetic receipt in production")
    require(type(started["schema_version"]) is int and started["schema_version"] == 1 and started["shell"] is False
            and started["source"] == auth["source"]
            and started["authorization_sha256"] == auth["authorization_sha256"]
            and started["run_id"] == auth["run_id"]
            and started["campaign_root"] == str(Path(campaign_root).resolve())
            and started["output_root"] == str(Path(auth["output_root"]).resolve())
            and started["synthetic"] is auth["source_test_only"], "launcher identity/provenance")
    clock_point(started["started"])
    parent=started["launcher_process"]
    require(set(parent)=={"pid","start_ticks","boot_id"}
            and type(parent["pid"]) is int and parent["pid"]>0
            and isinstance(parent["start_ticks"],str) and parent["start_ticks"].isascii() and parent["start_ticks"].isdigit()
            and parent["boot_id"]==started["started"]["boot_id"],"launcher original process schema")
    args = started["child_arguments"]
    require(len(args) == 7 and args[:3] == ["run-slot", "--campaign-root", started["campaign_root"]]
            and args[3] == "--input" and args[5] == "--authorization",
            "launcher bounded argv")
    require(all(isinstance(value,str) for value in started["argv"])
            and all(isinstance(value,str) for value in args)
            and all(Path(value).is_absolute() and str(Path(value).resolve())==value for value in (args[4],args[6])),
            "launcher canonical argv paths")
    module = "src.orchestration.x6_r1_5_3_source_test" if auth["source_test_only"] else "src.orchestration.x6_r1_5_3_campaign"
    require(started["argv"] == [started["argv"][0], "-m", module, *args]
            and Path(started["argv"][0]).is_absolute()
            and Path(started["argv"][0]).resolve() == Path(sys.executable).resolve()
            and started["cwd"] == auth["source"]["implementation_root"], "launcher argv provenance")
    require(type(started["timeout_seconds"]) in {int,float} and 0 < started["timeout_seconds"] < float("inf"), "launcher timeout")
    child = checked(directory / "child.json") if (directory / "child.json").exists() else None
    if child:
        clock_point(child["registered"])
        require(child["parent_pid"] == started["launcher_process"]["pid"]
                and type(child["process"]["pid"]) is int and child["process"]["pid"] > 0
                and child["process"]["pid"] != child["parent_pid"]
                and child["process"]["start_ticks"].isdigit(), "launcher process provenance")
        require(child["started_sha256"] == digest((directory / "started.json").read_bytes())
                and child["child_arguments"] == args, "launcher child binding")
        require(child["process"]["boot_id"] == started["started"]["boot_id"]
                and child["registered"]["boot_id"] == started["started"]["boot_id"]
                and child["registered"]["monotonic_ns"] >= started["started"]["monotonic_ns"],
                "launcher child clock")
    if not (directory / "terminal.json").exists():
        require(not require_known, "original child status unavailable")
        return {"kind": "UNAVAILABLE_CHILD_STATUS", "child_return_code": None}
    terminal = checked(directory / "terminal.json")
    require(type(terminal.get("schema_version")) is int and terminal["schema_version"]==1,"launcher terminal schema")
    require(terminal["started_sha256"] == digest((directory / "started.json").read_bytes())
            and terminal["child_sha256"] == (digest((directory / "child.json").read_bytes()) if child else None),
            "launcher terminal binding")
    clock_point(terminal["observed"])
    require(terminal["observed"]["boot_id"] == started["started"]["boot_id"]
            and terminal["observed"]["monotonic_ns"] >= started["started"]["monotonic_ns"], "launcher completion clock")
    if child:
        require(terminal["observed"]["monotonic_ns"] >= child["registered"]["monotonic_ns"], "launcher child completion clock")
    status = terminal["status"]; code = status["child_return_code"]
    require(status["kind"] in {"NORMAL_EXIT", "OBSERVED_SIGNAL", "LAUNCHER_INTERRUPTED", "UNAVAILABLE_CHILD_STATUS"},
            "launcher status kind")
    known = status["kind"] in {"NORMAL_EXIT", "OBSERVED_SIGNAL"}
    require(type(code) is int if known else code is None, "launcher observed status")
    require(not require_known or child is not None, "original child process identity unavailable")
    wrapped=status.get("wrapper_return_code")
    require(type(wrapped) is int if known else wrapped is None or
            (status["kind"]=="UNAVAILABLE_CHILD_STATUS" and type(wrapped) is int and wrapped==124),
            "launcher bounded layer status schema")
    if known or wrapped==124:
        require(isinstance(status.get("stdout"),str) and isinstance(status.get("stderr"),str),
                "launcher observed streams required")
    else:
        require(status.get("stdout") is None and status.get("stderr") is None,"launcher unavailable stream contradiction")
    if status.get("stdout") is not None:
        require(status["stdout_sha256"] == digest(status["stdout"].encode())
                and status["stderr_sha256"] == digest(status["stderr"].encode()), "launcher stream hashes")
    if known:
        require((code < 0) is (status["kind"] == "OBSERVED_SIGNAL")
                and status["wrapper_return_code"] == code, "launcher status contradiction")
    require(not require_known or known, "known original child status required")
    # Recovery may append files; original observed files must remain unchanged.
    for item in terminal["run_evidence"]:
        path = Path(auth["output_root"]) / item["path"]
        require(not Path(item["path"]).is_absolute() and ".." not in Path(item["path"]).parts
                and path.is_file() and not path.is_symlink()
                and digest(path.read_bytes()) == item["sha256"], "launcher evidence contradiction")
    expected={item["path"] for item in terminal["run_evidence"]}
    require(len(expected)==len(terminal["run_evidence"]),"duplicate launcher evidence binding")
    current={item["path"] for item in evidence_inventory(auth["output_root"])}
    extras=current-expected
    if extras:
        import re
        run=Path(auth["output_root"])
        journal_path=next((run/"state"/name for name in ("recovery.json","recovery-failed.json")
                           if (run/"state"/name).is_file() and "state/"+name not in expected),None)
        if journal_path is None:
            # An interruption immediately after CONSUMED, before lifecycle entry,
            # may publish only the terminal during classification. No cleanup
            # observations are invented for resources never deployed.
            from src.orchestration.x6_r1_5_3_durable import read_events
            history=read_events(campaign_root,"slot",auth["slot"]["slot_id"])
            require(extras=={"terminal/terminal.json"} and code!=0
                    and [event["state"] for event in history]==["RESERVED_UNDECIDED","ADMITTED","CONSUMED","TERMINAL"],
                    "unbound original run evidence")
            classification=load(run/"terminal/terminal.json")
            require(classification=={"status":"SLOT_INTERRUPTED_RECOVERED","qualified":False,
                                     "scientific_acceptance":False,"lifecycle_entered":False}
                    and history[-1]["evidence"].get("classification")==classification["status"]
                    and not any(path.startswith("raw/") for path in current),
                    "pre-entry recovery snapshot contradiction")
        else:
            require(journal_path is not None and code!=0,"unbound original run evidence")
            journal=load(journal_path);orders=set(journal["command_orders"])
            original_orders=[int(match.group(1)) for path in expected
                             if (match:=re.match(r"raw/commands/([0-9]+)",path))]
            require(orders and min(orders)>max(original_orders,default=0),"recovery precedes launcher snapshot boundary")
            permitted={"state/recovery.json","state/recovery-failed.json","state/restoration-action.json","state/cleanup.json","terminal/terminal.json"}
            for path in extras-permitted:
                match=re.match(r"raw/commands/([0-9]+)",path)
                require(match is not None and int(match.group(1)) in orders,"non-recovery evidence appended after launcher")
        # Full ownership, raw ordering and final absence are independently checked
        # by the slot verifier. This check only recognizes append-only additions.
    from src.orchestration.x6_r1_5_3_durable import read_events
    events=read_events(campaign_root,"slot",auth["slot"]["slot_id"])
    consumed=[event for event in events if event["state"]=="CONSUMED"]
    if consumed:
        require(child is not None and child["process"]==consumed[0]["evidence"]["process"],
                "original child/consumption process contradiction")
        if not auth["source_test_only"]:
            point=consumed[0]["evidence"]["consumed"]
            require(point["boot_id"]==child["registered"]["boot_id"]
                    and child["registered"]["monotonic_ns"]<=point["monotonic_ns"]<=terminal["observed"]["monotonic_ns"],
                    "launcher/consumption timestamp contradiction")
    inner = Path(auth["output_root"]) / "terminal/terminal.json"
    if known and inner.exists():
        complete = load(inner)["status"] == "SLOT_COMPLETE"
        require(code != 0 or complete, "zero original exit without complete terminal")
        if require_known and complete:
            require(code == 0, "complete terminal without successful original exit")
    return status


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--timeout-seconds", required=True, type=float)
    args = parser.parse_args(argv)
    return launch(args.campaign_root, args.input, args.authorization,
                  timeout_seconds=args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
