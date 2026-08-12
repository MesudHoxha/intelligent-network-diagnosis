from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.routing import Mount

from src.phase7.api import DASHBOARD_DIRECTORY, create_app
from src.phase7.catalog import ARTIFACT_SPECS, ArtifactSetUnavailableError
from src.phase7.projections import ProjectionLayer
from tests.unit.p7_r1_fixtures import build_p7_fixture_repository


EXPECTED_API_PATHS = {
    "/api/v1/health",
    "/api/v1/overview",
    "/api/v1/comparison",
    "/api/v1/cases",
    "/api/v1/cases/{input_id}",
    "/api/v1/provenance",
}
STATIC_FILES = {
    "index.html": "text/html",
    "styles.css": "text/css",
    "app.js": "text/javascript",
}


class _DashboardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []
        self.scripts: list[str] = []
        self.sections: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(str(values["id"]))
        if tag == "link" and values.get("href"):
            self.links.append(str(values["href"]))
        if tag == "script" and values.get("src"):
            self.scripts.append(str(values["src"]))
        if tag == "section" and values.get("id"):
            self.sections.append(str(values["id"]))


@pytest.fixture(scope="module")
def accepted_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_p7_fixture_repository(tmp_path_factory.mktemp("p7_r3_dashboard"))


@pytest.fixture(scope="module")
def dashboard_client(accepted_root: Path):
    with TestClient(create_app(repository_root=accepted_root)) as client:
        yield client


def _source_hashes(root: Path) -> dict[str, str]:
    return {
        spec.path: hashlib.sha256((root / spec.path).read_bytes()).hexdigest()
        for spec in ARTIFACT_SPECS
    }


def test_dashboard_assets_are_exact_repository_static_files() -> None:
    assert DASHBOARD_DIRECTORY == Path(__file__).resolve().parents[2] / (
        "src/phase7/dashboard"
    )
    assert {path.name for path in DASHBOARD_DIRECTORY.iterdir()} == set(STATIC_FILES)
    assert all(path.is_file() and not path.is_symlink() for path in DASHBOARD_DIRECTORY.iterdir())


@pytest.mark.parametrize(
    ("path", "content_type"),
    [("/", "text/html"), ("/styles.css", "text/css"), ("/app.js", "text/javascript")],
)
def test_dashboard_assets_are_served_from_the_same_local_application(
    path: str, content_type: str, dashboard_client: TestClient
) -> None:
    response = dashboard_client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.content


def test_static_mount_does_not_change_the_six_route_data_api() -> None:
    application = create_app(projection_layer=None)
    api_routes = [route for route in application.routes if isinstance(route, APIRoute)]
    mounts = [route for route in application.routes if isinstance(route, Mount)]

    assert {route.path for route in api_routes} == EXPECTED_API_PATHS
    assert all(route.methods == {"GET"} for route in api_routes)
    assert len(mounts) == 1
    assert mounts[0].path == ""
    assert mounts[0].name == "dashboard"


def test_dashboard_contains_exactly_the_four_frozen_views_and_accessible_landmarks() -> None:
    parser = _DashboardParser()
    parser.feed((DASHBOARD_DIRECTORY / "index.html").read_text(encoding="utf-8"))

    assert parser.sections == ["overview", "comparison", "cases", "provenance"]
    assert len(parser.ids) == len(set(parser.ids))
    assert parser.links == ["/styles.css"]
    assert parser.scripts == ["/app.js"]
    html = (DASHBOARD_DIRECTORY / "index.html").read_text(encoding="utf-8")
    assert 'href="#main-content"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-label="Case filters"' in html
    assert '<dialog id="case-dialog"' in html
    assert "Loading accepted overview" in html
    assert "Loading accepted metrics" in html
    assert "Loading verified cases" in html
    assert "Verifying provenance projection" in html


def test_dashboard_uses_only_same_origin_get_requests_and_no_external_assets() -> None:
    html = (DASHBOARD_DIRECTORY / "index.html").read_text(encoding="utf-8")
    css = (DASHBOARD_DIRECTORY / "styles.css").read_text(encoding="utf-8")
    javascript = (DASHBOARD_DIRECTORY / "app.js").read_text(encoding="utf-8")
    combined = "\n".join((html, css, javascript))

    assert "http://" not in combined
    assert "https://" not in combined
    assert "url(" not in css
    assert 'method:' not in javascript
    assert "WebSocket" not in javascript
    assert "EventSource" not in javascript
    assert "localStorage" not in javascript
    assert "sessionStorage" not in javascript
    assert "document.cookie" not in javascript
    assert "eval(" not in javascript

    api_literals = set(re.findall(r'"(/api/v1/[a-z]+)"', javascript))
    assert api_literals == {
        "/api/v1/health",
        "/api/v1/overview",
        "/api/v1/comparison",
        "/api/v1/cases",
        "/api/v1/provenance",
    }


def test_dashboard_source_covers_loading_empty_error_and_retry_states() -> None:
    javascript = (DASHBOARD_DIRECTORY / "app.js").read_text(encoding="utf-8")
    stylesheet = (DASHBOARD_DIRECTORY / "styles.css").read_text(encoding="utf-8")

    for token in (
        "setLoading",
        "setError",
        "is-empty",
        "data-retry",
        "No evaluated cases match the selected filters.",
        "Accepted results unavailable",
    ):
        assert token in javascript
    assert ".state-box.is-error" in stylesheet
    assert ".state-box.is-empty" in stylesheet
    assert "prefers-reduced-motion" in stylesheet
    assert "focus-visible" in stylesheet


def test_static_dashboard_remains_available_when_artifacts_fail_closed(
    tmp_path: Path,
) -> None:
    def missing_projection(_root: Path) -> ProjectionLayer:
        raise ArtifactSetUnavailableError("not disclosed")

    application = create_app(
        repository_root=tmp_path,
        projection_factory=missing_projection,
    )
    with TestClient(application) as client:
        dashboard = client.get("/")
        health = client.get("/api/v1/health")

    assert dashboard.status_code == 200
    assert "Intelligent Network Diagnosis" in dashboard.text
    assert health.status_code == 503
    assert health.json()["error"]["code"] == "ARTIFACT_SET_UNAVAILABLE"
    assert str(tmp_path) not in health.text


def test_dashboard_and_complete_api_read_path_change_no_accepted_source(
    accepted_root: Path,
) -> None:
    estimator = accepted_root / "models/p6_r6_six_class_v1/selected_estimator.joblib"
    before = _source_hashes(accepted_root)
    assert not estimator.exists()

    with TestClient(create_app(repository_root=accepted_root)) as client:
        for path in ("/", "/styles.css", "/app.js"):
            assert client.get(path).status_code == 200
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/overview").status_code == 200
        for scope in ("clean", "masked_overall", "overall"):
            assert client.get(
                "/api/v1/comparison", params={"scope": scope}
            ).status_code == 200
        listing = client.get("/api/v1/cases", params={"page_size": 100})
        assert listing.status_code == 200
        input_id = listing.json()["data"]["items"][0]["input_id"]
        assert client.get(f"/api/v1/cases/{input_id}").status_code == 200
        assert client.get("/api/v1/provenance").status_code == 200

    assert _source_hashes(accepted_root) == before
    assert not estimator.exists()
