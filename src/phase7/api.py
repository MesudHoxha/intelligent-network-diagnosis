from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path as RepositoryPath
from typing import Annotated, Any, Callable, Literal, Mapping

from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.phase7.catalog import (
    CONTRACT_ID,
    ArtifactIntegrityError,
    ArtifactSetUnavailableError,
)
from src.phase7.projections import (
    CaseNotFoundError,
    ProjectionLayer,
    ProjectionQueryError,
)


SOURCE_ROLE = "ACCEPTED_P6_R6_REPORT_ONLY_ARTIFACTS"
DASHBOARD_DIRECTORY = RepositoryPath(__file__).resolve().parent / "dashboard"

Scope = Literal["clean", "masked_overall", "overall"]
FaultType = Literal[
    "no_fault",
    "missing_static_route",
    "wrong_next_hop",
    "wrong_default_gateway",
    "interface_down",
    "acl_block",
]
MaskId = Literal[
    "clean",
    "mask_source_gateway_family",
    "mask_route_family",
    "mask_interface_state",
    "mask_policy_state",
]
MethodId = Literal[
    "rule_based_p6_v1",
    "machine_learning_p6_v1",
    "hybrid_p6_v1",
]
PredictionStatus = Literal[
    "RESOLVED",
    "INSUFFICIENT_EVIDENCE",
    "ABSTAINED",
    "NO_RULE_MATCH",
]

ProjectionFactory = Callable[[RepositoryPath], ProjectionLayer]


@dataclass(frozen=True, slots=True)
class _ApiFailure:
    status_code: int
    code: str
    message: str


class _ApiFailureError(RuntimeError):
    def __init__(self, failure: _ApiFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


_INVALID_QUERY = _ApiFailure(
    400,
    "INVALID_QUERY",
    "Query parameters violate the frozen read-only contract.",
)
_CASE_NOT_FOUND = _ApiFailure(
    404,
    "CASE_NOT_FOUND",
    "The requested input_id is not in the verified report-only set.",
)
_METHOD_NOT_ALLOWED = _ApiFailure(
    405,
    "METHOD_NOT_ALLOWED",
    "This read-only API allows GET requests only.",
)
_ARTIFACT_UNAVAILABLE = _ApiFailure(
    503,
    "ARTIFACT_SET_UNAVAILABLE",
    "The accepted artifact set is unavailable.",
)
_ARTIFACT_INTEGRITY_FAILED = _ApiFailure(
    503,
    "ARTIFACT_INTEGRITY_FAILED",
    "The accepted artifact set failed integrity verification.",
)
_INTERNAL_ERROR = _ApiFailure(
    500,
    "INTERNAL_ERROR",
    "The read-only service encountered an internal error.",
)


def _load_projection(repository_root: RepositoryPath) -> ProjectionLayer:
    return ProjectionLayer.from_repository(repository_root=repository_root)


def _success(data: Mapping[str, Any]) -> JSONResponse:
    return JSONResponse(
        content=jsonable_encoder(
            {
                "schema_version": 1,
                "data": data,
                "meta": {
                    "contract_id": CONTRACT_ID,
                    "read_only": True,
                    "source_role": SOURCE_ROLE,
                },
            }
        )
    )


def _error(failure: _ApiFailure) -> JSONResponse:
    return JSONResponse(
        status_code=failure.status_code,
        content={
            "schema_version": 1,
            "error": {
                "code": failure.code,
                "message": failure.message,
            },
        },
    )


def _projection_from_request(request: Request) -> ProjectionLayer:
    failure = getattr(request.app.state, "projection_failure", None)
    if failure is not None:
        raise _ApiFailureError(failure)
    projection = getattr(request.app.state, "projection_layer", None)
    if projection is None:
        raise _ApiFailureError(_INTERNAL_ERROR)
    return projection


def create_app(
    *,
    repository_root: RepositoryPath | None = None,
    projection_layer: ProjectionLayer | None = None,
    projection_factory: ProjectionFactory | None = None,
) -> FastAPI:
    """Build the six-route API and its same-origin static Dashboard."""

    root = (repository_root or RepositoryPath.cwd()).resolve()
    factory = projection_factory or _load_projection

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.projection_layer = None
        application.state.projection_failure = None
        if projection_layer is not None:
            application.state.projection_layer = projection_layer
        else:
            try:
                application.state.projection_layer = factory(root)
            except ArtifactSetUnavailableError:
                application.state.projection_failure = _ARTIFACT_UNAVAILABLE
            except ArtifactIntegrityError:
                application.state.projection_failure = _ARTIFACT_INTEGRITY_FAILED
            except Exception:
                application.state.projection_failure = _INTERNAL_ERROR
        yield
        application.state.projection_layer = None

    application = FastAPI(
        title="Intelligent Network Diagnosis Read-Only API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @application.exception_handler(_ApiFailureError)
    async def api_failure_handler(
        _request: Request, error: _ApiFailureError
    ) -> JSONResponse:
        return _error(error.failure)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _error_value: RequestValidationError
    ) -> JSONResponse:
        return _error(_INVALID_QUERY)

    @application.exception_handler(ProjectionQueryError)
    async def projection_query_handler(
        _request: Request, _error_value: ProjectionQueryError
    ) -> JSONResponse:
        return _error(_INVALID_QUERY)

    @application.exception_handler(CaseNotFoundError)
    async def case_not_found_handler(
        _request: Request, _error_value: CaseNotFoundError
    ) -> JSONResponse:
        return _error(_CASE_NOT_FOUND)

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        if error.status_code == 405:
            return _error(_METHOD_NOT_ALLOWED)
        return await http_exception_handler(request, error)

    @application.exception_handler(Exception)
    async def internal_error_handler(
        _request: Request, _error_value: Exception
    ) -> JSONResponse:
        return _error(_INTERNAL_ERROR)

    @application.get("/api/v1/health", operation_id="getHealth")
    async def get_health(
        projection: Annotated[ProjectionLayer, Depends(_projection_from_request)],
    ) -> JSONResponse:
        return _success(projection.health())

    @application.get("/api/v1/overview", operation_id="getOverview")
    async def get_overview(
        projection: Annotated[ProjectionLayer, Depends(_projection_from_request)],
    ) -> JSONResponse:
        return _success(projection.overview())

    @application.get("/api/v1/comparison", operation_id="getComparison")
    async def get_comparison(
        projection: Annotated[ProjectionLayer, Depends(_projection_from_request)],
        scope: Annotated[Scope, Query()] = "overall",
    ) -> JSONResponse:
        return _success(projection.comparison(scope))

    @application.get("/api/v1/cases", operation_id="listCases")
    async def list_cases(
        projection: Annotated[ProjectionLayer, Depends(_projection_from_request)],
        context_id: Annotated[str | None, Query(min_length=1)] = None,
        fault_type: Annotated[FaultType | None, Query()] = None,
        mask_id: Annotated[MaskId | None, Query()] = None,
        method_id: Annotated[MethodId | None, Query()] = None,
        prediction_status: Annotated[PredictionStatus | None, Query()] = None,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> JSONResponse:
        return _success(
            projection.list_cases(
                context_id=context_id,
                fault_type=fault_type,
                mask_id=mask_id,
                method_id=method_id,
                prediction_status=prediction_status,
                page=page,
                page_size=page_size,
            )
        )

    @application.get("/api/v1/cases/{input_id}", operation_id="getCase")
    async def get_case(
        projection: Annotated[ProjectionLayer, Depends(_projection_from_request)],
        input_id: Annotated[str, Path(min_length=1)],
    ) -> JSONResponse:
        return _success(projection.case(input_id))

    @application.get("/api/v1/provenance", operation_id="getProvenance")
    async def get_provenance(
        projection: Annotated[ProjectionLayer, Depends(_projection_from_request)],
    ) -> JSONResponse:
        return _success(projection.provenance())

    application.mount(
        "/",
        StaticFiles(directory=DASHBOARD_DIRECTORY, html=True),
        name="dashboard",
    )

    return application


app = create_app()
