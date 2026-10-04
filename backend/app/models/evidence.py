"""Quellen-Nachweis (SourceEvidence) für extrahierte Vertragswerte.

Jeder wichtige extrahierte Wert kann mit einem Nachweis verknüpft werden,
damit Herkunft (Seite/Text), Confidence und Prüfbedarf nachvollziehbar sind.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ExtractionMethod


class BoundingBox(BaseModel):
    """Rechteck in PDF-Punkten der ORIGINAL-Seite (Quell-Navigation).

    Koordinatensystem: Original-PDF-Punkt (72/inch), Ursprung oben links,
    y wächst nach unten – identisch zu PyMuPDF `page.rect`. Für OCR-Einheiten
    wird deterministisch aus den OCR-Bildpixeln umgerechnet
    (app/documents/geometry.py); es werden keine unzuverlässigen
    Bildkoordinaten gespeichert.
    """

    x0: float = Field(ge=0.0)
    y0: float = Field(ge=0.0)
    x1: float = Field(ge=0.0)
    y1: float = Field(ge=0.0)


class SourceEvidence(BaseModel):
    """Quellennachweis eines extrahierten Wertes.

    PDF-Werte nutzen `page` (1-basiert). DOCX-Werte nutzen die optionalen
    Felder `source_type` (paragraph/table) sowie `paragraph_index` /
    `table_index` (jeweils 1-basiert) und optional `cell_index` – es werden
    KEINE erfundenen Seitennummern für DOCX vergeben.
    """

    model_config = {"protected_namespaces": ()}

    page: Optional[int] = Field(
        default=None, ge=1, description="Seitennummer (1-basiert), >= 1"
    )
    source_type: Optional[str] = Field(
        default=None, description="page|paragraph|table (DOCX-Kontext)"
    )
    paragraph_index: Optional[int] = Field(
        default=None, ge=1, description="DOCX-Absatzindex (1-basiert)"
    )
    table_index: Optional[int] = Field(
        default=None, ge=1, description="DOCX-Tabellenindex (1-basiert)"
    )
    cell_index: Optional[str] = Field(
        default=None, description="DOCX-Zelle als 'Zeile|Spalte', z. B. '2|3'"
    )
    source_text: Optional[str] = Field(
        default=None, description="Originaltext aus dem Dokument"
    )
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Confidence zwischen 0 und 1"
    )
    extraction_method: ExtractionMethod = Field(
        default=ExtractionMethod.AI, description="Extraktionsmethode"
    )
    requires_review: bool = Field(
        default=False, description="Erfordert manuelle Prüfung"
    )
    # -- Quell-Navigation (Behaltbarkeit, KEIN neues Rendering) --
    document_id: Optional[str] = Field(
        default=None, description="ID des Quelldokuments (für Navigations-Index)"
    )
    bounding_box: Optional[BoundingBox] = Field(
        default=None,
        description="Region auf der Original-PDF-Seite in PDF-Punkten "
        "(nur bei belegter, deterministischer Seiten-, Koordinaten-Zuordnung)",
    )
    ocr_confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Durchschnittliche OCR-Konfidenz des Nachweistextes (0..1)",
    )
    source_context: Optional[dict[str, Any]] = Field(
        default=None,
        description="Strukturierter Quellkontext, z. B. Tabellenkopf und Zellenadresse",
    )

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("confidence muss zwischen 0 und 1 liegen")
        return v
