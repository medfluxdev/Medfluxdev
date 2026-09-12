"""Medflux – Textextraktion (Schritt 5).

Getter für die lokale Text-Extraktion von PDF/DOCX-Dokumenten, inkl.
Seiten-/Quellenzuordnung, Erkennung gescannter/leerer Dokumente und
lokalem OCR-Fallback.
"""

from app.documents.extraction.schemas import (
    ExtractionUnit,
    SourceType,
    TextExtractionResult,
    UnitMethod,
)
from app.documents.extraction.service import TextExtractionService

__all__ = [
    "ExtractionUnit",
    "SourceType",
    "TextExtractionResult",
    "TextExtractionService",
    "UnitMethod",
]
