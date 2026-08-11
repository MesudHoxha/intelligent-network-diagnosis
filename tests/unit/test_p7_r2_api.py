from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from src.phase7 import server
from src.phase7.api import CONTRACT_ID, SOURCE_ROLE, create_app
from src.phase7.catalog import ARTIFACT_SPECS
from src.phase7.projections import ProjectionLayer
from tests.unit.p7_r1_fixtures import build_p7_fixture_repository


EXPECTED_PATHS = {
    "/api/v1/health",
    "/api/v1/overview",
    "/api/v1/comparison",
    "/api/v1/cases",
    "/api/v1/cases/{input_id}",
    "/api/v1/provenance",
}
OPENAPI_CONTRACT = yaml.safe_load(
    (
        Path(__file__).resolve().parents[2]
        / "contracts/api/p7_readonly_api_v1.openapi.yml"
    ).read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def accepted_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_p7_fixture_repository(tmp_path_factory.mktemp("p7_r2_api"))


@pytest.fixture(scope="module")
def accepted_layer(accepted_root: Path) -> ProjectionLayer:
    return ProjectionLayer.from_repository(repository_root=accepted_root)


@pytest.fixture(scope="module")
def api_client(accepted_root: Path):
    application = create_app(repository_root=accepted_root)
    with TestClient(application) as client:
        yield client


def _assert_success_envelope(payload: dict[str, Any]) -> None:
    assert set(payload) == {"schema_version", "data", "meta"}
    assert payload["schema_version"] == 1
    assert payload["meta"] == {
        "contract_id": CONTRACT_ID,
        "read_only": True,
        "source_role": SOURCE_ROLE,
    }


def _assert_error(response: Any, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    payload = response.json()
    assert set(payload) == {"schema_version", "error"}
    assert payload["schema_version"] == 1
    assert payload["error"]["code"] == code
    assert set(payload["error"]) == {"code", "message"}
    assert payload["error"]["message"]


def _source_hashes(root: Path) -> dict[str, str]:
    return {
        spec.path: hashlib.sha256((root / spec.path).read_bytes()).hexdigest()
        for spec in ARTIFACT_SPECS
    }


def _validate_contract_schema(schema_name: str, payload: dict[str, Any]) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"#/components/schemas/{schema_name}",
        "components": OPENAPI_CONTRACT["components"],
    }
    Draft202012Validator(schema).validate(payload)


def test_application_exposes_exactly_six_get_routes() -> None:
    application = create_app(projection_layer=None)
    routes = [route for route in application.routes if isinstance(route, APIRoute)]

    assert {route.path for route in routes} == EXPECTED_PATHS
    assert all(route.methods == {"GET"} for route in routes)
    assert application.docs_url is None
    assert application.redoc_url is None
    assert application.openapi_url is None


@pytest.mark.parametrize(
    ("path", "expected_key"),
    [
        ("/api/v1/health", "status"),
        ("/api/v1/overview", "total_input_count"),
        ("/api/v1/provenance", "roots"),
    ],
)
def test_simple_routes_return_frozen_success_envelopes(
    path: str, expected_key: str, api_client: TestClient
) -> None:
    response = api_client.get(path)

    assert response.status_code == 200
    payload = response.json()
    _assert_success_envelope(payload)
    assert expected_key in payload["data"]


@pytest.mark.parametrize("scope", ["clean", "masked_overall", "overall"])
def test_comparison_route_preserves_each_frozen_scope(
    scope: str, api_client: TestClient
) -> None:
    response = api_client.get("/api/v1/comparison", params={"scope": scope})

    assert response.status_code == 200
    payload = response.json()
    _assert_success_envelope(payload)
    assert payload["data"]["scope"] == scope
    assert payload["data"]["comparison_type"] == "DESCRIPTIVE_ONLY"
    assert len(payload["data"]["methods"]) == 3


def test_case_list_route_filters_and_paginates_deterministically(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/api/v1/cases",
        params={
            "fault_type": "acl_block",
            "mask_id": "clean",
            "page": 1,
            "page_size": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_success_envelope(payload)
    assert payload["data"]["pagination"] == {
        "page": 1,
        "page_size": 2,
        "total_items": 4,
        "total_pages": 2,
        "sort": "input_id:asc",
    }
    identifiers = [item["input_id"] for item in payload["data"]["items"]]
    assert identifiers == sorted(identifiers)


def test_case_detail_route_returns_the_verified_join(api_client: TestClient) -> None:
    first = api_client.get("/api/v1/cases", params={"page_size": 1}).json()["data"][
        "items"
    ][0]

    response = api_client.get(f"/api/v1/cases/{first['input_id']}")

    assert response.status_code == 200
    payload = response.json()
    _assert_success_envelope(payload)
    assert payload["data"]["input_id"] == first["input_id"]
    assert len(payload["data"]["predictions"]) == 3
    assert len(payload["data"]["evidence"]["features"]) == 10


def test_all_success_and_error_envelopes_validate_against_openapi(
    api_client: TestClient,
) -> None:
    listing = api_client.get("/api/v1/cases", params={"page_size": 1})
    input_id = listing.json()["data"]["items"][0]["input_id"]
    checks = (
        ("HealthResponse", api_client.get("/api/v1/health")),
        ("OverviewResponse", api_client.get("/api/v1/overview")),
        ("ComparisonResponse", api_client.get("/api/v1/comparison")),
        ("CaseListResponse", listing),
        ("CaseDetailResponse", api_client.get(f"/api/v1/cases/{input_id}")),
        ("ProvenanceResponse", api_client.get("/api/v1/provenance")),
        (
            "ErrorResponse",
            api_client.get("/api/v1/comparison", params={"scope": "invalid"}),
        ),
    )

    for schema_name, response in checks:
        _validate_contract_schema(schema_name, response.json())


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/v1/comparison", {"scope": "by_context"}),
        ("/api/v1/cases", {"context_id": ""}),
        ("/api/v1/cases", {"fault_type": "not-a-class"}),
        ("/api/v1/cases", {"mask_id": "not-a-mask"}),
        ("/api/v1/cases", {"method_id": "not-a-method"}),
        ("/api/v1/cases", {"prediction_status": "RESOLVED"}),
        ("/api/v1/cases", {"page": 0}),
        ("/api/v1/cases", {"page_size": 101}),
        ("/api/v1/cases", {"page": "not-an-integer"}),
    ],
)
def test_framework_and_projection_validation_are_normalized_to_400(
    path: str, params: dict[str, object], api_client: TestClient
) -> None:
    response = api_client.get(path, params=params)

    _assert_error(response, 400, "INVALID_QUERY")
    assert "detail" not in response.text


@pytest.mark.parametrize("input_id", ["unknown", "..%5C..%5Cetc%5Cpasswd"])
def test_unknown_case_ids_are_normalized_to_404(
    input_id: str, api_client: TestClient
) -> None:
    response = api_client.get(f"/api/v1/cases/{input_id}")

    _assert_error(response, 404, "CASE_NOT_FOUND")


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_mutating_methods_are_rejected_with_the_frozen_405_envelope(
    method: str, api_client: TestClient
) -> None:
    response = api_client.request(method, "/api/v1/overview")

    _assert_error(response, 405, "METHOD_NOT_ALLOWED")


def test_missing_artifact_keeps_service_available_with_503(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    (root / ARTIFACT_SPECS[5].path).unlink()

    with TestClient(create_app(repository_root=root)) as client:
        _assert_error(client.get("/api/v1/health"), 503, "ARTIFACT_SET_UNAVAILABLE")
        _assert_error(client.get("/api/v1/overview"), 503, "ARTIFACT_SET_UNAVAILABLE")


def test_artifact_drift_keeps_service_available_with_integrity_503(
    tmp_path: Path,
) -> None:
    root = build_p7_fixture_repository(tmp_path)
    source = root / ARTIFACT_SPECS[5].path
    source.write_bytes(source.read_bytes() + b"\n")

    with TestClient(create_app(repository_root=root)) as client:
        response = client.get("/api/v1/health")

    _assert_error(response, 503, "ARTIFACT_INTEGRITY_FAILED")
    assert str(root) not in response.text


def test_unexpected_loader_failure_is_a_path_free_500(tmp_path: Path) -> None:
    def fail_loader(_root: Path) -> ProjectionLayer:
        raise RuntimeError(f"sensitive path: {tmp_path}")

    application = create_app(repository_root=tmp_path, projection_factory=fail_loader)
    with TestClient(application, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/health")

    _assert_error(response, 500, "INTERNAL_ERROR")
    assert str(tmp_path) not in response.text
    assert "traceback" not in response.text.lower()


def test_catalog_loads_once_during_startup(
    accepted_root: Path, accepted_layer: ProjectionLayer
) -> None:
    calls: list[Path] = []

    def counted_loader(root: Path) -> ProjectionLayer:
        calls.append(root)
        return accepted_layer

    application = create_app(
        repository_root=accepted_root,
        projection_factory=counted_loader,
    )
    with TestClient(application) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/overview").status_code == 200
        assert client.get("/api/v1/provenance").status_code == 200

    assert calls == [accepted_root.resolve()]


def test_full_api_read_path_changes_no_source_and_needs_no_estimator(
    accepted_root: Path,
) -> None:
    estimator = accepted_root / "models/p6_r6_six_class_v1/selected_estimator.joblib"
    assert not estimator.exists()
    before = _source_hashes(accepted_root)

    with TestClient(create_app(repository_root=accepted_root)) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/overview").status_code == 200
        assert client.get("/api/v1/comparison").status_code == 200
        listing = client.get("/api/v1/cases", params={"page_size": 100})
        assert listing.status_code == 200
        input_id = listing.json()["data"]["items"][0]["input_id"]
        assert client.get(f"/api/v1/cases/{input_id}").status_code == 200
        assert client.get("/api/v1/provenance").status_code == 200

    assert _source_hashes(accepted_root) == before
    assert not estimator.exists()


def test_generated_documentation_routes_are_disabled(api_client: TestClient) -> None:
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert api_client.get(path).status_code == 404


def test_server_entrypoint_uses_local_non_reload_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(application: Any, **kwargs: Any) -> None:
        captured["application"] = application
        captured.update(kwargs)

    monkeypatch.setattr(server.uvicorn, "run", fake_run)

    server.main()

    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8000
    assert captured["reload"] is False
    assert captured["application"].openapi_url is None
