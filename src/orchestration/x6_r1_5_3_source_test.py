"""Isolated synthetic entrypoint; never usable with real external commands."""
from pathlib import Path
import os
from src.orchestration.x6_r1_5_1_contract import load,require
from src.orchestration.x6_r1_5_3_campaign import main

class SyntheticContext:
    def validate(self,root):
        root=Path(root).resolve()
        marker=load(root/"SOURCE_TEST_ONLY.json")
        require(marker=={"source_test_only":True,"root":str(root)},"isolated synthetic root marker")
        stub=Path(__file__).resolve().parents[2]/"tests/fixtures/x6_r1_5_3_external_stub.py"
        tools=Path(os.environ.get("PATH",""))
        require(tools.is_absolute() and tools.is_dir(),"isolated substitute PATH only")
        for name in ("containerlab","docker","ip","tc","ps","uname","zgrep","lsmod","modinfo","python3","ethtool","git","cat"):
            require((tools/name).is_symlink() and (tools/name).resolve()==stub,"real command forbidden in source-test context")
        require(os.environ.get("X6_STUB_STATE") and os.environ.get("X6_R1_5_1_CONTROLLED_CLOCK")=="1","controlled substitute/clock required")

def synthetic_main():
    from src.orchestration.x6_r1_5_3_source_test import SyntheticContext as CanonicalSyntheticContext
    import sys,json,time
    from src.orchestration.x6_r1_5_1_contract import current_boot_id,digest
    from src.orchestration.x6_r1_5_1_durable import save
    root=Path(sys.argv[sys.argv.index("--campaign-root")+1]).resolve()
    SyntheticContext().validate(root)
    from src.orchestration import x6_r1_5_1_durable as clock
    points=[]
    def collect(value):
        if isinstance(value,dict):
            if type(value.get("monotonic_ns")) is int and value.get("boot_id")==current_boot_id():points.append(value["monotonic_ns"])
            for item in value.values():collect(item)
        elif isinstance(value,list):
            for item in value:collect(item)
    for path in root.rglob("*.json"):
        if "launcher-receipts" in path.parts:continue
        try:collect(json.loads(path.read_text()))
        except (ValueError,OSError):pass
    clock._CLOCK_NS=max(points,default=0)
    mode=os.environ.get("X6_R1_5_3_SOURCE_TEST_MODE","run")
    require(mode in {"run","run-pause-running","run-terminal-event-crash","signal-child","run-pause-window","run-authorization-crash","run-consumed-crash","run-reservation-crash","run-admission-crash"},"unknown synthetic failpoint")
    if mode=="run-authorization-crash":
        from src.orchestration import x6_r1_5_3_slot as lifecycle
        original_save=lifecycle.save
        def fail_authorization(path,value,**kwargs):
            if str(path).endswith("state/authorization.json"):
                raise OSError("synthetic fsync boundary")
            return original_save(path,value,**kwargs)
        lifecycle.save=fail_authorization
    if mode=="run-pause-window":
        from src.orchestration import x6_r1_5_3_slot as lifecycle
        original_window=lifecycle.CommandCollector.window
        def pause_window(self,run,window_id,phase):
            if window_id=="B01":
                save(root/"synthetic-window-pause.json",{"source_test_only":True},exclusive=True)
                deadline=time.monotonic()+30
                while not (root/"synthetic-window-release").exists():
                    if time.monotonic()>deadline:raise TimeoutError("synthetic window release absent")
                    time.sleep(.01)
            return original_window(self,run,window_id,phase)
        lifecycle.CommandCollector.window=pause_window
    if mode=="signal-child":
        import signal
        # Registration must be real even in a signal fixture.
        from src.orchestration.x6_r1_5_3_launcher import child_registration
        auth=json.loads(Path(sys.argv[sys.argv.index("--authorization")+1]).read_text())
        child_registration(root,auth,sys.argv[1:],synthetic=True)
        os.kill(os.getpid(),signal.SIGTERM)
    if mode in {"run-pause-running","run-terminal-event-crash","run-consumed-crash","run-reservation-crash","run-admission-crash"}:
        from src.orchestration import x6_r1_5_3_slot as lifecycle
        original=lifecycle.append_event
        def failpoint(root_arg,kind,identity,target,**kwargs):
            if mode=="run-terminal-event-crash" and target=="TERMINAL":
                terminal=root/"slots"/identity.lower().replace("_","-")/"terminal/terminal.json"
                save(root/"injected-terminal-publication-failure.json",{"source_test_only":True,"terminal_sha256":digest(terminal.read_bytes()),"failure_boundary":"after terminal fsync, before final accounting event"},exclusive=True)
                raise OSError("synthetic final accounting publication failure")
            event=original(root_arg,kind,identity,target,**kwargs)
            if (mode=="run-reservation-crash" and target=="RESERVED_UNDECIDED") or (mode=="run-admission-crash" and target=="ADMITTED"):
                raise SystemExit("synthetic abrupt durable boundary")
            if mode=="run-consumed-crash" and target=="CONSUMED":
                import signal
                os.kill(os.getpid(),signal.SIGKILL)
            if mode=="run-pause-running" and target=="RUNNING":
                save(root/"synthetic-running-pause.json",{"source_test_only":True,"event_sha256":event["event_sha256"]},exclusive=True)
                deadline=time.monotonic()+30
                while not (root/"synthetic-running-release").exists():
                    if time.monotonic()>deadline:raise TimeoutError("synthetic pause release absent")
                    time.sleep(.01)
            return event
        lifecycle.append_event=failpoint
    return main(_synthetic_context=CanonicalSyntheticContext())

if __name__=="__main__": raise SystemExit(synthetic_main())

