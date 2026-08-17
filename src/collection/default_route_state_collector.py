from __future__ import annotations

import hashlib
import json
from ipaddress import IPv4Interface, IPv4Network
from pathlib import Path, PurePosixPath
from typing import Mapping

from src.contracts.expansion import (
    validate_evidence_v4,
    validate_topology_context_v1,
)
from src.expansion.x2_addressing import (
    DEFAULT_EXECUTOR,
    X2AddressingError,
    address_inventory,
    default_route_inventory,
    load_json_rows,
)
from src.expansion.x2_missing_default_route import (
    MissingDefaultRouteScenario,
    load_missing_default_route_scenario,
)
from src.fault_injection.phase6_common import (
    Phase6CommandResult,
    Phase6Executor,
    execute_checked,
    sha256_file,
    utc_now,
    write_json_atomic,
)


ROOT = Path(__file__).resolve().parents[2]
RAW_DIRECTORY = PurePosixPath("raw/v4/addressing_state_collector_v2")
EVIDENCE_PATH = PurePosixPath("parsed/evidence_v4.json")
FEATURE_IDS = (
    "source_address_matches_expected",
    "source_prefix_matches_expected",
    "source_default_route_present",
    "duplicate_address_detected",
    "duplicate_address_mac_churn_detected",
)


def _load_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise X2AddressingError(f"Cannot read X2-R3 JSON object: {path}") from error
    if not isinstance(value, dict):
        raise X2AddressingError(f"X2-R3 JSON artifact must be an object: {path}")
    return value


def _persist_raw(
    output_directory: Path,
    name: str,
    artifact: Mapping[str, object],
) -> tuple[str, str]:
    relative = str(RAW_DIRECTORY / f"{name}.json")
    path = output_directory / relative
    write_json_atomic(path, dict(artifact))
    return relative, sha256_file(path)


def _command_artifact(
    probe_id: str,
    container: str,
    result: Phase6CommandResult,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "probe_id": probe_id,
        "container": container,
        **result,
    }


def _neighbor_macs(result: Mapping[str, object]) -> tuple[str, ...] | None:
    rows = load_json_rows(result)
    if rows is None:
        return None
    macs = {
        str(row["lladdr"]).lower()
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("lladdr"), str)
        and str(row.get("state", "")).upper() not in {"FAILED", "INCOMPLETE"}
    }
    return tuple(sorted(macs))


def _active_duplicate_probe(
    binding: MissingDefaultRouteScenario,
    executor: Phase6Executor,
) -> tuple[dict[str, object], bool | None]:
    results: list[Phase6CommandResult] = []
    observed_macs: set[str] = set()
    complete = True
    shell = (
        f"ip neigh flush to {binding.expected_address} dev "
        f"{binding.duplicate_observer_interface} >/dev/null 2>&1 || true; "
        f"ping -c 1 -W 1 {binding.expected_address} >/dev/null 2>&1 || true; "
        f"ip -j neigh show to {binding.expected_address} dev "
        f"{binding.duplicate_observer_interface}"
    )
    for _ in range(3):
        result = execute_checked(
            executor,
            binding.duplicate_observer_container,
            ["sh", "-c", shell],
        )
        results.append(result)
        macs = _neighbor_macs(result)
        if macs is None or len(macs) != 1:
            complete = False
        if macs is not None:
            observed_macs.update(macs)
    detected = len(observed_macs) > 1 if complete else None
    return (
        {
            "schema_version": 1,
            "probe_id": "active_duplicate_check",
            "observer_container": binding.duplicate_observer_container,
            "target_address": binding.expected_address,
            "sample_count": 3,
            "samples": results,
            "observed_macs": sorted(observed_macs),
            "complete": complete,
        },
        detected,
    )


def _observation(
    value: bool | None,
    *,
    availability: str,
    raw_path: str | None,
    raw_hash: str | None,
) -> dict[str, object]:
    return {
        "value": value,
        "value_type": "boolean",
        "availability": availability,
        "collector_id": "addressing_state_collector",
        "raw_artifact": raw_path,
        "raw_artifact_sha256": raw_hash,
    }


def _current_interface(addresses: tuple[str, ...]) -> IPv4Interface | None:
    if len(addresses) != 1:
        return None
    try:
        return IPv4Interface(addresses[0])
    except ValueError:
        return None


def collect_missing_default_route_evidence_v4(
    output_directory: Path,
    scenario_path: Path,
    *,
    executor: Phase6Executor = DEFAULT_EXECUTOR,
    repository_root: Path = ROOT,
) -> dict[str, object]:
    binding = load_missing_default_route_scenario(scenario_path)
    output_directory = Path(output_directory)
    evidence_path = output_directory / EVIDENCE_PATH
    if evidence_path.exists() or (output_directory / RAW_DIRECTORY).exists():
        raise X2AddressingError("X2-R3 Evidence v4 output already exists.")

    started = utc_now()
    address_result, addresses = address_inventory(executor, binding)
    address_path, address_hash = _persist_raw(
        output_directory,
        "source_address_state",
        _command_artifact(
            "source_address_state", binding.source_container, address_result
        ),
    )
    route_result, routes = default_route_inventory(executor, binding)
    route_path, route_hash = _persist_raw(
        output_directory,
        "source_default_route_state",
        _command_artifact(
            "source_default_route_state", binding.source_container, route_result
        ),
    )
    duplicate_artifact, duplicate_detected = _active_duplicate_probe(
        binding, executor
    )
    duplicate_path, duplicate_hash = _persist_raw(
        output_directory,
        "active_duplicate_check",
        duplicate_artifact,
    )

    current = _current_interface(addresses)
    address_available = current is not None
    route_available = route_result["return_code"] == 0
    duplicate_available = duplicate_detected is not None
    address_matches = (
        current.ip == IPv4Interface(binding.expected_interface).ip
        if current is not None
        else None
    )
    prefix_matches = (
        current.network == IPv4Network(binding.expected_prefix)
        and current.network.prefixlen == binding.expected_prefix_length
        if current is not None
        else None
    )
    default_present = bool(routes) if route_available else None

    observations = {
        "source_address_matches_expected": _observation(
            address_matches,
            availability="observed" if address_available else "collection_unavailable",
            raw_path=address_path,
            raw_hash=address_hash,
        ),
        "source_prefix_matches_expected": _observation(
            prefix_matches,
            availability="observed" if address_available else "collection_unavailable",
            raw_path=address_path,
            raw_hash=address_hash,
        ),
        "source_default_route_present": _observation(
            default_present,
            availability="observed" if route_available else "collection_unavailable",
            raw_path=route_path,
            raw_hash=route_hash,
        ),
        "duplicate_address_detected": _observation(
            duplicate_detected,
            availability="observed" if duplicate_available else "collection_unavailable",
            raw_path=duplicate_path,
            raw_hash=duplicate_hash,
        ),
        "duplicate_address_mac_churn_detected": _observation(
            None,
            availability="not_requested",
            raw_path=None,
            raw_hash=None,
        ),
    }
    required_available = all(
        observations[name]["availability"] == "observed" for name in FEATURE_IDS[:4]
    )
    errors = (
        []
        if required_available
        else ["One or more X2-R3 required addressing observations are unavailable."]
    )
    completed = utc_now()
    collector_run = {
        "schema_version": 1,
        "collector_id": "addressing_state_collector",
        "collector_version": 2,
        "domain": "addressing",
        "status": "completed" if required_available else "partial",
        "started_at_utc": started,
        "completed_at_utc": completed,
        "feature_ids": list(FEATURE_IDS),
        "raw_artifacts": [
            {"path": address_path, "sha256": address_hash},
            {"path": route_path, "sha256": route_hash},
            {"path": duplicate_path, "sha256": duplicate_hash},
        ],
        "errors": errors,
    }
    evidence = {
        "schema_version": 4,
        "evidence_id": f"{binding.scenario_id.lower()}:evidence:v4",
        "topology_context_id": binding.topology_context_id,
        "collected_at_utc": completed,
        "observation_path": {
            "direction": binding.scenario["observation"]["direction"],
            "source_node": binding.source_node,
            "destination_node": binding.destination_node,
            "observer_nodes": [binding.duplicate_observer_node],
        },
        "collector_runs": [collector_run],
        "observations": observations,
        "compatibility": {
            "origin": "native_v4",
            "source_schema_version": None,
            "source_artifact_sha256": None,
        },
    }
    context = _load_object(
        repository_root / binding.scenario["topology"]["context_file"]
    )
    catalog = _load_object(
        repository_root / "plans/expansion/X1_FEATURE_CATALOG_V1.json"
    )
    validate_topology_context_v1(context, repository_root=repository_root)
    if context["context_id"] != binding.topology_context_id:
        raise X2AddressingError("X2-R3 topology context binding drifted.")
    validate_evidence_v4(evidence, catalog, repository_root=repository_root)
    write_json_atomic(evidence_path, evidence)

    for artifact in collector_run["raw_artifacts"]:
        path = output_directory / str(artifact["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            raise X2AddressingError("X2-R3 raw evidence hash verification failed.")
    return evidence
