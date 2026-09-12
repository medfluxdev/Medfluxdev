"""Datenmodelle der Medflux-Textextraktion (Schritt 5)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import ExtractionStatus


class FileType(str, Enum):
    """Art des zu extrahierenden Dokuments."""

    PDF = "pdf"
    DOCX = "docx"


class SourceType(str, Enum):
    """Referenztyp einer Texteinheit."""

    PAGE = "page"
    PARAGRAPH = "paragraph"
    TABLE = "table"


class UnitMethod(str, Enum):
    """Methode, mit der eine Texteinheit gewonnen wurde."""

    TEXT = "text"
    OCR = "ocr"


class SourceBox(BaseModel):
    """Quellort einer Texteinheit/Region in PDF-Punkten der Original-Seite.

    Koordinaten beziehen sich IMMER auf die Original-PDF-Seite (Punkte,
    72/inch, Ursprung oben links, y nach unten). Für OCR-Seiten erfolgt die
    deterministische Umrechnung aus den OCR-Bildpixel über die bekannte
    Rasterauflösung (siehe app/documents/geometry.py) – es werden KEINE
    Bildkoordinaten gespeichert, die sich nicht auf die Seite abbilden lassen.
    """

    page: int = Field(ge=1, description="Seitennummer (1-basiert)")
    x0: float = Field(ge=0.0)
    y0: float = Field(ge=0.0)
    x1: float = Field(ge=0.0)
    y1: float = Field(ge=0.0)
    text: str = Field(default="", description="Wort-/Zeilentext an dieser Stelle")
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="OCR-Konfidenz (0..1), falls verfügbar"
    )


class ExtractionUnit(BaseModel):
    """Eine einzelne, quellbezogene Texteinheit (Seite/Absatz/Tabelle)."""

    source_type: SourceType
    index: int = Field(ge=0, description="Seitennummer (1-basiert) bzw. Absatz-/Tabellenindex")
    text: str
    method: UnitMethod = UnitMethod.TEXT
    # Quell-Navigation (Schritt-5/8B-Semantik): optionale Position der
    # Einheit in PDF-Punkten der Original-Seite. Niemals Pflicht, damit alle
    # bestehenden Aufrufer (DOCX, reine Textpfade) unverändert funktionieren.
    bbox: Optional[SourceBox] = Field(
        default=None, description="Gesamtregion der Einheit auf der Seite"
    )
    boxes: list[SourceBox] = Field(
        default_factory=list, description="Wort-/Zeilen-Boxen (native oder OCR)"
    )
    ocr_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Durchschnittliche OCR-Konfidenz der Einheit"
    )


class TextExtractionResult(BaseModel):
    """Ergebnis der lokalen Textextraktion eines Dokuments."""

    document_id: str
    file_type: FileType
    extraction_status: ExtractionStatus = ExtractionStatus.PARTIAL
    extraction_method: UnitMethod = UnitMethod.TEXT
    page_count: int = Field(ge=0)
    total_characters: int = Field(ge=0)
    text_available: bool = False
    requires_ocr: bool = False
    units: list[ExtractionUnit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: Optional[str] = None
