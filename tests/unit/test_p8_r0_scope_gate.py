from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.phase7.catalog import ArtifactIntegrityError
from src.phase8.scope import build_scope_manifest
from tests.unit.p7_r1_fixtures import build_p7_fixture_repository


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = Path("plans/phase8/P8_R0_EVIDENCE_CLAIM_SCOPE_V1.json")
SCHEMA_PATH = Path("schemas/p8_evidence_claim_scope_v1.schema.json")


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_scope_manifest_schema_is_valid_on_disposable_evidence(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    manifest = build_scope_manifest(repository_root=root)
    schema = _json(PROJECT_ROOT / SCHEMA_PATH)

    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(manifest))

    assert errors == []


def test_scope_builder_fails_closed_on_accepted_artifact_drift(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    comparison = root / "reports/experiments/p6_r6_six_class_v1/cross_method_comparison.json"
    comparison.write_bytes(comparison.read_bytes() + b"\n")

    with pytest.raises(ArtifactIntegrityError):
        build_scope_manifest(repository_root=root)


def test_tracked_scope_manifest_matches_verified_repository() -> None:
    tracked = _json(PROJECT_ROOT / PLAN_PATH)
    rebuilt = build_scope_manifest(repository_root=PROJECT_ROOT)

    assert tracked == rebuilt


def test_final_evaluation_snapshot_is_hash_bound() -> None:
    manifest = _json(PROJECT_ROOT / PLAN_PATH)
    snapshot = manifest["final_evaluation_snapshot"]
    assert isinstance(snapshot, dict)

    for key in ("catalog_binding", "comparison_binding", "method_gate_binding"):
        binding = snapshot[key]
        assert isinstance(binding, dict)
        path = PROJECT_ROOT / str(binding["path"])
        assert path.is_file()
        assert binding["sha256"] == _sha256(path)
        assert binding["size_bytes"] == path.stat().st_size
    assert snapshot["catalog_binding"]["artifact_count"] == 15


def test_evidence_inventory_is_bounded_and_resolvable() -> None:
    manifest = _json(PROJECT_ROOT / PLAN_PATH)
    evidence = manifest["accepted_evidence"]
    assert isinstance(evidence, list)

    assert [item["evidence_id"] for item in evidence] == [
        "E01",
        "E02",
        "E03",
        "E04",
        "E05",
        "E06",
    ]
    for item in evidence:
        for source in item["sources"]:
            assert (PROJECT_ROOT / source).is_file()
    assert [item["status"] for item in evidence].count("HASH_VERIFIED_NOW") == 1


def test_supported_claims_reference_only_inventoried_evidence() -> None:
    manifest = _json(PROJECT_ROOT / PLAN_PATH)
    evidence_ids = {item["evidence_id"] for item in manifest["accepted_evidence"]}
    claims = manifest["claim_matrix"]

    assert [item["claim_id"] for item in claims] == [f"C0{index}" for index in range(1, 9)]
    assert all(item["status"] == "SUPPORTED_BOUNDED" for item in claims)
    assert all(set(item["evidence_ids"]) <= evidence_ids for item in claims)
    assert all(item["limit"] for item in claims)


def test_blocked_claims_freeze_required_non_claims() -> None:
    manifest = _json(PROJECT_ROOT / PLAN_PATH)
    blocked = manifest["blocked_claims"]
    joined = " ".join(item["statement"] for item in blocked).lower()

    assert [item["claim_id"] for item in blocked] == [f"B0{index}" for index in range(1, 9)]
    for term in (
        "statistically outperforms",
        "real-world",
        "independent experimental samples",
        "multiple faults",
        "ospf",
        "live inference",
        "calibrated",
        "statistical significance",
    ):
        assert term in joined


def test_gate_finds_no_thesis_critical_empirical_runtime_gap() -> None:
    manifest = _json(PROJECT_ROOT / PLAN_PATH)

    assert manifest["decision"] == "NO_NEW_EXPERIMENT_REQUIRED"
    assert [gap["category"] for gap in manifest["gap_assessment"]] == [
        "REPRODUCIBILITY_ARCHIVE",
        "THESIS_EVALUATION_SYNTHESIS",
    ]
    assert all(gap["thesis_critical"] is True for gap in manifest["gap_assessment"])
    assert all(
        gap["empirical_runtime_required"] is False
        for gap in manifest["gap_assessment"]
    )


def test_runtime_authorization_is_entirely_false() -> None:
    manifest = _json(PROJECT_ROOT / PLAN_PATH)
    authorization = manifest["runtime_authorization"]

    assert len(authorization) == 10
    assert set(authorization.values()) == {False}


def test_phase8_sequence_is_frozen_through_closeout() -> None:
    manifest = _json(PROJECT_ROOT / PLAN_PATH)

    assert [item["milestone"] for item in manifest["phase8_milestones"]] == [
        "P8-R1",
        "P8-R2",
        "P8-R3",
    ]
    assert manifest["next_milestone"] == "P8-R1"


@pytest.mark.parametrize(
    ("path", "required"),
    [
        (
            "docs/DECISIONS.md",
            ("D-091", "NO_NEW_EXPERIMENT_REQUIRED", "P8-R1"),
        ),
        (
            "docs/MASTER_CONTEXT.md",
            ("P8-R0", "eight bounded thesis claims", "P8-R1"),
        ),
        (
            "docs/ROADMAP.md",
            ("Phase 8", "P8-R0 evidence and thesis-claim scope gate: complete", "P8-R3"),
        ),
        (
            "docs/STATUS.md",
            ("Latest P8-R0 scope gate", "no new experiment", "P8-R1"),
        ),
    ],
)
def test_central_documents_record_frozen_scope(path: str, required: tuple[str, ...]) -> None:
    text = (PROJECT_ROOT / path).read_text(encoding="utf-8")

    for token in required:
        assert token in text


def test_handoff_has_six_sections_and_preserves_empirical_boundary() -> None:
    text = (PROJECT_ROOT / "docs/HANDOFF_P8_R0.md").read_text(encoding="utf-8")

    for section in range(1, 7):
        assert f"## {section}." in text
    assert "No Containerlab" in text
    assert "P8-R1" in text
    assert "15-source" in text
