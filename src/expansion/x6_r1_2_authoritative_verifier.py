"""Independent, future-only acceptance verifier for authoritative X6-R1 trees.

This is deliberately stricter than the historical runner. It is a contract
for a future authorised pilot; it must never reinterpret the consumed X6-R1
diagnostic tree as acceptance evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from src.collection.x6_performance_collector import exact_fault_hierarchy, exact_noqueue
from src.collection.x6_r0_3_pre_runtime_validation import validate_threshold_manifest
from src.contracts.expansion import validate_evidence_v4, validate_feature_vector_v2
from src.expansion.x6_r1_gate import X6R1GateError, verify_x6_r1_source
from src.expansion.x6_r1_performance_rule import FEATURES, predicates_from_vector


TOPOLOGY_SHA256 = "9decd096606a7af5d6aa5a7de6c5d406c286e12094825cbc88b3fb59a2e37b14"
RAW_DIRECTORY = Path("raw/v4/performance_collector")
WINDOWS = tuple((phase, index) for phase, count in (("baseline", 10), ("fault", 3), ("restored", 3)) for index in range(1, count + 1))


def _fail(message: str) -> None:
    raise X6R1GateError("X6-R1 future-authoritative verifier: " + message)


def _load(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _fail("cannot read required artifact " + str(path))
        raise AssertionError from error
    if not isinstance(value, dict):
        _fail("required artifact is not an object: " + str(path))
    return value


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required(root: Path, relative: str) -> dict[str, object]:
    return _load(root / relative)


def _check_raw_inventory(root: Path, hashes: Mapping[str, object]) -> list[dict[str, object]]:
    artifacts = hashes.get("artifacts")
    expected = {str(RAW_DIRECTORY / f"{phase}_window_{index:02d}.json") for phase, index in WINDOWS}
    expected.add(str(RAW_DIRECTORY / "fault_aggregate_provenance.json"))
    if not isinstance(artifacts, dict) or set(artifacts) != expected:
        _fail("raw inventory must be exactly sixteen windows plus aggregate provenance")
    rows: list[dict[str, object]] = []
    for name, digest in artifacts.items():
        if not isinstance(digest, str) or not (root / name).is_file() or _hash(root / name) != digest:
            _fail("raw artifact hash mismatch: " + str(name))
    for phase, index in WINDOWS:
        row = _required(root, str(RAW_DIRECTORY / f"{phase}_window_{index:02d}.json"))
        if row.get("window_id") != f"{phase}-{index:02d}" or row.get("phase") != phase:
            _fail("window phase/order identity mismatch")
        elapsed = row.get("elapsed_seconds")
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or elapsed <= 0:
            _fail("window elapsed time invalid")
        if phase == "fault":
            if row.get("queue_drop_derivation") != "COUNTER_DELTA_CHILD_PFIFO_20" or not exact_fault_hierarchy(row.get("qdisc_before", {})) or not exact_fault_hierarchy(row.get("qdisc_after", {})):
                _fail("fault queue-drop provenance/hierarchy invalid")
        else:
            if row.get("queue_drop_derivation") != "STRUCTURAL_ZERO_NO_MANAGED_QUEUE" or not exact_noqueue(row.get("qdisc_before", {}), row.get("filters_before", [])) or not exact_noqueue(row.get("qdisc_after", {}), row.get("filters_after", [])):
                _fail("healthy structural queue-zero provenance invalid")
        if row.get("startup_skew_seconds") is None or float(row["startup_skew_seconds"]) > 0.250:
            _fail("traffic timing/skew invalid")
        rows.append(row)
    aggregate = _required(root, str(RAW_DIRECTORY / "fault_aggregate_provenance.json"))
    if aggregate.get("window_ids") != ["fault-01", "fault-02", "fault-03"] or not isinstance(aggregate.get("input_sha256"), dict):
        _fail("fault aggregate provenance invalid")
    for index in range(1, 4):
        name = str(RAW_DIRECTORY / f"fault_window_{index:02d}.json")
        if aggregate["input_sha256"].get(name) != artifacts[name]:
            _fail("fault aggregate raw-chain mismatch")
    return rows


def _check_lifecycle(root: Path, rows: list[dict[str, object]], threshold: Mapping[str, object]) -> None:
    lifecycle = _required(root, "validation/authoritative_acceptance_v1.json")
    expected_ids = [f"{phase}-{index:02d}" for phase, index in WINDOWS]
    if lifecycle.get("window_order") != expected_ids or lifecycle.get("status") != "COMPLETED_NO_RETRY_NO_OVERLAP":
        _fail("lifecycle order/retry/overlap contract invalid")
    if lifecycle.get("baseline_window_count") != 10 or lifecycle.get("fault_window_count") != 3 or lifecycle.get("restored_window_count") != 3:
        _fail("lifecycle window cardinality invalid")
    if lifecycle.get("traffic_schedule") != {"iperf3_offset_seconds": 0, "ping_offset_seconds": 5, "maximum_skew_seconds": 0.250}:
        _fail("frozen traffic schedule invalid")
    if lifecycle.get("threshold_input_window_ids") != [f"baseline-{index:02d}" for index in range(1, 11)]:
        _fail("threshold does not bind exactly the ten baseline windows")
    if threshold.get("fault_window_input") != "FORBIDDEN" or threshold.get("post_hoc_override") != "FORBIDDEN":
        _fail("threshold fault/post-hoc exclusion invalid")
    if len({row["window_id"] for row in rows}) != 16:
        _fail("duplicate window detected")


def verify_x6_r1_authoritative_independently(experiment_root: Path, repository_root: Path) -> dict[str, object]:
    """Verify a future authoritative tree from hashes and raw observations."""
    verify_x6_r1_source(repository_root)
    root = Path(experiment_root)
    manifest = _required(root, "manifest.json")
    source = _required(root, "validation/source_identity.json")
    image = _required(root, "validation/runtime_image_identity.json")
    prerequisite = _required(root, "validation/netem_prerequisite.json")
    threshold = _required(root, "validation/threshold_manifest_v1.json")
    freeze = _required(root, "validation/threshold_freeze_record.json")
    journal = _required(root, "mutation/action_journal.json")
    command = _required(root, "mutation/command_acceptance.json")
    effect = _required(root, "mutation/mutation_effectiveness.json")
    restoration = _required(root, "mutation/restoration_record.json")
    replay = _required(root, "mutation/standalone_replay.json")
    after = _required(root, "validation/baseline_after.json")
    hashes = _required(root, "validation/raw_hashes.json")
    evidence = _required(root, "parsed/evidence_v4.json")
    vector = _required(root, "parsed/feature_vector_v2.json")
    diagnosis = _required(root, "diagnosis/diagnosis_result_v2.json")
    predicates = _required(root, "diagnosis/conditional_predicates.json")
    cleanup = _required(root, "validation/cleanup_provenance.json")

    if manifest.get("status") != "AUTHORITATIVE" or manifest.get("release_id") != "X6_R1_PACKET_LOSS":
        _fail("manifest is not an authoritative X6-R1 result")
    if source.get("topology_sha256") != TOPOLOGY_SHA256 or not isinstance(source.get("dockerfile_sha256"), str):
        _fail("source topology/image identity invalid")
    if image.get("captured_before_deployment") is not True or not isinstance(image.get("image_id"), str) or not image["image_id"].startswith("sha256:"):
        _fail("predeployment runtime-image provenance invalid")
    if prerequisite.get("status") != "X6_R0_7_HOST_NETEM_PREREQUISITE_VERIFIED" or prerequisite.get("policy") != "VERIFY_ONLY_NEVER_PRIVILEGED_MODULE_LOAD":
        _fail("R0.7 NetEm prerequisite provenance invalid")
    validate_threshold_manifest(threshold, repository_root=repository_root)
    threshold_hash = _hash(root / "validation/threshold_manifest_v1.json")
    if freeze.get("status") != "FROZEN_BEFORE_MUTATION" or freeze.get("sha256") != threshold_hash or manifest.get("threshold_sha256") != threshold_hash:
        _fail("threshold freeze/manifest linkage invalid")

    rows = _check_raw_inventory(root, hashes)
    _check_lifecycle(root, rows, threshold)
    if command.get("status") != "COMMAND_ACCEPTED" or command.get("physical_effectiveness") != "NOT_INFERRED":
        _fail("command acceptance must remain distinct from physical effectiveness")
    if effect.get("status") != "MUTATION_EFFECTIVE" or not 6 <= effect.get("lost_packet_count", -1) <= 25 or effect.get("pfifo_drop_delta") != 0 or effect.get("hierarchy_exact") is not True:
        _fail("mutation effectiveness/separation invalid")
    if not isinstance(journal.get("actions"), list) or [row.get("status") for row in journal["actions"]] != ["COMMAND_ACCEPTED", "COMMAND_ACCEPTED"]:
        _fail("mutation journal state invalid")

    catalog = _load(Path(repository_root) / "plans/expansion/X1_FEATURE_CATALOG_V1.json")
    validate_evidence_v4(evidence, catalog, repository_root=repository_root)
    validate_feature_vector_v2(vector, catalog, repository_root=repository_root)
    collector_runs = evidence.get("collector_runs")
    if not isinstance(collector_runs, list) or len(collector_runs) != 1:
        _fail("Evidence v4 collector provenance invalid")
    raw_bound = {row.get("path"): row.get("sha256") for row in collector_runs[0].get("raw_artifacts", []) if isinstance(row, dict)}
    if not raw_bound or any(hashes["artifacts"].get(path) != digest for path, digest in raw_bound.items()):
        _fail("Evidence v4 observation-to-raw hash chain invalid")
    if vector.get("provenance", {}).get("evidence_sha256") != _hash(root / "parsed/evidence_v4.json"):
        _fail("Feature Vector v2 evidence linkage invalid")
    if any(vector["values"][name].get("availability") != "observed" for name in FEATURES):
        _fail("required feature observation unavailable")
    expected_predicates = predicates_from_vector(vector, threshold, repository_root=repository_root)
    if expected_predicates is None or predicates.get("rule_id") != "R_X6_PERFORMANCE_001" or predicates.get("predicates") != expected_predicates or not all(expected_predicates.values()):
        _fail("conditional signature invalid")
    if diagnosis.get("status") != "diagnosed" or diagnosis.get("explanation_refs") != ["rule:R_X6_PERFORMANCE_001"]:
        _fail("rule-based diagnosis invalid")
    if restoration.get("status") != "RESTORATION_CONFIRMED" or replay.get("status") != "STANDALONE_REPLAY_CONFIRMED" or after.get("status") != "BASELINE_VALID_AFTER":
        _fail("restoration/replay/baseline-after invalid")
    if cleanup.get("status") != "CLEANUP_CONFIRMED_ZERO_CONTAINERS_AND_NAMESPACES":
        _fail("durable zero-container/namespace cleanup invalid")
    return manifest
