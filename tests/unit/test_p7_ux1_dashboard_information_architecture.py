from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from fastapi.routing import APIRoute

from src.phase7.api import DASHBOARD_DIRECTORY, create_app


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HTML = DASHBOARD_DIRECTORY / "index.html"
JAVASCRIPT = DASHBOARD_DIRECTORY / "app.js"
STYLESHEET = DASHBOARD_DIRECTORY / "styles.css"
EXPECTED_API_PATHS = {
    "/api/v1/health",
    "/api/v1/overview",
    "/api/v1/comparison",
    "/api/v1/cases",
    "/api/v1/cases/{input_id}",
    "/api/v1/provenance",
}


class _TableHeaderParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_case_table = False
        self.in_header = False
        self.headers: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attrs)
        if tag == "table" and "case-table" in str(values.get("class", "")):
            self.in_case_table = True
        if self.in_case_table and tag == "th":
            self.in_header = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "th":
            self.in_header = False
        if tag == "table" and self.in_case_table:
            self.in_case_table = False

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if self.in_header and value:
            self.headers.append(value)


def test_main_information_hierarchy_leads_with_result_and_explanation() -> None:
    html = HTML.read_text(encoding="utf-8")

    assert "Network Diagnosis Evaluation" in html
    assert "This dashboard compares three approaches" in html
    assert "Original test cases" in JAVASCRIPT.read_text(encoding="utf-8")
    assert "Missing-evidence tests" in JAVASCRIPT.read_text(encoding="utf-8")
    assert html.index("Network Diagnosis Evaluation") < html.index(
        "Research methodology & limitations"
    )


def test_case_explorer_prioritizes_human_labels_over_internal_ids() -> None:
    parser = _TableHeaderParser()
    parser.feed(HTML.read_text(encoding="utf-8"))

    assert parser.headers == [
        "Network problem",
        "Network scenario",
        "Evidence",
        "Rule-based",
        "Machine Learning",
        "Hybrid",
        "View case details",
    ]
    html = HTML.read_text(encoding="utf-8")
    assert "Technical scenario ID" in html
    assert '<details class="advanced-filter">' in html


def test_ground_truth_is_explicitly_evaluation_only_and_not_diagnostic_input() -> None:
    javascript = JAVASCRIPT.read_text(encoding="utf-8")

    assert "Known ground truth — evaluation only" in javascript
    assert "It is not provided to the diagnostic methods as input." in javascript
    assert "diagnosisResult" in javascript
    assert 'label: "Correct"' in javascript
    assert 'label: "Incorrect"' in javascript
    assert 'label: "No diagnosis"' in javascript


def test_metrics_have_plain_language_micro_explanations() -> None:
    javascript = JAVASCRIPT.read_text(encoding="utf-8")
    html = HTML.read_text(encoding="utf-8")

    for label, explanation in (
        ("Accuracy", "correct fault type"),
        ("Macro F1", "equal importance"),
        ("Coverage", "provided a diagnosis"),
        ("Insufficient evidence", "information was not enough"),
    ):
        assert label in javascript
        assert explanation in javascript
    assert "What do these metrics mean?" in html
    assert "View all accepted metrics" in html


def test_all_ten_evidence_features_have_human_labels_and_explanations() -> None:
    javascript = JAVASCRIPT.read_text(encoding="utf-8")
    feature_block = javascript.split(
        "const FEATURE_DEFINITIONS = Object.freeze({", 1
    )[1].split("const METRICS =", 1)[0]
    feature_names = re.findall(r"^  ([a-z][a-z0-9_]+): Object\.freeze", feature_block, re.MULTILINE)

    assert len(feature_names) == 10
    assert len(feature_names) == len(set(feature_names))
    assert feature_block.count("label:") == 10
    assert feature_block.count("description:") == 10
    assert "Diagnostic evidence" in javascript
    assert "Intentionally hidden for this missing-evidence evaluation." in javascript


def test_accepted_reasons_are_rephrased_but_retained_in_technical_details() -> None:
    javascript = JAVASCRIPT.read_text(encoding="utf-8")

    assert "friendlyReason" in javascript
    assert "Exact deterministic Phase 6 signature match." in javascript
    assert "Frozen six-class estimator argmax prediction." in javascript
    assert "Frozen Hybrid policy accepted the deterministic rule output." in javascript
    assert "Accepted reason:" in javascript
    assert "The dashboard does not run a new diagnosis." in javascript


def test_internal_ids_hashes_and_provenance_remain_available_but_collapsed() -> None:
    html = HTML.read_text(encoding="utf-8")
    javascript = JAVASCRIPT.read_text(encoding="utf-8")

    assert "Technical provenance and SHA-256 verification" in html
    assert "Technical details" in javascript
    for label in (
        "Case ID",
        "Sample ID",
        "Context ID",
        "Topology ID",
        "Evidence SHA-256",
        "Dataset row SHA-256",
    ):
        assert label in javascript


def test_ux_amendment_keeps_same_origin_get_only_runtime_boundary() -> None:
    application = create_app(projection_layer=None)
    routes = [route for route in application.routes if isinstance(route, APIRoute)]
    javascript = JAVASCRIPT.read_text(encoding="utf-8")
    combined = "\n".join(
        (
            HTML.read_text(encoding="utf-8"),
            javascript,
            STYLESHEET.read_text(encoding="utf-8"),
        )
    )

    assert {route.path for route in routes} == EXPECTED_API_PATHS
    assert all(route.methods == {"GET"} for route in routes)
    assert "http://" not in combined
    assert "https://" not in combined
    assert 'method:' not in javascript
    for prohibited in (
        "WebSocket",
        "EventSource",
        "localStorage",
        "sessionStorage",
        "document.cookie",
        "eval(",
    ):
        assert prohibited not in javascript


def test_ux_handoff_preserves_phase9_pause_and_scientific_boundary() -> None:
    handoff = (
        REPOSITORY_ROOT / "docs/HANDOFF_P7_UX1.md"
    ).read_text(encoding="utf-8")
    normalized = " ".join(handoff.split())
    headings = re.findall(r"^## (\d)\. ", handoff, flags=re.MULTILINE)

    assert headings == ["1", "2", "3", "4", "5", "6"]
    assert "P9-R1 remains paused" in handoff
    assert "No accepted prediction, metric, ground truth, or API contract changed" in normalized
