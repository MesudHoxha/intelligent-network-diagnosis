from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.phase8.synthesis import (
    FIGURE_ACCURACY_PATH,
    FIGURE_MASKED_PATH,
    METHOD_ORDER,
    RECEIPT_PATH,
    REGISTRY_PATH,
    SCOPE_PATH,
    SYNTHESIS_PATH,
    TABLE_CLAIMS_PATH,
    TABLE_DESIGN_PATH,
    TABLE_METRICS_PATH,
    SynthesisError,
    build_synthesis,
    verify_tracked_synthesis,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = Path("schemas/p8_thesis_evaluation_synthesis_v1.schema.json")


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(payload: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))


def _copy_source_boundary(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    for relative in (SCOPE_PATH, REGISTRY_PATH, RECEIPT_PATH):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT_ROOT / relative, destination)
    scope = _json(PROJECT_ROOT / SCOPE_PATH)
    for evidence in scope["accepted_evidence"]:
        for source in evidence["sources"]:
            relative = Path(str(source))
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PROJECT_ROOT / relative, destination)
    return root


def test_source_contract_is_hash_verified() -> None:
    manifest, _ = build_synthesis(repository_root=PROJECT_ROOT)
    sources = {item["path"]: item for item in manifest["accepted_sources"]}

    assert set(sources) == {SCOPE_PATH.as_posix(), REGISTRY_PATH.as_posix(), RECEIPT_PATH.as_posix()}
    for relative, binding in sources.items():
        path = PROJECT_ROOT / relative
        assert binding["sha256"] == _sha256(path)
        assert binding["size_bytes"] == path.stat().st_size
    assert manifest["source_integrity"]["runtime_artifact_count"] == 1488


def test_builder_fails_closed_on_scope_drift(tmp_path: Path) -> None:
    root = _copy_source_boundary(tmp_path)
    with (root / SCOPE_PATH).open("ab") as stream:
        stream.write(b"\n")

    with pytest.raises(SynthesisError, match="P8-R0 bound (hash|size) drifted"):
        build_synthesis(repository_root=root)


def test_builder_fails_closed_on_registry_drift(tmp_path: Path) -> None:
    root = _copy_source_boundary(tmp_path)
    with (root / REGISTRY_PATH).open("ab") as stream:
        stream.write(b"\n")

    with pytest.raises(SynthesisError, match="P8-R1 registry (hash|size) drifted"):
        build_synthesis(repository_root=root)


def test_schema_accepts_synthesis() -> None:
    manifest, _ = build_synthesis(repository_root=PROJECT_ROOT)
    schema = _json(PROJECT_ROOT / SCHEMA_PATH)

    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(manifest))

    assert errors == [], errors[0].message if errors else ""


def test_tracked_manifest_matches_builder() -> None:
    expected, _ = build_synthesis(repository_root=PROJECT_ROOT)

    assert _json(PROJECT_ROOT / SYNTHESIS_PATH) == expected


def test_evaluation_design_table_is_exact() -> None:
    manifest, assets = build_synthesis(repository_root=PROJECT_ROOT)
    rows = _rows(assets[TABLE_DESIGN_PATH])
    values = {row["item"]: row["value"] for row in rows}

    assert len(rows) == 12
    assert values == {
        "diagnostic_classes": "6",
        "complete_contexts": "6",
        "clean_dataset_rows": "72",
        "train_rows": "36",
        "validation_rows": "12",
        "test_rows": "24",
        "clean_test_inputs": "24",
        "masked_test_inputs": "96",
        "total_evaluation_inputs": "120",
        "deterministic_masks": "4",
        "compared_methods": "3",
        "report_only_test_attempts": "1",
    }
    assert manifest["evaluation_design"]["masked_input_independence"] == "TRANSFORMATIONS_NOT_INDEPENDENT_EXPERIMENTS"


def test_method_metric_table_preserves_all_accepted_values() -> None:
    manifest, assets = build_synthesis(repository_root=PROJECT_ROOT)
    rows = _rows(assets[TABLE_METRICS_PATH])
    expected = manifest["comparison"]["methods"]

    assert len(rows) == 9
    for row in rows:
        metrics = expected[row["method_id"]][row["scope"]]
        assert row["sample_count"] == str(metrics["sample_count"])
        for metric in manifest["comparison"]["metric_order"]:
            assert row[metric] == str(metrics[metric])


def test_claim_evidence_table_resolves_all_sources() -> None:
    _, assets = build_synthesis(repository_root=PROJECT_ROOT)
    rows = _rows(assets[TABLE_CLAIMS_PATH])

    assert [row["claim_id"] for row in rows] == [f"C0{index}" for index in range(1, 9)]
    assert all(row["status"] == "SUPPORTED_BOUNDED" for row in rows)
    assert all(row["limit"] for row in rows)
    for row in rows:
        assert all((PROJECT_ROOT / path).is_file() for path in row["source_paths"].split(";"))


def test_figures_are_deterministic_safe_svg() -> None:
    _, first = build_synthesis(repository_root=PROJECT_ROOT)
    _, second = build_synthesis(repository_root=PROJECT_ROOT)

    for path in (FIGURE_ACCURACY_PATH, FIGURE_MASKED_PATH):
        payload = first[path]
        assert payload == second[path]
        root = ET.fromstring(payload)
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        text = payload.decode("utf-8").lower()
        assert "<script" not in text
        assert "href=" not in text
        assert "http://www.w3.org/2000/svg" in text
    assert b"79.17%" in first[FIGURE_ACCURACY_PATH]
    assert b"81.05%" in first[FIGURE_MASKED_PATH]


def test_tracked_assets_match_builder() -> None:
    manifest = verify_tracked_synthesis(repository_root=PROJECT_ROOT)

    assert [item["asset_id"] for item in manifest["assets"]] == ["T01", "T02", "T03", "F01", "F02"]
    assert all(_sha256(PROJECT_ROOT / item["path"]) == item["sha256"] for item in manifest["assets"])


def test_hybrid_is_operationally_distinct_but_numerically_equal() -> None:
    manifest, _ = build_synthesis(repository_root=PROJECT_ROOT)
    methods = manifest["comparison"]["methods"]
    findings = " ".join(item["statement"] for item in manifest["findings"])

    assert methods["machine_learning_p6_v1"] == methods["hybrid_p6_v1"]
    assert "operationally distinct" in findings
    assert "aggregate metrics equal Machine Learning" in findings
    assert manifest["comparison"]["statistical_superiority_test"] == "NOT_PERFORMED"


def test_runtime_authorization_is_entirely_false() -> None:
    manifest, _ = build_synthesis(repository_root=PROJECT_ROOT)
    authorization = manifest["runtime_authorization"]

    assert len(authorization) == 11
    assert set(authorization.values()) == {False}
    assert manifest["next_milestone"] == "P8-R3"


def test_synthesis_source_cannot_deserialize_or_execute() -> None:
    source = (PROJECT_ROOT / "src/phase8/synthesis.py").read_text(encoding="utf-8")
    import_lines = {line.strip() for line in source.splitlines() if line.startswith(("import ", "from "))}

    assert "import joblib" not in import_lines
    assert "import pickle" not in import_lines
    assert "import subprocess" not in import_lines
    assert not any("src.phase6.methods" in line for line in import_lines)
    assert METHOD_ORDER == ("rule_based_p6_v1", "machine_learning_p6_v1", "hybrid_p6_v1")


def test_central_documents_record_d093_and_p8_r3() -> None:
    requirements = {
        "docs/DECISIONS.md": ("D-093", "thesis-ready", "P8-R3"),
        "docs/MASTER_CONTEXT.md": ("P8-R2", "operationally distinct", "P8-R3"),
        "docs/ROADMAP.md": ("P8-R2 thesis-ready final evaluation synthesis: complete", "P8-R3"),
        "docs/STATUS.md": ("Latest P8-R2 thesis synthesis", "D-093", "P8-R3"),
    }
    for relative, tokens in requirements.items():
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        assert all(token in text for token in tokens)


def test_handoff_has_six_sections_and_preserves_scope() -> None:
    text = (PROJECT_ROOT / "docs/HANDOFF_P8_R2.md").read_text(encoding="utf-8")

    assert all(f"## {section}." in text for section in range(1, 7))
    assert "No Containerlab" in text
    assert "no new metric" in text
    assert "P8-R3" in text
    assert "numerically equal" in text
