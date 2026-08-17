from __future__ import annotations

import hashlib
import re
from ipaddress import IPv4Interface, IPv4Network
from pathlib import Path, PurePosixPath

from src.collection.default_route_state_collector import _command_artifact, _load_object, _observation, _persist_raw
from src.contracts.expansion import validate_evidence_v4, validate_topology_context_v1
from src.expansion.x2_addressing import DEFAULT_EXECUTOR, X2AddressingError, address_inventory, default_route_inventory
from src.expansion.x2_duplicate_ip import load_duplicate_ip_scenario
from src.fault_injection.phase6_common import Phase6Executor, execute_checked, utc_now, write_json_atomic

ROOT = Path(__file__).resolve().parents[2]
RAW_DIRECTORY = PurePosixPath("raw/v4/addressing_state_collector_v3")
EVIDENCE_PATH = PurePosixPath("parsed/evidence_v4.json")
MAC = re.compile(r"\bis-at\s+([0-9a-f]{2}(?::[0-9a-f]{2}){5})\b", re.I)
FEATURE_IDS = ("source_address_matches_expected", "source_prefix_matches_expected", "source_default_route_present", "duplicate_address_detected", "duplicate_address_mac_churn_detected")


def _save(output: Path, name: str, artifact: dict[str, object]) -> tuple[str, str]:
    relative = str(RAW_DIRECTORY / f"{name}.json")
    path = output / relative
    write_json_atomic(path, artifact)
    return relative, hashlib.sha256(path.read_bytes()).hexdigest()


def _duplicate_probe(binding, executor: Phase6Executor) -> tuple[dict[str, object], bool | None, bool | None]:
    samples = []
    sequence: list[str] = []
    capture = (
        "command -v tcpdump >/dev/null 2>&1 || exit 127; "
        "capture=$(mktemp); trap 'rm -f \"$capture\"' EXIT; "
        f"timeout 3 tcpdump -l -n -e -i {binding.observer_interface} "
        f"'arp and src host {binding.expected_address}' >\"$capture\" 2>&1 & pid=$!; "
        "sleep 0.2; "
        f"for i in 1 2 3 4 5 6 7 8; do ip neigh flush to {binding.expected_address} dev {binding.observer_interface} >/dev/null 2>&1 || true; "
        f"ping -c 1 -W 1 {binding.expected_address} >/dev/null 2>&1 || true; sleep 0.1; done; "
        "status=0; wait \"$pid\" || status=$?; "
        "case \"$status\" in 0|124) ;; *) cat \"$capture\"; exit \"$status\";; esac; "
        "cat \"$capture\""
    )
    for sample_id in range(4):
        result = execute_checked(executor, binding.target_container, ["ip", "netns", "exec", binding.observer_namespace, "sh", "-eu", "-c", capture])
        text = str(result.get("stdout", "")) + "\n" + str(result.get("stderr", ""))
        macs = [m.lower() for m in MAC.findall(text)]
        sequence.extend(macs)
        samples.append({"sample_id": sample_id, "command_result": result, "responder_macs": macs})
    usable = all(row["command_result"]["return_code"] == 0 for row in samples)
    unique = sorted(set(sequence))
    active = bool(sequence) if usable else None
    churn = (len(unique) >= 2 and any(a != b for a, b in zip(sequence, sequence[1:]))) if usable else None
    return {"schema_version": 1, "probe_id": "duplicate_ip_active_temporal_probe", "samples": samples, "responder_sequence": sequence, "unique_responder_macs": unique, "complete": usable}, active, churn


def collect_duplicate_ip_evidence_v4(output_directory: Path, scenario_path: Path, *, executor: Phase6Executor = DEFAULT_EXECUTOR, repository_root: Path = ROOT) -> dict[str, object]:
    binding = load_duplicate_ip_scenario(scenario_path)
    output = Path(output_directory)
    if (output / EVIDENCE_PATH).exists() or (output / RAW_DIRECTORY).exists():
        raise X2AddressingError("X2-R4 Evidence v4 output already exists.")
    started = utc_now()
    address_result, addresses = address_inventory(executor, binding)
    address_path, address_hash = _save(output, "source_address_state", _command_artifact("source_address_state", binding.source_container, address_result))
    route_result, routes = default_route_inventory(executor, binding)
    route_path, route_hash = _save(output, "source_default_route_state", _command_artifact("source_default_route_state", binding.source_container, route_result))
    duplicate_artifact, active, churn = _duplicate_probe(binding, executor)
    duplicate_path, duplicate_hash = _save(output, "duplicate_ip_active_temporal_probe", duplicate_artifact)
    current = IPv4Interface(addresses[0]) if len(addresses) == 1 else None
    address_ok = current is not None
    route_ok = route_result["return_code"] == 0
    duplicate_ok = active is not None and churn is not None
    observations = {
        "source_address_matches_expected": _observation(current.ip == IPv4Interface(binding.expected_interface).ip if current else None, availability="observed" if address_ok else "collection_unavailable", raw_path=address_path, raw_hash=address_hash),
        "source_prefix_matches_expected": _observation(current.network == IPv4Network(binding.expected_prefix) if current else None, availability="observed" if address_ok else "collection_unavailable", raw_path=address_path, raw_hash=address_hash),
        "source_default_route_present": _observation(bool(routes) if route_ok else None, availability="observed" if route_ok else "collection_unavailable", raw_path=route_path, raw_hash=route_hash),
        "duplicate_address_detected": _observation(active, availability="observed" if duplicate_ok else "collection_unavailable", raw_path=duplicate_path, raw_hash=duplicate_hash),
        "duplicate_address_mac_churn_detected": _observation(churn, availability="observed" if duplicate_ok else "collection_unavailable", raw_path=duplicate_path, raw_hash=duplicate_hash),
    }
    complete = all(v["availability"] == "observed" for v in observations.values())
    completed = utc_now()
    artifacts = [{"path": p, "sha256": h} for p, h in ((address_path, address_hash), (route_path, route_hash), (duplicate_path, duplicate_hash))]
    run = {"schema_version": 1, "collector_id": "addressing_state_collector", "collector_version": 3, "domain": "addressing", "status": "completed" if complete else "partial", "started_at_utc": started, "completed_at_utc": completed, "feature_ids": list(FEATURE_IDS), "raw_artifacts": artifacts, "errors": [] if complete else ["X2-R4 active or temporal evidence unavailable."]}
    evidence = {"schema_version": 4, "evidence_id": f"{binding.scenario_id.lower()}:evidence:v4", "topology_context_id": binding.topology_context_id, "collected_at_utc": completed, "observation_path": {"direction": binding.scenario["observation"]["direction"], "source_node": binding.source_node, "destination_node": binding.destination_node, "observer_nodes": [binding.scenario["observation"]["duplicate_observer_node"]]}, "collector_runs": [run], "observations": observations, "compatibility": {"origin": "native_v4", "source_schema_version": None, "source_artifact_sha256": None}}
    context = _load_object(repository_root / binding.scenario["topology"]["context_file"])
    catalog = _load_object(repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json")
    validate_topology_context_v1(context, repository_root=repository_root)
    validate_evidence_v4(evidence, catalog, repository_root=repository_root)
    write_json_atomic(output / EVIDENCE_PATH, evidence)
    return evidence
