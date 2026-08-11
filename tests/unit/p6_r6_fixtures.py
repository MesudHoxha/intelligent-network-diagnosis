from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.phase6.contracts import FEATURE_ORDER
from src.planning.fault_taxonomy import EXPECTED_SIGNATURES


GROUPS = {
    "train": "CTX_P6_E01_TOP01_LINEAR_SOURCE_EDGE",
    "validation": "CTX_P6_E04_TOP02_DUAL_TRANSIT_SELECTED_ARM",
    "test": "CTX_P6_E02_TOP02_CHAIN_OBSERVER_EDGE",
}


def method_input(
    fault_type: str = "no_fault",
    *,
    partition: str = "validation",
    sample_id: str | None = None,
) -> dict[str, Any]:
    identity = sample_id or f"sample-{fault_type}"
    signature = tuple(EXPECTED_SIGNATURES[fault_type])
    features = dict(zip(FEATURE_ORDER, signature, strict=True))
    availability = {
        name: "structurally_unavailable" if value == "unavailable" else "observed"
        for name, value in features.items()
    }
    return {
        "schema_version": 1,
        "input_id": identity,
        "sample_id": identity,
        "partition": partition,
        "split_group_id": GROUPS[partition],
        "topology_id": "TOP_01",
        "direction": "hosta_to_hostb",
        "source_node": "hosta",
        "route_observer_node": "r1",
        "transit_node": "r2",
        "destination_prefix": "10.10.2.0/24",
        "mask_id": None,
        "features": features,
        "availability": availability,
        "provenance": {
            "dataset_row_sha256": "a" * 64,
            "evidence_path": f"data/raw/{identity}/parsed/evidence.json",
            "evidence_sha256": "b" * 64,
        },
    }


def target_for(value: dict[str, Any], fault_type: str) -> dict[str, Any]:
    if fault_type == "no_fault":
        category = location = prefix = None
    else:
        category = (
            "link"
            if fault_type == "interface_down"
            else "access_control"
            if fault_type == "acl_block"
            else "routing"
        )
        location = value["source_node"] if fault_type == "wrong_default_gateway" else value[
            "route_observer_node"
        ]
        prefix = value["destination_prefix"]
    return {
        "input_id": value["input_id"],
        "sample_id": value["sample_id"],
        "labels": {
            "fault_category": category,
            "fault_type": fault_type,
            "fault_location": location,
            "affected_prefix": prefix,
        },
    }


def six_class_inputs(
    *, partition: str = "validation", repetitions: int = 1
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inputs: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for fault_type in EXPECTED_SIGNATURES:
        for repetition in range(repetitions):
            value = method_input(
                fault_type,
                partition=partition,
                sample_id=f"{partition}-{fault_type}-{repetition}",
            )
            inputs.append(value)
            targets.append(target_for(value, fault_type))
    return inputs, targets


def clone(value: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(value)

