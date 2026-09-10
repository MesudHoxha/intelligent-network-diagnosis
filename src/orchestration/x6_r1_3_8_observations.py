"""Command catalog and raw-only reconstruction shared by collection and replay."""
from __future__ import annotations
import json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from src.collection.x6_performance_collector import derive_window, exact_noqueue, validate_speed_pair
from src.orchestration.x6_r1_3_8_contract import ROOT, CONTEXT, TOPOLOGY, IMAGE, NODES, require
from src.collection.x6_r0_5_route_bootstrap import validate_management_default, validate_route_get


# Exact accepted six-route R0.5 bootstrap observations.
ROUTES = {
    "hosta_forward": ("hosta", "10.61.3.2", "10.61.1.1", "eth1", "10.61.1.2"),
    "hostb_reverse": ("hostb", "10.61.1.2", "10.61.3.1", "eth1", "10.61.3.2"),
    "r1_forward": ("r1", "10.61.3.2", "10.61.12.2", "eth2", "10.61.12.1"),
    "r2_forward": ("r2", "10.61.3.2", "10.61.23.2", "eth2", "10.61.23.1"),
    "r2_reverse": ("r2", "10.61.1.2", "10.61.12.1", "eth1", "10.61.12.2"),
    "r3_reverse": ("r3", "10.61.1.2", "10.61.23.1", "eth1", "10.61.23.2"),
}
BOOTSTRAP_NAMES = (*ROUTES, "hosta_default", "hostb_default", "r1_forwarding", "r2_forwarding", "r3_forwarding")

def bootstrap(rows):
    require([row["name"] for row in rows] == list(BOOTSTRAP_NAMES), "bootstrap inventory")
    for row in rows:
        success(row)
        if row["name"] in ROUTES:
            node, destination, via, dev, src = ROUTES[row["name"]]
            validate_route_get(row, destination=destination, via=via, dev=dev, src=src)
        elif row["name"].endswith("_default"):
            validate_management_default(row)
        else:
            require(row["stdout"].strip() == "1", "router forwarding disabled")

def catalog():
    context = json.loads((ROOT / CONTEXT).read_text())
    traffic = context["traffic"]
    commands = {
        "deploy": (["containerlab", "deploy", "-t", str(ROOT / TOPOLOGY)], 30),
        "cleanup": (["containerlab", "destroy", "-t", str(ROOT / TOPOLOGY), "--cleanup"], 30),
        "host_containers": (["docker", "ps", "-a", "--no-trunc", "--format", "{{json .}}"], 30),
        "host_namespaces": (["ip", "netns", "list"], 5),
        "host_links": (["ip", "-j", "link", "show"], 5),
        "host_qdisc": (["tc", "-j", "qdisc", "show"], 5),
        "host_processes": (["ps", "-eo", "pid,ppid,args"], 5),
        "kernel": (["uname", "-r"], 5),
        "kernel_config": (["zgrep", "CONFIG_NET_SCH_NETEM", "/proc/config.gz"], 5),
        "module": (["lsmod"], 5),
        "module_provenance": (["modinfo", "sch_netem"], 5),
        "image": (["docker", "image", "inspect", IMAGE], 30),
        "python": (["python3", "--version"], 5), "ip": (["ip", "-V"], 5),
        "tc": (["tc", "-V"], 5), "ethtool": (["ethtool", "--version"], 5),
        "docker": (["docker", "version", "--format", "json"], 30),
        "containerlab": (["containerlab", "version"], 5),
        "git": (["git", "-C", str(ROOT), "rev-parse", "HEAD", "HEAD^{tree}"], 5),
        "iperf": (traffic["client_command"], traffic["timeouts_seconds"]["client"]),
        "traffic_ping": (traffic["ping_command"], traffic["timeouts_seconds"]["ping"]),
        "server_start": (traffic["server_command"], 5),
        "server_ready": (traffic["server_readiness_command"], 5),
        "server_output": (traffic["server_output_command"], 5),
        "server_stop": (traffic["server_teardown_command"], 5),
        "qdisc": (context["qdisc"]["capture_command"], 10),
        "filters_root": (context["qdisc"]["filter_commands"][0], 10),
        "filters_ingress": (context["qdisc"]["filter_commands"][1], 10),
    }
    for node, interface, direction in (("r2", "eth2", "tx"), ("r3", "eth1", "rx")):
        prefix = ["docker", "exec", "clab-x6r1-" + node]
        commands[node + "_counter"] = (prefix + ["cat", "/sys/class/net/" + interface + "/statistics/" + direction + "_bytes"], 5)
        commands[node + "_speed"] = (prefix + ["cat", "/sys/class/net/" + interface + "/speed"], 5)
        commands[node + "_ethtool"] = (prefix + ["/usr/sbin/ethtool", interface], 5)
    for i, argv in enumerate(traffic["version_commands"]):
        commands["container_tool_" + str(i)] = (argv, 5)
    for name, (node, destination, via, dev, src) in ROUTES.items():
        commands[name] = (["docker", "exec", "clab-x6r1-" + node, "ip", "-j", "route", "get", destination], 5)
    for node in ("hosta", "hostb"):
        commands[node + "_default"] = (["docker", "exec", "clab-x6r1-" + node, "ip", "-j", "route", "show", "default"], 5)
    for node in ("r1", "r2", "r3"):
        commands[node + "_forwarding"] = (["docker", "exec", "clab-x6r1-" + node, "sysctl", "-n", "net.ipv4.ip_forward"], 5)
    return commands


def success(row, *, absent_process=False):
    require(not row.get("incomplete") and not row["interrupted"] and not row["timed_out"] and row["return_code"] in ({0, 1} if absent_process else {0}), "command failed: " + row["name"])
    return row


def controls(rows):
    require([r["name"] for r in rows] == ["r2_counter", "r3_counter", "qdisc", "filters_root", "filters_ingress"], "control inventory/order")
    for row in rows: success(row)
    require(exact_noqueue(rows[2], rows[3:]), "non-baseline qdisc/filter state")
    counters = [int(row["stdout"].strip()) for row in rows[:2]]
    require(all(x >= 0 for x in counters), "negative counter")
    return counters


def reconstruct_window(rows, speed):
    names = [r["name"] for r in rows]
    require(names[:3] == ["server_stop", "server_start", "server_ready"], "window startup order")
    ready_end = 3
    while ready_end < len(rows) and names[ready_end] == "server_ready": ready_end += 1
    require(rows[ready_end - 1]["stdout"].strip(), "server readiness absent")
    for row in rows: success(row, absent_process=row["name"] == "server_stop")
    before = rows[ready_end:ready_end + 5]
    a = ready_end + 5
    require(names[a:a+2] == ["iperf", "traffic_ping"], "composite command order")
    after = rows[a+2:a+7]
    require(names[a+7:] == ["server_output", "server_stop"], "window final order")
    before_c, after_c = controls(before), controls(after)
    require(all(y >= x for x, y in zip(before_c, after_c)), "counter reset")
    iperf, ping = rows[a:a+2]
    start, end = iperf["started"]["monotonic_ns"], iperf["completed"]["monotonic_ns"]
    ping_start = ping["started"]["monotonic_ns"]
    skew = abs(ping_start - start - 5_000_000_000) / 1e9
    require(end - start >= 20_000_000_000 and skew <= .250, "observed duration/startup skew")
    require(before[-1]["completed"]["monotonic_ns"] <= start and after[0]["started"]["monotonic_ns"] >= max(end, ping["completed"]["monotonic_ns"]), "counter/composite ordering")
    elapsed = (after[-1]["completed"]["monotonic_ns"] - before[0]["started"]["monotonic_ns"]) / 1e9
    raw = {"ping": ping, "iperf": iperf, "r2_tx_before": before[0], "r3_rx_before": before[1], "r2_tx_after": after[0], "r3_rx_after": after[1], "qdisc_before": before[2], "qdisc_after": after[2], "filters_before": before[3:], "filters_after": after[3:], "elapsed_seconds": elapsed}
    derived = derive_window(raw, phase="baseline", speed_mbps=speed)
    require(all(row["availability"] == "observed" for row in derived.values()), "measurement unavailable")
    require(derived["rate_limit_detected"]["value"] is False, "rate control unavailable")
    measurements = {}
    for key, value in derived.items():
        if key == "rate_limit_detected":
            continue
        observed = value["value"]
        measurements[key] = int(observed) if key == "queue_drop_count" else float(
            Decimal(str(observed)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
        )
    return {"measurements": measurements, "timing": {"start_ns": start, "end_ns": rows[-1]["completed"]["monotonic_ns"], "startup_skew_seconds": skew, "counter_elapsed_seconds": elapsed}, "counter_before": before_c, "counter_after": after_c}


def host_state(rows):
    require([r["name"] for r in rows] == ["host_containers", "host_namespaces", "host_links", "host_qdisc", "host_processes"], "host observation inventory")
    for row in rows: success(row)
    containers = [json.loads(line) for line in rows[0]["stdout"].splitlines() if line.strip()]
    require(all(isinstance(row, dict) for row in containers), "host container schema")
    owned = [row for row in containers if row.get("Names") in NODES]
    unknown = [row for row in containers if "x6r1" in str(row.get("Names", "")) and row not in owned]
    require(not unknown, "unknown experiment container")
    links = json.loads(rows[2]["stdout"])
    qdisc = json.loads(rows[3]["stdout"])
    require(isinstance(links, list) and isinstance(qdisc, list), "host networking schema")
    process_lines = rows[4]["stdout"].splitlines()
    traffic = [line for line in process_lines if "iperf3" in line and ("10.61.3.2" in line or any(name in line for name in NODES))]
    require(not traffic, "experiment traffic process remains outside container lifecycle")
    return {"containers": owned, "namespaces": rows[1]["stdout"].splitlines(), "links": [{k: row.get(k) for k in ("ifindex", "ifname", "link_index")} for row in links], "qdisc": qdisc}
