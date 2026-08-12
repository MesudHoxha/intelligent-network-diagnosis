from __future__ import annotations

import hashlib
import json
import os
import tempfile
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.phase7.catalog import (
    DEFAULT_CATALOG_MANIFEST_PATH,
    GATE_PATH,
    METHOD_ORDER,
    ArtifactCatalog,
)


GATE_ID = "p8_r0_evidence_claim_scope_v1"
SCHEMA_VERSION = 1
FINAL_EVALUATION_ID = "p6_r6_rules_ml_hybrid_report_only_comparison_v1"


class ScopeGateError(RuntimeError):
    """Raised when accepted evidence cannot support the frozen scope."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ScopeGateError(message)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_thaw(item) for item in value]
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_final_evaluation(catalog: ArtifactCatalog) -> None:
    comparison = catalog.comparison
    run = catalog.run_manifest
    gate = catalog.documents[GATE_PATH]

    _require(
        comparison.get("comparison_id") == FINAL_EVALUATION_ID,
        "Final comparison identity drifted.",
    )
    _require(
        comparison.get("comparison_type") == "DESCRIPTIVE_ONLY",
        "Final comparison is not descriptive-only.",
    )
    _require(
        comparison.get("test_role") == "REPORT_ONLY",
        "Final comparison test role drifted.",
    )
    _require(
        comparison.get("statistical_superiority_test") == "NOT_PERFORMED",
        "A statistical-superiority boundary drifted.",
    )
    _require(
        comparison.get("test_guided_revision") == "PROHIBITED",
        "The test-guided-revision boundary drifted.",
    )
    _require(run.get("status") == "COMPLETED", "Final run is not completed.")
    _require(
        run.get("test_use") == "ONE_REPORT_ONLY_EVALUATION",
        "Final test-use boundary drifted.",
    )
    _require(run.get("test_clean_inputs") == 24, "Clean test count drifted.")
    _require(run.get("test_masked_inputs") == 96, "Masked test count drifted.")
    _require(run.get("test_total_inputs") == 120, "Total test count drifted.")
    _require(run.get("model_refit_after_freeze") is False, "Model was refit.")
    _require(
        run.get("policy_reselection_after_freeze") is False,
        "Hybrid policy was reselected.",
    )
    _require(
        run.get("test_guided_revision") is False,
        "Final run records test-guided revision.",
    )
    _require(gate.get("status") == "COMPLETED", "Method gate is not completed.")
    _require(
        gate.get("development_freeze_verified") is True,
        "Development freeze is not verified.",
    )
    _require(
        gate.get("test_evaluation_attempt_count") == 1,
        "Final test attempt count drifted.",
    )

    methods = comparison.get("methods")
    _require(isinstance(methods, Mapping), "Final method map is unavailable.")
    _require(tuple(comparison.get("method_order", ())) == METHOD_ORDER, "Method order drifted.")
    _require(set(methods) == set(METHOD_ORDER), "Method set drifted.")
    for method_id in METHOD_ORDER:
        scopes = methods[method_id]
        _require(isinstance(scopes, Mapping), f"Scopes are unavailable for {method_id}.")
        for scope, count in (("clean", 24), ("masked_overall", 96), ("overall", 120)):
            metrics = scopes.get(scope)
            _require(isinstance(metrics, Mapping), f"{method_id}.{scope} is unavailable.")
            _require(
                metrics.get("sample_count") == count,
                f"{method_id}.{scope} sample count drifted.",
            )
        clean = scopes["clean"]
        _require(clean.get("accuracy") == 1.0, f"{method_id} clean accuracy drifted.")
        _require(clean.get("macro_f1") == 1.0, f"{method_id} clean macro-F1 drifted.")

    rule_masked = methods["rule_based_p6_v1"]["masked_overall"]
    _require(rule_masked.get("accuracy") == 0.0, "Rule masked accuracy drifted.")
    _require(rule_masked.get("macro_f1") == 0.0, "Rule masked macro-F1 drifted.")
    _require(rule_masked.get("coverage") == 0.0, "Rule masked coverage drifted.")
    _require(
        rule_masked.get("insufficient_evidence_rate") == 1.0,
        "Rule missing-evidence behavior drifted.",
    )
    ml = methods["machine_learning_p6_v1"]
    hybrid = methods["hybrid_p6_v1"]
    _require(ml == hybrid, "Accepted ML/Hybrid aggregate equality drifted.")
    _require(ml["masked_overall"].get("accuracy", 0.0) > 0.0, "ML masked accuracy vanished.")
    _require(ml["masked_overall"].get("coverage") == 1.0, "ML masked coverage drifted.")


def _accepted_evidence() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": "E01",
            "stage": "P1",
            "role": "pipeline_validation",
            "status": "ACCEPTED_DOCUMENTED",
            "sources": ["docs/MASTER_CONTEXT.md", "docs/STATUS.md"],
            "summary": "Controlled injection, passive evidence, diagnosis, evaluation, restoration, and baseline recovery were demonstrated end to end.",
        },
        {
            "evidence_id": "E02",
            "stage": "P2",
            "role": "pilot_dataset",
            "status": "ACCEPTED_DOCUMENTED",
            "sources": ["docs/HANDOFF_P2_R10.md", "docs/DECISIONS.md"],
            "summary": "A 30-row, three-class, five-context controlled campaign and leakage-safe 18/6/6 split were accepted.",
        },
        {
            "evidence_id": "E03",
            "stage": "P3-P5",
            "role": "method_development",
            "status": "ACCEPTED_DOCUMENTED",
            "sources": [
                "docs/HANDOFF_P3_R0.md",
                "docs/HANDOFF_P4_R1.md",
                "docs/HANDOFF_P5_R2.md",
            ],
            "summary": "Traditional, Machine Learning, and Hybrid methods were developed and compared under frozen partition roles before the extended evaluation.",
        },
        {
            "evidence_id": "E04",
            "stage": "P6-R5",
            "role": "final_clean_dataset",
            "status": "ACCEPTED_DOCUMENTED",
            "sources": ["docs/HANDOFF_P6_R5.md", "docs/DECISIONS.md"],
            "summary": "The canonical final dataset contains 72 clean rows across six classes and six complete contexts, split 36/12/24 by whole context.",
        },
        {
            "evidence_id": "E05",
            "stage": "P6-R6",
            "role": "final_method_evaluation",
            "status": "HASH_VERIFIED_NOW",
            "sources": [
                "plans/phase7/P7_R1_ACCEPTED_ARTIFACT_CATALOG_V1.json",
                "docs/HANDOFF_P6_R6.md",
            ],
            "summary": "The single frozen report-only comparison covers Rule-based, Machine Learning, and Hybrid methods on 24 clean and 96 deterministic masked inputs.",
        },
        {
            "evidence_id": "E06",
            "stage": "P7",
            "role": "local_presentation",
            "status": "ACCEPTED_DOCUMENTED",
            "sources": ["docs/HANDOFF_P7_R4.md", "docs/DECISIONS.md"],
            "summary": "A fail-closed local read-only API and Dashboard present the accepted final comparison without inference or artifact mutation.",
        },
    ]


def _claim_matrix() -> list[dict[str, Any]]:
    return [
        {
            "claim_id": "C01",
            "status": "SUPPORTED_BOUNDED",
            "evidence_ids": ["E01", "E02", "E04"],
            "statement": "The project implements a controlled-laboratory pipeline from fault injection and passive evidence collection through diagnosis, evaluation, restoration, and dataset construction.",
            "limit": "The claim is limited to the implemented local Containerlab contexts and approved single-fault taxonomy.",
        },
        {
            "claim_id": "C02",
            "status": "SUPPORTED_BOUNDED",
            "evidence_ids": ["E04"],
            "statement": "The final clean dataset covers six diagnostic classes in six complete contexts with a whole-context 36/12/24 train/validation/test split.",
            "limit": "Rows are controlled laboratory observations, not a representative sample of production networks.",
        },
        {
            "claim_id": "C03",
            "status": "SUPPORTED_BOUNDED",
            "evidence_ids": ["E03", "E05"],
            "statement": "Rule-based, Machine Learning, and Hybrid methods are compared under the same frozen report-only test protocol.",
            "limit": "The comparison is descriptive and contains no statistical-superiority test.",
        },
        {
            "claim_id": "C04",
            "status": "SUPPORTED_BOUNDED",
            "evidence_ids": ["E05"],
            "statement": "All three accepted methods achieve complete fault-type classification on the 24 clean final test inputs.",
            "limit": "Perfect clean-set results do not establish performance outside E02/E06 or beyond the controlled taxonomy.",
        },
        {
            "claim_id": "C05",
            "status": "SUPPORTED_BOUNDED",
            "evidence_ids": ["E05"],
            "statement": "Under four deterministic missing-evidence masks, the strict Rule-based method fails closed while the accepted Machine Learning and Hybrid methods retain full coverage and non-zero aggregate accuracy.",
            "limit": "The 96 masked inputs are transformations of 24 clean inputs, not independent network experiments.",
        },
        {
            "claim_id": "C06",
            "status": "SUPPORTED_BOUNDED",
            "evidence_ids": ["E03", "E05"],
            "statement": "The Hybrid method implements a rule-first, Machine-Learning-fallback decision policy with auditable provenance.",
            "limit": "Its final aggregate metrics equal the Machine Learning method; no Hybrid performance advantage is claimed.",
        },
        {
            "claim_id": "C07",
            "status": "SUPPORTED_BOUNDED",
            "evidence_ids": ["E05", "E06"],
            "statement": "Accepted evidence, predictions, comparisons, and limitations can be inspected through a local fail-closed read-only interface.",
            "limit": "The interface is not a live diagnosis service, production NMS, or remote deployment.",
        },
        {
            "claim_id": "C08",
            "status": "SUPPORTED_BOUNDED",
            "evidence_ids": ["E05"],
            "statement": "The final evaluation preserves train/validation/test roles, verifies the development freeze before test access, and records one report-only test attempt without refit or test-guided revision.",
            "limit": "This establishes protocol integrity for the accepted run, not independent external replication.",
        },
    ]


def _blocked_claims() -> list[dict[str, str]]:
    return [
        {"claim_id": "B01", "statement": "Hybrid statistically outperforms Machine Learning or Rule-based diagnosis."},
        {"claim_id": "B02", "statement": "The reported metrics generalize to real-world or unseen production networks."},
        {"claim_id": "B03", "statement": "The 96 deterministic masks are independent experimental samples."},
        {"claim_id": "B04", "statement": "The system diagnoses simultaneous multiple faults."},
        {"claim_id": "B05", "statement": "The system supports OSPF or arbitrary dynamic-routing failures."},
        {"claim_id": "B06", "statement": "The Dashboard performs live inference, remediation, or production network monitoring."},
        {"claim_id": "B07", "statement": "The accepted confidence values are statistically calibrated uncertainty estimates."},
        {"claim_id": "B08", "statement": "The accepted results establish population-level statistical significance."},
    ]


def build_scope_manifest(*, repository_root: Path) -> dict[str, Any]:
    """Build the deterministic P8-R0 scope gate from accepted P7 sources."""

    root = repository_root.resolve()
    catalog = ArtifactCatalog.load(repository_root=root)
    _verify_final_evaluation(catalog)
    catalog_path = root / DEFAULT_CATALOG_MANIFEST_PATH
    comparison_artifact = catalog.artifacts_by_path[
        "reports/experiments/p6_r6_six_class_v1/cross_method_comparison.json"
    ]
    gate_artifact = catalog.artifacts_by_path[GATE_PATH]
    return {
        "schema_version": SCHEMA_VERSION,
        "gate_id": GATE_ID,
        "status": "FROZEN",
        "decision": "NO_NEW_EXPERIMENT_REQUIRED",
        "scope_basis": "ACCEPTED_CONTROLLED_LABORATORY_EVIDENCE",
        "accepted_evidence": _accepted_evidence(),
        "final_evaluation_snapshot": {
            "comparison_id": FINAL_EVALUATION_ID,
            "comparison_type": "DESCRIPTIVE_ONLY",
            "method_order": list(METHOD_ORDER),
            "scopes": ["clean", "masked_overall", "overall"],
            "methods": _thaw(catalog.comparison["methods"]),
            "catalog_binding": {
                "path": DEFAULT_CATALOG_MANIFEST_PATH.as_posix(),
                "sha256": _sha256(catalog_path),
                "size_bytes": catalog_path.stat().st_size,
                "artifact_count": len(catalog.artifacts_by_path),
            },
            "comparison_binding": {
                "path": comparison_artifact.path,
                "sha256": comparison_artifact.sha256,
                "size_bytes": comparison_artifact.size_bytes,
            },
            "method_gate_binding": {
                "path": gate_artifact.path,
                "sha256": gate_artifact.sha256,
                "size_bytes": gate_artifact.size_bytes,
                "test_evaluation_attempt_count": 1,
            },
            "development_freeze_verified": True,
            "model_refit_after_freeze": False,
            "policy_reselection_after_freeze": False,
            "test_guided_revision": False,
            "statistical_superiority_test": "NOT_PERFORMED",
        },
        "claim_matrix": _claim_matrix(),
        "blocked_claims": _blocked_claims(),
        "gap_assessment": [
            {
                "gap_id": "G01",
                "category": "REPRODUCIBILITY_ARCHIVE",
                "thesis_critical": True,
                "empirical_runtime_required": False,
                "resolution_milestone": "P8-R1",
                "summary": "Create an immutable registry and private archive for the accepted experimental chain; the 15-source Phase 7 bundle is presentation-complete but not a full experiment archive.",
            },
            {
                "gap_id": "G02",
                "category": "THESIS_EVALUATION_SYNTHESIS",
                "thesis_critical": True,
                "empirical_runtime_required": False,
                "resolution_milestone": "P8-R2",
                "summary": "Produce thesis-ready tables, figures, and claim-to-evidence references from hash-verified accepted values without recomputation or new metrics.",
            },
        ],
        "phase8_milestones": [
            {
                "milestone": "P8-R1",
                "purpose": "Immutable final evidence registry and private reproducibility archive.",
            },
            {
                "milestone": "P8-R2",
                "purpose": "Thesis-ready final evaluation synthesis from accepted metrics.",
            },
            {
                "milestone": "P8-R3",
                "purpose": "Phase 8 acceptance closeout and handoff to thesis writing.",
            },
        ],
        "runtime_authorization": {
            "new_experiment": False,
            "containerlab": False,
            "network_mutation": False,
            "accepted_artifact_mutation": False,
            "model_deserialization": False,
            "model_refit": False,
            "policy_reselection": False,
            "test_partition_reopening": False,
            "metric_recalculation": False,
            "new_metric": False,
        },
        "next_milestone": "P8-R1",
    }


def write_scope_manifest(*, repository_root: Path, output_path: Path) -> dict[str, Any]:
    """Build and atomically write the P8-R0 manifest."""

    manifest = build_scope_manifest(repository_root=repository_root)
    destination = output_path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return manifest


def _main() -> int:
    parser = ArgumentParser(description="Build the P8-R0 evidence scope manifest.")
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    write_scope_manifest(
        repository_root=arguments.repository_root,
        output_path=arguments.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
