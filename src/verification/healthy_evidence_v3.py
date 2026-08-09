from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from src.collection.evidence_collector_v3 import (
    EVIDENCE_PATH,
    STATUS_PATH,
    load_observation_profile_v2,
)
from src.contracts.evidence import EvidenceContractError
from src.contracts.evidence_v3 import (
    EVIDENCE_V3_FEATURE_NAMES,
    validate_evidence_v3,
)
from src.contracts.observation_profile_v2 import ObservationProfileV2


class HealthyEvidenceV3VerificationError(RuntimeError):
    """Raised when the healthy Evidence v3 runtime gate fails."""


HEALTHY_FEATURES: dict[str, bool] = {
    "source_expected_gateway_reachable": True,
    "source_default_gateway_matches_expected": True,
    "destination_reachable": True,
    "route_to_destination_exists_on_observer": True,
    "route_next_hop_matches_expected": True,
    "route_next_hop_reachable_from_observer": True,
    "expected_next_hop_reachable_from_observer": True,
    "observer_egress_interface_oper_up": True,
    "destination_reachable_from_transit": True,
    "flow_blocked_by_policy": False,
}

EXPECTED_RAW_ARTIFACTS = {
    "raw/v3/source_expected_gateway_ping_v3.json",
    "raw/v3/source_default_route_v3.json",
    "raw/v3/source_destination_ping_v3.json",
    "raw/v3/observer_destination_route_v3.json",
    "raw/v3/observer_installed_next_hop_ping_v3.json",
    "raw/v3/observer_expected_next_hop_ping_v3.json",
    "raw/v3/observer_egress_link_v3.json",
    "raw/v3/transit_destination_ping_v3.json",
    "raw/v3/observer_forward_policy_v3.json",
}


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HealthyEvidenceV3VerificationError(
            f"Cannot read valid JSON object: {path}"
        ) from error
    if not isinstance(value, dict):
        raise HealthyEvidenceV3VerificationError(
            f"JSON artifact must be an object: {path}"
        )
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise HealthyEvidenceV3VerificationError(
            f"Cannot hash artifact: {path}"
        ) from error


def _require_profile_binding(
    evidence: dict[str, Any],
    profile: ObservationProfileV2,
) -> None:
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
        "source_expected_gateway_address": profile.source_gateway_address,
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
        raise HealthyEvidenceV3VerificationError(
            "Evidence v3 does not match the reviewed profile: "
            + json.dumps(drift, sort_keys=True)
        )


def _verify_raw_provenance(
    experiment_directory: Path,
    evidence: dict[str, Any],
) -> dict[str, str]:
    observed_paths: dict[str, str] = {}
    probes = evidence["probes"]
    for feature_name in EVIDENCE_V3_FEATURE_NAMES:
        probe = probes[feature_name]
        relative_path = probe["raw_artifact"]
        digest = probe["raw_artifact_sha256"]
        if not isinstance(relative_path, str) or not isinstance(digest, str):
            raise HealthyEvidenceV3VerificationError(
                f"Healthy feature lacks raw provenance: {feature_name}"
            )
        normalized = PurePosixPath(relative_path)
        if (
            normalized.is_absolute()
            or ".." in normalized.parts
            or str(normalized) != relative_path
        ):
            raise HealthyEvidenceV3VerificationError(
                f"Unsafe raw artifact path: {relative_path}"
            )
        artifact_path = experiment_directory / relative_path
        actual_digest = _sha256(artifact_path)
        if actual_digest != digest:
            raise HealthyEvidenceV3VerificationError(
                f"Raw artifact SHA-256 mismatch: {relative_path}"
            )
        previous = observed_paths.setdefault(relative_path, digest)
        if previous != digest:
            raise HealthyEvidenceV3VerificationError(
                f"Conflicting SHA-256 bindings: {relative_path}"
            )

    if set(observed_paths) != EXPECTED_RAW_ARTIFACTS:
        raise HealthyEvidenceV3VerificationError(
            "Healthy runtime gate must contain the exact nine raw probes."
        )
    actual_paths = {
        path.relative_to(experiment_directory).as_posix()
        for path in (experiment_directory / "raw/v3").glob("*.json")
        if path.is_file()
    }
    if actual_paths != EXPECTED_RAW_ARTIFACTS:
        raise HealthyEvidenceV3VerificationError(
            "raw/v3 contains an unexpected or missing JSON artifact."
        )
    for relative_path in sorted(actual_paths):
        raw = _read_json_object(experiment_directory / relative_path)
        if raw.get("return_code") != 0:
            raise HealthyEvidenceV3VerificationError(
                f"Healthy raw probe did not complete: {relative_path}"
            )
    return dict(sorted(observed_paths.items()))


def verify_healthy_evidence_v3(
    experiment_directory: Path,
    scenario_path: Path,
) -> dict[str, Any]:
    experiment_directory = Path(experiment_directory)
    profile = load_observation_profile_v2(Path(scenario_path))
    evidence_path = experiment_directory / EVIDENCE_PATH
    status_path = experiment_directory / STATUS_PATH
    evidence = _read_json_object(evidence_path)
    try:
        validate_evidence_v3(evidence)
    except EvidenceContractError as error:
        raise HealthyEvidenceV3VerificationError(
            f"Evidence v3 contract validation failed: {error}"
        ) from error
    _require_profile_binding(evidence, profile)

    if evidence["features"] != HEALTHY_FEATURES:
        raise HealthyEvidenceV3VerificationError(
            "Evidence v3 does not match the frozen healthy signature."
        )
    if set(evidence["availability"].values()) != {"observed"}:
        raise HealthyEvidenceV3VerificationError(
            "All ten healthy features must be observed."
        )
    if evidence["source_default_gateway_on_source"] != (
        profile.source_gateway_address
    ):
        raise HealthyEvidenceV3VerificationError(
            "The source default route does not use the expected gateway."
        )
    if evidence["route_next_hop_on_observer"] != profile.expected_next_hop:
        raise HealthyEvidenceV3VerificationError(
            "The installed observer route uses an unexpected next-hop."
        )
    if evidence["observer_egress_oper_state"] != "up":
        raise HealthyEvidenceV3VerificationError(
            "The observer egress interface is not operationally up."
        )
    if evidence["matching_block_rule_id"] is not None:
        raise HealthyEvidenceV3VerificationError(
            "Healthy evidence unexpectedly contains a matching block rule."
        )

    raw_hashes = _verify_raw_provenance(experiment_directory, evidence)
    status = _read_json_object(status_path)
    expected_status = {
        "collector": "RoleNeutralEvidenceCollectorV3",
        "status": "COLLECTION_COMPLETED",
        "evidence_schema_version": 3,
        "probe_artifact_count": 9,
        "observed_feature_count": 10,
        "structural_unavailable_count": 0,
        "collection_unavailable_count": 0,
        "topology_id": profile.topology_id,
        "direction": profile.direction,
    }
    for name, expected in expected_status.items():
        if status.get(name) != expected:
            raise HealthyEvidenceV3VerificationError(
                f"collector_status.{name} does not match the gate."
            )

    return {
        "status": "P6_R3_HEALTHY_EVIDENCE_V3_VERIFIED",
        "topology_id": profile.topology_id,
        "direction": profile.direction,
        "feature_count": len(HEALTHY_FEATURES),
        "observed_feature_count": 10,
        "raw_artifact_count": len(raw_hashes),
        "evidence_sha256": _sha256(evidence_path),
        "collector_status_sha256": _sha256(status_path),
        "raw_artifact_sha256": raw_hashes,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the P6-R3 healthy Evidence v3 runtime gate."
    )
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--scenario", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        summary = verify_healthy_evidence_v3(
            arguments.experiment,
            arguments.scenario,
        )
    except (
        HealthyEvidenceV3VerificationError,
        OSError,
        ValueError,
    ) as error:
        print(f"[ERROR] {error}")
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
