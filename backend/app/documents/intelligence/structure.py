"""Strukturrollen fuer Kopf-/Fuss-/Seitenzahlen und Wiederholungs-Haertung.

Hintergrund (STEP 8B): Docling klassifiziert auf Scans keine Kopf-/Fusszeilen
(ReadingOrder.hf_max_share = 0.0). Wiederkehrende Zeilen (Firmen-Kopf,
Seitenzahlen, Docusign-Envelope-ID, "Confidential") dominieren sonst die
Volltextsuche und spaetere KI-Extraktion.

Loesung: deterministischer, provider-neutraler Nachbereitungs-Pass, der im
kanonischen Modell lediglich `metadata["structural_role"]` setzt:
- `header`, `footer`, `page_number` – wiederholt ueber >= min_pages_share der
  Seiten an definierter Bande (oben/unten) ODER reines Seitenzahl-Muster.
- Text wird NIE geloescht oder veraendert; die Rollen erlauben Downstream-
  Systemen, Dominanz zu filtern (z. B. Docusign-Envelope-ID).

Kein Raten: eine Zeile wird nur dann markiert, wenn sie (a) bandkonform
wiederkehrt UND (b) den Schwellwert erreicht.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

from app.documents.intelligence.canonical import Element, ElementType, Page

HEADER = "header"
FOOTER = "footer"
PAGE_NUMBER = "page_number"
BODY = "body"

_PAGE_NUMBER_RE = re.compile(r"^(?:\d{1,3}|seite\s*\d{1,3})$", re.IGNORECASE)

# Normalisierung fuer Wiederholungs-Erkennung (Whitespace + Gross/Klein nur).
def _norm(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _has_region(e: Element) -> bool:
    return e is not None and e.region is not None


def _band(e: Element, page_height: float, top_fraction: float, bottom_fraction: float) -> Optional[str]:
    if e.region is None or page_height <= 0:
        return None
    y0 = e.region.y0
    y1 = e.region.y1
    top = min(top_fraction, 1.0) * page_height
    bottom = (1.0 - min(bottom_fraction, 1.0)) * page_height
    if y1 <= top:
        return HEADER
    if y0 >= bottom:
        return FOOTER
    return None


@dataclass
class StructuralRolesReport:
    """Ergebnis des Strukturrollen-Passes (Diagnose/Nachweis)."""

    marked: list[tuple[str, str]] = field(default_factory=list)
    roles_seen: dict[str, int] = field(default_factory=dict)
    skipped_no_region: int = 0

    @property
    def count(self) -> int:
        return len(self.marked)


def _classify_single_pages(pages: list[Page], top_fraction: float, bottom_fraction: float) -> dict[str, str]:
    """Seitenzahl-Erkennung: Musterbasiert + bandgebunden, isoliert je Seite."""
    result: dict[str, str] = {}
    for page in pages:
        for e in page.elements:
            text = (e.text or "").strip()
            if not text or not _has_region(e):
                continue
            if _PAGE_NUMBER_RE.match(text) and _band(e, page.height_pt, top_fraction, bottom_fraction):
                result[e.element_id] = PAGE_NUMBER
    return result


def apply_structural_roles(
    pages: list[Page],
    *,
    top_fraction: float = 0.08,
    bottom_fraction: float = 0.08,
    min_pages_share: float = 0.5,
) -> StructuralRolesReport:
    """Markiert wiederkehrende Kopf-/Fusszeilen und Seitenzahlen.

    Args:
        pages: Kanonische Seiten (in Lesereihenfolge).
        top_fraction/bottom_fraction: Anteil der Seitenhoehe als Band.
        min_pages_share: Mindestanteil der Seiten, auf denen eine Zeile
            in derselben Bande auftauchen muss, um markiert zu werden.
    Returns:
        Report mit markierten Elementen (nur `metadata` wird geschrieben).
    """
    if not pages:
        return StructuralRolesReport()
    total = len(pages)
    # Wiederholung braucht mindestens 2 Seiten, sonst ist "Kopf/Fuss" nicht belegbar.
    min_pages = max(2, math.ceil(min_pages_share * total))

    page_number_roles = _classify_single_pages(pages, top_fraction, bottom_fraction)

    # Zaehle Wiederholungen je Bande ueber alle Seiten (normalisiert).
    occurrence_header: dict[str, int] = {}
    occurrence_footer: dict[str, int] = {}
    for page in pages:
        seen_header_this_page: set[str] = set()
        seen_footer_this_page: set[str] = set()
        for e in page.elements:
            if not _has_region(e):
                continue
            text = (e.text or "").strip()
            if not text:
                continue
            band = _band(e, page.height_pt, top_fraction, bottom_fraction)
            if band == HEADER:
                key = _norm(text)
                if key not in seen_header_this_page:
                    occurrence_header[key] = occurrence_header.get(key, 0) + 1
                    seen_header_this_page.add(key)
            elif band == FOOTER:
                key = _norm(text)
                if key not in seen_footer_this_page:
                    occurrence_footer[key] = occurrence_footer.get(key, 0) + 1
                    seen_footer_this_page.add(key)

    header_keys = {k for k, v in occurrence_header.items() if v >= min_pages}
    footer_keys = {k for k, v in occurrence_footer.items() if v >= min_pages}

    report = StructuralRolesReport()
    for page in pages:
        for e in page.elements:
            if e.element_id in page_number_roles:
                e.metadata["structural_role"] = PAGE_NUMBER
                report.marked.append((e.element_id, PAGE_NUMBER))
                continue
            text = _norm(e.text or "")
            if not text or not _has_region(e):
                report.skipped_no_region += 1
                continue
            band = _band(e, page.height_pt, top_fraction, bottom_fraction)
            if band == HEADER and text in header_keys:
                e.metadata["structural_role"] = HEADER
                report.marked.append((e.element_id, HEADER))
            elif band == FOOTER and text in footer_keys:
                e.metadata["structural_role"] = FOOTER
                report.marked.append((e.element_id, FOOTER))

    for role in (PAGE_NUMBER, HEADER, FOOTER):
        report.roles_seen[role] = sum(1 for _, r in report.marked if r == role)
    return report


def dominant_repeated_lines(
    pages: list[Page],
    *,
    top_fraction: float = 0.08,
    bottom_fraction: float = 0.08,
    max_lines: int = 10,
) -> list[dict]:
    """Diagnose: haeufigste wiederholte normalisierte Zeilen ueber alle Seiten.

    Nur fuer Diagnose/Filtersnapshot – Downstream-Systeme duerfen diese Zeilen
    als Kandidaten fuer Rausch-Filter nutzen, muessen aber BODY-Texte erhalten.
    """
    aggregated: dict[str, dict] = {}
    for page in pages:
        for e in page.elements:
            if not _has_region(e):
                continue
            text = (e.text or "").strip()
            if not text:
                continue
            key = _norm(text)
            band = _band(e, page.height_pt, top_fraction, bottom_fraction) or BODY
            entry = aggregated.setdefault(
                key, {"text": text, "role": band, "pages": 0, "occurrences": 0}
            )
            entry["occurrences"] += 1
    # Seitenzahl berechnen: Anzahl Seiten mit mind. einem Vorkommen.
    per_key_pages: dict[str, set[int]] = {}
    for page in pages:
        for e in page.elements:
            text = _norm(e.text or "")
            if text and _has_region(e):
                per_key_pages.setdefault(text, set()).add(page.page_number)
    for key, entry in aggregated.items():
        entry["pages"] = len(per_key_pages.get(key, set()))

    lines = sorted(aggregated.values(), key=lambda d: (d["pages"], d["occurrences"]), reverse=True)
    return lines[:max_lines]