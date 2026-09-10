"""Real successor CLI and durable code against explicitly simulated external tools."""
from __future__ import annotations
import copy
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from src.orchestration.x6_r1_3_8_contract import ROOT, PREDECESSOR, Invalid, canonical, digest, frozen_contract, identity, load, validate_authorization
from src.orchestration.x6_r1_3_8_durable import reserve, reservation_path


def authorization(root, source=None):
    value = {"schema_version": 2, "release_id": "X6_R1_4_BASELINE_ONLY_RUNTIME_AUTHORIZATION", "authorization_id": "synthetic-source-only", "scope": "BASELINE_ONLY_QUALIFICATION", "source_identity": source or identity(), "predecessor": PREDECESSOR, "output_root": str(root), "run_id": "synthetic-run", "issued_ns": time.monotonic_ns(), "expires_ns": time.monotonic_ns()+3600_000_000_000, "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(), "source_test_only": True, "contract": frozen_contract(), "runtime_image": {"Id": "sha256:"+"1"*64, "RepoDigests": []}}
    value["authorization_sha256"] = digest(canonical(value))
    return value


def environment(tmp_path, *, fail=False):
    bin_path = tmp_path / "tools"; bin_path.mkdir()
    for name in ("containerlab", "docker", "ip", "tc", "ps", "uname", "zgrep", "lsmod", "modinfo", "python3", "ethtool", "git"):
        (bin_path / name).symlink_to(ROOT / "tests/fixtures/x6_r1_3_8_external_stub.py")
    state = tmp_path / "external-state.json"; state.write_text(json.dumps({"deployed": False, "fail_iperf": fail}))
    return {**os.environ, "PATH": str(bin_path), "X6_STUB_STATE": str(state), "PYTHONDONTWRITEBYTECODE": "1"}


def command(auth, root):
    return [sys.executable, "-m", "src.orchestration.x6_r1_3_8_production_path", "--authorization", str(auth), "--run-root", str(root), "--run-id", "synthetic-run", "--execute", "--source-test"]


@pytest.mark.parametrize("mutation", ["directory", "alias", "source", "image", "schedule", "expired", "epoch", "production"])
def test_authorization_rejects_binding_and_validity_drift(tmp_path, mutation):
    root=tmp_path/"run"; source=identity(); auth=authorization(root,source)
    actual=root; simulation=True
    if mutation == "directory": actual=tmp_path/"alternate"
    elif mutation == "alias":
        (tmp_path/"alias").symlink_to(tmp_path, target_is_directory=True); actual=tmp_path/"alias/run"
    elif mutation == "source": auth["source_identity"]={}
    elif mutation == "image": auth["runtime_image"]["Id"]="tag-only"
    elif mutation == "schedule": auth["contract"]["schedule"]["window_seconds"]=1
    elif mutation == "expired": auth["expires_ns"]=0
    elif mutation == "epoch": auth["boot_id"]="other-boot"
    else: simulation=False
    unsigned=dict(auth);unsigned.pop("authorization_sha256");auth["authorization_sha256"]=digest(canonical(unsigned))
    with pytest.raises(Invalid): validate_authorization(auth,root=actual,run_id="synthetic-run",source_identity=source,now_ns=time.monotonic_ns(),simulation=simulation)


def test_concurrent_consumption_is_exclusive_and_survives_run_directory_loss(tmp_path):
    root=tmp_path/"run"; auth=authorization(root)
    def attempt():
        try: reserve(root,auth);return True
        except (FileExistsError,Invalid):return False
    with ThreadPoolExecutor(max_workers=2) as pool: assert sorted(pool.map(lambda _: attempt(), range(2))) == [False,True]
    import shutil
    shutil.rmtree(root)
    assert load(reservation_path(root,auth))["state"] == "CONSUMED"
    assert attempt() is False


def test_cli_rejects_synthetic_authorization_at_production_boundary(tmp_path):
    root=tmp_path/"run"; authpath=tmp_path/"auth.json";authpath.write_bytes(canonical(authorization(root)))
    result=subprocess.run(command(authpath,root)[:-1],capture_output=True,text=True,cwd=ROOT,timeout=30)
    assert result.returncode != 0 and "synthetic authorization" in result.stderr
    assert not root.exists()


def test_cli_command_failure_terminalizes_and_standalone_recovery_accepts_failed_records(tmp_path):
    env=environment(tmp_path,fail=True);root=tmp_path/"run";authpath=tmp_path/"auth.json";authpath.write_bytes(canonical(authorization(root)))
    result=subprocess.run(command(authpath,root),env=env,cwd=ROOT,capture_output=True,text=True,timeout=60)
    assert result.returncode != 0
    assert load(root/"terminal/terminal.json")["status"] == "COLLECTION_UNAVAILABLE", result.stderr
    recovery=subprocess.run([sys.executable,"-m","src.orchestration.x6_r1_3_8_recovery","--run-root",str(root),"--source-test"],env=env,cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert recovery.returncode == 0,recovery.stderr
    assert load(root/"state/recovery.json")["failed_orders"]
    assert json.loads(Path(env["X6_STUB_STATE"]).read_text())["deployed"] is False


def test_cli_abrupt_death_is_recovered_from_actual_intermediate_state(tmp_path):
    env=environment(tmp_path);root=tmp_path/"run";authpath=tmp_path/"auth.json";authpath.write_bytes(canonical(authorization(root)))
    child=subprocess.Popen(command(authpath,root),env=env,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        deadline=time.monotonic()+30
        while not (root/"state/deployment.json").exists() and child.poll() is None and time.monotonic()<deadline: time.sleep(.05)
        assert (root/"state/deployment.json").exists(), child.communicate(timeout=5)
        child.kill();child.communicate(timeout=5)
        assert not (root/"terminal/terminal.json").exists()
        result=subprocess.run([sys.executable,"-m","src.orchestration.x6_r1_3_8_recovery","--run-root",str(root),"--source-test"],env=env,cwd=ROOT,capture_output=True,text=True,timeout=30)
        assert result.returncode == 0,result.stderr
        assert load(root/"terminal/terminal.json")["status"] == "INTERRUPTED"
    finally:
        if child.poll() is None: child.kill();child.communicate(timeout=5)


def test_source_test_cli_cannot_invoke_real_external_tools(tmp_path):
    root=tmp_path/"run";authpath=tmp_path/"auth.json";authpath.write_bytes(canonical(authorization(root)))
    result=subprocess.run(command(authpath,root),capture_output=True,text=True,cwd=ROOT,timeout=30)
    assert result.returncode != 0 and "simulation stub" in result.stderr
    assert not root.exists()


@pytest.fixture(scope="module")
def complete_simulated_run(tmp_path_factory):
    base=tmp_path_factory.mktemp("r138-complete-simulated")
    env=environment(base);root=base/"run";authpath=base/"auth.json";authpath.write_bytes(canonical(authorization(root)))
    result=subprocess.run(command(authpath,root),env=env,cwd=ROOT,capture_output=True,text=True,timeout=1100)
    assert result.returncode == 0,result.stderr
    replay=subprocess.run([sys.executable,"-m","src.orchestration.x6_r1_3_8_recovery","--run-root",str(root),"--source-test"],env=env,cwd=ROOT,capture_output=True,text=True,timeout=60)
    assert replay.returncode == 0,replay.stderr
    return root,env


def test_complete_cli_and_standalone_replay_reconstruct_all_thirty_windows(complete_simulated_run):
    from src.expansion.x6_r1_3_8_materialized_verifier import verify
    root,env=complete_simulated_run
    result=verify(root,source_identity=identity(),simulation=True)
    assert result["windows"] == 30 and result["qualified"] is False and result["source_test_only"] is True
    assert load(root/"terminal/terminal.json")["status"] == "SOURCE_CONTRACT_COMPLETE_REPLAY_VERIFIED"
    calls=json.loads(Path(env["X6_STUB_STATE"]).read_text())["calls"]
    deploy=next(i for i,row in enumerate(calls) if row[:2] == ["containerlab","deploy"])
    destroy=next(i for i,row in enumerate(calls) if row[:2] == ["containerlab","destroy"])
    assert all(deploy < i < destroy for i,row in enumerate(calls) if row[:2] == ["docker","exec"])


@pytest.mark.parametrize("mutation",["measurement","duration","skew","threshold","cleanup_order","raw_stream"])
def test_materialized_verifier_rejects_raw_summary_contradictions(complete_simulated_run,mutation):
    from src.expansion.x6_r1_3_8_materialized_verifier import verify
    root,_=complete_simulated_run
    if mutation in {"measurement","duration","skew"}:
        path=root/"raw/windows/C11.json";value=load(path)
        if mutation == "measurement": value["measurements"]["throughput_mbps"] += 1
        elif mutation == "duration": value["timing"]["end_ns"] += 1000000000
        else: value["timing"]["startup_skew_seconds"] = 0.0
        if mutation == "skew" and value == load(path): value["timing"]["startup_skew_seconds"] = .123
    elif mutation == "threshold":
        path=root/"state/threshold_freeze.json";value=load(path);value["sha256"]="0"*64
    else:
        paths=sorted((root/"raw/commands").glob("*.result.json"))
        path=next(p for p in paths if load(p)["phase"] == ("final_controls" if mutation == "cleanup_order" else "window"))
        value=load(path)
        if mutation == "cleanup_order":
            value["started"]["monotonic_ns"] += 1000_000_000_000;value["completed"]["monotonic_ns"] += 1000_000_000_000
        else: value["stdout"] += "tampered"
    original=path.read_bytes()
    try:
        path.write_bytes(canonical(value))
        with pytest.raises(Invalid):verify(root,source_identity=identity(),simulation=True)
    finally:path.write_bytes(original)


def test_successor_bindings_and_historical_preservation():
    from src.expansion.x6_r1_3_8_gate import verify_source
    assert verify_source(historical=False)["authorization"] == "0/10_FALSE"
