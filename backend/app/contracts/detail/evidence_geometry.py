"""Lage der Nachweise auf der Seite – aus dem Text belegt, nicht angenommen.

Zur Lesezeit wird jeder Nachweis-Wortlaut im kanonischen Seitentext gesucht
(Abschnitte = Docling-Segmente mit eigener Box). Nur wenn der Wortlaut dort
steht, gilt die Box der getroffenen Abschnitte als genaue Lage. Steht er nicht
dort, bleibt die gespeicherte Box als ungefaehre Lage – nie als "genau".

Abgleich ohne Leerraum und Satzzeichen, damit Erkennungsfehler wie
"Frankfurtam Main" oder "Impella®AIC" den Treffer nicht verhindern.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# Eine genaue Box darf den Wortlaut nicht um ein Vielfaches ueberragen.
_MAX_OVERHANG = 3
_MIN_SPAN_CHARS = 160
_MIN_KEY_CHARS = 3


def match_key(text: Optional[str]) -> str:
    """Vergleichsschluessel: klein, ohne Leerraum, Satzzeichen und Auslassungszeichen."""
    return re.sub(r"[\W_]+", "", (text or "").replace("…", "").casefold())


def same_text(a: Optional[str], b: Optional[str]) -> bool:
    """Gleich bis auf Leerraum/Satzzeichen/Gross-Klein (fuer den Abgleich Dokument ↔ MedFlux)."""
    return bool(match_key(a)) and match_key(a) == match_key(b)


def _segments(page: dict) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for element in page.get("elements") or []:
        regions = [w for w in element.get("word_regions") or [] if isinstance(w, dict)]
        if regions:
            out.extend((str(w.get("text") or ""), w.get("region")) for w in regions)
        elif element.get("text"):
            out.append((str(element.get("text") or ""), element.get("region")))
    return [(text, region) for text, region in out if text.strip() and _is_box(region)]


def _is_box(region) -> bool:
    if not isinstance(region, dict):
        return False
    try:
        return float(region["x1"]) > float(region["x0"]) and float(region["y1"]) > float(region["y0"])
    except (KeyError, TypeError, ValueError):
        return False


def _union(regions: Iterable[dict]) -> dict:
    items = list(regions)
    return {
        "x0": min(float(r["x0"]) for r in items),
        "y0": min(float(r["y0"]) for r in items),
        "x1": max(float(r["x1"]) for r in items),
        "y1": max(float(r["y1"]) for r in items),
    }


def _center(box: dict) -> tuple[float, float]:
    return ((float(box["x0"]) + float(box["x1"])) / 2, (float(box["y0"]) + float(box["y1"])) / 2)


def flip_box(box: dict, height: float) -> dict:
    return {**box, "y0": max(0.0, height - float(box["y1"])), "y1": max(0.0, height - float(box["y0"]))}


def locate(page: dict, quote: Optional[str], near: Optional[dict] = None) -> Optional[tuple[dict, bool]]:
    """Sucht den Wortlaut auf der Seite. Liefert (Box, genau) oder None, wenn er dort nicht steht.

    `genau` heisst: die Box umfasst nur die Abschnitte mit dem Wortlaut und ist nicht viel
    groesser als er. Mehrere Fundstellen: die naechste zur gespeicherten Box.
    """
    target = match_key(quote)
    if len(target) < _MIN_KEY_CHARS:
        return None
    segments = _segments(page)
    if not segments:
        return None
    joined = ""
    owner: list[int] = []
    for index, (text, _region) in enumerate(segments):
        key = match_key(text)
        joined += key
        owner.extend([index] * len(key))
    hits: list[tuple[dict, int]] = []
    start = joined.find(target)
    while start >= 0:
        covered = sorted(set(owner[start:start + len(target)]))
        span = sum(len(match_key(segments[i][0])) for i in covered)
        hits.append((_union(segments[i][1] for i in covered), span))
        start = joined.find(target, start + 1)
    if not hits:
        return None
    if near is not None and _is_box(near) and len(hits) > 1:
        cx, cy = _center(near)
        hits.sort(key=lambda hit: (_center(hit[0])[0] - cx) ** 2 + (_center(hit[0])[1] - cy) ** 2)
    box, span = hits[0]
    return box, span <= max(len(target) * _MAX_OVERHANG, _MIN_SPAN_CHARS)


def flip_stored_box(ref: dict, pages: list[dict]) -> dict:
    """Gespeicherte Nachweis-Box aus einem Alt-Artefakt (unten-links) nach oben-links drehen.

    Nur fuer Boxen aus der Datenbank; Boxen aus `load_canonical_pages` sind bereits gedreht.
    """
    box = ref.get("bbox")
    if not _is_box(box) or ref.get("geometry_normalized") or ref.get("page") is None:
        return ref
    page = next((p for p in pages or [] if p.get("page") == ref.get("page")), None)
    if page is not None and page.get("legacy_bottom_up") and page.get("height_pt"):
        ref["bbox"] = flip_box(box, float(page["height_pt"]))
    return ref


def verify_evidence_locations(refs: list[dict], pages: list[dict], document_version_id) -> list[dict]:
    """Setzt `location` (exact/approx/page/none) und `text_verified` je Nachweis; korrigiert die Box.

    Nur Nachweise des Dokuments, dessen kanonische Seiten vorliegen; andere behalten ihre
    Box, gelten aber nie als genau (kein Textbeleg).
    """
    by_page = {int(page["page"]): page for page in pages or [] if page.get("page")}
    version = str(document_version_id) if document_version_id is not None else None
    for ref in refs:
        ref["text_verified"] = False
        page_no = ref.get("page")
        normalized = bool(ref.get("geometry_normalized"))
        box = ref.get("bbox") if _is_box(ref.get("bbox")) else None
        page = by_page.get(int(page_no)) if page_no is not None and ref.get("document_version_id") == version else None
        found = locate(page, ref.get("snippet"), near=None if normalized else box) if page is not None else None
        if found is not None:
            box, exact = found
            ref["text_verified"] = True
            ref["location"] = "exact" if exact else "approx"
            ref["geometry_normalized"] = False
            ref["bbox_space"] = "pdf_points"
        elif page_no is None:
            ref["location"] = "none"
        else:
            ref["location"] = "approx" if box is not None else "page"
        if box is not None:
            ref["bbox"] = {key: float(box[key]) for key in ("x0", "y0", "x1", "y1")}
            ref["supports_exact_navigation"] = page_no is not None
    return refs
