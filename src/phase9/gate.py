from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path("plans/phase9/P9_R0_THESIS_STRUCTURE_SOURCE_CITATION_GATE_V1.json")
CHAPTER_ASSET_PATH = Path("docs/thesis_assets/phase9/P9_R0_CHAPTER_STRUCTURE.csv")
SOURCE_ASSET_PATH = Path("docs/thesis_assets/phase9/P9_R0_VERIFIED_SOURCE_SEED.csv")
P8_CLOSEOUT_PATH = Path("plans/phase8/P8_R3_PHASE8_CLOSEOUT_V1.json")
P8_SYNTHESIS_PATH = Path("plans/phase8/P8_R2_THESIS_EVALUATION_SYNTHESIS_V1.json")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _chapters() -> list[dict[str, Any]]:
    return [
        {
            "chapter_id": "CH01",
            "title_sq": "Hyrje",
            "role": "INTRODUCTION",
            "word_target_min": 900,
            "word_target_max": 1100,
            "evidence_ids": ["E01", "E04", "E05"],
            "claim_ids": ["C01", "C03"],
            "research_question_ids": ["RQ0", "RQ1"],
            "source_ids": ["INST01", "ACAD01", "ACAD02", "ACAD03"],
            "asset_ids": [],
            "required_content": [
                "problem_and_motivation",
                "bounded_research_question",
                "objectives_and_contributions",
                "scope_and_thesis_structure",
            ],
            "prohibited_content": [
                "presupposed_hybrid_superiority",
                "real_world_generalization",
            ],
        },
        {
            "chapter_id": "CH02",
            "title_sq": "Shqyrtimi i literaturës dhe bazat teorike",
            "role": "BACKGROUND_AND_RELATED_WORK",
            "word_target_min": 1600,
            "word_target_max": 2000,
            "evidence_ids": ["E01", "E03"],
            "claim_ids": [],
            "research_question_ids": ["RQ0"],
            "source_ids": [
                "ACAD01",
                "ACAD02",
                "ACAD03",
                "ACAD07",
                "STD01",
                "STD02",
            ],
            "asset_ids": [],
            "required_content": [
                "network_fault_diagnosis",
                "rule_based_diagnosis",
                "machine_learning_for_networking",
                "hybrid_and_explainable_diagnosis",
                "research_gap",
            ],
            "prohibited_content": [
                "literature_as_project_evidence",
                "uncited_technical_definitions",
            ],
        },
        {
            "chapter_id": "CH03",
            "title_sq": "Metodologjia dhe dizajni eksperimental",
            "role": "METHODOLOGY",
            "word_target_min": 1400,
            "word_target_max": 1700,
            "evidence_ids": ["E02", "E04", "E05"],
            "claim_ids": ["C01", "C02", "C03", "C08"],
            "research_question_ids": ["RQ1", "RQ2", "RQ3"],
            "source_ids": ["ACAD04", "ACAD05", "ACAD06", "ACAD09"],
            "asset_ids": ["T01"],
            "required_content": [
                "controlled_fault_injection",
                "taxonomy_and_contexts",
                "whole_context_split",
                "development_freeze_and_report_only_test",
                "metrics_and_missing_evidence_masks",
            ],
            "prohibited_content": [
                "masked_inputs_as_independent_experiments",
                "unperformed_statistical_test",
            ],
        },
        {
            "chapter_id": "CH04",
            "title_sq": "Arkitektura dhe implementimi i sistemit",
            "role": "ARCHITECTURE_AND_IMPLEMENTATION",
            "word_target_min": 1400,
            "word_target_max": 1700,
            "evidence_ids": ["E01", "E03", "E06"],
            "claim_ids": ["C01", "C06", "C07"],
            "research_question_ids": ["RQ4"],
            "source_ids": ["ACAD08", "TECH01", "TECH02", "TECH03"],
            "asset_ids": [],
            "required_content": [
                "pipeline_and_artifact_contracts",
                "three_diagnostic_methods",
                "hybrid_rule_first_ml_fallback_provenance",
                "read_only_api_and_dashboard",
                "reproducible_local_toolchain",
            ],
            "prohibited_content": [
                "live_production_monitoring",
                "automatic_remediation",
            ],
        },
        {
            "chapter_id": "CH05",
            "title_sq": "Rezultatet",
            "role": "RESULTS",
            "word_target_min": 1000,
            "word_target_max": 1300,
            "evidence_ids": ["E04", "E05"],
            "claim_ids": ["C02", "C03", "C04", "C05", "C06", "C08"],
            "research_question_ids": ["RQ1", "RQ2", "RQ3", "RQ4"],
            "source_ids": [],
            "asset_ids": ["T01", "T02", "F01", "F02"],
            "required_content": [
                "exact_accepted_descriptive_values",
                "clean_scope_comparison",
                "masked_scope_comparison",
                "coverage_and_insufficient_evidence",
            ],
            "prohibited_content": [
                "metric_recalculation",
                "hybrid_or_statistical_superiority",
            ],
        },
        {
            "chapter_id": "CH06",
            "title_sq": "Diskutimi, kufizimet dhe vlefshmëria",
            "role": "DISCUSSION_AND_VALIDITY",
            "word_target_min": 1200,
            "word_target_max": 1500,
            "evidence_ids": ["E05", "E06"],
            "claim_ids": ["C03", "C04", "C05", "C06", "C07", "C08"],
            "research_question_ids": ["RQ0", "RQ2", "RQ3", "RQ4"],
            "source_ids": ["ACAD01", "ACAD04", "ACAD05", "ACAD06", "ACAD07"],
            "asset_ids": ["T03"],
            "required_content": [
                "claim_to_evidence_interpretation",
                "internal_external_construct_and_conclusion_validity",
                "hybrid_operational_distinction_without_numeric_advantage",
                "controlled_lab_limitations",
            ],
            "prohibited_content": [
                "blocked_claim_conversion",
                "confidence_as_calibrated_uncertainty",
            ],
        },
        {
            "chapter_id": "CH07",
            "title_sq": "Përfundimet dhe puna e ardhshme",
            "role": "CONCLUSIONS",
            "word_target_min": 600,
            "word_target_max": 700,
            "evidence_ids": ["E01", "E05", "E06"],
            "claim_ids": ["C01", "C03", "C05", "C06", "C07", "C08"],
            "research_question_ids": ["RQ0"],
            "source_ids": [],
            "asset_ids": [],
            "required_content": [
                "bounded_answers",
                "implemented_contributions",
                "limitations",
                "explicitly_scoped_future_work",
            ],
            "prohibited_content": [
                "future_work_as_implemented",
                "production_readiness",
            ],
        },
    ]


def _sources() -> list[dict[str, Any]]:
    verified_on = "2026-08-12"
    return [
        {
            "source_id": "INST01",
            "category": "INSTITUTIONAL_GUIDE",
            "authors": ["Universiteti i Prishtinës Hasan Prishtina"],
            "year": 2026,
            "title": "Udhëzues për temën e diplomës për studentët e programeve Bachelor",
            "venue": "Universiteti i Prishtinës Hasan Prishtina",
            "persistent_id": "OFFICIAL_UP_GUIDE_2026",
            "verification_url": "https://fa.uni-pr.edu/desk/inc/media/6A814270-6BC0-4EDC-8B08-4CE239A207E7.pdf",
            "verification_level": "OFFICIAL_FULL_TEXT_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH01", "CH02", "CH03", "CH05", "CH07"],
            "use_boundary": "University-wide Bachelor structure, integrity, APA, reference-count, abstract, and formatting requirements only; a documented FIEK-specific instruction overrides formatting details.",
            "counts_toward_scientific_minimum": False,
        },
        {
            "source_id": "INST02",
            "category": "INSTITUTIONAL_FORM",
            "authors": ["Fakulteti i Inxhinierisë Elektrike dhe Kompjuterike"],
            "year": 2026,
            "title": "Formulari F1B: Kërkesë për lejimin e punimit të diplomës Bachelor dhe caktimin e mentorit",
            "venue": "Universiteti i Prishtinës Hasan Prishtina",
            "persistent_id": "FIEK_FORM_F1B",
            "verification_url": "https://fiek.uni-pr.edu/desk/inc/media/82E71A9C-4193-4769-96C3-3A35ED5F400D.doc",
            "verification_level": "OFFICIAL_METADATA_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": [],
            "use_boundary": "Administrative title and mentor-approval process only; not evidence for technical or empirical claims.",
            "counts_toward_scientific_minimum": False,
        },
        {
            "source_id": "ACAD01",
            "category": "ACADEMIC_ARTICLE",
            "authors": ["Małgorzata Steinder", "Adarshpal S. Sethi"],
            "year": 2004,
            "title": "A survey of fault localization techniques in computer networks",
            "venue": "Science of Computer Programming, 53(2), 165–194",
            "persistent_id": "doi:10.1016/j.scico.2004.01.010",
            "verification_url": "https://research.ibm.com/publications/a-survey-of-fault-localization-techniques-in-computer-networks",
            "verification_level": "PUBLISHER_AND_AUTHOR_RECORD_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH01", "CH02", "CH06"],
            "use_boundary": "Definitions, challenges, and taxonomy of fault localization; not evidence that this project generalizes beyond its lab.",
            "counts_toward_scientific_minimum": True,
        },
        {
            "source_id": "ACAD02",
            "category": "ACADEMIC_ARTICLE",
            "authors": ["Raouf Boutaba", "Mohammad A. Salahuddin", "Noura Limam", "Sara Ayoubi", "Nashid Shahriar", "Felipe Estrada-Solano", "Oscar M. Caicedo"],
            "year": 2018,
            "title": "A comprehensive survey on machine learning for networking: Evolution, applications and research opportunities",
            "venue": "Journal of Internet Services and Applications, 9, Article 16",
            "persistent_id": "doi:10.1186/s13174-018-0087-2",
            "verification_url": "https://link.springer.com/article/10.1186/s13174-018-0087-2",
            "verification_level": "OPEN_PUBLISHER_FULL_TEXT_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH01", "CH02"],
            "use_boundary": "Machine-learning-for-networking context and limitations; not support for any project metric.",
            "counts_toward_scientific_minimum": True,
        },
        {
            "source_id": "ACAD03",
            "category": "ACADEMIC_BOOK_CHAPTER",
            "authors": ["Mourad Nouioua", "Philippe Fournier-Viger", "Ganghuan He", "Farid Nouioua", "Min Zhou"],
            "year": 2021,
            "title": "A survey of machine learning for network fault management",
            "venue": "Machine Learning and Data Mining for Emerging Trend in Cyber Dynamics, 1–27",
            "persistent_id": "doi:10.1007/978-3-030-66288-2_1",
            "verification_url": "https://www.philippe-fournier-viger.com/2021_SURVEY_NETWORK_FAULT_MANAGEMENT.pdf",
            "verification_level": "AUTHOR_FULL_TEXT_AND_DOI_METADATA_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH01", "CH02"],
            "use_boundary": "Rule-based and machine-learning fault-management literature; not support for Hybrid superiority.",
            "counts_toward_scientific_minimum": True,
        },
        {
            "source_id": "ACAD04",
            "category": "ACADEMIC_ARTICLE",
            "authors": ["David R. Roberts", "Volker Bahn", "Simone Ciuti", "Mark S. Boyce", "Jane Elith", "Gurutzeta Guillera-Arroita", "Severin Hauenstein", "José J. Lahoz-Monfort", "Boris Schröder", "Wilfried Thuiller", "David I. Warton", "Brendan A. Wintle", "Florian Hartig", "Carsten F. Dormann"],
            "year": 2017,
            "title": "Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure",
            "venue": "Ecography, 40(8), 913–929",
            "persistent_id": "doi:10.1111/ecog.02881",
            "verification_url": "https://nsojournals.onlinelibrary.wiley.com/doi/abs/10.1111/ecog.02881",
            "verification_level": "PUBLISHER_METADATA_AND_ABSTRACT_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH03", "CH06"],
            "use_boundary": "Structured-data split rationale; it does not independently validate this project's split execution.",
            "counts_toward_scientific_minimum": True,
        },
        {
            "source_id": "ACAD05",
            "category": "ACADEMIC_ARTICLE",
            "authors": ["Sudhir Varma", "Richard Simon"],
            "year": 2006,
            "title": "Bias in error estimation when using cross-validation for model selection",
            "venue": "BMC Bioinformatics, 7, Article 91",
            "persistent_id": "doi:10.1186/1471-2105-7-91",
            "verification_url": "https://link.springer.com/article/10.1186/1471-2105-7-91",
            "verification_level": "OPEN_PUBLISHER_FULL_TEXT_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH03", "CH06"],
            "use_boundary": "Model-selection and error-estimation separation rationale; not a claim of statistical significance here.",
            "counts_toward_scientific_minimum": True,
        },
        {
            "source_id": "ACAD06",
            "category": "ACADEMIC_ARTICLE",
            "authors": ["Marina Sokolova", "Guy Lapalme"],
            "year": 2009,
            "title": "A systematic analysis of performance measures for classification tasks",
            "venue": "Information Processing & Management, 45(4), 427–437",
            "persistent_id": "doi:10.1016/j.ipm.2009.03.002",
            "verification_url": "https://dl.acm.org/doi/10.1016/j.ipm.2009.03.002",
            "verification_level": "PUBLISHER_METADATA_AND_ABSTRACT_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH03", "CH06"],
            "use_boundary": "Accuracy and F-measure interpretation for classification; no new metric is authorized.",
            "counts_toward_scientific_minimum": True,
        },
        {
            "source_id": "ACAD07",
            "category": "ACADEMIC_ARTICLE",
            "authors": ["Alejandro Barredo Arrieta", "Natalia Díaz-Rodríguez", "Javier Del Ser", "Adrien Bennetot", "Siham Tabik", "Alberto Barbado", "Salvador García", "Sergio Gil-López", "Daniel Molina", "Richard Benjamins", "Raja Chatila", "Francisco Herrera"],
            "year": 2020,
            "title": "Explainable Artificial Intelligence (XAI): Concepts, taxonomies, opportunities and challenges toward responsible AI",
            "venue": "Information Fusion, 58, 82–115",
            "persistent_id": "doi:10.1016/j.inffus.2019.12.012",
            "verification_url": "https://arxiv.org/abs/1910.10045",
            "verification_level": "AUTHOR_PREPRINT_AND_PUBLISHER_METADATA_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH02", "CH06"],
            "use_boundary": "Explainability terminology and audience context; project provenance must not be relabeled as an unimplemented post-hoc XAI method.",
            "counts_toward_scientific_minimum": True,
        },
        {
            "source_id": "ACAD08",
            "category": "ACADEMIC_ARTICLE",
            "authors": ["Fabian Pedregosa", "Gaël Varoquaux", "Alexandre Gramfort", "Vincent Michel", "Bertrand Thirion", "Olivier Grisel", "Mathieu Blondel", "Peter Prettenhofer", "Ron Weiss", "Vincent Dubourg", "Jake VanderPlas", "Alexandre Passos", "David Cournapeau", "Matthieu Brucher", "Matthieu Perrot", "Édouard Duchesnay"],
            "year": 2011,
            "title": "Scikit-learn: Machine Learning in Python",
            "venue": "Journal of Machine Learning Research, 12, 2825–2830",
            "persistent_id": "JMLR:v12:pedregosa11a",
            "verification_url": "https://jmlr.org/papers/v12/pedregosa11a.html",
            "verification_level": "OPEN_PUBLISHER_FULL_TEXT_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH04"],
            "use_boundary": "Implementation-library provenance only; estimator choice and results remain internal project evidence.",
            "counts_toward_scientific_minimum": True,
        },
        {
            "source_id": "ACAD09",
            "category": "ACADEMIC_ARTICLE",
            "authors": ["Mei-Chen Hsueh", "Timothy K. Tsai", "Ravishankar K. Iyer"],
            "year": 1997,
            "title": "Fault injection techniques and tools",
            "venue": "Computer, 30(4), 75–82",
            "persistent_id": "doi:10.1109/2.585157",
            "verification_url": "https://experts.illinois.edu/en/publications/fault-injection-techniques-and-tools/",
            "verification_level": "INSTITUTIONAL_AND_PUBLISHER_METADATA_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH03"],
            "use_boundary": "General controlled fault-injection methodology; not evidence that every fault type is covered by this project.",
            "counts_toward_scientific_minimum": True,
        },
        {
            "source_id": "STD01",
            "category": "INTERNET_STANDARD",
            "authors": ["Jon Postel"],
            "year": 1981,
            "title": "Internet Control Message Protocol",
            "venue": "RFC 792, STD 5",
            "persistent_id": "RFC792",
            "verification_url": "https://www.rfc-editor.org/info/rfc792/",
            "verification_level": "OFFICIAL_FULL_TEXT_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH02"],
            "use_boundary": "ICMP protocol behavior underlying collected evidence; not a performance or diagnosis result.",
            "counts_toward_scientific_minimum": False,
        },
        {
            "source_id": "STD02",
            "category": "INTERNET_STANDARD",
            "authors": ["Fred Baker"],
            "year": 1995,
            "title": "Requirements for IP Version 4 Routers",
            "venue": "RFC 1812",
            "persistent_id": "RFC1812",
            "verification_url": "https://www.rfc-editor.org/info/rfc1812/",
            "verification_level": "OFFICIAL_FULL_TEXT_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH02"],
            "use_boundary": "IPv4 forwarding and router behavior; not support for production generalization.",
            "counts_toward_scientific_minimum": False,
        },
        {
            "source_id": "TECH01",
            "category": "OFFICIAL_TECHNICAL_DOCUMENTATION",
            "authors": ["Containerlab project"],
            "year": 2026,
            "title": "Topology definition",
            "venue": "Containerlab documentation",
            "persistent_id": "containerlab:topology-definition",
            "verification_url": "https://containerlab.dev/manual/topo-def-file/",
            "verification_level": "OFFICIAL_DOCUMENTATION_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH04"],
            "use_boundary": "Tool and topology-file description only; implementation claims require repository evidence.",
            "counts_toward_scientific_minimum": False,
        },
        {
            "source_id": "TECH02",
            "category": "OFFICIAL_TECHNICAL_SPECIFICATION",
            "authors": ["JSON Schema project"],
            "year": 2020,
            "title": "JSON Schema Draft 2020-12",
            "venue": "JSON Schema specification",
            "persistent_id": "JSON-SCHEMA-2020-12",
            "verification_url": "https://json-schema.org/draft/2020-12",
            "verification_level": "OFFICIAL_SPECIFICATION_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH04"],
            "use_boundary": "Artifact-contract format only; validation success remains internal project evidence.",
            "counts_toward_scientific_minimum": False,
        },
        {
            "source_id": "TECH03",
            "category": "OFFICIAL_TECHNICAL_SPECIFICATION",
            "authors": ["OpenAPI Initiative"],
            "year": 2021,
            "title": "OpenAPI Specification 3.1.0",
            "venue": "OpenAPI Initiative",
            "persistent_id": "OAS:3.1.0",
            "verification_url": "https://github.com/OAI/OpenAPI-Specification/blob/main/versions/3.1.0.md",
            "verification_level": "OFFICIAL_SPECIFICATION_VERIFIED",
            "verified_on": verified_on,
            "chapter_ids": ["CH04"],
            "use_boundary": "API contract vocabulary only; route behavior requires repository evidence.",
            "counts_toward_scientific_minimum": False,
        },
    ]


def _research_questions() -> list[dict[str, Any]]:
    return [
        {
            "question_id": "RQ0",
            "kind": "PRIMARY",
            "text_sq": "Si krahasohen qasja me rregulla, Machine Learning dhe qasja hibride në diagnostikimin e problemeve të rrjetit brenda laboratorit të kontrolluar, dhe çfarë vlere operative sjell politika hibride pa presupozuar epërsi numerike?",
            "claim_ids": ["C03", "C04", "C05", "C06"],
        },
        {
            "question_id": "RQ1",
            "kind": "SECONDARY",
            "text_sq": "Çfarë mbulimi eksperimental ofrojnë gjashtë klasat dhe gjashtë kontekstet e kontrolluara me ndarje sipas kontekstit?",
            "claim_ids": ["C01", "C02"],
        },
        {
            "question_id": "RQ2",
            "kind": "SECONDARY",
            "text_sq": "Si sillen tri metodat në 24 hyrjet e pastra të testit nën protokollin e ngrirë report-only?",
            "claim_ids": ["C03", "C04", "C08"],
        },
        {
            "question_id": "RQ3",
            "kind": "SECONDARY",
            "text_sq": "Si ndikon mungesa deterministe e evidencës në saktësi, macro-F1, mbulim dhe dështim të kontrolluar të tri metodave?",
            "claim_ids": ["C05"],
        },
        {
            "question_id": "RQ4",
            "kind": "SECONDARY",
            "text_sq": "Si sigurojnë provenienca e politikës hibride dhe ndërfaqja lokale read-only gjurmueshmëri pa inferencë të re, remedim ose pretendime të reja?",
            "claim_ids": ["C06", "C07", "C08"],
        },
    ]


def render_chapter_csv(chapters: list[dict[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([
        "chapter_id",
        "title_sq",
        "role",
        "word_target_min",
        "word_target_max",
        "evidence_ids",
        "claim_ids",
        "research_question_ids",
        "source_ids",
        "asset_ids",
    ])
    for chapter in chapters:
        writer.writerow([
            chapter["chapter_id"],
            chapter["title_sq"],
            chapter["role"],
            chapter["word_target_min"],
            chapter["word_target_max"],
            ";".join(chapter["evidence_ids"]),
            ";".join(chapter["claim_ids"]),
            ";".join(chapter["research_question_ids"]),
            ";".join(chapter["source_ids"]),
            ";".join(chapter["asset_ids"]),
        ])
    return output.getvalue().encode("utf-8")


def render_source_csv(sources: list[dict[str, Any]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([
        "source_id",
        "category",
        "authors",
        "year",
        "title",
        "venue",
        "persistent_id",
        "verification_url",
        "verification_level",
        "verified_on",
        "chapter_ids",
        "counts_toward_scientific_minimum",
        "use_boundary",
    ])
    for source in sources:
        writer.writerow([
            source["source_id"],
            source["category"],
            ";".join(source["authors"]),
            source["year"],
            source["title"],
            source["venue"],
            source["persistent_id"],
            source["verification_url"],
            source["verification_level"],
            source["verified_on"],
            ";".join(source["chapter_ids"]),
            str(source["counts_toward_scientific_minimum"]).lower(),
            source["use_boundary"],
        ])
    return output.getvalue().encode("utf-8")


def build_gate_manifest(repository_root: Path, source_commit: str) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    closeout_path = repository_root / P8_CLOSEOUT_PATH
    synthesis_path = repository_root / P8_SYNTHESIS_PATH
    closeout = _load_json(closeout_path)
    synthesis = _load_json(synthesis_path)
    chapters = _chapters()
    sources = _sources()
    chapter_bytes = render_chapter_csv(chapters)
    source_bytes = render_source_csv(sources)

    return {
        "gate_id": "p9_r0_thesis_structure_source_citation_gate_v1",
        "schema_version": 1,
        "status": "ACCEPTED_WITH_FIEK_OVERRIDE_GUARD",
        "source_checkpoint": {
            "branch": "main",
            "commit": source_commit,
            "commit_short": source_commit[:7],
            "repository": "MesudHoxha/intelligent-network-diagnosis",
        },
        "accepted_phase8_boundary": {
            "path": P8_CLOSEOUT_PATH.as_posix(),
            "sha256": _sha256(closeout_path),
            "size_bytes": closeout_path.stat().st_size,
            "status": closeout["status"],
            "supported_claim_ids": closeout["claim_boundary"]["supported_claim_ids"],
            "blocked_claim_ids": closeout["claim_boundary"]["blocked_claim_ids"],
            "writing_constraints": closeout["phase9_handoff"]["writing_constraints"],
            "hybrid_interpretation": closeout["claim_boundary"]["hybrid_interpretation"],
            "masked_inputs": closeout["claim_boundary"]["masked_inputs"],
        },
        "university_alignment": {
            "authority_source_id": "INST01",
            "guide_status": "UNIVERSITY_WIDE_2026_GUIDE_VERIFIED",
            "thesis_type": "EMPIRICAL_ENGINEERING_PROJECT",
            "body_word_range": {"minimum": 8000, "maximum": 10000},
            "page_range_excluding_references_and_appendices": {"minimum": 30, "maximum": 50},
            "abstract_max_words": 350,
            "keyword_range": {"minimum": 3, "maximum": 5},
            "scientific_reference_recommendation_minimum": 30,
            "citation_family": "APA_AUTHOR_DATE",
            "required_front_matter": [
                "cover_and_title_page",
                "copyright_page",
                "originality_and_ai_use_declaration",
                "table_of_contents",
                "abstract_and_keywords",
            ],
            "required_back_matter": ["references", "appendices_if_used"],
            "ai_use_disclosure_required": True,
            "fiek_specific_public_guide_status": "NOT_LOCATED_AS_OF_2026_08_12",
            "fiek_or_mentor_override_policy": "APPLY_ONLY_IF_DOCUMENTED_AND_DO_NOT_CHANGE_EMPIRICAL_BOUNDARY",
        },
        "research_questions": _research_questions(),
        "chapter_structure": chapters,
        "source_gate": {
            "verified_source_count": len(sources),
            "verified_scientific_seed_count": sum(
                source["counts_toward_scientific_minimum"] for source in sources
            ),
            "final_scientific_reference_target_minimum": 30,
            "inventory_is_final_bibliography": False,
            "sources": sources,
            "admission_rules": [
                "VERIFY_AUTHOR_TITLE_YEAR_VENUE_AND_PERSISTENT_IDENTIFIER",
                "READ_PRIMARY_FULL_TEXT_OR_PUBLISHER_ABSTRACT_BEFORE_BOUNDED_USE",
                "PREFER_DOI_RFC_OR_OFFICIAL_STABLE_URL",
                "RECORD_CHAPTER_ROLE_AND_USE_BOUNDARY",
                "DO_NOT_CITE_SEARCH_SNIPPETS_OR_GENERATIVE_AI_AS_AUTHORITIES",
                "DO_NOT_USE_LITERATURE_TO_ENLARGE_INTERNAL_EMPIRICAL_CLAIMS",
            ],
        },
        "citation_and_asset_policy": {
            "in_text_style": "APA_AUTHOR_DATE",
            "direct_quote_requires_page_or_section": True,
            "reference_list_order": "ALPHABETICAL_BY_FIRST_AUTHOR",
            "reference_list_contains_only_cited_sources": True,
            "doi_form": "https://doi.org/{doi}",
            "edition_guard": "UP_GUIDE_REQUIRES_APA_AND_SHOWS_APA6_EXAMPLES_CONFIRM_FIEK_OR_MENTOR_BEFORE_FINAL_RENDERING",
            "table_numbering": "Table 1, Table 2, ... with title and source/note",
            "figure_numbering": "Figure 1, Figure 2, ... with caption and source/note",
            "internal_asset_rule": "P8_R2_VALUES_MUST_BE_COPIED_NOT_RECOMPUTED",
            "external_asset_rule": "LICENSE_OR_PERMISSION_AND_ATTRIBUTION_REQUIRED",
        },
        "traceability_assets": [
            {
                "asset_id": "P9T01",
                "path": CHAPTER_ASSET_PATH.as_posix(),
                "kind": "CSV_CHAPTER_STRUCTURE",
                "row_count": len(chapters),
                "size_bytes": len(chapter_bytes),
                "sha256": _sha256_bytes(chapter_bytes),
            },
            {
                "asset_id": "P9T02",
                "path": SOURCE_ASSET_PATH.as_posix(),
                "kind": "CSV_VERIFIED_SOURCE_SEED",
                "row_count": len(sources),
                "size_bytes": len(source_bytes),
                "sha256": _sha256_bytes(source_bytes),
            },
        ],
        "claim_boundary": {
            "supported_claims": synthesis["claim_matrix"],
            "blocked_claims": synthesis["blocked_claims"],
        },
        "drafting_authorization": {
            "chapter_skeleton": True,
            "bounded_paraphrase_of_verified_sources": True,
            "copy_exact_accepted_values": True,
            "format_accepted_tables_and_figures": True,
            "new_experiment": False,
            "test_partition_access": False,
            "estimator_deserialization": False,
            "metric_recalculation": False,
            "new_metric": False,
            "claim_broadening": False,
            "hybrid_superiority_claim": False,
            "search_snippet_as_citation": False,
            "generative_ai_as_academic_source": False,
        },
        "next_milestone": "P9-R1_THESIS_SKELETON_AND_TRACEABILITY_MATRIX",
    }


def _expected_json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_gate(repository_root: Path, source_commit: str) -> None:
    repository_root = repository_root.resolve()
    manifest = build_gate_manifest(repository_root, source_commit)
    chapters = manifest["chapter_structure"]
    sources = manifest["source_gate"]["sources"]
    outputs = {
        CHAPTER_ASSET_PATH: render_chapter_csv(chapters),
        SOURCE_ASSET_PATH: render_source_csv(sources),
        MANIFEST_PATH: _expected_json_bytes(manifest),
    }
    for relative_path, content in outputs.items():
        path = repository_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def verify_gate(repository_root: Path) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    manifest_path = repository_root / MANIFEST_PATH
    manifest = _load_json(manifest_path)
    rebuilt = build_gate_manifest(repository_root, manifest["source_checkpoint"]["commit"])
    if rebuilt != manifest:
        raise ValueError("Tracked P9-R0 manifest does not rebuild deterministically.")
    if manifest_path.read_bytes() != _expected_json_bytes(rebuilt):
        raise ValueError("Tracked P9-R0 manifest bytes are not canonical.")

    expected_assets = {
        CHAPTER_ASSET_PATH: render_chapter_csv(rebuilt["chapter_structure"]),
        SOURCE_ASSET_PATH: render_source_csv(rebuilt["source_gate"]["sources"]),
    }
    by_path = {Path(item["path"]): item for item in rebuilt["traceability_assets"]}
    for relative_path, expected_bytes in expected_assets.items():
        path = repository_root / relative_path
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"P9-R0 traceability asset is missing or unsafe: {relative_path}")
        if path.read_bytes() != expected_bytes:
            raise ValueError(f"P9-R0 traceability asset drifted: {relative_path}")
        metadata = by_path[relative_path]
        if metadata["size_bytes"] != len(expected_bytes):
            raise ValueError(f"P9-R0 traceability asset size drifted: {relative_path}")
        if metadata["sha256"] != _sha256_bytes(expected_bytes):
            raise ValueError(f"P9-R0 traceability asset hash drifted: {relative_path}")
    return rebuilt


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify the P9-R0 thesis gate.")
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--source-commit")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.write:
        if not args.source_commit:
            parser.error("--source-commit is required with --write")
        write_gate(args.repository_root, args.source_commit)
        print(f"p9_r0_gate={args.repository_root.resolve() / MANIFEST_PATH}")
        print("p9_r0_status=ACCEPTED_WITH_FIEK_OVERRIDE_GUARD")
    else:
        manifest = verify_gate(args.repository_root)
        print("p9_r0_gate=VERIFIED")
        print(f"verified_sources={manifest['source_gate']['verified_source_count']}")
        print(f"verified_scientific_seed={manifest['source_gate']['verified_scientific_seed_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
