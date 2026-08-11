from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.campaign.phase6_plan import CLASS_ORDER
from src.contracts.evidence import EvidenceContractError
from src.contracts.evidence_v3 import EVIDENCE_V3_FEATURE_NAMES, validate_evidence_v3
from src.dataset.contract_v3 import (
    MISSING_EVIDENCE_MASKS_V1,
    DatasetRowV3ContractError,
    validate_dataset_row_v3,
)


METHOD_INPUT_SCHEMA_VERSION = 1
METHOD_PREDICTION_SCHEMA_VERSION = 1
FEATURE_ORDER = tuple(EVIDENCE_V3_FEATURE_NAMES)
MASK_ORDER = tuple(MISSING_EVIDENCE_MASKS_V1)
PARTITION_NAMES = ("train", "validation", "test")
TRISTATE_VALUES = {"true", "false", "unavailable"}
AVAILABILITY_STATES = {
    "observed",
    "structurally_unavailable",
    "collection_unavailable",
    "masked_missing",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
METHOD_IDS = (
    "rule_based_p6_v1",
    "machine_learning_p6_v1",
    "hybrid_p6_v1",
)
PREDICTION_STATUSES = {
    "RESOLVED",
    "INSUFFICIENT_EVIDENCE",
    "ABSTAINED",
    "NO_RULE_MATCH",
}


class Phase6MethodContractError(ValueError):
    """Raised when a Phase 6 method artifact violates its frozen contract."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if not path.is_file():
        raise Phase6MethodContractError(f"Required file does not exist: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise Phase6MethodContractError(f"Required JSON does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise Phase6MethodContractError(
            f"Invalid JSON in {path}: {error.msg}"
        ) from error
    if not isinstance(value, dict):
        raise Phase6MethodContractError(f"Expected a JSON object in: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def jsonl_payload(records: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )


def write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> str:
    payload = jsonl_payload(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return sha256_bytes(payload.encode("utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [record for record, _ in read_jsonl_with_hashes(path)]


def read_jsonl_with_hashes(path: Path) -> list[tuple[dict[str, Any], str]]:
    if not path.is_file():
        raise Phase6MethodContractError(f"Required JSONL does not exist: {path}")
    records: list[tuple[dict[str, Any], str]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise Phase6MethodContractError(
                f"Invalid JSON on line {line_number} of {path}: {error.msg}"
            ) from error
        if not isinstance(value, dict):
            raise Phase6MethodContractError(
                f"Line {line_number} of {path} is not an object."
            )
        records.append((value, sha256_bytes(line.encode("utf-8"))))
    return records


def _require_string(value: object, reference: str) -> str:
    if not isinstance(value, str) or not value:
        raise Phase6MethodContractError(f"{reference} must be a non-empty string.")
    return value


def _validate_digest(value: object, reference: str) -> str:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise Phase6MethodContractError(
            f"{reference} must be a lowercase SHA-256 digest."
        )
    return value


def validate_method_input(value: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "input_id",
        "sample_id",
        "partition",
        "split_group_id",
        "topology_id",
        "direction",
        "source_node",
        "route_observer_node",
        "transit_node",
        "destination_prefix",
        "mask_id",
        "features",
        "availability",
        "provenance",
    }
    if set(value) != required or value.get("schema_version") != 1:
        raise Phase6MethodContractError("Method input keys/version drifted.")
    input_id = _require_string(value["input_id"], "input_id")
    sample_id = _require_string(value["sample_id"], "sample_id")
    if value["partition"] not in PARTITION_NAMES:
        raise Phase6MethodContractError("Method input partition is invalid.")
    for name in (
        "split_group_id",
        "topology_id",
        "direction",
        "source_node",
        "route_observer_node",
        "transit_node",
        "destination_prefix",
    ):
        _require_string(value[name], name)
    features = value["features"]
    availability = value["availability"]
    if not isinstance(features, Mapping) or set(features) != set(FEATURE_ORDER):
        raise Phase6MethodContractError("Method input feature whitelist drifted.")
    if not isinstance(availability, Mapping) or set(availability) != set(
        FEATURE_ORDER
    ):
        raise Phase6MethodContractError("Method input availability whitelist drifted.")
    for name in FEATURE_ORDER:
        feature_value = features[name]
        state = availability[name]
        if feature_value not in TRISTATE_VALUES or state not in AVAILABILITY_STATES:
            raise Phase6MethodContractError(f"Invalid feature state for {name}.")
        if state == "observed" and feature_value not in {"true", "false"}:
            raise Phase6MethodContractError(f"Observed feature {name} is unavailable.")
        if state != "observed" and feature_value != "unavailable":
            raise Phase6MethodContractError(
                f"Unavailable feature {name} contains a value."
            )
    mask_id = value["mask_id"]
    masked = {
        name for name, state in availability.items() if state == "masked_missing"
    }
    if mask_id is None:
        if masked or input_id != sample_id:
            raise Phase6MethodContractError("Clean input mask identity drifted.")
    else:
        if mask_id not in MASK_ORDER or input_id != f"{sample_id}::{mask_id}":
            raise Phase6MethodContractError("Masked input identity is invalid.")
        allowed = set(MISSING_EVIDENCE_MASKS_V1[mask_id])
        if not masked or not masked <= allowed:
            raise Phase6MethodContractError("Masked input family is invalid.")
        if any(
            availability[name] == "observed"
            for name in MISSING_EVIDENCE_MASKS_V1[mask_id]
        ):
            raise Phase6MethodContractError(
                "A frozen mask left an observed family member unmasked."
            )
    provenance = value["provenance"]
    if not isinstance(provenance, Mapping) or set(provenance) != {
        "dataset_row_sha256",
        "evidence_path",
        "evidence_sha256",
    }:
        raise Phase6MethodContractError("Method input provenance drifted.")
    _validate_digest(provenance["dataset_row_sha256"], "dataset_row_sha256")
    _require_string(provenance["evidence_path"], "evidence_path")
    _validate_digest(provenance["evidence_sha256"], "evidence_sha256")


def validate_target(value: Mapping[str, Any]) -> None:
    if set(value) != {"input_id", "sample_id", "labels"}:
        raise Phase6MethodContractError("Target keys drifted.")
    _require_string(value["input_id"], "target.input_id")
    _require_string(value["sample_id"], "target.sample_id")
    labels = value["labels"]
    if not isinstance(labels, Mapping) or set(labels) != {
        "fault_category",
        "fault_type",
        "fault_location",
        "affected_prefix",
    }:
        raise Phase6MethodContractError("Target label contract drifted.")
    if labels["fault_type"] not in CLASS_ORDER:
        raise Phase6MethodContractError("Target fault_type is not a Phase 6 class.")


def validate_prediction(value: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "input_id",
        "sample_id",
        "method_id",
        "status",
        "predicted_fault_type",
        "confidence",
        "diagnosis",
        "reason",
    }
    if set(value) != required or value.get("schema_version") != 1:
        raise Phase6MethodContractError("Prediction keys/version drifted.")
    _require_string(value["input_id"], "prediction.input_id")
    _require_string(value["sample_id"], "prediction.sample_id")
    if value["method_id"] not in METHOD_IDS:
        raise Phase6MethodContractError("Prediction method_id is invalid.")
    status = value["status"]
    predicted = value["predicted_fault_type"]
    if status not in PREDICTION_STATUSES:
        raise Phase6MethodContractError("Prediction status is invalid.")
    if status == "RESOLVED":
        if predicted not in CLASS_ORDER:
            raise Phase6MethodContractError("Resolved prediction has no valid class.")
        confidence = value["confidence"]
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise Phase6MethodContractError("Resolved prediction confidence is invalid.")
        if not 0.0 <= float(confidence) <= 1.0:
            raise Phase6MethodContractError("Prediction confidence is outside [0,1].")
        diagnosis = value["diagnosis"]
        if not isinstance(diagnosis, Mapping) or set(diagnosis) != {
            "fault_type",
            "fault_category",
            "fault_location",
            "affected_prefix",
        }:
            raise Phase6MethodContractError("Resolved diagnosis is invalid.")
        if diagnosis["fault_type"] != predicted:
            raise Phase6MethodContractError("Diagnosis class differs from prediction.")
    elif predicted is not None or value["confidence"] is not None or value[
        "diagnosis"
    ] is not None:
        raise Phase6MethodContractError(
            "Unresolved prediction cannot contain class/confidence/diagnosis."
        )
    _require_string(value["reason"], "prediction.reason")


def _evidence_for_row(
    *,
    row: Mapping[str, Any],
    row_sha256: str,
    partition: str,
    evidence_path: Path,
    repository_root: Path,
) -> dict[str, Any]:
    try:
        validate_dataset_row_v3(dict(row))
    except DatasetRowV3ContractError as error:
        raise Phase6MethodContractError(f"Invalid Dataset Row v3: {error}") from error
    if row["provenance"]["mask_id"] is not None:
        raise Phase6MethodContractError("Method source must be a clean Dataset Row v3.")
    evidence = read_json(evidence_path)
    try:
        validate_evidence_v3(evidence)
    except EvidenceContractError as error:
        raise Phase6MethodContractError(f"Invalid source Evidence v3: {error}") from error
    observed_hash = sha256_file(evidence_path)
    if observed_hash != row["provenance"]["source_evidence_sha256"]:
        raise Phase6MethodContractError("Dataset Row v3 evidence binding drifted.")
    if row["features"] != {
        name: (
            "true"
            if evidence["features"][name] is True
            else "false"
            if evidence["features"][name] is False
            else "unavailable"
        )
        for name in FEATURE_ORDER
    }:
        raise Phase6MethodContractError("Dataset row and Evidence v3 features differ.")
    metadata = row["metadata"]
    for name in (
        "topology_id",
        "direction",
        "source_node",
        "route_observer_node",
        "transit_node",
    ):
        if metadata[name] != evidence[name]:
            raise Phase6MethodContractError(f"Evidence metadata mismatch: {name}")
    try:
        evidence_relative = evidence_path.resolve().relative_to(
            repository_root.resolve()
        )
    except ValueError as error:
        raise Phase6MethodContractError(
            "Evidence artifact escaped the repository root."
        ) from error
    method_input = {
        "schema_version": 1,
        "input_id": row["sample_id"],
        "sample_id": row["sample_id"],
        "partition": partition,
        "split_group_id": metadata["split_group_id"],
        "topology_id": metadata["topology_id"],
        "direction": metadata["direction"],
        "source_node": metadata["source_node"],
        "route_observer_node": metadata["route_observer_node"],
        "transit_node": metadata["transit_node"],
        "destination_prefix": evidence["destination_prefix"],
        "mask_id": None,
        "features": copy.deepcopy(row["features"]),
        "availability": copy.deepcopy(
            row["provenance"]["feature_availability"]
        ),
        "provenance": {
            "dataset_row_sha256": row_sha256,
            "evidence_path": evidence_relative.as_posix(),
            "evidence_sha256": observed_hash,
        },
    }
    validate_method_input(method_input)
    return method_input


def apply_method_input_mask(
    clean_input: Mapping[str, Any], mask_id: str
) -> dict[str, Any]:
    validate_method_input(clean_input)
    if clean_input["mask_id"] is not None or mask_id not in MASK_ORDER:
        raise Phase6MethodContractError("Mask requires a clean input and frozen ID.")
    masked = copy.deepcopy(dict(clean_input))
    masked["input_id"] = f"{clean_input['sample_id']}::{mask_id}"
    masked["mask_id"] = mask_id
    changed = 0
    for name in MISSING_EVIDENCE_MASKS_V1[mask_id]:
        if masked["availability"][name] == "observed":
            masked["features"][name] = "unavailable"
            masked["availability"][name] = "masked_missing"
            changed += 1
    if changed == 0:
        raise Phase6MethodContractError("Frozen mask changed no observed feature.")
    validate_method_input(masked)
    return masked


def build_partition_inputs(
    *,
    partition_path: Path,
    partition: str,
    repository_root: Path,
    raw_campaign_root: Path,
    group_to_slot: Mapping[str, str],
    include_masks: bool,
    expected_clean_rows: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if partition not in PARTITION_NAMES:
        raise Phase6MethodContractError("Unsupported partition.")
    source_records = read_jsonl_with_hashes(partition_path)
    if len(source_records) != expected_clean_rows:
        raise Phase6MethodContractError(
            f"{partition} must contain exactly {expected_clean_rows} clean rows."
        )
    clean_inputs: list[dict[str, Any]] = []
    clean_targets: list[dict[str, Any]] = []
    samples: set[str] = set()
    groups: Counter[str] = Counter()
    classes: Counter[str] = Counter()
    for row, row_sha256 in source_records:
        sample_id = row.get("sample_id")
        group_id = row.get("metadata", {}).get("split_group_id")
        if not isinstance(sample_id, str) or sample_id in samples:
            raise Phase6MethodContractError("Duplicate or invalid source sample_id.")
        if not isinstance(group_id, str) or group_id not in group_to_slot:
            raise Phase6MethodContractError("Source split group is not frozen.")
        slot = group_to_slot[group_id]
        evidence_path = (
            raw_campaign_root / slot / sample_id / "parsed" / "evidence.json"
        )
        method_input = _evidence_for_row(
            row=row,
            row_sha256=row_sha256,
            partition=partition,
            evidence_path=evidence_path,
            repository_root=repository_root,
        )
        target = {
            "input_id": sample_id,
            "sample_id": sample_id,
            "labels": copy.deepcopy(row["labels"]),
        }
        validate_target(target)
        clean_inputs.append(method_input)
        clean_targets.append(target)
        samples.add(sample_id)
        groups[group_id] += 1
        classes[row["labels"]["fault_type"]] += 1
    clean_inputs.sort(key=lambda item: item["input_id"])
    clean_targets.sort(key=lambda item: item["input_id"])
    inputs = list(clean_inputs)
    targets = list(clean_targets)
    if include_masks:
        target_by_sample = {item["sample_id"]: item for item in clean_targets}
        for clean_input in clean_inputs:
            for mask_id in MASK_ORDER:
                masked = apply_method_input_mask(clean_input, mask_id)
                target = copy.deepcopy(target_by_sample[clean_input["sample_id"]])
                target["input_id"] = masked["input_id"]
                validate_target(target)
                inputs.append(masked)
                targets.append(target)
    inputs.sort(key=lambda item: item["input_id"])
    targets.sort(key=lambda item: item["input_id"])
    if [item["input_id"] for item in inputs] != [
        item["input_id"] for item in targets
    ]:
        raise Phase6MethodContractError("Method inputs and targets are misaligned.")
    expected_total = expected_clean_rows * (1 + len(MASK_ORDER) if include_masks else 1)
    if len(inputs) != expected_total:
        raise Phase6MethodContractError("Method input expansion count drifted.")
    summary = {
        "partition": partition,
        "source_path": str(partition_path.resolve()),
        "source_sha256": sha256_file(partition_path),
        "clean_input_count": expected_clean_rows,
        "masked_input_count": expected_clean_rows * len(MASK_ORDER)
        if include_masks
        else 0,
        "total_input_count": expected_total,
        "group_counts": dict(sorted(groups.items())),
        "class_counts": {label: classes[label] for label in CLASS_ORDER},
        "mask_counts": {
            mask_id: expected_clean_rows if include_masks else 0
            for mask_id in MASK_ORDER
        },
    }
    return inputs, targets, summary
