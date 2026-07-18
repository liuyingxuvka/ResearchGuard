"""Validated LogicGuard template-pack catalog, selector, and builder."""

from .builder import EFFECTIVE_BOUNDARY, build_template_instance
from .catalog import (
    CatalogValidationError,
    MANIFEST_SCHEMA,
    PROFILE_SCHEMA,
    REQUIRED_FAMILIES,
    default_catalog_root,
    load_catalog,
)
from .models import (
    BuildResult,
    Finding,
    TemplateCatalog,
    TemplateInstance,
    TemplateProfile,
    TemplateRequest,
    TemplateSelection,
    ValidationObservation,
)
from .selection import select_template_pack

__all__ = [
    "BuildResult",
    "CatalogValidationError",
    "EFFECTIVE_BOUNDARY",
    "Finding",
    "MANIFEST_SCHEMA",
    "PROFILE_SCHEMA",
    "REQUIRED_FAMILIES",
    "TemplateCatalog",
    "TemplateInstance",
    "TemplateProfile",
    "TemplateRequest",
    "TemplateSelection",
    "ValidationObservation",
    "build_template_instance",
    "default_catalog_root",
    "load_catalog",
    "select_template_pack",
]
