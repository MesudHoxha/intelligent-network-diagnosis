"""Semantic validator for the source-only X6-R0.4 F1 runtime freeze."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator
import yaml


ROOT = Path(__file__).resolve().parents[2]
CONTEXT = Path("labs/topologies/x6_r1_packet_loss/runtime_context_v1.json")
SCHEMA = Path("schemas/x6_r0_4_f1_runtime_context_v1.schema.json")
TOPOLOGY = Path("labs/topologies/x6_r1_packet_loss/topology.clab.yml")
FEATURE_CATALOG = Path("plans/expansion/X1_FEATURE_CATALOG_V1.json")
EXPECTED_FEATURES = (
    "packet_loss_ratio",
    "round_trip_latency_ms_p95",
    "throughput_mbps",
    "interface_utilization_ratio",
    "queue_drop_count",
    "rate_limit_detected",
)


class X6R04ParameterFreezeError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise X6R04ParameterFreezeError(message)


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    return []


def _binomial_probability(n: int, k: int, p: float) -> float:
    return math.comb(n, k) * p**k * (1.0 - p) ** (n - k)


def _validate_topology(context: dict[str, Any], root: Path) -> None:
    topology = context["topology"]
    topology_path = root / topology["file"]
    _require(topology_path == root / TOPOLOGY and topology_path.is_file(), "X6-R0.4 topology path drifted")
    _require(hashlib.sha256(topology_path.read_bytes()).hexdigest() == topology["sha256"], "X6-R0.4 topology hash drifted")
    parsed = yaml.safe_load(topology_path.read_text(encoding="utf-8"))
    _require(isinstance(parsed, dict) and parsed.get("name") == "x6r1", "X6-R0.4 Containerlab name drifted")
    yaml_nodes = parsed.get("topology", {}).get("nodes", {})
    expected_nodes = ["hosta", "r1", "r2", "r3", "hostb"]
    _require(list(yaml_nodes) == expected_nodes, "X6-R0.4 node order/set drifted")
    _require(all(yaml_nodes[name].get("kind") == "linux" and yaml_nodes[name].get("image") == "ind-linux:0.1" for name in expected_nodes), "X6-R0.4 node kind/image drifted")
    manifest_nodes = topology["nodes"]
    _require([row["name"] for row in manifest_nodes] == expected_nodes and len({row["role"] for row in manifest_nodes}) == 5, "X6-R0.4 node roles drifted")

    yaml_links = [tuple(row["endpoints"]) for row in parsed["topology"]["links"]]
    manifest_links = [(row["a"], row["b"]) for row in topology["links"]]
    _require(yaml_links == manifest_links and len(yaml_links) == 4, "X6-R0.4 links drifted")
    endpoints = [endpoint for link in yaml_links for endpoint in link]
    _require(len(endpoints) == len(set(endpoints)), "X6-R0.4 interface endpoint reused")

    addresses: list[ipaddress.IPv4Interface] = []
    for link in topology["links"]:
        network = ipaddress.ip_network(link["prefix"])
        _require(isinstance(network, ipaddress.IPv4Network) and network.prefixlen == 30, "X6-R0.4 requires IPv4 /30 links")
        for endpoint in (link["a"], link["b"]):
            address = ipaddress.ip_interface(link["addresses"][endpoint])
            _require(address.network == network and address.ip not in {network.network_address, network.broadcast_address}, "X6-R0.4 address/prefix mismatch")
            addresses.append(address)
            node, interface = endpoint.split(":", 1)
            command = "ip address add " + str(address) + " dev " + interface
            _require(command in yaml_nodes[node].get("exec", []), "X6-R0.4 address is not materialized in topology: " + endpoint)
    _require(len({address.ip for address in addresses}) == 8, "X6-R0.4 IPv4 addresses are not unique")
    _require(topology["mutation_owner"] == {"node": "r2", "container": "clab-x6r1-r2", "interface": "eth2", "peer": "r3:eth1", "direction": "hosta_to_hostb"}, "X6-R0.4 mutation owner drifted")
    _require(topology["source"]["address"] == "10.61.1.2" and topology["destination"]["address"] == "10.61.3.2", "X6-R0.4 traffic endpoints drifted")
    _require(topology["healthy_exclusions"] == {"finite_f3_bottleneck": False, "f4_rate_limiter": False, "competing_traffic": False}, "X6-R0.4 healthy exclusions drifted")
    for route in topology["routes"]:
        destination = route["destination"]
        command = "ip route add " + ("default" if destination == "default" else destination) + " via " + route["via"]
        _require(command in yaml_nodes[route["node"]].get("exec", []), "X6-R0.4 route is not materialized: " + route["node"] + " " + destination)


def _validate_image(context: dict[str, Any], root: Path) -> None:
    image = context["image"]
    dockerfile = root / image["dockerfile"]
    _require(image["tag"] == "ind-linux:0.1" and dockerfile.is_file(), "X6-R0.4 image source drifted")
    _require(hashlib.sha256(dockerfile.read_bytes()).hexdigest() == image["dockerfile_sha256"], "X6-R0.4 Dockerfile hash drifted")
    source = dockerfile.read_text(encoding="utf-8")
    for binary in ("iproute2", "iputils-ping", "iperf3", "ethtool"):
        _require(binary in source, "X6-R0.4 image lacks required package: " + binary)
    _require(image["identity_command"] == ["docker", "image", "inspect", "ind-linux:0.1"] and "fails before official deployment" in image["identity_policy"], "X6-R0.4 runtime image identity policy drifted")


def _validate_commands_and_qdisc(context: dict[str, Any]) -> None:
    traffic, qdisc = context["traffic"], context["qdisc"]
    _require(traffic["client_command"] == ["docker", "exec", "clab-x6r1-hosta", "/usr/bin/iperf3", "-c", "10.61.3.2", "-t", "20", "-P", "1", "-p", "5201", "-J"], "X6-R0.4 iperf client drifted")
    _require(traffic["ping_command"] == ["docker", "exec", "--env", "LC_ALL=C", "clab-x6r1-hosta", "/usr/bin/ping", "-n", "-i", "0.2", "-c", "50", "-W", "1", "-s", "56", "10.61.3.2"], "X6-R0.4 ping command drifted")
    _require(traffic["transport"] == "TCP" and traffic["streams"] == 1 and traffic["duration_seconds"] == 20 and traffic["iperf3_port"] == 5201, "X6-R0.4 traffic parameters drifted")
    _require(qdisc["pre_state"] == {"kind": "noqueue", "handle": "0:", "parent": "root", "children": [], "policy": "exactly one root noqueue record; any other qdisc or any filter fails before recovery intent or mutation"}, "X6-R0.4 qdisc pre-state drifted")
    _require(qdisc["loss_percent"] == "10.000000" and qdisc["correlation_percent"] == "0.000000" and qdisc["seed"] is None, "X6-R0.4 loss parameters drifted")
    expected_forward = [
        ["docker", "exec", "clab-x6r1-r2", "/usr/sbin/tc", "qdisc", "replace", "dev", "eth2", "root", "handle", "10:", "netem", "limit", "1000", "loss", "random", "10%", "0%"],
        ["docker", "exec", "clab-x6r1-r2", "/usr/sbin/tc", "qdisc", "replace", "dev", "eth2", "parent", "10:1", "handle", "20:", "pfifo", "limit", "1000"],
    ]
    _require(qdisc["forward_commands"] == expected_forward, "X6-R0.4 forward commands drifted")
    _require(qdisc["recovery_command"] == ["docker", "exec", "clab-x6r1-r2", "/usr/sbin/tc", "qdisc", "del", "dev", "eth2", "root"], "X6-R0.4 recovery command drifted")
    _require(qdisc["netem"] == {"kind": "netem", "handle": "10:", "parent": "root", "limit_packets": 1000}, "X6-R0.4 NetEm ownership drifted")
    _require(qdisc["pfifo"] == {"kind": "pfifo", "handle": "20:", "parent": "10:1", "limit_packets": 1000, "feature_owner": "queue_drop_count"}, "X6-R0.4 pfifo ownership drifted")
    _require(qdisc["state_machine"] == ["PLANNED", "ATTEMPTED", "COMMAND_ACCEPTED", "MUTATION_EFFECTIVE", "RESTORATION_CONFIRMED"], "X6-R0.4 state machine drifted")


def _validate_windows_features_and_effectiveness(context: dict[str, Any], root: Path) -> None:
    windows = context["windows"]
    _require(windows["warm_up"]["count"] == 1 and windows["warm_up"]["duration_seconds"] == 5, "X6-R0.4 warm-up drifted")
    _require((windows["baseline"]["count"], windows["fault"]["count"], windows["restoration"]["count"]) == (10, 3, 3), "X6-R0.4 window counts drifted")
    _require([row["offset_seconds"] for row in windows["timeline"]] == ["0.000", "0.000", "5.000", "20.000_or_bounded_completion"], "X6-R0.4 composite timeline drifted")
    _require(windows["allowed_start_skew_seconds"] == "0.250" and "no selective feature/window retry" in windows["failure_policy"], "X6-R0.4 synchronization/failure policy drifted")

    features = context["features"]
    _require(tuple(row["feature_id"] for row in features) == EXPECTED_FEATURES, "X6-R0.4 feature order/set drifted")
    expected_types = {row["feature_id"]: row["value_type"] for row in json.loads((root / FEATURE_CATALOG).read_text(encoding="utf-8"))["features"] if row["feature_id"] in EXPECTED_FEATURES}
    _require(expected_types == {row["feature_id"]: row["value_type"] for row in features}, "X6-R0.4 feature types drifted from X1")
    utilization = next(row for row in features if row["feature_id"] == "interface_utilization_ratio")
    _require("measured_speed_mbps" in utilization["per_window"] and "never use nominal topology capacity" in utilization["denominator"], "X6-R0.4 utilization denominator is not directly measured")
    queue = next(row for row in features if row["feature_id"] == "queue_drop_count")
    _require("pfifo 20:" in queue["source"] and "NetEm 10: dropped never maps" in queue["unavailable"], "X6-R0.4 queue ownership drifted")
    rate = next(row for row in features if row["feature_id"] == "rate_limit_detected")
    _require("direct tc" in rate["source"] and "tbf/htb/cake/police" in rate["per_window"], "X6-R0.4 neutral rate-limit proof drifted")

    effect = context["effectiveness"]
    p, n = float(effect["configured_probability"]), effect["aggregate_trials"]
    _require((p, n) == (0.1, 150) and effect["acceptance_drop_count_inclusive"] == [6, 25], "X6-R0.4 effectiveness inputs drifted")
    probabilities = [_binomial_probability(n, k, p) for k in range(n + 1)]
    _require(math.isclose(1.0 - (1.0 - p) ** 50, float(effect["single_window_detection_probability"]), rel_tol=0, abs_tol=1e-15), "X6-R0.4 detection calculation drifted")
    _require(math.isclose(sum(probabilities[:6]), float(effect["lower_tail_probability"]), rel_tol=0, abs_tol=1e-15), "X6-R0.4 lower tail drifted")
    _require(math.isclose(sum(probabilities[26:]), float(effect["upper_tail_probability"]), rel_tol=0, abs_tol=1e-15), "X6-R0.4 upper tail drifted")
    _require(math.isclose(sum(probabilities[6:26]), float(effect["central_coverage"]), rel_tol=0, abs_tol=1e-15), "X6-R0.4 effectiveness coverage drifted")
    _require("diagnosis and non-loss predicates are forbidden inputs" in effect["criterion"], "X6-R0.4 effectiveness leaks rule output")


def _validate_rule_and_policy(context: dict[str, Any]) -> None:
    rule = context["rule"]
    _require(rule["rule_id"] == "R_X6_PERFORMANCE_001" and rule["family"] == "performance_rule_engine:v1", "X6-R0.4 rule identity drifted")
    _require(rule["canonical_fault_type"] == "packet_loss" and tuple(rule["required_raw_features"]) == EXPECTED_FEATURES, "X6-R0.4 rule inputs drifted")
    _require(rule["conditional_signature"] == ["loss_above_baseline", "latency_within_baseline", "throughput_within_baseline", "utilization_within_baseline", "queue_delta_zero", "rate_limit_false"], "X6-R0.4 conditional signature drifted")
    _require(rule["diagnosed"]["explanation_ref"] == "rule:R_X6_PERFORMANCE_001" and rule["insufficient_evidence"]["status"] == "insufficient_evidence" and rule["no_rule_match"]["status"] == "abstained", "X6-R0.4 Diagnosis Result v2 mapping drifted")
    rerun = context["rerun_policy"]
    _require(rerun["official_pilot_count"] == 1 and "never overwrite" in rerun["retry_rule"] and "no opportunistic rerun" in rerun["post_mutation"], "X6-R0.4 rerun policy drifted")
    current, future = context["authorization"]["current_release"], context["authorization"]["next_release"]
    _require(len(current) == 10 and not any(current.values()), "X6-R0.4 current release must remain 0/10")
    _require(future["x6_r1_source_implementation"] is True and future["x6_r1_controlled_runtime_pilot"] is True and not any(value for key, value in future.items() if key not in {"x6_r1_source_implementation", "x6_r1_controlled_runtime_pilot"}), "X6-R0.4 future authorization overreached")


def validate_x6_r0_4_runtime_context(repository_root: Path = ROOT) -> dict[str, Any]:
    root = Path(repository_root)
    context = json.loads((root / CONTEXT).read_text(encoding="utf-8"))
    schema = json.loads((root / SCHEMA).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(context), key=lambda error: list(error.path))
    if errors:
        raise X6R04ParameterFreezeError("X6-R0.4 schema failure: " + errors[0].message)
    forbidden = ("TBD", "PENDING", "PLACEHOLDER", "CHOOSE_AT_RUNTIME")
    for text in _strings(context):
        _require(not any(token in text for token in forbidden) and re.search(r"<[A-Za-z_][A-Za-z0-9_]*>", text) is None, "X6-R0.4 runtime placeholder remains: " + text)
    _validate_topology(context, root)
    _validate_image(context, root)
    _validate_commands_and_qdisc(context)
    _validate_windows_features_and_effectiveness(context, root)
    _validate_rule_and_policy(context)
    return context
