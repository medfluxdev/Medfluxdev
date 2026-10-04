"""Quellen-Nachweis-Bruecke: kanonisches Element -> SourceEvidence (STEP 8B).

Provider-neutraler Uebergang von der Recognition-Ebene (Dokument-Intelligence)
in das Quellen-Nachweis-Modell. Grundsatz aus STEP 8B: OCR-/Recognition-
Konfidenz bleibt STRENG getrennt von jeder KI-semantischen Konfidenz.

- `ocr_confidence` traegt die Recognition-Konfidenz des Elements (oder None,
  wenn z. B. native Textschicht oder Konfidenz nicht verfuegbar).
- `confidence` (semantische Konfidenz) bleibt hier IMMER None – sie wird erst
  von einer spaeteren, expliziten semantischen Stufe gesetzt.
- `extraction_method` wird als PROGRAMMATIC markiert (noch keine KI-Entscheidung).
"""

from __future__ import annotations

from typing import Optional

from app.documents.intelligence.canonical import Cell, Element
from app.models.enums import ExtractionMethod
from app.models.evidence import BoundingBox, SourceEvidence


def bounding_box_from_region(region) -> Optional[BoundingBox]:
    """Konvertiert eine kanonische Region (PDF-Punkte) zu `BoundingBox`.

    Keine Koordinaten-Erfindung: ohne Region wird None geliefert.
    """
    if region is None:
        return None
    return BoundingBox(x0=region.x0, y0=region.y0, x1=region.x1, y1=region.y1)


def evidence_from_element(
    element: Element,
    *,
    document_id: Optional[str] = None,
    source_text: Optional[str] = None,
    page: Optional[int] = None,
) -> SourceEvidence:
    """Baut einen SourceEvidence-Nachweis aus einem kanonischen Element.

    Args:
        element: Kanonisches Element (Region/Methode/Konfidenz).
        document_id: Optionales Quelldokument (fuer Navigations-Index).
        source_text: Optionaler wörtlicher Quelltext (fallback: element.text).
        page: Optionaler Seiten-Override (default: element.page).
    Returns:
        SourceEvidence mit getrennter OCR-/semantischer Konfidenz.
    """
    return SourceEvidence(
        page=page if page is not None else element.page,
        source_type="page",
        source_text=source_text if source_text is not None else element.text,
        confidence=None,  # semantische Konfidenz gehoert NICHT hierher
        extraction_method=ExtractionMethod.PROGRAMMATIC,
        requires_review=False,
        document_id=document_id,
        bounding_box=bounding_box_from_region(element.region),
        ocr_confidence=element.confidence,
    )


def evidence_from_cell(
    cell: Cell,
    *,
    document_id: Optional[str] = None,
    page: Optional[int] = None,
) -> Optional[SourceEvidence]:
    """Baut einen SourceEvidence-Nachweis aus einer Tabellenzelle.

    Gibt None zurueck, wenn keine Beleg-Text vorhanden ist (z. B. leere Zelle).
    """
    if cell is None or not (cell.text or "").strip():
        return None
    return SourceEvidence(
        page=page if page is not None else (cell.region.page if cell.region else None),
        source_type="page",
        source_text=cell.text,
        confidence=None,
        extraction_method=ExtractionMethod.PROGRAMMATIC,
        requires_review=False,
        document_id=document_id,
        bounding_box=bounding_box_from_region(cell.region),
        ocr_confidence=cell.confidence,
    )