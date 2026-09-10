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
with state_path.open("r+") as stream:
    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
    state = json.load(stream)
    state.setdefault("calls", []).append([name, *args])
    out, rc, delay = "simulated tool 1.0", 0, 0
    if name == "containerlab" and args[0] in {"deploy", "destroy"}:
        state["deployed"] = args[0] == "deploy"
        out = "simulated lifecycle command"
    elif name == "uname": out = "synthetic-kernel"
    elif name == "zgrep": out = "CONFIG_NET_SCH_NETEM=m"
    elif name == "lsmod": out = "sch_netem 32768 0"
    elif name == "modinfo": out = "name: sch_netem\nvermagic: synthetic-kernel"
    elif name == "ps": out = "PID PPID COMMAND"
    elif name == "ip":
        out = "[]" if "link" in args else "" if "netns" in args else "iproute2 simulated"
    elif name == "tc": out = "[]" if "qdisc" in args else "tc simulated"
    elif name == "docker":
        if args[0] == "ps":
            out = "\n".join(json.dumps({"Names": "clab-x6r1-" + node, "ID": node, "Image": "ind-linux:0.1", "Labels": "containerlab=x6r1"}) for node in ("hosta", "r1", "r2", "r3", "hostb")) if state.get("deployed") else ""
        elif args[:2] == ["image", "inspect"]:
            out = json.dumps([{"Id": "sha256:" + "1"*64, "RepoTags": ["ind-linux:0.1"], "RepoDigests": []}])
        elif args[0] == "exec":
            if not state.get("deployed"):
                out, rc = "container absent", 1
            elif "-V" in args or "--version" in args: out = "simulated tool version"
            elif "-r" in args and any("uname" in a for a in args): out = "synthetic-kernel"
            elif any("/speed" in a for a in args): out = "1000"
            elif any(a.endswith("ethtool") for a in args): out = "Speed: 1000Mb/s"
            elif any("statistics" in a for a in args):
                key = "tx" if any("tx_bytes" in a for a in args) else "rx"
                # Stable counters are a valid simulated quiet baseline. They
                # keep the fixture independent from test-host scheduling
                # jitter while production still derives utilization from the
                # recorded elapsed time and before/after observations.
                state[key] = state.get(key, 1000000)
                out = str(state[key])
            elif "route" in args:
                node = next(a.removeprefix("clab-x6r1-") for a in args if a.startswith("clab-x6r1-"))
                if "default" in args: out = json.dumps([{"dst": "default", "dev": "eth0", "gateway": "172.20.20.1"}])
                else:
                    destination = args[-1]
                    route = {("hosta","10.61.3.2"):("10.61.1.1","eth1","10.61.1.2"), ("hostb","10.61.1.2"):("10.61.3.1","eth1","10.61.3.2"), ("r1","10.61.3.2"):("10.61.12.2","eth2","10.61.12.1"), ("r2","10.61.3.2"):("10.61.23.2","eth2","10.61.23.1"), ("r2","10.61.1.2"):("10.61.12.1","eth1","10.61.12.2"), ("r3","10.61.1.2"):("10.61.23.1","eth1","10.61.23.2")}[node,destination]
                    out = json.dumps([{"dst":destination,"gateway":route[0],"dev":route[1],"prefsrc":route[2]}])
            elif "net.ipv4.ip_forward" in args: out = "1"
            elif "qdisc" in args: out = '[{"kind":"noqueue","handle":"0:","root":true,"options":{}}]'
            elif "filter" in args: out = "[]"
            elif any(a.endswith("pkill") for a in args): out, rc = "", 1
            elif any(a.endswith("ss") for a in args): out = "LISTEN 0 1 0.0.0.0:5201"
            elif "-c" in args and "-J" in args:
                out = json.dumps({"end": {"sum_received": {"bits_per_second": 100000000}}})
                delay = 20.05
                if state.get("fail_iperf"): rc, delay = 1, 0
            elif any(a.endswith("ping") for a in args):
                out = "PING 10.61.3.2 (10.61.3.2) 56(84) bytes of data.\n" + "\n".join(f"64 bytes from 10.61.3.2: icmp_seq={i} ttl=64 time=1.000 ms" for i in range(1,51)) + "\n--- 10.61.3.2 ping statistics ---\n50 packets transmitted, 50 received, 0% packet loss, time 9800ms"
                delay = 9.8
            elif any("iperf-server.json" in a for a in args): out = "{}"
            else: out = ""
    stream.seek(0); json.dump(state, stream); stream.truncate(); stream.flush(); os.fsync(stream.fileno())
if delay: time.sleep(delay)
print(out)
sys.exit(rc)
