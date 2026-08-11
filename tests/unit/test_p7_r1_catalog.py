from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType

import pytest
from jsonschema import Draft202012Validator

from src.phase7.catalog import (
    ARTIFACT_SPECS,
    DEFAULT_CATALOG_MANIFEST_PATH,
    GATE_PATH,
    REPORT_ROOT,
    ArtifactCatalog,
    ArtifactIntegrityError,
    ArtifactSetUnavailableError,
    build_catalog_manifest,
)
from tests.unit.p7_r1_fixtures import build_p7_fixture_repository


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_catalog_manifest_schema_is_valid_and_bounded(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    manifest = json.loads((root / DEFAULT_CATALOG_MANIFEST_PATH).read_text())
    schema = json.loads(
        (PROJECT_ROOT / "schemas/p7_accepted_artifact_catalog_v1.schema.json").read_text()
    )

    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(manifest))

    assert errors == []
    assert manifest["artifact_count"] == 15
    assert [item["path"] for item in manifest["artifacts"]] == [
        spec.path for spec in ARTIFACT_SPECS
    ]


def test_catalog_loads_fifteen_sources_without_estimator_access(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    assert not (root / "models/p6_r6_six_class_v1/selected_estimator.joblib").exists()

    catalog = ArtifactCatalog.load(repository_root=root)

    assert len(catalog.roots) == 4
    assert len(catalog.artifacts_by_path) == 15
    assert len(catalog.inputs) == 120
    assert len(catalog.targets_by_id) == 120
    assert all(len(values) == 120 for values in catalog.predictions_by_method.values())
    assert isinstance(catalog.documents, MappingProxyType)


def test_catalog_is_deeply_immutable(tmp_path: Path) -> None:
    catalog = ArtifactCatalog.load(
        repository_root=build_p7_fixture_repository(tmp_path)
    )

    with pytest.raises(TypeError):
        catalog.inputs[0]["mask_id"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        catalog.targets_by_id["new"] = {}  # type: ignore[index]
    with pytest.raises((AttributeError, TypeError)):
        catalog.inputs.append({})  # type: ignore[attr-defined]


def test_catalog_fails_closed_when_source_is_missing(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    (root / REPORT_ROOT / "ml_predictions.jsonl").unlink()

    with pytest.raises(ArtifactSetUnavailableError) as caught:
        ArtifactCatalog.load(repository_root=root)

    assert caught.value.code == "ARTIFACT_SET_UNAVAILABLE"
    assert str(root) not in str(caught.value)


def test_catalog_fails_closed_on_byte_drift(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    comparison = root / REPORT_ROOT / "cross_method_comparison.json"
    comparison.write_bytes(comparison.read_bytes() + b"\n")

    with pytest.raises(ArtifactIntegrityError, match="root SHA-256") as caught:
        ArtifactCatalog.load(repository_root=root)

    assert caught.value.code == "ARTIFACT_INTEGRITY_FAILED"


def test_bootstrap_rejects_drifted_transitive_reference(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    gate_path = root / GATE_PATH
    gate = json.loads(gate_path.read_text())
    gate["artifacts"]["test_inputs.jsonl"]["sha256"] = "0" * 64
    _write_json(gate_path, gate)

    with pytest.raises(ArtifactIntegrityError, match="gate test_inputs.jsonl"):
        build_catalog_manifest(repository_root=root)


def test_bootstrap_rejects_join_drift_even_with_updated_reference(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    targets_path = root / REPORT_ROOT / "test_targets.jsonl"
    lines = targets_path.read_text().splitlines()
    first = json.loads(lines[0])
    first["input_id"] = "different-input-id"
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    targets_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    gate_path = root / GATE_PATH
    gate = json.loads(gate_path.read_text())
    reference = gate["artifacts"]["test_targets.jsonl"]
    reference["sha256"] = _sha256(targets_path)
    reference["size_bytes"] = targets_path.stat().st_size
    _write_json(gate_path, gate)

    with pytest.raises(ArtifactIntegrityError, match="Input/target order"):
        build_catalog_manifest(repository_root=root)


def test_catalog_manifest_rejects_path_rebinding(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    manifest_path = root / DEFAULT_CATALOG_MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"][0]["path"] = "../outside.json"
    _write_json(manifest_path, manifest)

    with pytest.raises(ArtifactIntegrityError, match="artifact path"):
        ArtifactCatalog.load(repository_root=root)
