from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / "plans/phase7/P7_R0_READ_ONLY_INTERFACE_V1.json"
OPENAPI_PATH = ROOT / "contracts/api/p7_readonly_api_v1.openapi.yml"

EXPECTED_ROUTES = {
    "/api/v1/health",
    "/api/v1/overview",
    "/api/v1/comparison",
    "/api/v1/cases",
    "/api/v1/cases/{input_id}",
    "/api/v1/provenance",
}
EXPECTED_ROOT_HASHES = {
    "freeze_manifest": (
        "fa98a17e2ffae42f6dd009a13af65ad32174035eca8352bf26f321531a4fe0f5"
    ),
    "freeze_receipt": (
        "5c6c6537cb233efdeb52c6872f7a6ef7fb32eb3ac7b2474e2514b2908cd29bcc"
    ),
    "run_manifest": (
        "44c505b451c6211b4515564f4b889633b6d74ed0c618f19cc0ab3b9bdfe72b1d"
    ),
    "cross_method_comparison": (
        "ca1c15d04828c0ae61cacaf80a5ee6f49f64a9cf3ac151a4b4ccd2386987e570"
    ),
}


def load_plan() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def load_openapi() -> dict:
    value = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_plan_identity_and_status_are_frozen() -> None:
    plan = load_plan()
    assert plan["schema_version"] == 1
    assert plan["contract_id"] == "p7_readonly_dashboard_api_v1"
    assert plan["status"] == "FROZEN_FOR_IMPLEMENTATION"
    assert plan["mode"] == "READ_ONLY_ACCEPTED_ARTIFACT_PROJECTION"


def test_local_zero_cost_architecture_is_explicit() -> None:
    deployment = load_plan()["deployment"]
    assert deployment == {
        "api_framework": "fastapi",
        "application_server": "uvicorn",
        "bind_host": "127.0.0.1",
        "dashboard": "static_html_css_javascript",
        "same_origin": True,
        "external_assets": False,
        "database": "NONE",
        "paid_service": "NONE",
    }


def test_accepted_root_hashes_are_exact() -> None:
    roots = load_plan()["accepted_root_bindings"]
    assert len(roots) == 4
    assert {item["artifact_id"]: item["sha256"] for item in roots} == (
        EXPECTED_ROOT_HASHES
    )


def test_projection_allowlist_is_exact_and_contains_no_estimator() -> None:
    plan = load_plan()
    allowed = plan["projection_source_allowlist"]
    assert len(allowed) == len(set(allowed)) == 15
    assert all(path.endswith((".json", ".jsonl")) for path in allowed)
    assert not any(path.endswith(".joblib") for path in allowed)
    assert "models/p6_r6_six_class_v1/selected_estimator.joblib" in (
        plan["forbidden_runtime_sources"]
    )


def test_http_surface_contains_only_frozen_get_routes() -> None:
    plan = load_plan()
    specification = load_openapi()
    assert plan["allowed_http_methods"] == ["GET"]
    assert set(plan["api_routes"]) == EXPECTED_ROUTES
    assert set(specification["paths"]) == EXPECTED_ROUTES
    for path_item in specification["paths"].values():
        operations = {key.lower() for key in path_item if not key.startswith("x-")}
        assert operations == {"get"}


def test_openapi_is_local_read_only_and_same_contract() -> None:
    specification = load_openapi()
    assert specification["openapi"] == "3.1.0"
    assert specification["servers"] == [{"url": "http://127.0.0.1:8000"}]
    assert specification["security"] == []
    assert specification["x-p7-read-only"] is True
    assert specification["x-p7-contract-id"] == (
        load_plan()["contract_id"]
    )


def test_success_responses_use_versioned_data_and_meta_envelopes() -> None:
    specification = load_openapi()
    schemas = specification["components"]["schemas"]
    response_names = {
        "HealthResponse",
        "OverviewResponse",
        "ComparisonResponse",
        "CaseListResponse",
        "CaseDetailResponse",
        "ProvenanceResponse",
    }
    for name in response_names:
        assert schemas[name]["required"] == ["schema_version", "data", "meta"]
        assert schemas[name]["properties"]["schema_version"]["const"] == 1
        assert schemas[name]["properties"]["meta"]["$ref"].endswith(
            "/ResponseMeta"
        )


def test_error_codes_and_fail_closed_invariants_are_frozen() -> None:
    plan = load_plan()
    assert set(plan["error_codes"]) == {
        "INVALID_QUERY",
        "CASE_NOT_FOUND",
        "METHOD_NOT_ALLOWED",
        "ARTIFACT_SET_UNAVAILABLE",
        "ARTIFACT_INTEGRITY_FAILED",
        "INTERNAL_ERROR",
    }
    invariants = set(plan["invariants"])
    assert "FAIL_CLOSED_ON_MISSING_OR_DRIFTED_ARTIFACT" in invariants
    assert "NO_MODEL_DESERIALIZATION_OR_INFERENCE" in invariants
    assert "NO_FILESYSTEM_WRITE" in invariants
    assert "NO_GENERIC_FILE_OR_DOWNLOAD_ENDPOINT" in invariants


def test_case_pagination_and_method_specific_status_filter_are_bounded() -> None:
    plan = load_plan()
    assert plan["pagination"] == {
        "default_page": 1,
        "default_page_size": 25,
        "maximum_page_size": 100,
        "sort_key": "input_id",
        "sort_direction": "ascending",
    }
    parameters = load_openapi()["paths"]["/api/v1/cases"]["get"]["parameters"]
    by_name = {parameter["name"]: parameter for parameter in parameters}
    assert set(by_name) == {
        "context_id",
        "fault_type",
        "mask_id",
        "method_id",
        "prediction_status",
        "page",
        "page_size",
    }
    assert by_name["page_size"]["schema"]["maximum"] == 100
    assert by_name["prediction_status"]["description"] == "Requires method_id"


def test_dashboard_scope_and_next_milestone_are_bounded() -> None:
    plan = load_plan()
    assert plan["dashboard_views"] == [
        "overview",
        "method_comparison",
        "case_explorer",
        "provenance_and_limitations",
    ]
    assert plan["next_milestone"] == "P7-R1_ARTIFACT_CATALOG_AND_PROJECTION"
