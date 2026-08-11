from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.phase7.catalog import ARTIFACT_SPECS
from src.phase7.projections import (
    CaseNotFoundError,
    ProjectionLayer,
    ProjectionQueryError,
)
from tests.unit.p7_r1_fixtures import build_p7_fixture_repository


def _layer(tmp_path: Path) -> tuple[Path, ProjectionLayer]:
    root = build_p7_fixture_repository(tmp_path)
    return root, ProjectionLayer.from_repository(repository_root=root)


def _hashes(root: Path) -> dict[str, str]:
    return {
        spec.path: hashlib.sha256((root / spec.path).read_bytes()).hexdigest()
        for spec in ARTIFACT_SPECS
    }


def test_health_overview_and_provenance_use_accepted_identities(tmp_path: Path) -> None:
    _, layer = _layer(tmp_path)

    assert dict(layer.health()) == {
        "status": "READY",
        "verified_root_count": 4,
        "projection_source_count": 15,
    }
    overview = layer.overview()
    assert overview["clean_input_count"] == 24
    assert overview["masked_input_count"] == 96
    assert overview["total_input_count"] == 120
    assert overview["selected_ml_candidate"] == "logreg_l2_c1"
    assert overview["selected_hybrid_policy"] == "rule_then_ml_fallback_v1"
    provenance = layer.provenance()
    assert len(provenance["roots"]) == 4
    assert all(root["verified"] is True for root in provenance["roots"])
    assert len(provenance["limitations"]) == 4


@pytest.mark.parametrize("scope", ["clean", "masked_overall", "overall"])
def test_comparison_preserves_raw_accepted_metrics(scope: str, tmp_path: Path) -> None:
    _, layer = _layer(tmp_path)

    projection = layer.comparison(scope)

    assert projection["scope"] == scope
    assert projection["comparison_type"] == "DESCRIPTIVE_ONLY"
    assert projection["statistical_superiority_test"] == "NOT_PERFORMED"
    assert [item["method_id"] for item in projection["methods"]] == [
        "rule_based_p6_v1",
        "machine_learning_p6_v1",
        "hybrid_p6_v1",
    ]
    assert projection["methods"][1]["metrics"] == projection["methods"][2]["metrics"]


def test_case_listing_is_sorted_filterable_and_deterministically_paginated(
    tmp_path: Path,
) -> None:
    _, layer = _layer(tmp_path)

    first_page = layer.list_cases(page=1, page_size=25)
    second_page = layer.list_cases(page=2, page_size=25)
    clean_acl = layer.list_cases(
        fault_type="acl_block", mask_id="clean", page_size=100
    )

    assert first_page["pagination"] == {
        "page": 1,
        "page_size": 25,
        "total_items": 120,
        "total_pages": 5,
        "sort": "input_id:asc",
    }
    first_ids = [item["input_id"] for item in first_page["items"]]
    second_ids = [item["input_id"] for item in second_page["items"]]
    assert first_ids == sorted(first_ids)
    assert first_ids[-1] < second_ids[0]
    assert clean_acl["pagination"]["total_items"] == 4
    assert all(item["mask_id"] == "clean" for item in clean_acl["items"])


def test_prediction_status_filter_requires_method_and_is_method_specific(
    tmp_path: Path,
) -> None:
    _, layer = _layer(tmp_path)

    with pytest.raises(ProjectionQueryError, match="requires a method_id"):
        layer.list_cases(prediction_status="INSUFFICIENT_EVIDENCE")

    rule_unresolved = layer.list_cases(
        method_id="rule_based_p6_v1",
        prediction_status="INSUFFICIENT_EVIDENCE",
        page_size=100,
    )
    ml_unresolved = layer.list_cases(
        method_id="machine_learning_p6_v1",
        prediction_status="INSUFFICIENT_EVIDENCE",
        page_size=100,
    )
    assert rule_unresolved["pagination"]["total_items"] == 96
    assert ml_unresolved["pagination"]["total_items"] == 0


def test_case_detail_contains_joined_evidence_target_and_three_predictions(
    tmp_path: Path,
) -> None:
    _, layer = _layer(tmp_path)
    input_id = layer.list_cases(page_size=1)["items"][0]["input_id"]

    detail = layer.case(input_id)

    assert detail["input_id"] == input_id
    assert len(detail["evidence"]["features"]) == 10
    assert len(detail["evidence"]["availability"]) == 10
    assert detail["expected_diagnosis"]["fault_type"] == detail["expected_fault_type"]
    assert [prediction["method_id"] for prediction in detail["predictions"]] == [
        "rule_based_p6_v1",
        "machine_learning_p6_v1",
        "hybrid_p6_v1",
    ]


def test_unknown_and_traversal_like_ids_never_become_paths(tmp_path: Path) -> None:
    _, layer = _layer(tmp_path)

    for input_id in ("unknown", "../../etc/passwd", "/absolute/path"):
        with pytest.raises(CaseNotFoundError):
            layer.case(input_id)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"scope": "by_context"}, "scope"),
        ({"page": 0}, "page"),
        ({"page_size": 101}, "page_size"),
        ({"fault_type": "not-a-class"}, "fault_type"),
        ({"mask_id": "not-a-mask"}, "mask_id"),
        ({"method_id": "not-a-method"}, "method_id"),
    ],
)
def test_invalid_projection_queries_fail_closed(
    kwargs: dict[str, object], message: str, tmp_path: Path
) -> None:
    _, layer = _layer(tmp_path)

    with pytest.raises(ProjectionQueryError, match=message):
        if "scope" in kwargs:
            layer.comparison(**kwargs)  # type: ignore[arg-type]
        else:
            layer.list_cases(**kwargs)  # type: ignore[arg-type]


def test_projection_operations_do_not_modify_any_source_artifact(tmp_path: Path) -> None:
    root = build_p7_fixture_repository(tmp_path)
    before = _hashes(root)
    layer = ProjectionLayer.from_repository(repository_root=root)

    layer.health()
    layer.overview()
    layer.comparison("overall")
    page = layer.list_cases(page=3, page_size=17)
    layer.case(page["items"][0]["input_id"])
    layer.provenance()

    assert _hashes(root) == before
