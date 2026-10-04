"""Evidence-First-Verifikation (STEP 8B-Semantik).

Prüft deterministisch (ohne KI), ob ein von der KI gelieferter `SourceEvidence`
tatsächlich durch das extrahierte Dokument belegt ist. Grundlage sind die echten
Texteinheiten (ExtractionUnit) des Dokuments.

Regeln:
- DOCX (keine Seiten-Einheiten): `page` darf NICHT gesetzt werden (keine erfundene
  Seitennummer). Gültige Nachweise nutzen source_type 'paragraph'|'table' mit
  passendem paragraph_index/table_index (1-basiert) und source_text.
- PDF (Seiten-Einheiten): `page` muss existieren; source_text muss in der Seite stehen.
- Ist der Zeiger selbst nicht vorhanden bzw. der source_text nicht in der zitierten
  Einheit auffindbar, gilt der Nachweis als NICHT gestützt -> lower confidence und
  requires_review (never silent trust).
- Fehlt ein Positionszeiger, aber source_text ist belegt, wird per Ganztextsuche
  eine Einheit gesucht (falls eindeutig) und nachgeführt.
"""

from __future__ import annotations

from typing import Optional

from app.documents.extraction.schemas import ExtractionUnit, SourceType
from app.models.enums import ExtractionMethod
from app.models.evidence import BoundingBox, SourceEvidence


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def _find_unit(units: list[ExtractionUnit], source_type: SourceType, index: int):
    for u in units:
        if u.source_type == source_type and u.index == index:
            return u
    return None


def _attach_navigation(evidence: SourceEvidence, unit: Optional[ExtractionUnit]) -> None:
    """Füllt deterministisch bounding_box/ocr_confidence aus der Einheit.

    Mathematik statt Raterei: nur wenn die Einheit echte Wort-/Zeilen-Boxen
    (PDF-Punkte der Original-Seite) mitführt, wird die Region des Nachweis-
    texts daraus zusammengeführt; sonst die Einheiten-Region (unit.bbox).
    Fehlt beides, bleibt bounding_box None. Die OCR-Konfidenz wird nur aus
    der echten Einheit übernommen (niemals erfunden).
    """
    if unit is None:
        return
    if evidence.bounding_box is None:
        norm_text = _norm(evidence.source_text or "")
        box = None
        if unit.boxes and norm_text:
            match = [
                b for b in unit.boxes
                if b.text and _norm(b.text) and _norm(b.text) in norm_text
            ]
            if match:
                box = (
                    min(b.x0 for b in match),
                    min(b.y0 for b in match),
                    max(b.x1 for b in match),
                    max(b.y1 for b in match),
                )
        if box is None and unit.bbox is not None:
            box = (unit.bbox.x0, unit.bbox.y0, unit.bbox.x1, unit.bbox.y1)
        if box is not None:
            evidence.bounding_box = BoundingBox(x0=box[0], y0=box[1], x1=box[2], y1=box[3])
    if evidence.ocr_confidence is None and unit.ocr_confidence is not None:
        evidence.ocr_confidence = unit.ocr_confidence


def _contains_evidence(unit: ExtractionUnit, source_text: Optional[str]) -> bool:
    if not source_text or not source_text.strip():
        return False
    return _norm(source_text) in _norm(unit.text)


def _search_all_units(
    units: list[ExtractionUnit], source_text: str
) -> Optional[ExtractionUnit]:
    """Sucht eine EINDEUTIGE Einheit, die source_text enthält."""
    found = [u for u in units if _contains_evidence(u, source_text)]
    return found[0] if len(found) == 1 else None


def _is_docx(units: list[ExtractionUnit]) -> bool:
    return not any(u.source_type == SourceType.PAGE for u in units)


def _downgrade(ev: SourceEvidence, issues: list[str], message: str) -> None:
    """Mark evidence as review-required without ever increasing confidence."""
    issues.append(message)
    ev.requires_review = True
    if ev.confidence is None or ev.confidence > 0.5:
        ev.confidence = 0.5


def verify_evidence(
    evidence: Optional[SourceEvidence], units: list[ExtractionUnit], *, max_source_len: int = 140
) -> tuple[Optional[SourceEvidence], list[str]]:
    """Prüft `evidence` gegen das Dokument.

    Liefert (nachgeführtes/normalisiertes evidenc_or_None, issues) – `issues` sind
    deutsche Hinweise, die zu requires_review bzw. Herabstufung führen.
    """
    if evidence is None:
        return None, []
    issues: list[str] = []

    ev = evidence.model_copy(deep=True)

    docx = _is_docx(units)
    text = ev.source_text or ""

    # A pointer alone is not evidence. Every accepted citation must carry a
    # concrete excerpt that can be checked against the original extraction unit.
    if not text.strip():
        _downgrade(ev, issues, "Nachweis ohne source_text ist nicht verifizierbar")

    # DOCX: eine erfundene Seite ist ein klarer Verstoß
    if docx and ev.page is not None:
        issues.append("DOCX: Seite darf nicht gesetzt werden (page entfernt)")
        ev.page = None

    if docx:
        # Positionszeiger prüfen
        if ev.source_type in ("page", None):
            # kein gültiger DOCX-Zeiger -> Ganztextsuche nachführen
            hit = _search_all_units(units, text) if text else None
            if hit is None:
                _downgrade(ev, issues, "Nachweis ohne gültige DOCX-Position, source_text nicht belegt")
            else:
                ev.source_type = hit.source_type.value
                if hit.source_type == SourceType.PARAGRAPH:
                    ev.paragraph_index = hit.index
                elif hit.source_type == SourceType.TABLE:
                    ev.table_index = hit.index
                _attach_navigation(ev, hit)
        else:
            if ev.source_type == "paragraph":
                unit = _find_unit(units, SourceType.PARAGRAPH, ev.paragraph_index or -1)
            elif ev.source_type == "table":
                unit = _find_unit(units, SourceType.TABLE, ev.table_index or -1)
            else:
                unit = None
            if unit is None:
                _downgrade(
                    ev,
                    issues,
                    f"Angegebene DOCX-Position ({ev.source_type} {ev.paragraph_index or ev.table_index}) existiert nicht",
                )
            else:
                if text and not _contains_evidence(unit, text):
                    _downgrade(ev, issues, "source_text nicht in der zitierten Einheit gefunden")
                _attach_navigation(ev, unit)
    else:
        # PDF
        if ev.page is None:
            hit = _search_all_units(units, text) if text else None
            if hit is None:
                _downgrade(ev, issues, "PDF-Nachweis ohne Seite und source_text nicht belegt")
            else:
                ev.page = hit.index
                _attach_navigation(ev, hit)
        else:
            unit = _find_unit(units, SourceType.PAGE, ev.page)
            if unit is None:
                _downgrade(ev, issues, f"Angegebene Seite {ev.page} existiert nicht")
            else:
                if text and not _contains_evidence(unit, text):
                    _downgrade(ev, issues, "source_text nicht auf der zitierten Seite gefunden")
                _attach_navigation(ev, unit)

    if ev.extraction_method != ExtractionMethod.AI:
        ev.extraction_method = ExtractionMethod.AI

    return ev, issues
