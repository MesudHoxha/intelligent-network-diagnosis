from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from fastapi.routing import APIRoute
from starlette.routing import Mount

from src.phase7.api import DASHBOARD_DIRECTORY, create_app
from src.phase7.server import DEFAULT_HOST, DEFAULT_PORT


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = REPOSITORY_ROOT / "docs/P7_R4_PHASE7_CLOSEOUT.md"
HANDOFF = REPOSITORY_ROOT / "docs/HANDOFF_P7_R4.md"
CATALOG = REPOSITORY_ROOT / (
    "plans/phase7/P7_R1_ACCEPTED_ARTIFACT_CATALOG_V1.json"
)
OPENAPI = REPOSITORY_ROOT / "contracts/api/p7_readonly_api_v1.openapi.yml"
EXPECTED_API_PATHS = {
    "/api/v1/health",
    "/api/v1/overview",
    "/api/v1/comparison",
    "/api/v1/cases",
    "/api/v1/cases/{input_id}",
    "/api/v1/provenance",
}


def test_phase7_data_api_route_set_remains_exactly_six_get_operations() -> None:
    application = create_app(projection_layer=None)
    routes = [route for route in application.routes if isinstance(route, APIRoute)]
    mounts = [route for route in application.routes if isinstance(route, Mount)]

    assert {route.path for route in routes} == EXPECTED_API_PATHS
    assert all(route.methods == {"GET"} for route in routes)
    assert len(mounts) == 1
    assert mounts[0].path == ""
    assert mounts[0].name == "dashboard"


def test_frozen_openapi_paths_match_the_runtime_data_routes() -> None:
    contract = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))

    assert set(contract["paths"]) == EXPECTED_API_PATHS
    assert all(set(path_item) == {"get"} for path_item in contract["paths"].values())
    assert contract["servers"] == [{"url": "http://127.0.0.1:8000"}]
    assert contract["x-p7-read-only"] is True


def test_phase7_dashboard_asset_set_remains_exactly_three_static_files() -> None:
    assets = list(DASHBOARD_DIRECTORY.iterdir())

    assert {asset.name for asset in assets} == {"index.html", "styles.css", "app.js"}
    assert all(asset.is_file() and not asset.is_symlink() for asset in assets)


def test_phase7_server_entry_point_remains_loopback_only() -> None:
    server_source = (REPOSITORY_ROOT / "src/phase7/server.py").read_text(
        encoding="utf-8"
    )

    assert DEFAULT_HOST == "127.0.0.1"
    assert DEFAULT_PORT == 8000
    assert "reload=False" in server_source
    assert "0.0.0.0" not in server_source


def test_closeout_runbook_has_reproducible_start_health_and_stop_steps() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "PYTHONDONTWRITEBYTECODE=1 python -m src.phase7.server" in runbook
    assert "http://127.0.0.1:8000/api/v1/health" in runbook
    assert "http://127.0.0.1:8000/" in runbook
    assert "Ctrl+C" in runbook
    assert "phase7_readiness=PASS" in runbook


def test_closeout_runbook_freezes_all_final_acceptance_commands() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")

    for test_file in (
        "test_p7_r0_interface_contract.py",
        "test_p7_r1_catalog.py",
        "test_p7_r1_projections.py",
        "test_p7_r2_api.py",
        "test_p7_r3_dashboard.py",
        "test_p7_r4_closeout.py",
    ):
        assert test_file in runbook
    assert "python -m pytest -q tests/unit/test_p6_*" in runbook
    assert "85/85" in runbook
    assert "185/185" in runbook
    assert "513/513" in runbook


def test_public_archive_policy_uses_only_the_tracked_head_tree() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    normalized = " ".join(runbook.split())

    assert "git archive --format=tar.gz" in runbook
    assert "HEAD" in runbook
    assert "source archive, not a self-contained accepted-result archive" in normalized
    for excluded in (".venv", "Containerlab state", "generated datasets", "model files"):
        assert excluded in runbook


def test_private_projection_archive_is_catalog_bounded_and_excludes_estimator() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    runbook = RUNBOOK.read_text(encoding="utf-8")
    paths = [artifact["path"] for artifact in catalog["artifacts"]]

    assert catalog["artifact_count"] == len(paths) == 15
    assert len(paths) == len(set(paths))
    assert not any(path.endswith("selected_estimator.joblib") for path in paths)
    assert 'catalog["artifact_count"] == 15' in runbook
    assert 'print(artifact["path"])' in runbook
    assert "The private bundle contains 16 files" in runbook
    assert "The selected estimator" in runbook


def test_p7_r4_handoff_contains_the_six_required_sections() -> None:
    handoff = HANDOFF.read_text(encoding="utf-8")
    headings = re.findall(r"^## (\d)\. ", handoff, flags=re.MULTILINE)

    assert headings == ["1", "2", "3", "4", "5", "6"]
    assert "Status: COMPLETED — PHASE 7 CLOSED" in handoff


def test_central_documents_close_phase7_and_name_p8_r0_next() -> None:
    roadmap = (REPOSITORY_ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
    status = (REPOSITORY_ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
    context = (REPOSITORY_ROOT / "docs/MASTER_CONTEXT.md").read_text(
        encoding="utf-8"
    )
    decisions = (REPOSITORY_ROOT / "docs/DECISIONS.md").read_text(encoding="utf-8")

    phase7 = roadmap.split("## Phase 7", 1)[1].split("## Phase 8", 1)[0]
    assert "Status: Complete" in phase7
    assert "P7-R4 Phase 7 closeout: complete" in phase7
    assert "P8-R0" in roadmap
    assert "P8-R0" in status
    assert "P8-R0" in context
    assert "## D-090" in decisions
