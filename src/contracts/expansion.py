from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_PATHS = {
    "topology_context_v1": "schemas/topology_context_v1.schema.json",
    "collector_run_v1": "schemas/collector_run_v1.schema.json",
    "evidence_v4": "schemas/evidence_v4.schema.json",
    "feature_catalog_v1": "schemas/feature_catalog_v1.schema.json",
    "feature_vector_v2": "schemas/feature_vector_v2.schema.json",
    "dataset_row_v4": "schemas/dataset_row_v4.schema.json",
    "diagnosis_result_v2": "schemas/diagnosis_result_v2.schema.json",
    "evidence_mask_plan_v2": "schemas/evidence_mask_plan_v2.schema.json",
}

FROZEN_P6_MASKS = {
    "mask_source_gateway_family": (
        "source_expected_gateway_reachable",
        "source_default_gateway_matches_expected",
    ),
    "mask_route_family": (
        "route_to_destination_exists_on_observer",
        "route_next_hop_matches_expected",
        "route_next_hop_reachable_from_observer",
    ),
    "mask_interface_state": ("observer_egress_interface_oper_up",),
    "mask_policy_state": ("flow_blocked_by_policy",),
}


class ExpansionContractError(ValueError):
    """Raised when an X1 expansion contract fails closed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ExpansionContractError(message)


def _load_schema(repository_root: Path, contract_name: str) -> dict[str, Any]:
    try:
        relative_path = SCHEMA_PATHS[contract_name]
    except KeyError as error:
        raise ExpansionContractError(
            f"Unknown expansion contract: {contract_name}"
        ) from error
    value = json.loads(
        (repository_root / relative_path).read_text(encoding="utf-8")
    )
    _require(isinstance(value, dict), f"Schema is not an object: {relative_path}")
    return value


def validate_schema_contract(
    contract_name: str,
    value: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    schema = _load_schema(repository_root, contract_name)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        path = ".".join(str(part) for part in errors[0].path)
        location = f" at {path}" if path else ""
        raise ExpansionContractError(
            f"{contract_name} schema validation failed{location}: "
            + errors[0].message
        )


def validate_feature_catalog_v1(
    catalog: Mapping[str, Any],
    *,
    repository_root: Path,
) -> dict[str, Mapping[str, Any]]:
    validate_schema_contract(
        "feature_catalog_v1", catalog, repository_root=repository_root
    )
    features = catalog["features"]
    assert isinstance(features, list)
    index: dict[str, Mapping[str, Any]] = {}
    for row in features:
        assert isinstance(row, Mapping)
        feature_id = row["feature_id"]
        assert isinstance(feature_id, str)
        _require(feature_id not in index, f"Duplicate feature_id: {feature_id}")
        lifecycle = row["lifecycle"]
        source = row["source_feature_v3"]
        if lifecycle == "FROZEN_BASELINE":
            _require(
                row["target_phase"] == "BASELINE" and source == feature_id,
                f"Frozen feature {feature_id} must map to itself in v3.",
            )
        else:
            _require(
                row["target_phase"] != "BASELINE" and source is None,
                f"Planned feature {feature_id} cannot claim a v3 source.",
            )
        index[feature_id] = row
    return index


def validate_topology_context_v1(
    context: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    validate_schema_contract(
        "topology_context_v1", context, repository_root=repository_root
    )
    nodes = context["nodes"]
    links = context["links"]
    assert isinstance(nodes, list) and isinstance(links, list)
    node_ids = [row["node_id"] for row in nodes]
    _require(len(node_ids) == len(set(node_ids)), "Topology node IDs must be unique.")
    link_ids = [row["link_id"] for row in links]
    _require(len(link_ids) == len(set(link_ids)), "Topology link IDs must be unique.")
    node_set = set(node_ids)
    roles = context["observation_roles"]
    assert isinstance(roles, Mapping)
    referenced_roles = {
        roles["source"],
        roles["destination"],
        *roles["observers"],
    }
    _require(
        referenced_roles <= node_set,
        "Topology observation roles must reference declared nodes.",
    )
    for link in links:
        endpoint_ids = [row["node_id"] for row in link["endpoints"]]
        _require(
            len(set(endpoint_ids)) == 2 and set(endpoint_ids) <= node_set,
            f"Link {link['link_id']} must connect two declared nodes.",
        )


def validate_collector_run_v1(
    run: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    validate_schema_contract(
        "collector_run_v1", run, repository_root=repository_root
    )
    status = run["status"]
    errors = run["errors"]
    if status in {"completed", "not_applicable"}:
        _require(not errors, f"Collector status {status} cannot claim errors.")
    if status == "failed":
        _require(bool(errors), "A failed collector run must record an error.")


def _value_matches_type(value: object, value_type: str) -> bool:
    if value_type == "boolean":
        return value is True or value is False
    if value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, str)


def validate_evidence_v4(
    evidence: Mapping[str, Any],
    catalog: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    validate_schema_contract("evidence_v4", evidence, repository_root=repository_root)
    catalog_index = validate_feature_catalog_v1(
        catalog, repository_root=repository_root
    )
    runs = evidence["collector_runs"]
    assert isinstance(runs, list)
    run_ids: set[str] = set()
    features_by_run: dict[str, set[str]] = {}
    owner_by_feature: dict[str, str] = {}
    artifacts_by_run: dict[str, set[tuple[str, str]]] = {}
    for run in runs:
        assert isinstance(run, Mapping)
        validate_collector_run_v1(run, repository_root=repository_root)
        collector_id = run["collector_id"]
        assert isinstance(collector_id, str)
        _require(collector_id not in run_ids, "Evidence collector IDs must be unique.")
        run_ids.add(collector_id)
        run_features = set(run["feature_ids"])
        _require(
            run_features <= set(catalog_index),
            f"Collector run {collector_id} references unknown features.",
        )
        overlap = run_features & set(owner_by_feature)
        _require(
            not overlap,
            "Evidence features cannot have multiple collector owners: "
            + ", ".join(sorted(overlap)),
        )
        features_by_run[collector_id] = run_features
        for feature_id in run_features:
            owner_by_feature[feature_id] = collector_id
        artifacts_by_run[collector_id] = {
            (artifact["path"], artifact["sha256"])
            for artifact in run["raw_artifacts"]
        }

    observations = evidence["observations"]
    assert isinstance(observations, Mapping)
    _require(
        set(observations) <= set(catalog_index),
        "Evidence v4 observations must exist in Feature Catalog v1.",
    )
    for feature_id, observation in observations.items():
        assert isinstance(observation, Mapping)
        definition = catalog_index[feature_id]
        _require(
            observation["value_type"] == definition["value_type"],
            f"Observation type drifted for {feature_id}.",
        )
        availability = observation["availability"]
        value = observation["value"]
        raw_path = observation["raw_artifact"]
        raw_hash = observation["raw_artifact_sha256"]
        if availability == "observed":
            _require(
                _value_matches_type(value, str(definition["value_type"])),
                f"Observed value has the wrong type for {feature_id}.",
            )
        else:
            _require(value is None, f"Unavailable value must be null: {feature_id}")
        if availability in {"observed", "collection_unavailable"}:
            _require(
                isinstance(raw_path, str) and isinstance(raw_hash, str),
                f"Observed or failed collection requires raw provenance: {feature_id}",
            )
        else:
            _require(
                raw_path is None and raw_hash is None,
                f"Unrequested or structural evidence cannot claim raw data: {feature_id}",
            )
        collector_id = observation["collector_id"]
        _require(
            collector_id in features_by_run
            and feature_id in features_by_run[collector_id],
            f"Collector run does not own observation {feature_id}.",
        )
        if isinstance(raw_path, str) and isinstance(raw_hash, str):
            _require(
                (raw_path, raw_hash) in artifacts_by_run[collector_id],
                f"Collector run raw provenance does not cover {feature_id}.",
            )

    _require(
        set(owner_by_feature) == set(observations),
        "Collector-run feature IDs must exactly match Evidence v4 observations.",
    )

    compatibility = evidence["compatibility"]
    assert isinstance(compatibility, Mapping)
    if compatibility["origin"] == "read_only_v3_adapter":
        _require(
            compatibility["source_schema_version"] == 3
            and isinstance(compatibility["source_artifact_sha256"], str),
            "The v3 adapter must bind to an immutable Evidence v3 hash.",
        )
    else:
        _require(
            compatibility["source_schema_version"] is None
            and compatibility["source_artifact_sha256"] is None,
            "Native Evidence v4 cannot claim a legacy source artifact.",
        )


def validate_feature_vector_v2(
    vector: Mapping[str, Any],
    catalog: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    validate_schema_contract(
        "feature_vector_v2", vector, repository_root=repository_root
    )
    index = validate_feature_catalog_v1(catalog, repository_root=repository_root)
    _require(
        vector["catalog_id"] == catalog["catalog_id"],
        "Feature Vector v2 catalog_id drifted.",
    )
    values = vector["values"]
    assert isinstance(values, Mapping)
    _require(set(values) <= set(index), "Feature Vector v2 has unknown features.")
    masked = False
    for feature_id, item in values.items():
        assert isinstance(item, Mapping)
        availability = item["availability"]
        value = item["value"]
        if availability == "observed":
            _require(
                _value_matches_type(value, str(index[feature_id]["value_type"])),
                f"Feature Vector v2 value type drifted: {feature_id}",
            )
        else:
            _require(value is None, f"Unavailable vector value must be null: {feature_id}")
        masked = masked or availability == "masked_missing"
    _require(
        masked == (vector["mask_id"] is not None),
        "Feature Vector v2 mask_id must match masked_missing values.",
    )


def validate_evidence_mask_plan_v2(
    plan: Mapping[str, Any],
    catalog: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    validate_schema_contract(
        "evidence_mask_plan_v2", plan, repository_root=repository_root
    )
    index = validate_feature_catalog_v1(catalog, repository_root=repository_root)
    _require(plan["catalog_id"] == catalog["catalog_id"], "Mask catalog drifted.")
    masks = plan["masks"]
    assert isinstance(masks, list)
    mask_index: dict[str, tuple[str, ...]] = {}
    for row in masks:
        mask_id = row["mask_id"]
        _require(mask_id not in mask_index, f"Duplicate mask_id: {mask_id}")
        feature_ids = tuple(row["feature_ids"])
        _require(
            set(feature_ids) <= set(index),
            f"Mask {mask_id} references unknown catalog features.",
        )
        mask_index[mask_id] = feature_ids
    for mask_id, expected in FROZEN_P6_MASKS.items():
        _require(
            mask_index.get(mask_id) == expected,
            f"Frozen Phase 6 mask drifted: {mask_id}",
        )


def validate_dataset_row_v4(
    row: Mapping[str, Any],
    catalog: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    validate_schema_contract("dataset_row_v4", row, repository_root=repository_root)
    vector = row["feature_vector"]
    assert isinstance(vector, Mapping)
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    metadata = row["metadata"]
    assert isinstance(metadata, Mapping)
    _require(row["sample_id"] == metadata["experiment_id"], "sample_id drifted.")
    values = vector["values"]
    quality = row["quality"]
    observed = sum(item["availability"] == "observed" for item in values.values())
    masked = sum(
        item["availability"] == "masked_missing" for item in values.values()
    )
    unavailable = len(values) - observed - masked
    _require(
        quality["observed_feature_count"] == observed
        and quality["masked_missing_count"] == masked
        and quality["unavailable_feature_count"] == unavailable,
        "Dataset Row v4 quality counts drifted from Feature Vector v2.",
    )
    provenance = row["provenance"]
    assert isinstance(provenance, Mapping)
    _require(
        (vector["mask_id"] is None)
        == (provenance["evidence_mask_plan_id"] is None),
        "A masked Dataset Row v4 must bind to Evidence Mask Plan v2.",
    )


def validate_diagnosis_result_v2(
    result: Mapping[str, Any],
    *,
    repository_root: Path,
) -> None:
    validate_schema_contract(
        "diagnosis_result_v2", result, repository_root=repository_root
    )
    candidates = result["ranked_candidates"]
    assert isinstance(candidates, list)
    labels = [row["fault_type"] for row in candidates]
    _require(len(labels) == len(set(labels)), "Diagnosis candidates must be unique.")
    _require(
        all(
            candidates[index]["score"] >= candidates[index + 1]["score"]
            for index in range(len(candidates) - 1)
        ),
        "Diagnosis candidates must be sorted by descending score.",
    )
    prediction = result["prediction"]
    if result["status"] == "diagnosed":
        _require(
            bool(candidates) and prediction == candidates[0],
            "A diagnosed result must select its first ranked candidate.",
        )
    else:
        _require(prediction is None, "An abstention cannot claim a prediction.")
