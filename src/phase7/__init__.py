"""Read-only Phase 7 artifact catalog and projection boundary."""

from .catalog import (
    ArtifactCatalog,
    ArtifactCatalogError,
    ArtifactIntegrityError,
    ArtifactSetUnavailableError,
    build_catalog_manifest,
)
from .projections import (
    CaseNotFoundError,
    ProjectionLayer,
    ProjectionQueryError,
)

__all__ = [
    "ArtifactCatalog",
    "ArtifactCatalogError",
    "ArtifactIntegrityError",
    "ArtifactSetUnavailableError",
    "CaseNotFoundError",
    "ProjectionLayer",
    "ProjectionQueryError",
    "build_catalog_manifest",
]
