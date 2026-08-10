from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from src.collection.evidence_collector_v3 import (
    EVIDENCE_PATH,
    STATUS_PATH,
)
from src.contracts.evidence import EvidenceContractError
from src.contracts.evidence_v3 import (
    EVIDENCE_V3_FEATURE_NAMES,
    validate_evidence_v3,
)
from src.fault_injection.phase6_common import load_phase6_scenario
from src.verification.healthy_evidence_v3 import (
    EXPECTED_RAW_ARTIFACTS,
)


class FaultEvidenceV3VerificationError(RuntimeError):
    """Raised when a P6-R4 fault Evidence v3 gate fails."""


FAULT_FEATURES: dict[str, dict[str, bool | None]] = {
    "wrong_default_gateway": {
        "source_expected_gateway_reachable": True,
        "source_default_gateway_matches_expected": False,
        "destination_reachable": False,
        "route_to_destination_exists_on_observer": True,
        "route_next_hop_matches_expected": True,
        "route_next_hop_reachable_from_observer": True,
        "expected_next_hop_reachable_from_observer": True,
        "observer_egress_interface_oper_up": True,
        "destination_reachable_from_transit": True,
        "flow_blocked_by_policy": False,
    },
    "interface_down": {
        "source_expected_gateway_reachable": True,
        "source_default_gateway_matches_expected": True,
        "destination_reachable": False,
        "route_to_destination_exists_on_observer": False,
        "route_next_hop_matches_expected": None,
        "route_next_hop_reachable_from_observer": None,
        "expected_next_hop_reachable_from_observer": False,
        "observer_egress_interface_oper_up": False,
        "destination_reachable_from_transit": True,
        "flow_blocked_by_policy": False,
    },
    "acl_block": {
        "source_expected_gateway_reachable": True,
        "source_default_gateway_matches_expected": True,
        "destination_reachable": False,
        "route_to_destination_exists_on_observer": True,
        "route_next_hop_matches_expected": True,
        "route_next_hop_reachable_from_observer": True,
        "expected_next_hop_reachable_from_observer": True,
        "observer_egress_interface_oper_up": True,
        "destination_reachable_from_transit": True,
        "flow_blocked_by_policy": True,
    },
}

NONZERO_RAW_PROBES = {
    "wrong_default_gateway": {
        "raw/v3/source_destination_ping_v3.json",
    },
    "interface_down": {
        "raw/v3/source_destination_ping_v3.json",
        "raw/v3/observer_expected_next_hop_ping_v3.json",
    },
    "acl_block": {
        "raw/v3/source_destination_ping_v3.json",
    },
}

STRUCTURAL_FEATURES = {
    "route_next_hop_matches_expected",
    "route_next_hop_reachable_from_observer",
}

FAULT_RAW_ARTIFACTS = {
    fault_type: (
        EXPECTED_RAW_ARTIFACTS
        - (
            {"raw/v3/observer_installed_next_hop_ping_v3.json"}
            if fault_type == "interface_down"
            else set()
        )
    )
    for fault_type in FAULT_FEATURES
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FaultEvidenceV3VerificationError(
            f"Cannot read valid JSON: {path}"
        ) from error
    if not isinstance(value, dict):
        raise FaultEvidenceV3VerificationError(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise FaultEvidenceV3VerificationError(
            f"Cannot hash artifact: {path}"
        ) from error


def _require_profile_binding(evidence, profile) -> None:
    expected = {
        "topology_id": profile.topology_id,
        "direction": profile.direction,
        "source_node": profile.source_node,
        "route_observer_node": profile.route_observer_node,
        "transit_node": profile.transit_node,
        "source_address": profile.source_address,
        "source_prefix": profile.source_prefix,
        "destination_address": profile.destination_address,
        "destination_prefix": profile.destination_prefix,
        "source_expected_gateway_address": (
            profile.source_gateway_address
        ),
        "expected_next_hop": profile.expected_next_hop,
        "observer_egress_interface": profile.observer_egress_interface,
        "flow_protocol": profile.flow_protocol,
        "flow_source_port": profile.flow_source_port,
        "flow_destination_port": profile.flow_destination_port,
        "policy_backend": profile.policy_backend,
        "policy_table": profile.policy_table,
        "policy_chain": profile.policy_chain,
    }
    drift = {
        name: {"expected": value, "observed": evidence.get(name)}
        for name, value in expected.items()
        if evidence.get(name) != value
    }
    if drift:
        raise FaultEvidenceV3VerificationError(
            "Evidence v3 profile binding drifted: "
            + json.dumps(drift, sort_keys=True)
        )


def _verify_raw(
    experiment_directory: Path,
    evidence: dict[str, Any],
    fault_type: str,
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for feature_name in EVIDENCE_V3_FEATURE_NAMES:
        probe = evidence["probes"][feature_name]
        relative_path = probe["raw_artifact"]
        expected_hash = probe["raw_artifact_sha256"]
        availability = evidence["availability"][feature_name]
        if availability == "structurally_unavailable":
            if (
                feature_name not in STRUCTURAL_FEATURES
                or relative_path is not None
                or expected_hash is not None
                or probe.get("status") != "not_applicable"
            ):
                raise FaultEvidenceV3VerificationError(
                    "Invalid structural raw provenance for "
                    + feature_name
                )
            continue
        if not isinstance(relative_path, str) or not isinstance(
            expected_hash, str
        ):
            raise FaultEvidenceV3VerificationError(
                f"Fault feature lacks raw provenance: {feature_name}"
            )
        normalized = PurePosixPath(relative_path)
        if (
            normalized.is_absolute()
            or ".." in normalized.parts
            or str(normalized) != relative_path
        ):
            raise FaultEvidenceV3VerificationError(
                f"Unsafe raw artifact path: {relative_path}"
            )
        actual_hash = _sha256(experiment_directory / relative_path)
        if actual_hash != expected_hash:
            raise FaultEvidenceV3VerificationError(
                f"Raw SHA-256 mismatch: {relative_path}"
            )
        previous = hashes.setdefault(relative_path, expected_hash)
        if previous != expected_hash:
            raise FaultEvidenceV3VerificationError(
                f"Conflicting raw binding: {relative_path}"
            )
    expected_artifacts = FAULT_RAW_ARTIFACTS[fault_type]
    if set(hashes) != expected_artifacts:
        raise FaultEvidenceV3VerificationError(
            "P6-R4 fault evidence has an unexpected raw-probe set."
        )
    actual_paths = {
        path.relative_to(experiment_directory).as_posix()
        for path in (experiment_directory / "raw/v3").glob("*.json")
        if path.is_file()
    }
    if actual_paths != expected_artifacts:
        raise FaultEvidenceV3VerificationError(
            "raw/v3 contains an unexpected or missing artifact."
        )
    expected_nonzero = NONZERO_RAW_PROBES[fault_type]
    for relative_path in sorted(actual_paths):
        raw = _read_json(experiment_directory / relative_path)
        expected_return_code = 1 if relative_path in expected_nonzero else 0
        if raw.get("return_code") != expected_return_code:
            raise FaultEvidenceV3VerificationError(
                "Unexpected raw return code for " + relative_path
            )
    return dict(sorted(hashes.items()))


def verify_fault_evidence_v3(
    experiment_directory: Path,
    scenario_path: Path,
) -> dict[str, Any]:
    experiment_directory = Path(experiment_directory)
    scenario_path = Path(scenario_path)
    document = _read_json(experiment_directory / EVIDENCE_PATH)
    try:
        validate_evidence_v3(document)
    except EvidenceContractError as error:
        raise FaultEvidenceV3VerificationError(
            f"Evidence v3 contract validation failed: {error}"
        ) from error

    # Determine the reviewed class from the scenario only in this
    # independent verification layer. The rule engine never receives it.
    scenario_document = yaml.safe_load(
        scenario_path.read_text(encoding="utf-8")
    )
    fault_type = scenario_document["scenario"]["fault"]["type"]
    if fault_type not in FAULT_FEATURES:
        raise FaultEvidenceV3VerificationError(
            "P6-R4 verifier received an unsupported fault class."
        )
    binding = load_phase6_scenario(scenario_path, fault_type)
    profile = binding.profile
    _require_profile_binding(document, profile)
    if document["features"] != FAULT_FEATURES[fault_type]:
        raise FaultEvidenceV3VerificationError(
            f"Evidence v3 does not match the frozen {fault_type} signature."
        )
    expected_availability = {
        name: (
            "structurally_unavailable"
            if fault_type == "interface_down"
            and name in STRUCTURAL_FEATURES
            else "observed"
        )
        for name in EVIDENCE_V3_FEATURE_NAMES
    }
    if document["availability"] != expected_availability:
        raise FaultEvidenceV3VerificationError(
            "Evidence v3 availability does not match the fault signature."
        )

    expected_runtime = {
        "source_default_gateway_on_source": (
            binding.parameters["wrong_gateway"]
            if fault_type == "wrong_default_gateway"
            else profile.source_gateway_address
        ),
        "route_next_hop_on_observer": (
            None
            if fault_type == "interface_down"
            else profile.expected_next_hop
        ),
        "observer_egress_oper_state": (
            "down" if fault_type == "interface_down" else "up"
        ),
        "matching_block_rule_id": (
            binding.parameters["rule_tag"]
            if fault_type == "acl_block"
            else None
        ),
    }
    if any(
        document.get(name) != value
        for name, value in expected_runtime.items()
    ):
        raise FaultEvidenceV3VerificationError(
            "Evidence v3 raw runtime fields drifted from the fault."
        )
    raw_hashes = _verify_raw(
        experiment_directory,
        document,
        fault_type,
    )
    status = _read_json(experiment_directory / STATUS_PATH)
    expected_status = {
        "collector": "RoleNeutralEvidenceCollectorV3",
        "status": "COLLECTION_COMPLETED",
        "evidence_schema_version": 3,
        "probe_artifact_count": len(FAULT_RAW_ARTIFACTS[fault_type]),
        "observed_feature_count": (
            8 if fault_type == "interface_down" else 10
        ),
        "structural_unavailable_count": (
            2 if fault_type == "interface_down" else 0
        ),
        "collection_unavailable_count": 0,
        "topology_id": profile.topology_id,
        "direction": profile.direction,
    }
    if any(status.get(name) != value for name, value in expected_status.items()):
        raise FaultEvidenceV3VerificationError(
            "collector_status does not match the P6-R4 gate."
        )
    return {
        "status": "P6_R4_FAULT_EVIDENCE_V3_VERIFIED",
        "fault_type": fault_type,
        "topology_id": profile.topology_id,
        "direction": profile.direction,
        "feature_count": 10,
        "observed_feature_count": expected_status[
            "observed_feature_count"
        ],
        "structural_unavailable_count": expected_status[
            "structural_unavailable_count"
        ],
        "raw_artifact_count": len(raw_hashes),
        "evidence_sha256": _sha256(
            experiment_directory / EVIDENCE_PATH
        ),
        "collector_status_sha256": _sha256(
            experiment_directory / STATUS_PATH
        ),
        "raw_artifact_sha256": raw_hashes,
    }
