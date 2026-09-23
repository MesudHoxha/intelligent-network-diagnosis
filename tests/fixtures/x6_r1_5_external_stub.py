#!/usr/bin/python3
"""Simulated external observations only. Never invokes networking tools."""
import fcntl
import json
import os
import sys
import time
from pathlib import Path

name, args = Path(sys.argv[0]).name, sys.argv[1:]
if name == "git":
    os.execv("/usr/bin/git", ["git", *args])  # read-only Git commands from the catalog
state_path = Path(os.environ["X6_STUB_STATE"])
fast = os.environ.get("X6_R1_5_CONTROLLED_CLOCK") == "1"
with state_path.open("r+") as stream:
    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
    state = json.load(stream)
    state.setdefault("calls", []).append([name, *args])
    out, err, rc, delay = "simulated tool 1.0", "", 0, 0
    if name == "containerlab" and args[0] in {"deploy", "destroy"}:
        if args[0] == "destroy" and state.get("fail_cleanup"):
            out, err, rc = "", "simulated cleanup failure", 1
        else:
            state["deployed"] = args[0] == "deploy"
            out = "simulated lifecycle command"
    elif name == "uname": out = "synthetic-kernel"
    elif name == "zgrep": out = "CONFIG_NET_SCH_NETEM=m"
    elif name == "lsmod": out = "" if state.get("bad_module") else "sch_netem 32768 0"
    elif name == "modinfo": out = "name: sch_netem\nvermagic: synthetic-kernel"
    elif name == "ps": out = "PID PPID COMMAND"
    elif name == "ip":
        out = "[]" if "link" in args else "" if "netns" in args else "iproute2 simulated"
    elif name == "tc": out = "[]" if "qdisc" in args else "tc simulated"
    elif name == "docker":
        if args[0] == "ps":
            nodes = ("hosta", "r1") if state.get("partial_deploy") else ("hosta", "r1", "r2", "r3", "hostb")
            out = "\n".join(json.dumps({"Names": "clab-x6r1-" + node, "ID": state.get("replacement_id", {}).get(node, node), "Image": "ind-linux:0.1", "Labels": "containerlab=x6r1"}) for node in nodes) if state.get("deployed") else ""
        elif args[:2] == ["image", "inspect"]:
            out = json.dumps([{"Id": "sha256:66392daabae6054416fba5043f312bfc464bcc18246956867870e4953847ff5c", "RepoTags": ["ind-linux:0.1"], "RepoDigests": []}])
        elif args[0] == "exec":
            if not state.get("deployed"):
                out, rc = "container absent", 1
            elif "/usr/bin/printf" in args and "X6_SERVER_CONTAINER_OK\\n" in args: out = "X6_SERVER_CONTAINER_OK"
            elif "/usr/bin/pgrep" in args:
                if state.get("probe_mode") == "docker_error": out, err, rc = "", "docker exec failed", 1
                elif state.get("probe_mode") == "tool_error": out, err, rc = "", "pgrep failed", 1
                elif state.get("probe_mode") == "ambiguous": out, err, rc = "unexpected", "", 1
                elif state.get("server_running"): out = "4242"
                else: out, rc = "", 1
            elif any(a.endswith("pkill") for a in args):
                mode = state.get("teardown_mode", "success")
                if mode == "error_rc1": out, err, rc = "", "docker exec failed", 1
                elif mode == "ambiguous_rc1": out, rc = "", 1
                elif mode == "timeout": delay = 6
                elif state.get("server_running"): state["server_running"] = False
                else: out, rc = "", 1
            elif "/bin/sh" in args and any("iperf3 -s" in a for a in args): state["server_running"] = True; out = ""
            elif "-V" in args or "--version" in args: out = "simulated tool version"
            elif "-r" in args and any("uname" in a for a in args): out = "synthetic-kernel"
            elif any("/speed" in a for a in args): out = "10000"
            elif any(a.endswith("ethtool") for a in args): out = "Speed: 10000Mb/s"
            elif any("statistics" in a for a in args):
                key = "tx" if any("tx_bytes" in a for a in args) else "rx"
                state[key] = state.get(key, 1000000)
                out = str(state[key])
                state[key] += 30000000000 if fast else 17500000000
            elif "route" in args:
                node = next(a.removeprefix("clab-x6r1-") for a in args if a.startswith("clab-x6r1-"))
                if "default" in args: out = json.dumps([{"dst": "default", "dev": "eth0", "gateway": "172.20.20.1"}])
                else:
                    destination = args[-1]
                    route = {("hosta","10.61.3.2"):("10.61.1.1","eth1","10.61.1.2"), ("hostb","10.61.1.2"):("10.61.3.1","eth1","10.61.3.2"), ("r1","10.61.3.2"):("10.61.12.2","eth2","10.61.12.1"), ("r2","10.61.3.2"):("10.61.23.2","eth2","10.61.23.1"), ("r2","10.61.1.2"):("10.61.12.1","eth1","10.61.12.2"), ("r3","10.61.1.2"):("10.61.23.1","eth1","10.61.23.2")}[node,destination]
                    out = json.dumps([{"dst":destination,"gateway":route[0],"dev":route[1],"prefsrc":route[2]}])
            elif "net.ipv4.ip_forward" in args: out = "1"
            elif "qdisc" in args and "replace" in args:
                state["qdisc"] = "fault" if "parent" in args else "root"
                if "parent" in args and state.get("pause_mutation_child"):
                    delay = float(state["pause_mutation_child"])
                out = ""
            elif "qdisc" in args and "del" in args:
                state["qdisc"] = "baseline"
                out = ""
            elif "qdisc" in args:
                if state.get("qdisc") == "fault":
                    out = json.dumps([{"kind":"netem","handle":"10:","root":True,"stats":{"drops":state.get("netem_drops",0)}},{"kind":"pfifo","handle":"20:","parent":"10:1","stats":{"drops":0}}])
                elif state.get("qdisc") == "root":
                    out = json.dumps([{"kind":"netem","handle":"10:","root":True,"stats":{"drops":state.get("netem_drops",0)}}])
                else:
                    out = '[{"kind":"noqueue","handle":"0:","root":true,"options":{}}]'
            elif "filter" in args: out = "[]"
            elif any(a.endswith("ss") for a in args): out = "LISTEN 0 1 0.0.0.0:5201"
            elif "-c" in args and "-J" in args:
                out = json.dumps({"end": {"sum_received": {"bits_per_second": 7750000000}}})
                delay = .05 if fast else 20.05
                state["server_running"] = False
                if state.get("fail_iperf"): rc, delay = 1, 0
            elif any(a.endswith("ping") for a in args):
                received = 45 if state.get("qdisc") == "fault" else 50
                if received == 45: state["netem_drops"] = state.get("netem_drops", 0) + 5
                out = "PING 10.61.3.2 (10.61.3.2) 56(84) bytes of data.\n" + "\n".join(f"64 bytes from 10.61.3.2: icmp_seq={i} ttl=64 time=0.060 ms" for i in range(1,received+1)) + f"\n--- 10.61.3.2 ping statistics ---\n50 packets transmitted, {received} received, {100-int(received*2)}% packet loss, time 9800ms"
                delay = .02 if fast else 9.8
            elif any("iperf-server.json" in a for a in args): out = "{}"
            else: out = ""
    stream.seek(0); json.dump(state, stream); stream.truncate(); stream.flush(); os.fsync(stream.fileno())
if delay: time.sleep(delay)
if out: print(out)
if err: print(err, file=sys.stderr)
sys.exit(rc)
