from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

from src.phase8.closeout import build_closeout_manifest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPOSITORY_ROOT / "plans/phase8/P8_R3_PHASE8_CLOSEOUT_V1.json"
SCHEMA_PATH = REPOSITORY_ROOT / "schemas/p8_phase8_closeout_v1.schema.json"
RUNBOOK_PATH = REPOSITORY_ROOT / "docs/P8_R3_PHASE8_CLOSEOUT.md"
HANDOFF_PATH = REPOSITORY_ROOT / "docs/HANDOFF_P8_R3.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_p8_r3_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA_PATH))


def test_p8_r3_manifest_validates_against_schema() -> None:
    schema = _load(SCHEMA_PATH)
    manifest = _load(MANIFEST_PATH)

    errors = sorted(
        Draft202012Validator(schema).iter_errors(manifest),
        key=lambda error: list(error.path),
    )
    assert errors == []


def test_source_checkpoint_is_the_exact_local_p8_r2_boundary() -> None:
    checkpoint = _load(MANIFEST_PATH)["source_checkpoint"]

    assert checkpoint["branch"] == "main"
    assert checkpoint["commit"].startswith("cb489a3")
    assert len(checkpoint["commit"]) == 40
    assert checkpoint["parent_commit"] == (
        "c55c803dbb42752f1597b2276026204267e35e0f"
    )


def test_four_accepted_inputs_retain_hash_and_size_bindings() -> None:
    inputs = _load(MANIFEST_PATH)["accepted_inputs"]

    assert [item["milestone"] for item in inputs] == [
        "P8-R0",
        "P8-R1-REGISTRY",
        "P8-R1-RECEIPT",
        "P8-R2",
    ]
    for item in inputs:
        path = REPOSITORY_ROOT / item["path"]
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == item["size_bytes"]
        assert _sha256(path) == item["sha256"]


def test_five_thesis_assets_retain_hash_and_size_bindings() -> None:
    assets = _load(MANIFEST_PATH)["thesis_assets"]

    assert [asset["asset_id"] for asset in assets] == [
        "T01",
        "T02",
        "T03",
        "F01",
        "F02",
    ]
    for asset in assets:
        path = REPOSITORY_ROOT / asset["path"]
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == asset["size_bytes"]
        assert _sha256(path) == asset["sha256"]


def test_final_archive_and_runtime_counts_are_frozen() -> None:
    chain = _load(MANIFEST_PATH)["accepted_chain"]

    assert chain["runtime_artifact_count"] == 1488
    assert chain["archive_member_count"] == 1490
    assert chain["private_archive_size_bytes"] == 639729
    assert chain["private_archive_sha256"] == (
        "e9eea5fe520779eee4f4eba4df442ae46c0fd43ea382eed9f5ad5de94cbd14b6"
    )
    assert chain["estimator_deserialized"] is False
    assert chain["test_partition_reopened"] is False
    assert chain["metric_recalculated"] is False


def test_supported_and_blocked_claim_sets_remain_exact() -> None:
    claims = _load(MANIFEST_PATH)["claim_boundary"]

    assert claims["supported_claim_ids"] == [f"C0{index}" for index in range(1, 9)]
    assert claims["blocked_claim_ids"] == [f"B0{index}" for index in range(1, 9)]


def test_hybrid_and_masked_evidence_interpretations_remain_bounded() -> None:
    claims = _load(MANIFEST_PATH)["claim_boundary"]

    assert claims["comparison_type"] == "DESCRIPTIVE_ONLY"
    assert claims["hybrid_interpretation"] == (
        "OPERATIONALLY_DISTINCT_NUMERICALLY_EQUAL_TO_ML"
    )
    assert claims["masked_inputs"] == "TRANSFORMATIONS_NOT_INDEPENDENT_EXPERIMENTS"
    assert claims["external_generalization"] == "NOT_ESTABLISHED"


def test_phase9_handoff_has_seven_ordered_chapter_roles() -> None:
    handoff = _load(MANIFEST_PATH)["phase9_handoff"]
    chapters = handoff["chapter_map"]

    assert handoff["next_milestone"] == "P9-R0"
    assert handoff["entry_gate"] == "THESIS_STRUCTURE_AND_SOURCE_CITATION_GATE"
    assert [chapter["chapter_id"] for chapter in chapters] == [
        f"CH0{index}" for index in range(1, 8)
    ]
    assert {evidence for chapter in chapters for evidence in chapter["evidence_ids"]} == {
        f"E0{index}" for index in range(1, 7)
    }


def test_phase9_writing_constraints_prohibit_claim_drift() -> None:
    constraints = _load(MANIFEST_PATH)["phase9_handoff"]["writing_constraints"]

    assert len(constraints) == 6
    assert "PRESERVE_EXACT_ACCEPTED_VALUES" in constraints
    assert "KEEP_ALL_BLOCKED_CLAIMS_PROHIBITED" in constraints
    assert "DO_NOT_TREAT_MASKS_AS_INDEPENDENT_EXPERIMENTS" in constraints
    assert "DO_NOT_CLAIM_HYBRID_OR_STATISTICAL_SUPERIORITY" in constraints


def test_all_twelve_runtime_authorizations_are_false() -> None:
    authorization = _load(MANIFEST_PATH)["runtime_authorization"]

    assert len(authorization) == 12
    assert set(authorization.values()) == {False}
    assert authorization["thesis_claim_broadening"] is False


def test_tracked_closeout_rebuilds_deterministically_from_tracked_inputs() -> None:
    manifest = _load(MANIFEST_PATH)
    rebuilt = build_closeout_manifest(
        REPOSITORY_ROOT, manifest["source_checkpoint"]["commit"]
    )

    assert rebuilt == manifest
    expected_bytes = (json.dumps(rebuilt, indent=2, sort_keys=True) + "\n").encode()
    assert MANIFEST_PATH.read_bytes() == expected_bytes


def test_closeout_module_has_no_experiment_or_estimator_loader_path() -> None:
    source = (REPOSITORY_ROOT / "src/phase8/closeout.py").read_text(encoding="utf-8")

    for prohibited in (
        "import joblib",
        "from joblib",
        "import pickle",
        "from pickle",
        "import subprocess",
        "containerlab deploy",
        "docker exec",
    ):
        assert prohibited not in source


def test_closeout_runbook_freezes_preservation_and_phase9_entry() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
    normalized = " ".join(runbook.split())

    assert "Status: CLOSED — FINAL EVIDENCE AND EVALUATION ACCEPTED" in runbook
    assert "1,488 accepted runtime artifacts" in runbook
    assert "e9eea5fe520779eee4f4eba4df442ae46c0fd43ea382eed9f5ad5de94cbd14b6" in runbook
    assert "P9-R0 is next: Thesis Structure and Source/Citation Gate" in runbook
    assert "not independent network experiments" in normalized


def test_handoff_and_central_documents_close_phase8_and_open_p9_r0() -> None:
    handoff = HANDOFF_PATH.read_text(encoding="utf-8")
    headings = re.findall(r"^## (\d)\. ", handoff, flags=re.MULTILINE)
    roadmap = (REPOSITORY_ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
    status = (REPOSITORY_ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
    context = (REPOSITORY_ROOT / "docs/MASTER_CONTEXT.md").read_text(encoding="utf-8")
    decisions = (REPOSITORY_ROOT / "docs/DECISIONS.md").read_text(encoding="utf-8")
    phase8 = roadmap.split("## Phase 8", 1)[1].split("## Phase 9", 1)[0]

    assert headings == ["1", "2", "3", "4", "5", "6"]
    assert "Status: COMPLETED — PHASE 8 CLOSED" in handoff
    assert "Status: Complete" in phase8
    assert "P9-R0" in roadmap and "P9-R0" in status and "P9-R0" in context
    assert "## D-094" in decisions
