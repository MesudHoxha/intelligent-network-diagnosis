from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from src.campaign.phase6_plan import CLASS_ORDER
from src.phase6.contracts import (
    MASK_ORDER,
    METHOD_IDS,
    Phase6MethodContractError,
    validate_method_input,
    validate_prediction,
    validate_target,
)


CONTRACT_ID = "p7_readonly_dashboard_api_v1"
CATALOG_ID = "p7_r1_accepted_artifact_catalog_v1"
DEFAULT_INTERFACE_PLAN_PATH = Path(
    "plans/phase7/P7_R0_READ_ONLY_INTERFACE_V1.json"
)
DEFAULT_CATALOG_MANIFEST_PATH = Path(
    "plans/phase7/P7_R1_ACCEPTED_ARTIFACT_CATALOG_V1.json"
)
REPORT_ROOT = "reports/experiments/p6_r6_six_class_v1"
FREEZE_ROOT = "models/p6_r6_six_class_v1"
GATE_PATH = "data/metadata/p6_r6_six_class_method_gate_v1.json"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")

METHOD_ORDER = tuple(METHOD_IDS)
SCOPE_ORDER = ("clean", "masked_overall", "overall")
PREDICTION_FILES = {
    "rule_based_p6_v1": "rule_predictions.jsonl",
    "machine_learning_p6_v1": "ml_predictions.jsonl",
    "hybrid_p6_v1": "hybrid_predictions.jsonl",
}
REPORT_FILES = {
    "rule_based_p6_v1": "rule_report.json",
    "machine_learning_p6_v1": "ml_report.json",
    "hybrid_p6_v1": "hybrid_report.json",
}
REPORT_ARTIFACT_NAMES = (
    "test_inputs.jsonl",
    "test_targets.jsonl",
    "rule_predictions.jsonl",
    "ml_predictions.jsonl",
    "hybrid_predictions.jsonl",
    "rule_report.json",
    "ml_report.json",
    "hybrid_report.json",
    "cross_method_comparison.json",
    "run_manifest.json",
)


@dataclass(frozen=True, slots=True)
class ArtifactSpec:
    artifact_id: str
    path: str
    role: str


ARTIFACT_SPECS = (
    ArtifactSpec("method_gate", GATE_PATH, "accepted_gate"),
    ArtifactSpec(
        "freeze_manifest",
        f"{FREEZE_ROOT}/freeze_manifest.json",
        "accepted_root",
    ),
    ArtifactSpec(
        "freeze_receipt",
        f"{FREEZE_ROOT}/freeze_receipt.json",
        "accepted_root",
    ),
    ArtifactSpec("ml_selection", f"{FREEZE_ROOT}/ml_selection.json", "selection"),
    ArtifactSpec(
        "hybrid_selection",
        f"{FREEZE_ROOT}/hybrid_selection.json",
        "selection",
    ),
    ArtifactSpec("test_inputs", f"{REPORT_ROOT}/test_inputs.jsonl", "case_source"),
    ArtifactSpec("test_targets", f"{REPORT_ROOT}/test_targets.jsonl", "target_source"),
    ArtifactSpec(
        "rule_predictions",
        f"{REPORT_ROOT}/rule_predictions.jsonl",
        "prediction_source",
    ),
    ArtifactSpec(
        "ml_predictions",
        f"{REPORT_ROOT}/ml_predictions.jsonl",
        "prediction_source",
    ),
    ArtifactSpec(
        "hybrid_predictions",
        f"{REPORT_ROOT}/hybrid_predictions.jsonl",
        "prediction_source",
    ),
    ArtifactSpec("rule_report", f"{REPORT_ROOT}/rule_report.json", "method_report"),
    ArtifactSpec("ml_report", f"{REPORT_ROOT}/ml_report.json", "method_report"),
    ArtifactSpec(
        "hybrid_report", f"{REPORT_ROOT}/hybrid_report.json", "method_report"
    ),
    ArtifactSpec(
        "cross_method_comparison",
        f"{REPORT_ROOT}/cross_method_comparison.json",
        "accepted_root",
    ),
    ArtifactSpec(
        "run_manifest", f"{REPORT_ROOT}/run_manifest.json", "accepted_root"
    ),
)
SPEC_BY_PATH = {spec.path: spec for spec in ARTIFACT_SPECS}
SPEC_BY_ID = {spec.artifact_id: spec for spec in ARTIFACT_SPECS}
ROOT_IDS = (
    "freeze_manifest",
    "freeze_receipt",
    "run_manifest",
    "cross_method_comparison",
)


class ArtifactCatalogError(RuntimeError):
    """Base error with a stable API-facing error code."""

    code = "INTERNAL_ERROR"


class ArtifactSetUnavailableError(ArtifactCatalogError):
    code = "ARTIFACT_SET_UNAVAILABLE"


class ArtifactIntegrityError(ArtifactCatalogError):
    code = "ARTIFACT_INTEGRITY_FAILED"


@dataclass(frozen=True, slots=True)
class VerifiedArtifact:
    artifact_id: str
    path: str
    role: str
    sha256: str
    size_bytes: int
    root: bool


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise ArtifactIntegrityError("An artifact contains an unsupported JSON value.")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ArtifactIntegrityError(message)


def _safe_path(repository_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.as_posix() != relative:
        raise ArtifactIntegrityError("An artifact path is not a canonical relative path.")
    resolved_root = repository_root.resolve()
    resolved = (resolved_root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise ArtifactIntegrityError("An artifact path escaped the repository root.") from error
    return resolved


def _read_required_bytes(repository_root: Path, relative: str) -> bytes:
    path = _safe_path(repository_root, relative)
    if not path.is_file() or path.is_symlink():
        raise ArtifactSetUnavailableError(f"Required artifact is unavailable: {relative}")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ArtifactSetUnavailableError(
            f"Required artifact cannot be read: {relative}"
        ) from error


def _read_json_file(repository_root: Path, relative: Path) -> dict[str, Any]:
    payload = _read_required_bytes(repository_root, relative.as_posix())
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArtifactIntegrityError(f"Invalid JSON contract file: {relative}") from error
    if not isinstance(value, dict):
        raise ArtifactIntegrityError(f"Expected a JSON object: {relative}")
    return value


def _parse_source(relative: str, payload: bytes) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ArtifactIntegrityError(f"Artifact is not UTF-8: {relative}") from error
    if relative.endswith(".jsonl"):
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                raise ArtifactIntegrityError(
                    f"Blank JSONL record in {relative} at line {line_number}."
                )
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ArtifactIntegrityError(
                    f"Invalid JSONL record in {relative} at line {line_number}."
                ) from error
            if not isinstance(value, dict):
                raise ArtifactIntegrityError(
                    f"Non-object JSONL record in {relative} at line {line_number}."
                )
            rows.append(value)
        return rows
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise ArtifactIntegrityError(f"Invalid JSON artifact: {relative}") from error
    if not isinstance(value, dict):
        raise ArtifactIntegrityError(f"Expected a JSON object: {relative}")
    return value


def _load_plan(repository_root: Path, plan_path: Path) -> dict[str, Any]:
    plan = _read_json_file(repository_root, plan_path)
    _require(plan.get("schema_version") == 1, "P7-R0 plan version drifted.")
    _require(plan.get("contract_id") == CONTRACT_ID, "P7-R0 contract identity drifted.")
    _require(
        plan.get("mode") == "READ_ONLY_ACCEPTED_ARTIFACT_PROJECTION",
        "P7-R0 read-only mode drifted.",
    )
    allowlist = plan.get("projection_source_allowlist")
    _require(
        isinstance(allowlist, list)
        and tuple(allowlist) == tuple(spec.path for spec in ARTIFACT_SPECS),
        "P7-R0 projection allowlist drifted.",
    )
    roots = plan.get("accepted_root_bindings")
    _require(isinstance(roots, list) and len(roots) == 4, "Root bindings drifted.")
    expected_root_paths = {SPEC_BY_ID[root_id].path for root_id in ROOT_IDS}
    observed_root_paths: set[str] = set()
    for root in roots:
        _require(isinstance(root, dict), "A root binding is not an object.")
        artifact_id = root.get("artifact_id")
        path = root.get("path")
        digest = root.get("sha256")
        _require(artifact_id in ROOT_IDS, "An accepted root identity drifted.")
        _require(path == SPEC_BY_ID[str(artifact_id)].path, "A root path drifted.")
        _require(
            isinstance(digest, str) and SHA256_PATTERN.fullmatch(digest) is not None,
            "A root SHA-256 is invalid.",
        )
        observed_root_paths.add(str(path))
    _require(observed_root_paths == expected_root_paths, "Accepted root set drifted.")
    return plan


def _read_sources(
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, tuple[str, int]]]:
    documents: dict[str, Any] = {}
    observed: dict[str, tuple[str, int]] = {}
    for spec in ARTIFACT_SPECS:
        payload = _read_required_bytes(repository_root, spec.path)
        documents[spec.path] = _parse_source(spec.path, payload)
        observed[spec.path] = (_sha256(payload), len(payload))
    return documents, observed


def _expect_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ArtifactIntegrityError(f"{label} is not an object.")
    return value


def _expect_sequence(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)):
        raise ArtifactIntegrityError(f"{label} is not an array.")
    return value


def _verify_reference(
    reference: Any,
    expected_path: str,
    observed: Mapping[str, tuple[str, int]],
    label: str,
) -> None:
    value = _expect_mapping(reference, label)
    _require(value.get("path") == expected_path, f"{label} path binding drifted.")
    digest, size = observed[expected_path]
    _require(value.get("sha256") == digest, f"{label} SHA-256 binding drifted.")
    _require(value.get("size_bytes") == size, f"{label} size binding drifted.")


def _verify_forbidden_estimator_reference(reference: Any, label: str) -> None:
    value = _expect_mapping(reference, label)
    _require(
        value.get("path") == f"{FREEZE_ROOT}/selected_estimator.joblib",
        f"{label} path drifted.",
    )
    digest = value.get("sha256")
    _require(
        isinstance(digest, str) and SHA256_PATTERN.fullmatch(digest) is not None,
        f"{label} SHA-256 is invalid.",
    )
    size = value.get("size_bytes")
    _require(
        isinstance(size, int) and not isinstance(size, bool) and size > 0,
        f"{label} size is invalid.",
    )


def _comparison_metrics(report_scope: Mapping[str, Any]) -> dict[str, Any]:
    macro = _expect_mapping(report_scope.get("macro"), "report macro metrics")
    exact = _expect_mapping(report_scope.get("exact_diagnosis"), "exact diagnosis")
    affected = _expect_mapping(
        report_scope.get("affected_prefix_fault_only"), "affected-prefix metrics"
    )
    return {
        "sample_count": report_scope.get("sample_count"),
        "accuracy": report_scope.get("accuracy"),
        "macro_f1": macro.get("f1"),
        "exact_diagnosis_rate": exact.get("rate"),
        "affected_prefix_rate": affected.get("rate"),
        "coverage": report_scope.get("coverage"),
        "abstention_rate": report_scope.get("abstention_rate"),
        "insufficient_evidence_rate": report_scope.get(
            "insufficient_evidence_rate"
        ),
    }


def _verify_artifact_graph(
    documents: Mapping[str, Any], observed: Mapping[str, tuple[str, int]]
) -> None:
    gate = _expect_mapping(documents[GATE_PATH], "P6-R6 gate")
    _require(gate.get("gate_id") == "p6_r6_six_class_method_gate_v1", "Gate ID drifted.")
    _require(gate.get("status") == "COMPLETED", "Gate is not completed.")
    _require(gate.get("development_freeze_verified") is True, "Freeze was not verified.")
    _require(gate.get("test_opened") is True, "Report-only test was not opened.")
    _require(gate.get("test_evaluation_attempt_count") == 1, "Test attempt count drifted.")
    _require(gate.get("error") is None, "Completed gate contains an error.")
    gate_artifacts = _expect_mapping(gate.get("artifacts"), "gate artifacts")
    _require(set(gate_artifacts) == set(REPORT_ARTIFACT_NAMES), "Gate artifact set drifted.")
    for name in REPORT_ARTIFACT_NAMES:
        _verify_reference(
            gate_artifacts[name], f"{REPORT_ROOT}/{name}", observed, f"gate {name}"
        )

    manifest_path = f"{FREEZE_ROOT}/freeze_manifest.json"
    receipt_path = f"{FREEZE_ROOT}/freeze_receipt.json"
    ml_selection_path = f"{FREEZE_ROOT}/ml_selection.json"
    hybrid_selection_path = f"{FREEZE_ROOT}/hybrid_selection.json"
    manifest = _expect_mapping(documents[manifest_path], "freeze manifest")
    receipt = _expect_mapping(documents[receipt_path], "freeze receipt")
    ml_selection = _expect_mapping(documents[ml_selection_path], "ML selection")
    hybrid_selection = _expect_mapping(
        documents[hybrid_selection_path], "Hybrid selection"
    )
    _require(
        manifest.get("freeze_id") == "p6_r6_six_class_method_freeze_v1",
        "Freeze ID drifted.",
    )
    _require(manifest.get("selected_ml_candidate") == "logreg_l2_c1", "ML identity drifted.")
    _require(
        manifest.get("selected_hybrid_policy") == "rule_then_ml_fallback_v1",
        "Hybrid identity drifted.",
    )
    _require(manifest.get("test_inputs_read") == 0, "Freeze read test inputs.")
    _require(
        manifest.get("test_predictions_or_metrics") == "ABSENT",
        "Freeze contains test-derived output.",
    )
    _require(
        _expect_mapping(ml_selection.get("selected_candidate"), "selected ML candidate").get(
            "candidate_id"
        )
        == "logreg_l2_c1",
        "ML selection drifted.",
    )
    _require(
        ml_selection.get("test_predictions_or_metrics") == "ABSENT",
        "ML selection contains test output.",
    )
    _require(
        _expect_mapping(
            hybrid_selection.get("selected_policy"), "selected Hybrid policy"
        ).get("candidate_id")
        == "rule_then_ml_fallback_v1",
        "Hybrid selection drifted.",
    )
    _require(
        hybrid_selection.get("test_predictions_or_metrics") == "ABSENT",
        "Hybrid selection contains test output.",
    )
    _require(
        receipt.get("authorization") == "ONE_REPORT_ONLY_TEST_EVALUATION",
        "Freeze receipt authorization drifted.",
    )
    _verify_reference(receipt.get("freeze_manifest"), manifest_path, observed, "receipt manifest")
    _verify_reference(receipt.get("ml_selection"), ml_selection_path, observed, "receipt ML selection")
    _verify_reference(
        receipt.get("hybrid_selection"),
        hybrid_selection_path,
        observed,
        "receipt Hybrid selection",
    )
    _verify_forbidden_estimator_reference(receipt.get("selected_estimator"), "receipt estimator")

    run_path = f"{REPORT_ROOT}/run_manifest.json"
    comparison_path = f"{REPORT_ROOT}/cross_method_comparison.json"
    run = _expect_mapping(documents[run_path], "run manifest")
    _require(run.get("run_id") == "p6_r6_six_class_report_only_v1", "Run ID drifted.")
    _require(run.get("status") == "COMPLETED", "Run is not completed.")
    _require(run.get("test_use") == "ONE_REPORT_ONLY_EVALUATION", "Test use drifted.")
    _require(tuple(run.get("method_ids", ())) == METHOD_ORDER, "Run method order drifted.")
    _require(run.get("test_clean_inputs") == 24, "Clean input count drifted.")
    _require(run.get("test_masked_inputs") == 96, "Masked input count drifted.")
    _require(run.get("test_total_inputs") == 120, "Total input count drifted.")
    _require(run.get("model_refit_after_freeze") is False, "Model refit boundary drifted.")
    _require(
        run.get("policy_reselection_after_freeze") is False,
        "Policy reselection boundary drifted.",
    )
    _require(run.get("test_guided_revision") is False, "Test-guided revision drifted.")
    _require(
        run.get("statistical_superiority_test") == "NOT_PERFORMED",
        "Superiority-test boundary drifted.",
    )
    for key, path in (
        ("freeze_manifest", manifest_path),
        ("freeze_receipt", receipt_path),
        ("ml_selection", ml_selection_path),
        ("hybrid_selection", hybrid_selection_path),
    ):
        _verify_reference(run.get(key), path, observed, f"run {key}")
    _verify_forbidden_estimator_reference(run.get("selected_estimator"), "run estimator")

    input_path = f"{REPORT_ROOT}/test_inputs.jsonl"
    target_path = f"{REPORT_ROOT}/test_targets.jsonl"
    inputs = _expect_sequence(documents[input_path], "test inputs")
    targets = _expect_sequence(documents[target_path], "test targets")
    _require(len(inputs) == len(targets) == 120, "Input/target count drifted.")
    try:
        for value in inputs:
            validate_method_input(_expect_mapping(value, "method input"))
        for value in targets:
            validate_target(_expect_mapping(value, "target"))
    except Phase6MethodContractError as error:
        raise ArtifactIntegrityError(f"Phase 6 method contract failed: {error}") from error
    input_ids = [str(value["input_id"]) for value in inputs]
    target_ids = [str(value["input_id"]) for value in targets]
    _require(len(set(input_ids)) == 120, "Input IDs are not unique.")
    _require(target_ids == input_ids, "Input/target order drifted.")
    for value, target in zip(inputs, targets, strict=True):
        _require(value["sample_id"] == target["sample_id"], "Input/target sample ID drifted.")
    clean = [value for value in inputs if value["mask_id"] is None]
    masked = [value for value in inputs if value["mask_id"] is not None]
    _require(len(clean) == 24 and len(masked) == 96, "Clean/masked counts drifted.")
    by_sample: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for value in inputs:
        by_sample[str(value["sample_id"])].append(value)
    _require(len(by_sample) == 24, "Clean sample count drifted.")
    expected_masks = Counter({None: 1, **{mask: 1 for mask in MASK_ORDER}})
    for values in by_sample.values():
        _require(
            Counter(value["mask_id"] for value in values) == expected_masks,
            "A sample mask family drifted.",
        )
    targets_by_id = {str(value["input_id"]): value for value in targets}
    class_balance = Counter(
        targets_by_id[str(value["input_id"])]["labels"]["fault_type"]
        for value in clean
    )
    _require(
        class_balance == Counter({fault_type: 4 for fault_type in CLASS_ORDER}),
        "Clean class balance drifted.",
    )

    predictions: dict[str, Sequence[Any]] = {}
    for method_id, file_name in PREDICTION_FILES.items():
        path = f"{REPORT_ROOT}/{file_name}"
        values = _expect_sequence(documents[path], f"{method_id} predictions")
        _require(len(values) == 120, f"{method_id} prediction count drifted.")
        try:
            for value in values:
                prediction = _expect_mapping(value, "prediction")
                validate_prediction(prediction)
                _require(prediction["method_id"] == method_id, "Prediction method drifted.")
        except Phase6MethodContractError as error:
            raise ArtifactIntegrityError(
                f"Phase 6 prediction contract failed: {error}"
            ) from error
        _require(
            [str(value["input_id"]) for value in values] == input_ids,
            f"{method_id} prediction order drifted.",
        )
        for method_input, prediction in zip(inputs, values, strict=True):
            _require(
                method_input["sample_id"] == prediction["sample_id"],
                f"{method_id} prediction sample ID drifted.",
            )
        predictions[method_id] = values
    _require(
        Counter(value["status"] for value in predictions["rule_based_p6_v1"])
        == Counter({"RESOLVED": 24, "INSUFFICIENT_EVIDENCE": 96}),
        "Rule status boundary drifted.",
    )
    for method_id in ("machine_learning_p6_v1", "hybrid_p6_v1"):
        _require(
            Counter(value["status"] for value in predictions[method_id])
            == Counter({"RESOLVED": 120}),
            f"{method_id} coverage boundary drifted.",
        )

    comparison = _expect_mapping(documents[comparison_path], "comparison")
    _require(
        comparison.get("comparison_id")
        == "p6_r6_rules_ml_hybrid_report_only_comparison_v1",
        "Comparison ID drifted.",
    )
    _require(comparison.get("comparison_type") == "DESCRIPTIVE_ONLY", "Comparison type drifted.")
    _require(comparison.get("test_role") == "REPORT_ONLY", "Comparison role drifted.")
    _require(tuple(comparison.get("method_order", ())) == METHOD_ORDER, "Comparison method order drifted.")
    _require(
        comparison.get("statistical_superiority_test") == "NOT_PERFORMED",
        "Comparison superiority boundary drifted.",
    )
    _require(comparison.get("test_guided_revision") == "PROHIBITED", "Comparison revision boundary drifted.")
    comparison_methods = _expect_mapping(comparison.get("methods"), "comparison methods")
    _require(set(comparison_methods) == set(METHOD_ORDER), "Comparison method set drifted.")

    for method_id, report_name in REPORT_FILES.items():
        report_path = f"{REPORT_ROOT}/{report_name}"
        report = _expect_mapping(documents[report_path], f"{method_id} report")
        _require(report.get("method_id") == method_id, "Report method ID drifted.")
        _require(report.get("evaluation_role") == "TEST_REPORT_ONLY", "Report role drifted.")
        _require(tuple(report.get("class_order", ())) == tuple(CLASS_ORDER), "Report class order drifted.")
        _require(report.get("input_count") == 120, "Report input count drifted.")
        _require(report.get("clean_input_count") == 24, "Report clean count drifted.")
        _require(report.get("masked_input_count") == 96, "Report masked count drifted.")
        _require(report.get("test_influenced_fitting_or_selection") is False, "Report test influence drifted.")
        _require(report.get("statistical_superiority_claim") is False, "Report superiority claim drifted.")
        sources = _expect_mapping(report.get("sources"), "report sources")
        _verify_reference(sources.get("inputs"), input_path, observed, "report inputs")
        _verify_reference(sources.get("targets"), target_path, observed, "report targets")
        prediction_path = f"{REPORT_ROOT}/{PREDICTION_FILES[method_id]}"
        _verify_reference(
            sources.get("predictions"), prediction_path, observed, "report predictions"
        )
        records = _expect_sequence(report.get("records"), "report records")
        _require(len(records) == 120, "Report record count drifted.")
        _require(
            [str(record["input_id"]) for record in records] == sorted(input_ids),
            "Report record order drifted.",
        )
        report_scopes = _expect_mapping(report.get("scopes"), "report scopes")
        method_comparison = _expect_mapping(
            comparison_methods.get(method_id), "method comparison"
        )
        for scope in SCOPE_ORDER:
            report_scope = _expect_mapping(report_scopes.get(scope), f"report {scope}")
            comparison_scope = _expect_mapping(
                method_comparison.get(scope), f"comparison {scope}"
            )
            _require(
                _comparison_metrics(report_scope) == dict(comparison_scope),
                f"{method_id}.{scope} report/comparison metrics drifted.",
            )
    _require(
        comparison_methods["machine_learning_p6_v1"]
        == comparison_methods["hybrid_p6_v1"],
        "Accepted ML/Hybrid aggregate equality drifted.",
    )


def _verify_plan_roots(
    plan: Mapping[str, Any], observed: Mapping[str, tuple[str, int]]
) -> None:
    roots = _expect_sequence(plan.get("accepted_root_bindings"), "accepted roots")
    for root in roots:
        value = _expect_mapping(root, "accepted root")
        path = str(value["path"])
        _require(
            observed[path][0] == value["sha256"],
            f"Accepted root SHA-256 drifted: {path}",
        )


def build_catalog_manifest(
    *,
    repository_root: Path,
    interface_plan_path: Path = DEFAULT_INTERFACE_PLAN_PATH,
) -> dict[str, Any]:
    """Verify the accepted graph and return the deterministic 15-file binding."""

    root = repository_root.resolve()
    plan = _load_plan(root, interface_plan_path)
    documents, observed = _read_sources(root)
    _verify_plan_roots(plan, observed)
    _verify_artifact_graph(documents, observed)
    return {
        "schema_version": 1,
        "catalog_id": CATALOG_ID,
        "contract_id": CONTRACT_ID,
        "status": "ACCEPTED_IMMUTABLE",
        "integrity_model": "GIT_TRACKED_CATALOG_BINDS_ALL_PROJECTION_SOURCES",
        "artifact_count": len(ARTIFACT_SPECS),
        "root_artifact_ids": list(ROOT_IDS),
        "artifacts": [
            {
                "artifact_id": spec.artifact_id,
                "path": spec.path,
                "role": spec.role,
                "sha256": observed[spec.path][0],
                "size_bytes": observed[spec.path][1],
            }
            for spec in ARTIFACT_SPECS
        ],
    }


def _load_catalog_manifest(
    repository_root: Path, catalog_manifest_path: Path
) -> dict[str, Any]:
    catalog = _read_json_file(repository_root, catalog_manifest_path)
    _require(catalog.get("schema_version") == 1, "Catalog version drifted.")
    _require(catalog.get("catalog_id") == CATALOG_ID, "Catalog ID drifted.")
    _require(catalog.get("contract_id") == CONTRACT_ID, "Catalog contract drifted.")
    _require(catalog.get("status") == "ACCEPTED_IMMUTABLE", "Catalog status drifted.")
    _require(
        catalog.get("integrity_model")
        == "GIT_TRACKED_CATALOG_BINDS_ALL_PROJECTION_SOURCES",
        "Catalog integrity model drifted.",
    )
    _require(catalog.get("artifact_count") == 15, "Catalog artifact count drifted.")
    _require(tuple(catalog.get("root_artifact_ids", ())) == ROOT_IDS, "Catalog roots drifted.")
    entries = _expect_sequence(catalog.get("artifacts"), "catalog artifacts")
    _require(len(entries) == 15, "Catalog entry count drifted.")
    for entry, spec in zip(entries, ARTIFACT_SPECS, strict=True):
        value = _expect_mapping(entry, "catalog entry")
        _require(
            set(value) == {"artifact_id", "path", "role", "sha256", "size_bytes"},
            "Catalog entry keys drifted.",
        )
        _require(value.get("artifact_id") == spec.artifact_id, "Catalog artifact ID drifted.")
        _require(value.get("path") == spec.path, "Catalog artifact path drifted.")
        _require(value.get("role") == spec.role, "Catalog artifact role drifted.")
        digest = value.get("sha256")
        size = value.get("size_bytes")
        _require(
            isinstance(digest, str) and SHA256_PATTERN.fullmatch(digest) is not None,
            "Catalog SHA-256 is invalid.",
        )
        _require(
            isinstance(size, int) and not isinstance(size, bool) and size > 0,
            "Catalog size is invalid.",
        )
    return catalog


@dataclass(frozen=True, slots=True)
class ArtifactCatalog:
    contract_id: str
    roots: tuple[VerifiedArtifact, ...]
    artifacts_by_path: Mapping[str, VerifiedArtifact]
    documents: Mapping[str, Any]
    inputs: tuple[Mapping[str, Any], ...]
    targets_by_id: Mapping[str, Mapping[str, Any]]
    predictions_by_method: Mapping[str, Mapping[str, Mapping[str, Any]]]
    reports_by_method: Mapping[str, Mapping[str, Any]]
    comparison: Mapping[str, Any]
    run_manifest: Mapping[str, Any]
    freeze_manifest: Mapping[str, Any]
    ml_selection: Mapping[str, Any]
    hybrid_selection: Mapping[str, Any]

    @classmethod
    def load(
        cls,
        *,
        repository_root: Path,
        interface_plan_path: Path = DEFAULT_INTERFACE_PLAN_PATH,
        catalog_manifest_path: Path = DEFAULT_CATALOG_MANIFEST_PATH,
    ) -> "ArtifactCatalog":
        root = repository_root.resolve()
        plan = _load_plan(root, interface_plan_path)
        catalog_manifest = _load_catalog_manifest(root, catalog_manifest_path)
        documents, observed = _read_sources(root)
        _verify_plan_roots(plan, observed)
        entries = _expect_sequence(catalog_manifest["artifacts"], "catalog artifacts")
        for entry in entries:
            value = _expect_mapping(entry, "catalog entry")
            path = str(value["path"])
            _require(observed[path][0] == value["sha256"], f"Catalog SHA-256 drifted: {path}")
            _require(observed[path][1] == value["size_bytes"], f"Catalog size drifted: {path}")
        _verify_artifact_graph(documents, observed)

        artifacts = {
            spec.path: VerifiedArtifact(
                artifact_id=spec.artifact_id,
                path=spec.path,
                role=spec.role,
                sha256=observed[spec.path][0],
                size_bytes=observed[spec.path][1],
                root=spec.artifact_id in ROOT_IDS,
            )
            for spec in ARTIFACT_SPECS
        }
        roots_by_id = {
            artifact.artifact_id: artifact
            for artifact in artifacts.values()
            if artifact.root
        }
        frozen_documents = {path: _freeze(value) for path, value in documents.items()}
        frozen_inputs = tuple(frozen_documents[f"{REPORT_ROOT}/test_inputs.jsonl"])
        frozen_targets = tuple(frozen_documents[f"{REPORT_ROOT}/test_targets.jsonl"])
        targets_by_id = {
            str(value["input_id"]): value for value in frozen_targets
        }
        predictions_by_method: dict[str, Mapping[str, Mapping[str, Any]]] = {}
        for method_id, name in PREDICTION_FILES.items():
            values = frozen_documents[f"{REPORT_ROOT}/{name}"]
            predictions_by_method[method_id] = MappingProxyType(
                {str(value["input_id"]): value for value in values}
            )
        reports_by_method = {
            method_id: frozen_documents[f"{REPORT_ROOT}/{name}"]
            for method_id, name in REPORT_FILES.items()
        }
        return cls(
            contract_id=CONTRACT_ID,
            roots=tuple(roots_by_id[root_id] for root_id in ROOT_IDS),
            artifacts_by_path=MappingProxyType(artifacts),
            documents=MappingProxyType(frozen_documents),
            inputs=frozen_inputs,
            targets_by_id=MappingProxyType(targets_by_id),
            predictions_by_method=MappingProxyType(predictions_by_method),
            reports_by_method=MappingProxyType(reports_by_method),
            comparison=frozen_documents[f"{REPORT_ROOT}/cross_method_comparison.json"],
            run_manifest=frozen_documents[f"{REPORT_ROOT}/run_manifest.json"],
            freeze_manifest=frozen_documents[f"{FREEZE_ROOT}/freeze_manifest.json"],
            ml_selection=frozen_documents[f"{FREEZE_ROOT}/ml_selection.json"],
            hybrid_selection=frozen_documents[f"{FREEZE_ROOT}/hybrid_selection.json"],
        )
