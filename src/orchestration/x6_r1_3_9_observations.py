"""Command catalog and raw-only reconstruction shared by collection and replay."""
from __future__ import annotations
import json
import re
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from src.collection.x6_performance_collector import derive_window, exact_noqueue, validate_speed_pair
from src.orchestration.x6_r1_3_9_contract import ROOT, CONTEXT, TOPOLOGY, IMAGE, NODES, canonical, digest, require
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
        "server_container_probe": (["docker", "exec", "clab-x6r1-hostb", "/usr/bin/printf", "X6_SERVER_CONTAINER_OK\\n"], 5),
        "server_process_probe": (["docker", "exec", "clab-x6r1-hostb", "/usr/bin/pgrep", "-x", "iperf3"], 5),
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


def success(row):
    require(not row.get("incomplete") and not row["interrupted"] and not row["timed_out"] and row["return_code"] == 0, "command failed: " + row["name"])
    return row


def server_process_state(container_probe, process_probe):
    """Distinguish an absent iperf3 from an outer Docker or tool failure."""
    success(container_probe)
    require(container_probe["name"] == "server_container_probe" and container_probe["stdout"] == "X6_SERVER_CONTAINER_OK\n" and not container_probe["stderr"], "server container identity unavailable")
    require(process_probe["name"] == "server_process_probe" and not process_probe.get("incomplete") and not process_probe["interrupted"] and not process_probe["timed_out"], "server process observation unavailable")
    if process_probe["return_code"] == 0:
        require(not process_probe["stderr"] and bool(re.fullmatch(r"[0-9]+(?:\n[0-9]+)*\n?", process_probe["stdout"])), "ambiguous present server observation")
        return "PRESENT"
    if process_probe["return_code"] == 1:
        require(process_probe["stdout"] == "" and process_probe["stderr"] == "", "rc=1 does not prove server absence")
        return "ABSENT"
    require(False, "server process observation failed")


def reconstruct_teardown(rows, offset):
    """Validate one bounded teardown state transition and return the next offset."""
    require([row["name"] for row in rows[offset:offset+2]] == ["server_container_probe", "server_process_probe"], "server teardown pre-observation order")
    state = server_process_state(rows[offset], rows[offset+1])
    if state == "ABSENT":
        return offset + 2
    require([row["name"] for row in rows[offset+2:offset+5]] == ["server_stop", "server_container_probe", "server_process_probe"], "server teardown action/order")
    # Once a process was positively observed, only a successful pkill is an
    # accepted action. A later clean probe never converts a failed action into
    # success.
    success(rows[offset+2])
    require(server_process_state(rows[offset+3], rows[offset+4]) == "ABSENT", "server remains after teardown")
    return offset + 5


def failed_command_orders(rows):
    """Classify nonzero observations without treating proved absence as failure."""
    failed = []
    for index, row in enumerate(rows):
        if row.get("return_code") == 0:
            continue
        proved_absent = False
        if row.get("name") == "server_process_probe" and index:
            try:
                proved_absent = server_process_state(rows[index-1], row) == "ABSENT"
            except (Invalid, KeyError):
                proved_absent = False
        if not proved_absent:
            failed.append(row["order"])
    return failed


def controls(rows):
    require([r["name"] for r in rows] == ["r2_counter", "r3_counter", "qdisc", "filters_root", "filters_ingress"], "control inventory/order")
    for row in rows: success(row)
    require(exact_noqueue(rows[2], rows[3:]), "non-baseline qdisc/filter state")
    counters = [int(row["stdout"].strip()) for row in rows[:2]]
    require(all(x >= 0 for x in counters), "negative counter")
    return counters


def reconstruct_window(rows, speed):
    names = [r["name"] for r in rows]
    ready_start = reconstruct_teardown(rows, 0)
    require(names[ready_start:ready_start+2] == ["server_start", "server_ready"], "window startup order")
    success(rows[ready_start])
    ready_end = ready_start + 2
    while ready_end < len(rows) and names[ready_end] == "server_ready": ready_end += 1
    require(rows[ready_end - 1]["stdout"].strip(), "server readiness absent")
    for row in rows[ready_start+1:ready_end]: success(row)
    before = rows[ready_end:ready_end + 5]
    a = ready_end + 5
    require(names[a:a+2] == ["iperf", "traffic_ping"], "composite command order")
    after = rows[a+2:a+7]
    require(names[a+7] == "server_output", "window final order")
    success(rows[a+7])
    require(reconstruct_teardown(rows, a+8) == len(rows), "window teardown trailing observations")
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


HOST_NAMES = ["host_containers", "host_namespaces", "host_links", "host_qdisc", "host_processes"]


def validate_owned_cleanup_state(state, deployment=None, *, require_complete=False):
    containers = state["containers"]
    require(len({row.get("Names") for row in containers}) == len(containers) and len({row.get("ID") for row in containers}) == len(containers), "duplicate cleanup container identity")
    require(all(row.get("Names") in NODES and row.get("Image") == IMAGE and "containerlab=x6r1" in row.get("Labels", "") and row.get("ID") for row in containers), "foreign cleanup ownership")
    if deployment is not None:
        deployed = {row["Names"]: row for row in deployment["containers"]}
        require(all(row["Names"] in deployed and row["ID"] == deployed[row["Names"]]["ID"] and row["Image"] == deployed[row["Names"]].get("Image") for row in containers), "cleanup deployment identity mismatch")
        if require_complete:
            require({row["Names"] for row in containers} == set(NODES) == set(deployed), "successful cleanup requires complete deployment")
    else:
        require(not require_complete, "successful cleanup deployment identity missing")
    return state


def cleanup_cycle(before_rows, action_row, after_rows, *, initial, deployment, require_complete, run_id, output_root, index):
    require([row["name"] for row in before_rows] == HOST_NAMES and all(row["phase"] == "cleanup_before" for row in before_rows), "cleanup_before inventory/order")
    require([row["name"] for row in after_rows] == HOST_NAMES and all(row["phase"] == "cleanup_after" for row in after_rows), "cleanup_after inventory/order")
    chain = [*before_rows, *([action_row] if action_row is not None else []), *after_rows]
    require(all(b["order"] == a["order"] + 1 for a, b in zip(chain, chain[1:])), "cleanup command group is not contiguous")
    before = validate_owned_cleanup_state(host_state(before_rows), deployment, require_complete=require_complete)
    require((action_row is not None) == bool(before["containers"]), "cleanup action contradicts observed resources")
    if action_row is not None:
        require(action_row["name"] == "cleanup" and action_row["phase"] == "cleanup", "cleanup action identity")
        success(action_row)
    after = host_state(after_rows)
    require(not after["containers"] and not any("x6r1" in name for name in after["namespaces"]), "residual experiment resources")
    require(after["links"] == initial["links"] and after["qdisc"] == initial["qdisc"], "host networking drift")
    return {"index": index, "run_id": run_id, "output_root": output_root,
            "deployment_sha256": digest(canonical(deployment)) if deployment is not None else None,
            "before_orders": [row["order"] for row in before_rows], "action_order": action_row["order"] if action_row is not None else None,
            "after_orders": [row["order"] for row in after_rows],
            "owned_before": [{key: row[key] for key in ("Names", "ID", "Image")} for row in sorted(before["containers"], key=lambda row: row["Names"])]}


def reconstruct_cleanup_cycles(rows, *, initial, deployment, journal, run_id, output_root, release_id, successful):
    selected = [row for row in rows if row["phase"] in {"cleanup_before", "cleanup", "cleanup_after"}]
    cycles = []
    offset = 0
    while offset < len(selected):
        before_rows = selected[offset:offset+5]
        offset += 5
        action = selected[offset] if offset < len(selected) and selected[offset]["phase"] == "cleanup" else None
        if action is not None: offset += 1
        after_rows = selected[offset:offset+5]
        offset += 5
        cycles.append(cleanup_cycle(before_rows, action, after_rows, initial=initial, deployment=deployment,
                                    require_complete=successful and len(cycles) == 0, run_id=run_id,
                                    output_root=output_root, index=len(cycles) + 1))
    require(offset == len(selected) and cycles, "cleanup observation cardinality")
    if successful:
        require(all(not cycle["owned_before"] for cycle in cycles[1:]), "owned resources reappeared after successful cleanup")
    require(journal == {"release_id": release_id, "run_id": run_id, "output_root": output_root, "cycles": cycles}, "cleanup journal contradicts raw observations")
    return cycles


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
