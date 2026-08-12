"""Build the P8-R2 thesis-ready evaluation synthesis.

This module reads only the tracked P8-R0 scope gate and the tracked P8-R1
registry/receipt chain.  It formats already accepted values as CSV tables and
deterministic SVG figures; it does not execute a diagnosis, deserialize a
model, reopen the test partition, or calculate a new empirical metric.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
from argparse import ArgumentParser
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = 1
SYNTHESIS_ID = "p8_r2_thesis_evaluation_synthesis_v1"
PARENT_CHECKPOINT = "c55c803dbb42752f1597b2276026204267e35e0f"
SCOPE_PATH = Path("plans/phase8/P8_R0_EVIDENCE_CLAIM_SCOPE_V1.json")
REGISTRY_PATH = Path("plans/phase8/P8_R1_FINAL_EVIDENCE_REGISTRY_V1.json")
RECEIPT_PATH = Path("plans/phase8/P8_R1_PRIVATE_ARCHIVE_RECEIPT_V1.json")
SYNTHESIS_PATH = Path("plans/phase8/P8_R2_THESIS_EVALUATION_SYNTHESIS_V1.json")
ASSET_ROOT = Path("docs/thesis_assets/phase8")
TABLE_DESIGN_PATH = ASSET_ROOT / "P8_R2_TABLE_01_EVALUATION_DESIGN.csv"
TABLE_METRICS_PATH = ASSET_ROOT / "P8_R2_TABLE_02_METHOD_METRICS.csv"
TABLE_CLAIMS_PATH = ASSET_ROOT / "P8_R2_TABLE_03_CLAIM_EVIDENCE.csv"
FIGURE_ACCURACY_PATH = ASSET_ROOT / "P8_R2_FIGURE_01_ACCURACY_BY_SCOPE.svg"
FIGURE_MASKED_PATH = ASSET_ROOT / "P8_R2_FIGURE_02_MASKED_EVIDENCE_METRICS.svg"

METHOD_ORDER = (
    "rule_based_p6_v1",
    "machine_learning_p6_v1",
    "hybrid_p6_v1",
)
METHOD_LABELS = {
    "rule_based_p6_v1": "Rule-based",
    "machine_learning_p6_v1": "Machine Learning",
    "hybrid_p6_v1": "Hybrid",
}
METHOD_COLORS = {
    "rule_based_p6_v1": "#0f766e",
    "machine_learning_p6_v1": "#2563eb",
    "hybrid_p6_v1": "#d97706",
}
SCOPE_ORDER = ("clean", "masked_overall", "overall")
SCOPE_LABELS = {
    "clean": "Clean",
    "masked_overall": "Masked evidence",
    "overall": "Overall",
}
METRIC_ORDER = (
    "accuracy",
    "macro_f1",
    "coverage",
    "exact_diagnosis_rate",
    "affected_prefix_rate",
    "insufficient_evidence_rate",
    "abstention_rate",
)


class SynthesisError(RuntimeError):
    """Raised when the accepted synthesis boundary is missing or drifted."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SynthesisError(message)


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SynthesisError(f"Cannot read accepted JSON: {path}") from exc
    _require(isinstance(value, dict), f"Accepted JSON is not an object: {path}")
    return value


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _binding(
    root: Path,
    relative: Path,
    *,
    identifier_key: str,
    identifier: str,
) -> dict[str, Any]:
    path = root / relative
    value = _json(path)
    _require(value.get(identifier_key) == identifier, f"Identity drifted: {relative}")
    return {
        "path": relative.as_posix(),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
        identifier_key: identifier,
    }


def _verify_sources(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scope_path = root / SCOPE_PATH
    registry_path = root / REGISTRY_PATH
    receipt_path = root / RECEIPT_PATH
    for path in (scope_path, registry_path, receipt_path):
        _require(path.is_file(), f"Accepted source is missing: {path}")

    scope = _json(scope_path)
    registry = _json(registry_path)
    receipt = _json(receipt_path)

    _require(scope.get("gate_id") == "p8_r0_evidence_claim_scope_v1", "P8-R0 identity drifted.")
    _require(scope.get("status") == "FROZEN", "P8-R0 is not frozen.")
    _require(scope.get("decision") == "NO_NEW_EXPERIMENT_REQUIRED", "P8-R0 decision drifted.")
    _require(registry.get("registry_id") == "p8_r1_final_evidence_registry_v1", "P8-R1 registry identity drifted.")
    _require(registry.get("status") == "ACCEPTED_IMMUTABLE", "P8-R1 registry is not accepted immutable.")
    _require(receipt.get("receipt_id") == "p8_r1_private_archive_receipt_v1", "P8-R1 receipt identity drifted.")
    _require(receipt.get("status") == "VERIFIED", "P8-R1 receipt is not verified.")

    scope_binding = registry.get("p8_scope_gate")
    _require(isinstance(scope_binding, Mapping), "P8-R1 scope binding is unavailable.")
    _require(scope_binding.get("path") == SCOPE_PATH.as_posix(), "P8-R0 bound path drifted.")
    _require(scope_binding.get("sha256") == _sha256(scope_path), "P8-R0 bound hash drifted.")
    _require(scope_binding.get("size_bytes") == scope_path.stat().st_size, "P8-R0 bound size drifted.")

    registry_binding = receipt.get("registry")
    _require(isinstance(registry_binding, Mapping), "P8-R1 registry receipt binding is unavailable.")
    _require(registry_binding.get("path") == REGISTRY_PATH.as_posix(), "P8-R1 registry path drifted.")
    _require(registry_binding.get("sha256") == _sha256(registry_path), "P8-R1 registry hash drifted.")
    _require(registry_binding.get("size_bytes") == registry_path.stat().st_size, "P8-R1 registry size drifted.")

    _require(receipt.get("archive_sha256") == "e9eea5fe520779eee4f4eba4df442ae46c0fd43ea382eed9f5ad5de94cbd14b6", "Private archive identity drifted.")
    _require(receipt.get("runtime_artifact_count") == 1488, "Runtime artifact count drifted.")
    _require(receipt.get("archive_member_count") == 1490, "Archive member count drifted.")
    _require(receipt.get("estimator_deserialized") is False, "Receipt records estimator deserialization.")
    _require(receipt.get("experiment_executed") is False, "Receipt records experiment execution.")
    _require(receipt.get("metric_recalculated") is False, "Receipt records metric recalculation.")
    _require(set(registry.get("runtime_authorization", {}).values()) == {False}, "P8-R1 runtime authorization drifted.")
    return scope, registry, receipt


def _verify_snapshot(scope: Mapping[str, Any]) -> Mapping[str, Any]:
    snapshot = scope.get("final_evaluation_snapshot")
    _require(isinstance(snapshot, Mapping), "Final evaluation snapshot is unavailable.")
    _require(snapshot.get("comparison_id") == "p6_r6_rules_ml_hybrid_report_only_comparison_v1", "Comparison identity drifted.")
    _require(snapshot.get("comparison_type") == "DESCRIPTIVE_ONLY", "Comparison type drifted.")
    _require(tuple(snapshot.get("method_order", ())) == METHOD_ORDER, "Method order drifted.")
    _require(tuple(snapshot.get("scopes", ())) == SCOPE_ORDER, "Scope order drifted.")
    _require(snapshot.get("development_freeze_verified") is True, "Development freeze is not verified.")
    _require(snapshot.get("model_refit_after_freeze") is False, "Model refit boundary drifted.")
    _require(snapshot.get("policy_reselection_after_freeze") is False, "Policy reselection boundary drifted.")
    _require(snapshot.get("test_guided_revision") is False, "Test-guided revision boundary drifted.")
    _require(snapshot.get("statistical_superiority_test") == "NOT_PERFORMED", "Statistical boundary drifted.")

    methods = snapshot.get("methods")
    _require(isinstance(methods, Mapping), "Accepted method metrics are unavailable.")
    _require(set(methods) == set(METHOD_ORDER), "Accepted method set drifted.")
    for method_id in METHOD_ORDER:
        scopes = methods.get(method_id)
        _require(isinstance(scopes, Mapping), f"Scopes are unavailable for {method_id}.")
        for scope_id, sample_count in (("clean", 24), ("masked_overall", 96), ("overall", 120)):
            metrics = scopes.get(scope_id)
            _require(isinstance(metrics, Mapping), f"Metrics are unavailable for {method_id}.{scope_id}.")
            _require(metrics.get("sample_count") == sample_count, f"Sample count drifted for {method_id}.{scope_id}.")
            _require(set(metrics) == {"sample_count", *METRIC_ORDER}, f"Metric set drifted for {method_id}.{scope_id}.")
            for metric_id in METRIC_ORDER:
                value = metrics.get(metric_id)
                _require(isinstance(value, int | float) and not isinstance(value, bool), f"Metric is non-numeric: {method_id}.{scope_id}.{metric_id}.")
                _require(0.0 <= float(value) <= 1.0, f"Metric is outside [0, 1]: {method_id}.{scope_id}.{metric_id}.")

    _require(methods["machine_learning_p6_v1"] == methods["hybrid_p6_v1"], "Accepted ML/Hybrid equality drifted.")
    return snapshot


def _csv_bytes(fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _evaluation_design_table() -> bytes:
    rows = [
        {"item": "diagnostic_classes", "value": 6, "evidence": "E04;C02", "interpretation": "Six accepted single-fault diagnostic classes."},
        {"item": "complete_contexts", "value": 6, "evidence": "E04;C02", "interpretation": "Six complete controlled laboratory contexts."},
        {"item": "clean_dataset_rows", "value": 72, "evidence": "E04;C02", "interpretation": "Accepted final clean Dataset Row v3 observations."},
        {"item": "train_rows", "value": 36, "evidence": "E04;C02", "interpretation": "Whole-context training partition."},
        {"item": "validation_rows", "value": 12, "evidence": "E04;C02", "interpretation": "Whole-context validation partition."},
        {"item": "test_rows", "value": 24, "evidence": "E04;C02", "interpretation": "Whole-context sealed test partition."},
        {"item": "clean_test_inputs", "value": 24, "evidence": "E05;C04", "interpretation": "Clean report-only inputs."},
        {"item": "masked_test_inputs", "value": 96, "evidence": "E05;C05", "interpretation": "Deterministic missing-evidence transformations; not independent experiments."},
        {"item": "total_evaluation_inputs", "value": 120, "evidence": "E05;C03", "interpretation": "Accepted descriptive comparison inputs per method."},
        {"item": "deterministic_masks", "value": 4, "evidence": "E05;C05", "interpretation": "Four frozen missing-evidence masks applied to clean test inputs."},
        {"item": "compared_methods", "value": 3, "evidence": "E03;E05;C03", "interpretation": "Rule-based, Machine Learning, and Hybrid."},
        {"item": "report_only_test_attempts", "value": 1, "evidence": "E05;C08", "interpretation": "One accepted test evaluation after the development freeze."},
    ]
    return _csv_bytes(("item", "value", "evidence", "interpretation"), rows)


def _method_metrics_table(snapshot: Mapping[str, Any]) -> bytes:
    methods = snapshot["methods"]
    rows: list[dict[str, Any]] = []
    for scope_id in SCOPE_ORDER:
        for method_id in METHOD_ORDER:
            metrics = methods[method_id][scope_id]
            row = {
                "scope": scope_id,
                "method_id": method_id,
                "method_label": METHOD_LABELS[method_id],
                "sample_count": metrics["sample_count"],
            }
            row.update({metric_id: metrics[metric_id] for metric_id in METRIC_ORDER})
            row["source"] = "P8_R0_EVIDENCE_CLAIM_SCOPE_V1.final_evaluation_snapshot"
            rows.append(row)
    return _csv_bytes(
        ("scope", "method_id", "method_label", "sample_count", *METRIC_ORDER, "source"),
        rows,
    )


def _claim_evidence_table(root: Path, scope: Mapping[str, Any]) -> bytes:
    evidence_items = scope.get("accepted_evidence")
    claims = scope.get("claim_matrix")
    _require(isinstance(evidence_items, list), "Accepted evidence inventory is unavailable.")
    _require(isinstance(claims, list), "Accepted claim matrix is unavailable.")
    _require([item.get("evidence_id") for item in evidence_items] == [f"E0{index}" for index in range(1, 7)], "Evidence identity set drifted.")
    _require([item.get("claim_id") for item in claims] == [f"C0{index}" for index in range(1, 9)], "Claim identity set drifted.")
    evidence = {item["evidence_id"]: item for item in evidence_items}
    rows: list[dict[str, str]] = []
    for claim in claims:
        evidence_ids = claim.get("evidence_ids")
        _require(isinstance(evidence_ids, list) and evidence_ids, f"Claim evidence is unavailable: {claim.get('claim_id')}")
        sources: list[str] = []
        for evidence_id in evidence_ids:
            _require(evidence_id in evidence, f"Unknown evidence id: {evidence_id}")
            for source in evidence[evidence_id]["sources"]:
                _require((root / source).is_file(), f"Claim source is missing: {source}")
                if source not in sources:
                    sources.append(source)
        rows.append(
            {
                "claim_id": str(claim["claim_id"]),
                "status": str(claim["status"]),
                "statement": str(claim["statement"]),
                "evidence_ids": ";".join(str(value) for value in evidence_ids),
                "source_paths": ";".join(sources),
                "limit": str(claim["limit"]),
            }
        )
    return _csv_bytes(
        ("claim_id", "status", "statement", "evidence_ids", "source_paths", "limit"),
        rows,
    )


def _percent(value: object) -> Decimal:
    return Decimal(str(value)) * Decimal(100)


def _display_percent(value: Decimal) -> str:
    rendered = f"{value.quantize(Decimal('0.01')):f}".rstrip("0").rstrip(".")
    return f"{rendered}%"


def _svg_header(*, title: str, description: str, width: int, height: int) -> list[str]:
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f"  <title id=\"title\">{escape(title)}</title>",
        f"  <desc id=\"desc\">{escape(description)}</desc>",
        "  <rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>",
    ]


def _svg_axes(*, left: int, top: int, plot_width: int, plot_height: int) -> list[str]:
    lines: list[str] = []
    for tick in (0, 25, 50, 75, 100):
        y = top + plot_height - (plot_height * tick / 100)
        lines.append(f'  <line x1="{left}" y1="{y:g}" x2="{left + plot_width}" y2="{y:g}" stroke="#dbe3ea" stroke-width="1"/>')
        lines.append(f'  <text x="{left - 14}" y="{y + 5:g}" text-anchor="end" font-family="Arial, sans-serif" font-size="14" fill="#475569">{tick}%</text>')
    lines.append(f'  <line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#64748b" stroke-width="1.5"/>')
    lines.append(f'  <line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#64748b" stroke-width="1.5"/>')
    return lines


def _svg_legend(*, y: int, width: int) -> list[str]:
    item_width = 220
    start = (width - item_width * len(METHOD_ORDER)) // 2
    lines: list[str] = []
    for index, method_id in enumerate(METHOD_ORDER):
        x = start + index * item_width
        lines.append(f'  <rect x="{x}" y="{y}" width="18" height="18" rx="3" fill="{METHOD_COLORS[method_id]}"/>')
        lines.append(f'  <text x="{x + 27}" y="{y + 14}" font-family="Arial, sans-serif" font-size="15" fill="#1e293b">{escape(METHOD_LABELS[method_id])}</text>')
    return lines


def _accuracy_figure(snapshot: Mapping[str, Any]) -> bytes:
    width, height = 1080, 640
    left, top, plot_width, plot_height = 82, 142, 958, 390
    lines = _svg_header(
        title="Accuracy by evaluation scope",
        description="Accepted descriptive accuracy for Rule-based, Machine Learning, and Hybrid methods on clean, masked-evidence, and overall scopes. Machine Learning and Hybrid values are identical.",
        width=width,
        height=height,
    )
    lines.extend(
        [
            '  <text x="540" y="42" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="#0f172a">Accuracy by evaluation scope</text>',
            '  <text x="540" y="72" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#475569">Accepted P6-R6 descriptive comparison; percentage labels are display formatting only</text>',
        ]
    )
    lines.extend(_svg_legend(y=94, width=width))
    lines.extend(_svg_axes(left=left, top=top, plot_width=plot_width, plot_height=plot_height))
    group_width = Decimal(plot_width) / Decimal(len(SCOPE_ORDER))
    bar_width = Decimal(64)
    gap = Decimal(12)
    cluster_width = bar_width * Decimal(3) + gap * Decimal(2)
    methods = snapshot["methods"]
    for scope_index, scope_id in enumerate(SCOPE_ORDER):
        center = Decimal(left) + group_width * (Decimal(scope_index) + Decimal("0.5"))
        cluster_left = center - cluster_width / Decimal(2)
        for method_index, method_id in enumerate(METHOD_ORDER):
            value = _percent(methods[method_id][scope_id]["accuracy"])
            x = cluster_left + Decimal(method_index) * (bar_width + gap)
            bar_height = Decimal(plot_height) * value / Decimal(100)
            y = Decimal(top + plot_height) - bar_height
            lines.append(f'  <rect x="{x:f}" y="{y:f}" width="{bar_width:f}" height="{bar_height:f}" rx="4" fill="{METHOD_COLORS[method_id]}"/>')
            lines.append(f'  <text x="{(x + bar_width / 2):f}" y="{max(Decimal(top + 14), y - Decimal(8)):f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" font-weight="600" fill="#334155">{_display_percent(value)}</text>')
        lines.append(f'  <text x="{center:f}" y="{top + plot_height + 34}" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="600" fill="#1e293b">{escape(SCOPE_LABELS[scope_id])}</text>')
    lines.extend(
        [
            '  <text x="540" y="616" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" fill="#64748b">Source: P8-R0 frozen final-evaluation snapshot. No statistical-superiority test was performed.</text>',
            "</svg>",
        ]
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _masked_figure(snapshot: Mapping[str, Any]) -> bytes:
    width, height = 1080, 660
    left, top, plot_width, plot_height = 82, 142, 958, 400
    metrics = (
        ("accuracy", "Accuracy"),
        ("macro_f1", "Macro F1"),
        ("coverage", "Coverage"),
        ("insufficient_evidence_rate", "Insufficient evidence"),
    )
    lines = _svg_header(
        title="Masked-evidence method behavior",
        description="Accepted masked-evidence metrics for Rule-based, Machine Learning, and Hybrid methods. The strict Rule-based method reports insufficient evidence, while Machine Learning and Hybrid retain coverage and have identical aggregate results.",
        width=width,
        height=height,
    )
    lines.extend(
        [
            '  <text x="540" y="42" text-anchor="middle" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="#0f172a">Behavior under deterministic missing evidence</text>',
            '  <text x="540" y="72" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" fill="#475569">96 transformations of 24 clean cases; they are not independent experiments</text>',
        ]
    )
    lines.extend(_svg_legend(y=94, width=width))
    lines.extend(_svg_axes(left=left, top=top, plot_width=plot_width, plot_height=plot_height))
    group_width = Decimal(plot_width) / Decimal(len(metrics))
    bar_width = Decimal(50)
    gap = Decimal(9)
    cluster_width = bar_width * Decimal(3) + gap * Decimal(2)
    methods = snapshot["methods"]
    for metric_index, (metric_id, label) in enumerate(metrics):
        center = Decimal(left) + group_width * (Decimal(metric_index) + Decimal("0.5"))
        cluster_left = center - cluster_width / Decimal(2)
        for method_index, method_id in enumerate(METHOD_ORDER):
            value = _percent(methods[method_id]["masked_overall"][metric_id])
            x = cluster_left + Decimal(method_index) * (bar_width + gap)
            bar_height = Decimal(plot_height) * value / Decimal(100)
            y = Decimal(top + plot_height) - bar_height
            lines.append(f'  <rect x="{x:f}" y="{y:f}" width="{bar_width:f}" height="{bar_height:f}" rx="4" fill="{METHOD_COLORS[method_id]}"/>')
            label_y = max(Decimal(top + 14), y - Decimal(8)) if value else Decimal(top + plot_height - 8)
            lines.append(f'  <text x="{(x + bar_width / 2):f}" y="{label_y:f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="600" fill="#334155">{_display_percent(value)}</text>')
        if label == "Insufficient evidence":
            lines.append(f'  <text x="{center:f}" y="{top + plot_height + 30}" text-anchor="middle" font-family="Arial, sans-serif" font-size="15" font-weight="600" fill="#1e293b">Insufficient</text>')
            lines.append(f'  <text x="{center:f}" y="{top + plot_height + 49}" text-anchor="middle" font-family="Arial, sans-serif" font-size="15" font-weight="600" fill="#1e293b">evidence</text>')
        else:
            lines.append(f'  <text x="{center:f}" y="{top + plot_height + 38}" text-anchor="middle" font-family="Arial, sans-serif" font-size="15" font-weight="600" fill="#1e293b">{escape(label)}</text>')
    lines.extend(
        [
            '  <text x="540" y="636" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" fill="#64748b">Hybrid is operationally distinct but numerically equal to Machine Learning in the accepted aggregate comparison.</text>',
            "</svg>",
        ]
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _asset_record(path: Path, payload: bytes, *, asset_id: str, kind: str, title: str, row_count: int | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "asset_id": asset_id,
        "kind": kind,
        "path": path.as_posix(),
        "sha256": _sha256_bytes(payload),
        "size_bytes": len(payload),
        "title": title,
    }
    if row_count is not None:
        record["row_count"] = row_count
    return record


def build_synthesis(*, repository_root: Path) -> tuple[dict[str, Any], dict[Path, bytes]]:
    """Build the deterministic manifest and thesis assets in memory."""

    root = repository_root.resolve()
    scope, registry, receipt = _verify_sources(root)
    snapshot = _verify_snapshot(scope)
    claims = scope.get("claim_matrix")
    blocked = scope.get("blocked_claims")
    _require(isinstance(claims, list) and len(claims) == 8, "Supported claim count drifted.")
    _require(isinstance(blocked, list) and len(blocked) == 8, "Blocked claim count drifted.")

    assets = {
        TABLE_DESIGN_PATH: _evaluation_design_table(),
        TABLE_METRICS_PATH: _method_metrics_table(snapshot),
        TABLE_CLAIMS_PATH: _claim_evidence_table(root, scope),
        FIGURE_ACCURACY_PATH: _accuracy_figure(snapshot),
        FIGURE_MASKED_PATH: _masked_figure(snapshot),
    }
    asset_records = [
        _asset_record(TABLE_DESIGN_PATH, assets[TABLE_DESIGN_PATH], asset_id="T01", kind="CSV_TABLE", title="Final evaluation design", row_count=12),
        _asset_record(TABLE_METRICS_PATH, assets[TABLE_METRICS_PATH], asset_id="T02", kind="CSV_TABLE", title="Accepted method metrics by scope", row_count=9),
        _asset_record(TABLE_CLAIMS_PATH, assets[TABLE_CLAIMS_PATH], asset_id="T03", kind="CSV_TABLE", title="Bounded claim-to-evidence matrix", row_count=8),
        _asset_record(FIGURE_ACCURACY_PATH, assets[FIGURE_ACCURACY_PATH], asset_id="F01", kind="SVG_FIGURE", title="Accuracy by evaluation scope"),
        _asset_record(FIGURE_MASKED_PATH, assets[FIGURE_MASKED_PATH], asset_id="F02", kind="SVG_FIGURE", title="Behavior under deterministic missing evidence"),
    ]
    methods = snapshot["methods"]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "synthesis_id": SYNTHESIS_ID,
        "status": "THESIS_READY",
        "parent_checkpoint": {
            "branch": "main",
            "commit": PARENT_CHECKPOINT,
            "commit_short": "c55c803",
        },
        "accepted_sources": [
            _binding(root, SCOPE_PATH, identifier_key="gate_id", identifier="p8_r0_evidence_claim_scope_v1"),
            _binding(root, REGISTRY_PATH, identifier_key="registry_id", identifier="p8_r1_final_evidence_registry_v1"),
            _binding(root, RECEIPT_PATH, identifier_key="receipt_id", identifier="p8_r1_private_archive_receipt_v1"),
        ],
        "evaluation_design": {
            "diagnostic_class_count": 6,
            "complete_context_count": 6,
            "clean_dataset_row_count": 72,
            "split_row_counts": {"train": 36, "validation": 12, "test": 24},
            "evaluation_input_counts": {"clean": 24, "masked": 96, "overall": 120},
            "deterministic_mask_count": 4,
            "method_count": 3,
            "report_only_test_attempt_count": 1,
            "masked_input_independence": "TRANSFORMATIONS_NOT_INDEPENDENT_EXPERIMENTS",
        },
        "comparison": {
            "comparison_id": snapshot["comparison_id"],
            "comparison_type": snapshot["comparison_type"],
            "method_order": list(METHOD_ORDER),
            "scopes": list(SCOPE_ORDER),
            "metric_order": list(METRIC_ORDER),
            "methods": snapshot["methods"],
            "statistical_superiority_test": "NOT_PERFORMED",
            "display_percentage_policy": "UNIT_FRACTIONS_MULTIPLIED_BY_100_AND_ROUNDED_ONLY_FOR_LABELS",
        },
        "findings": [
            {"finding_id": "FND01", "claim_ids": ["C04"], "statement": "All three methods have 1.0 clean accuracy and 1.0 clean macro-F1 on 24 accepted clean inputs.", "limit": "This is confined to the controlled final test contexts and taxonomy."},
            {"finding_id": "FND02", "claim_ids": ["C05"], "statement": "On 96 deterministic masked inputs, Rule-based accuracy, macro-F1, and coverage are 0.0 while insufficient-evidence rate is 1.0.", "limit": "The 96 inputs are transformations of 24 clean inputs, not independent experiments."},
            {"finding_id": "FND03", "claim_ids": ["C05", "C06"], "statement": "On masked inputs, Machine Learning and Hybrid both have accuracy 0.7916666666666666, macro-F1 0.8104858104858105, and coverage 1.0.", "limit": "This descriptive equality does not establish statistical superiority or real-world generalization."},
            {"finding_id": "FND04", "claim_ids": ["C06"], "statement": "Hybrid is operationally distinct through rule-first and Machine-Learning-fallback provenance, but its accepted aggregate metrics equal Machine Learning in every scope.", "limit": "No Hybrid performance-advantage claim is authorized."},
            {"finding_id": "FND05", "claim_ids": ["C03", "C08"], "statement": "The comparison is descriptive, follows one frozen report-only test attempt, and records no refit, policy reselection, or test-guided revision.", "limit": "No statistical-superiority test or independent external replication was performed."},
        ],
        "claim_matrix": claims,
        "blocked_claims": blocked,
        "assets": asset_records,
        "source_integrity": {
            "p8_r0_scope_hash_verified_against_p8_r1_registry": True,
            "p8_r1_registry_hash_verified_against_receipt": True,
            "private_archive_sha256": receipt["archive_sha256"],
            "runtime_artifact_count": registry["runtime_artifact_count"],
            "estimator_deserialized": False,
        },
        "runtime_authorization": {
            "new_experiment": False,
            "containerlab": False,
            "network_mutation": False,
            "diagnosis_execution": False,
            "accepted_artifact_mutation": False,
            "model_deserialization": False,
            "model_refit": False,
            "policy_reselection": False,
            "test_evaluation": False,
            "metric_recalculation": False,
            "new_metric": False,
        },
        "next_milestone": "P8-R3",
    }

    _require(methods["machine_learning_p6_v1"] == methods["hybrid_p6_v1"], "ML/Hybrid equality drifted during synthesis.")
    return manifest, assets


def _manifest_bytes(manifest: Mapping[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_new(path: Path, payload: bytes) -> None:
    _require(not path.exists(), f"Refusing to overwrite synthesis output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o644)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_synthesis(*, repository_root: Path) -> dict[str, Any]:
    """Write all P8-R2 generated outputs once, refusing overwrite."""

    root = repository_root.resolve()
    manifest, assets = build_synthesis(repository_root=root)
    destinations = [root / path for path in (*assets, SYNTHESIS_PATH)]
    _require(not any(path.exists() for path in destinations), "One or more synthesis outputs already exist.")
    for relative, payload in assets.items():
        _write_new(root / relative, payload)
    _write_new(root / SYNTHESIS_PATH, _manifest_bytes(manifest))
    return manifest


def verify_tracked_synthesis(*, repository_root: Path) -> dict[str, Any]:
    """Rebuild in memory and verify every tracked P8-R2 generated byte."""

    root = repository_root.resolve()
    expected, assets = build_synthesis(repository_root=root)
    tracked_path = root / SYNTHESIS_PATH
    _require(tracked_path.is_file(), "Tracked synthesis manifest is missing.")
    tracked = _json(tracked_path)
    _require(tracked == expected, "Tracked synthesis manifest drifted.")
    for relative, payload in assets.items():
        path = root / relative
        _require(path.is_file(), f"Tracked synthesis asset is missing: {relative}")
        _require(path.read_bytes() == payload, f"Tracked synthesis asset drifted: {relative}")
    return tracked


def _main() -> int:
    parser = ArgumentParser(description="Build or verify the P8-R2 thesis synthesis.")
    parser.add_argument("--repository-root", type=Path, required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    arguments = parser.parse_args()
    if arguments.write:
        write_synthesis(repository_root=arguments.repository_root)
    else:
        verify_tracked_synthesis(repository_root=arguments.repository_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
