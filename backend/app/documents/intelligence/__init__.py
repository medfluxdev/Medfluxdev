"""Dokument-Intelligence (STEP 8B) – Exports."""

from app.documents.intelligence.canonical import (
    BoundingRegion,
    Cell,
    DocumentIntelligenceResult,
    Element,
    ElementType,
    Method,
    Page,
    ProcessingProvenance,
    TableStructure,
    TextSpan,
    build_canonical_text,
)
from app.documents.intelligence.provider import (
    DocumentIntelligenceProvider,
    DocumentIntelligenceSettings,
    IntelligenceProviderError,
    IntelligenceProviderUnavailableError,
    ProviderCapabilities,
    available_providers,
    get_provider,
)

__all__ = [
    "BoundingRegion",
    "Cell",
    "DocumentIntelligenceProvider",
    "DocumentIntelligenceResult",
    "DocumentIntelligenceSettings",
    "Element",
    "ElementType",
    "IntelligenceProviderError",
    "IntelligenceProviderUnavailableError",
    "Method",
    "Page",
    "ProcessingProvenance",
    "ProviderCapabilities",
    "TableStructure",
    "TextSpan",
    "available_providers",
    "build_canonical_text",
    "get_provider",
]