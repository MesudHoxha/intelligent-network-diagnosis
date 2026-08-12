from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

from src.phase9.gate import build_gate_manifest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "plans/phase9/P9_R0_THESIS_STRUCTURE_SOURCE_CITATION_GATE_V1.json"
)
SCHEMA_PATH = REPOSITORY_ROOT / "schemas/p9_thesis_structure_source_citation_gate_v1.schema.json"
RUNBOOK_PATH = REPOSITORY_ROOT / "docs/P9_R0_THESIS_STRUCTURE_SOURCE_CITATION_GATE.md"
HANDOFF_PATH = REPOSITORY_ROOT / "docs/HANDOFF_P9_R0.md"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_p9_r0_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_load(SCHEMA_PATH))


def test_p9_r0_manifest_validates_against_schema() -> None:
    validator = Draft202012Validator(_load(SCHEMA_PATH))
    errors = sorted(validator.iter_errors(_load(MANIFEST_PATH)), key=lambda error: list(error.path))
    assert errors == []


def test_source_checkpoint_is_exact_public_p8_r3_boundary() -> None:
    checkpoint = _load(MANIFEST_PATH)["source_checkpoint"]

    assert checkpoint == {
        "branch": "main",
        "commit": "01d6d356fbac6444bbd89fd2bcbc7a6e5e1cdea7",
        "commit_short": "01d6d35",
        "repository": "MesudHoxha/intelligent-network-diagnosis",
    }


def test_p8_r3_closeout_is_hash_size_and_status_bound() -> None:
    boundary = _load(MANIFEST_PATH)["accepted_phase8_boundary"]
    path = REPOSITORY_ROOT / boundary["path"]

    assert path.is_file() and not path.is_symlink()
    assert path.stat().st_size == boundary["size_bytes"]
    assert _sha256(path) == boundary["sha256"]
    assert boundary["status"] == "PHASE8_ACCEPTED_CLOSED"


def test_university_alignment_retains_verified_2026_requirements() -> None:
    alignment = _load(MANIFEST_PATH)["university_alignment"]

    assert alignment["guide_status"] == "UNIVERSITY_WIDE_2026_GUIDE_VERIFIED"
    assert alignment["thesis_type"] == "EMPIRICAL_ENGINEERING_PROJECT"
    assert alignment["body_word_range"] == {"minimum": 8000, "maximum": 10000}
    assert alignment["page_range_excluding_references_and_appendices"] == {
        "minimum": 30,
        "maximum": 50,
    }
    assert alignment["abstract_max_words"] == 350
    assert alignment["keyword_range"] == {"minimum": 3, "maximum": 5}
    assert alignment["scientific_reference_recommendation_minimum"] == 30


def test_ai_use_declaration_and_unit_override_guard_are_explicit() -> None:
    alignment = _load(MANIFEST_PATH)["university_alignment"]

    assert alignment["ai_use_disclosure_required"] is True
    assert "originality_and_ai_use_declaration" in alignment["required_front_matter"]
    assert alignment["fiek_specific_public_guide_status"] == "NOT_LOCATED_AS_OF_2026_08_12"
    assert alignment["fiek_or_mentor_override_policy"] == (
        "APPLY_ONLY_IF_DOCUMENTED_AND_DO_NOT_CHANGE_EMPIRICAL_BOUNDARY"
    )


def test_seven_chapters_have_exact_roles_and_bounded_word_budget() -> None:
    chapters = _load(MANIFEST_PATH)["chapter_structure"]

    assert [chapter["chapter_id"] for chapter in chapters] == [f"CH0{i}" for i in range(1, 8)]
    assert [chapter["role"] for chapter in chapters] == [
        "INTRODUCTION",
        "BACKGROUND_AND_RELATED_WORK",
        "METHODOLOGY",
        "ARCHITECTURE_AND_IMPLEMENTATION",
        "RESULTS",
        "DISCUSSION_AND_VALIDITY",
        "CONCLUSIONS",
    ]
    assert sum(chapter["word_target_min"] for chapter in chapters) == 8100
    assert sum(chapter["word_target_max"] for chapter in chapters) == 10000


def test_chapter_map_covers_all_internal_evidence_claims_questions_and_assets() -> None:
    chapters = _load(MANIFEST_PATH)["chapter_structure"]

    assert {item for chapter in chapters for item in chapter["evidence_ids"]} == {
        f"E0{i}" for i in range(1, 7)
    }
    assert {item for chapter in chapters for item in chapter["claim_ids"]} == {
        f"C0{i}" for i in range(1, 9)
    }
    assert {item for chapter in chapters for item in chapter["research_question_ids"]} == {
        f"RQ{i}" for i in range(5)
    }
    assert {item for chapter in chapters for item in chapter["asset_ids"]} == {
        "T01",
        "T02",
        "T03",
        "F01",
        "F02",
    }


def test_primary_question_does_not_presuppose_hybrid_superiority() -> None:
    questions = _load(MANIFEST_PATH)["research_questions"]
    primary = questions[0]

    assert primary["question_id"] == "RQ0" and primary["kind"] == "PRIMARY"
    assert "pa presupozuar epërsi numerike" in primary["text_sq"]
    assert set(primary["claim_ids"]) == {"C03", "C04", "C05", "C06"}


def test_claim_boundary_remains_exactly_eight_supported_and_eight_blocked() -> None:
    boundary = _load(MANIFEST_PATH)["claim_boundary"]

    assert [claim["claim_id"] for claim in boundary["supported_claims"]] == [
        f"C0{i}" for i in range(1, 9)
    ]
    assert [claim["claim_id"] for claim in boundary["blocked_claims"]] == [
        f"B0{i}" for i in range(1, 9)
    ]
    assert all(claim["status"] == "SUPPORTED_BOUNDED" for claim in boundary["supported_claims"])
    assert all(claim["limit"] for claim in boundary["supported_claims"])


def test_hybrid_and_masked_input_interpretations_remain_frozen() -> None:
    boundary = _load(MANIFEST_PATH)["accepted_phase8_boundary"]

    assert boundary["hybrid_interpretation"] == (
        "OPERATIONALLY_DISTINCT_NUMERICALLY_EQUAL_TO_ML"
    )
    assert boundary["masked_inputs"] == "TRANSFORMATIONS_NOT_INDEPENDENT_EXPERIMENTS"


def test_source_seed_has_sixteen_unique_verified_entries() -> None:
    source_gate = _load(MANIFEST_PATH)["source_gate"]
    sources = source_gate["sources"]

    assert source_gate["verified_source_count"] == len(sources) == 16
    assert len({source["source_id"] for source in sources}) == 16
    assert len({source["persistent_id"] for source in sources}) == 16
    assert {source["verified_on"] for source in sources} == {"2026-08-12"}
    assert all(urlparse(source["verification_url"]).scheme == "https" for source in sources)


def test_scientific_seed_has_nine_doi_or_primary_publication_records() -> None:
    source_gate = _load(MANIFEST_PATH)["source_gate"]
    scientific = [
        source for source in source_gate["sources"] if source["counts_toward_scientific_minimum"]
    ]

    assert source_gate["verified_scientific_seed_count"] == len(scientific) == 9
    assert all(source["category"].startswith("ACADEMIC_") for source in scientific)
    assert sum(source["persistent_id"].startswith("doi:") for source in scientific) == 8
    assert {source["source_id"] for source in scientific} == {
        f"ACAD0{i}" for i in range(1, 10)
    }


def test_source_seed_is_not_misrepresented_as_final_bibliography() -> None:
    source_gate = _load(MANIFEST_PATH)["source_gate"]

    assert source_gate["inventory_is_final_bibliography"] is False
    assert source_gate["final_scientific_reference_target_minimum"] == 30
    assert "DO_NOT_CITE_SEARCH_SNIPPETS_OR_GENERATIVE_AI_AS_AUTHORITIES" in source_gate[
        "admission_rules"
    ]
    assert "DO_NOT_USE_LITERATURE_TO_ENLARGE_INTERNAL_EMPIRICAL_CLAIMS" in source_gate[
        "admission_rules"
    ]


def test_every_source_has_chapter_scope_and_bounded_use() -> None:
    manifest = _load(MANIFEST_PATH)
    sources = manifest["source_gate"]["sources"]
    valid_chapters = {chapter["chapter_id"] for chapter in manifest["chapter_structure"]}

    for source in sources:
        assert set(source["chapter_ids"]) <= valid_chapters
        assert len(source["use_boundary"]) >= 20
    assert next(source for source in sources if source["source_id"] == "INST02")["chapter_ids"] == []


def test_apa_citation_and_table_figure_conventions_are_frozen() -> None:
    policy = _load(MANIFEST_PATH)["citation_and_asset_policy"]

    assert policy["in_text_style"] == "APA_AUTHOR_DATE"
    assert policy["direct_quote_requires_page_or_section"] is True
    assert policy["reference_list_order"] == "ALPHABETICAL_BY_FIRST_AUTHOR"
    assert policy["reference_list_contains_only_cited_sources"] is True
    assert policy["internal_asset_rule"] == "P8_R2_VALUES_MUST_BE_COPIED_NOT_RECOMPUTED"
    assert "Table 1" in policy["table_numbering"]
    assert "Figure 1" in policy["figure_numbering"]


def test_two_traceability_csv_assets_retain_hash_size_and_row_counts() -> None:
    manifest = _load(MANIFEST_PATH)

    assert [asset["asset_id"] for asset in manifest["traceability_assets"]] == ["P9T01", "P9T02"]
    assert [asset["row_count"] for asset in manifest["traceability_assets"]] == [7, 16]
    for asset in manifest["traceability_assets"]:
        path = REPOSITORY_ROOT / asset["path"]
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_size == asset["size_bytes"]
        assert _sha256(path) == asset["sha256"]
        with path.open(encoding="utf-8", newline="") as stream:
            assert len(list(csv.DictReader(stream))) == asset["row_count"]


def test_gate_rebuilds_deterministically_from_tracked_inputs() -> None:
    manifest = _load(MANIFEST_PATH)
    rebuilt = build_gate_manifest(REPOSITORY_ROOT, manifest["source_checkpoint"]["commit"])

    assert rebuilt == manifest
    expected = (json.dumps(rebuilt, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    assert MANIFEST_PATH.read_bytes() == expected


def test_gate_module_has_no_network_experiment_or_estimator_execution_path() -> None:
    source = (REPOSITORY_ROOT / "src/phase9/gate.py").read_text(encoding="utf-8")

    for prohibited in (
        "import requests",
        "import httpx",
        "import subprocess",
        "import joblib",
        "from joblib",
        "import pickle",
        "containerlab deploy",
        "docker exec",
    ):
        assert prohibited not in source


def test_drafting_authorization_is_bounded_and_fail_closed() -> None:
    authorization = _load(MANIFEST_PATH)["drafting_authorization"]
    allowed = {
        "chapter_skeleton",
        "bounded_paraphrase_of_verified_sources",
        "copy_exact_accepted_values",
        "format_accepted_tables_and_figures",
    }

    assert {key for key, value in authorization.items() if value is True} == allowed
    assert {value for key, value in authorization.items() if key not in allowed} == {False}


def test_runbook_handoff_and_central_documents_close_p9_r0() -> None:
    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
    handoff = HANDOFF_PATH.read_text(encoding="utf-8")
    roadmap = (REPOSITORY_ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
    status = (REPOSITORY_ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
    context = (REPOSITORY_ROOT / "docs/MASTER_CONTEXT.md").read_text(encoding="utf-8")
    decisions = (REPOSITORY_ROOT / "docs/DECISIONS.md").read_text(encoding="utf-8")

    assert "Status: ACCEPTED — STRUCTURE AND SOURCE/CITATION GATE PASSED" in runbook
    assert re.findall(r"^## (\d)\. ", handoff, flags=re.MULTILINE) == [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
    ]
    assert "P9-R0" in roadmap and "P9-R0" in status and "P9-R0" in context
    assert "P9-R1" in roadmap and "P9-R1" in status and "P9-R1" in context
    assert "## D-095" in decisions
