from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from src.campaign.phase6_plan import CLASS_ORDER
from src.phase6.contracts import MASK_ORDER, PREDICTION_STATUSES
from src.phase7.catalog import (
    DEFAULT_CATALOG_MANIFEST_PATH,
    DEFAULT_INTERFACE_PLAN_PATH,
    METHOD_ORDER,
    SCOPE_ORDER,
    ArtifactCatalog,
    _freeze,
)


LIMITATIONS = (
    "The 96 masked cases are deterministic transformations of 24 clean test "
    "cases, not independent network experiments.",
    "The three-method comparison is descriptive only; no statistical "
    "superiority test was performed.",
    "Machine Learning and Hybrid have identical aggregate results in every "
    "accepted comparison scope.",
    "Controlled laboratory results do not establish population-level or "
    "production-network generalization.",
)


class ProjectionError(ValueError):
    code = "INTERNAL_ERROR"


class ProjectionQueryError(ProjectionError):
    code = "INVALID_QUERY"


class CaseNotFoundError(ProjectionError):
    code = "CASE_NOT_FOUND"


def _prediction_projection(prediction: Mapping[str, Any]) -> Mapping[str, Any]:
    return _freeze(
        {
            "method_id": prediction["method_id"],
            "status": prediction["status"],
            "predicted_fault_type": prediction["predicted_fault_type"],
            "confidence": prediction["confidence"],
            "diagnosis": prediction["diagnosis"],
            "reason": prediction["reason"],
        }
    )


def _positive_integer(value: object, name: str, *, maximum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ProjectionQueryError(f"{name} must be a positive integer.")
    if maximum is not None and value > maximum:
        raise ProjectionQueryError(f"{name} must not exceed {maximum}.")
    return value


@dataclass(frozen=True, slots=True)
class ProjectionLayer:
    """Deterministic, immutable Python projections over one verified catalog."""

    catalog: ArtifactCatalog
    _health: Mapping[str, Any] = field(init=False, repr=False)
    _overview: Mapping[str, Any] = field(init=False, repr=False)
    _provenance: Mapping[str, Any] = field(init=False, repr=False)
    _case_summaries: tuple[Mapping[str, Any], ...] = field(init=False, repr=False)
    _case_details: Mapping[str, Mapping[str, Any]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        run = self.catalog.run_manifest
        selected_candidate = self.catalog.ml_selection["selected_candidate"][
            "candidate_id"
        ]
        selected_policy = self.catalog.hybrid_selection["selected_policy"][
            "candidate_id"
        ]
        object.__setattr__(
            self,
            "_health",
            _freeze(
                {
                    "status": "READY",
                    "verified_root_count": len(self.catalog.roots),
                    "projection_source_count": len(self.catalog.artifacts_by_path),
                }
            ),
        )
        object.__setattr__(
            self,
            "_overview",
            _freeze(
                {
                    "title": "Intelligent Network Diagnosis — Accepted P6-R6 Result",
                    "method_order": list(METHOD_ORDER),
                    "class_order": list(CLASS_ORDER),
                    "clean_input_count": run["test_clean_inputs"],
                    "masked_input_count": run["test_masked_inputs"],
                    "total_input_count": run["test_total_inputs"],
                    "selected_ml_candidate": selected_candidate,
                    "selected_hybrid_policy": selected_policy,
                    "comparison_type": self.catalog.comparison["comparison_type"],
                    "limitations": list(LIMITATIONS),
                }
            ),
        )
        object.__setattr__(
            self,
            "_provenance",
            _freeze(
                {
                    "roots": [
                        {
                            "artifact_id": root.artifact_id,
                            "path": root.path,
                            "sha256": root.sha256,
                            "verified": True,
                        }
                        for root in self.catalog.roots
                    ],
                    "projection_source_count": len(self.catalog.artifacts_by_path),
                    "selected_ml_candidate": selected_candidate,
                    "selected_hybrid_policy": selected_policy,
                    "limitations": list(LIMITATIONS),
                }
            ),
        )

        summaries: list[Mapping[str, Any]] = []
        details: dict[str, Mapping[str, Any]] = {}
        for method_input in sorted(
            self.catalog.inputs, key=lambda value: str(value["input_id"])
        ):
            input_id = str(method_input["input_id"])
            target = self.catalog.targets_by_id[input_id]
            predictions = tuple(
                _prediction_projection(
                    self.catalog.predictions_by_method[method_id][input_id]
                )
                for method_id in METHOD_ORDER
            )
            mask_id = method_input["mask_id"] or "clean"
            common = {
                "input_id": input_id,
                "sample_id": method_input["sample_id"],
                "context_id": method_input["split_group_id"],
                "topology_id": method_input["topology_id"],
                "mask_id": mask_id,
                "expected_fault_type": target["labels"]["fault_type"],
                "predictions": predictions,
            }
            summaries.append(_freeze(common))
            details[input_id] = _freeze(
                {
                    **common,
                    "direction": method_input["direction"],
                    "source_node": method_input["source_node"],
                    "route_observer_node": method_input["route_observer_node"],
                    "transit_node": method_input["transit_node"],
                    "destination_prefix": method_input["destination_prefix"],
                    "expected_diagnosis": target["labels"],
                    "evidence": {
                        "features": method_input["features"],
                        "availability": method_input["availability"],
                        "provenance": method_input["provenance"],
                    },
                }
            )
        object.__setattr__(self, "_case_summaries", tuple(summaries))
        object.__setattr__(self, "_case_details", MappingProxyType(details))

    @classmethod
    def from_repository(
        cls,
        *,
        repository_root: Path,
        interface_plan_path: Path = DEFAULT_INTERFACE_PLAN_PATH,
        catalog_manifest_path: Path = DEFAULT_CATALOG_MANIFEST_PATH,
    ) -> "ProjectionLayer":
        return cls(
            ArtifactCatalog.load(
                repository_root=repository_root,
                interface_plan_path=interface_plan_path,
                catalog_manifest_path=catalog_manifest_path,
            )
        )

    def health(self) -> Mapping[str, Any]:
        return self._health

    def overview(self) -> Mapping[str, Any]:
        return self._overview

    def comparison(self, scope: str = "overall") -> Mapping[str, Any]:
        if scope not in SCOPE_ORDER:
            raise ProjectionQueryError("scope is outside the frozen comparison set.")
        comparison = self.catalog.comparison
        methods = comparison["methods"]
        return _freeze(
            {
                "comparison_id": comparison["comparison_id"],
                "comparison_type": comparison["comparison_type"],
                "scope": scope,
                "methods": [
                    {"method_id": method_id, "metrics": methods[method_id][scope]}
                    for method_id in METHOD_ORDER
                ],
                "statistical_superiority_test": comparison[
                    "statistical_superiority_test"
                ],
            }
        )

    def list_cases(
        self,
        *,
        context_id: str | None = None,
        fault_type: str | None = None,
        mask_id: str | None = None,
        method_id: str | None = None,
        prediction_status: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Mapping[str, Any]:
        if context_id is not None and (
            not isinstance(context_id, str) or not context_id
        ):
            raise ProjectionQueryError("context_id must be a non-empty string.")
        if fault_type is not None and fault_type not in CLASS_ORDER:
            raise ProjectionQueryError("fault_type is outside the frozen class set.")
        if mask_id is not None and mask_id not in ("clean", *MASK_ORDER):
            raise ProjectionQueryError("mask_id is outside the frozen mask set.")
        if method_id is not None and method_id not in METHOD_ORDER:
            raise ProjectionQueryError("method_id is outside the frozen method set.")
        if prediction_status is not None:
            if method_id is None:
                raise ProjectionQueryError(
                    "prediction_status requires a method_id filter."
                )
            if prediction_status not in PREDICTION_STATUSES:
                raise ProjectionQueryError(
                    "prediction_status is outside the frozen status set."
                )
        valid_page = _positive_integer(page, "page")
        valid_page_size = _positive_integer(page_size, "page_size", maximum=100)

        filtered: list[Mapping[str, Any]] = []
        for item in self._case_summaries:
            if context_id is not None and item["context_id"] != context_id:
                continue
            if fault_type is not None and item["expected_fault_type"] != fault_type:
                continue
            if mask_id is not None and item["mask_id"] != mask_id:
                continue
            if prediction_status is not None:
                by_method = {
                    prediction["method_id"]: prediction
                    for prediction in item["predictions"]
                }
                if by_method[method_id]["status"] != prediction_status:
                    continue
            filtered.append(item)

        total_items = len(filtered)
        total_pages = ceil(total_items / valid_page_size) if total_items else 0
        start = (valid_page - 1) * valid_page_size
        stop = start + valid_page_size
        return _freeze(
            {
                "items": filtered[start:stop],
                "pagination": {
                    "page": valid_page,
                    "page_size": valid_page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "sort": "input_id:asc",
                },
            }
        )

    def case(self, input_id: str) -> Mapping[str, Any]:
        if not isinstance(input_id, str) or not input_id:
            raise ProjectionQueryError("input_id must be a non-empty string.")
        try:
            return self._case_details[input_id]
        except KeyError as error:
            raise CaseNotFoundError("The requested case is not in the verified index.") from error

    def provenance(self) -> Mapping[str, Any]:
        return self._provenance
