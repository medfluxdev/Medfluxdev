"""Exakte Quell-Navigation: Wort-/Segment-Boxen und transparente Hervorhebung.

Ziel (STEP 8B-Korrektur Gate D → prüfbar): Die Hervorhebung im Original-PDF
muss aus der Geometrie des tatsächlich getroffenen Tokens/Textes stammen –
NIE aus der grossflaechigen Element-/Absatz-Box.

1) `resolve_span_boxes()`: waehlt ausschliesslich WordRegion-Boxen, deren
   Seiten-Text-Span [offset, offset+length) überlappt. Gibt es koine, wird
   NUR als expliziter Fallback eine Element-Box mit granularity="element"
   geliefert (nie still).
2) `page_view_to_mediabox()`: wandelt kanonische (View-)Koordinaten in das
   ORIGINAL-PDF-Medibox-System um; beruecksichtigt page.rotation (0/90/180/
   270), Origin, View- vs. Medibox-Abmessungen. Kein Raten ueber Skalierung.
3) `guard_oversized()`: deterministische Schutzregel gegen obersgroesse Boxen
   (Breiten-/Hoehen-/Flaeche-Praportionen zur Zieltextlaenge, Seiten-Einschluss).
4) `render_transparent_highlights()`: erzeugt NUR ein abgeleitetes Render
   (derivatives PNG, Original bleibt unveraendert), halbtransparente Fuellung
   (`fill_opacity`), duenne Umrisslinie, Text bleibt lesbar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.documents.intelligence.canonical import (
    AtomicUnit,
    BoundingRegion,
    GeometryPrecision,
    Page,
    WordRegion,
)

# -------------------------------------------------------------- Spans -> Boxen


def _all_word_regions(page: Page) -> list[WordRegion]:
    out: list[WordRegion] = []
    for e in page.elements:
        out.extend(e.word_regions)
    return out


def _element_overlapping(page: Page, offset: int, length: int) -> list[WordRegion]:
    end = offset + length
    hits: list[WordRegion] = []
    for e in page.elements:
        if not e.text.strip() or not e.spans:
            continue
        sp = e.spans[0]
        if sp.offset < end and sp.to() > offset:
            for wr in e.word_regions:
                if wr.granularity == "element":
                    hits.append(wr)
                    return hits
            # Element hat nur segment-Boxen: genau eine "element"-Fallback-Box
            hits.append(
                WordRegion(
                    text=e.text,
                    offset=sp.offset,
                    length=len(e.text),
                    region=e.region,
                    granularity="element",
                )
            )
    return hits


def resolve_span_boxes(page: Page, offset: int, length: int) -> list[WordRegion]:
    """EOF (target-span) -> exakte Wort-/Segment-Boxen.

    Waehlt alle WordRegion.Boxen, die die Zielspanne wirklich schneiden.
    Ohne einen einzigen Treffer: Element-Fallback (granularity="element"),
    damit Die Navigation nicht schweigt – aber Zustand explizit kenntlich ist.
    """
    if length < 1 or offset < 0:
        return []
    end = offset + length
    hits = [wr for wr in _all_word_regions(page) if wr.offset < end and wr.to() > offset]
    if hits:
        return hits
    return _element_overlapping(page, offset, length)


# -------------------------------------------------------------- Atomare Aufloesung


@dataclass
class AtomicResolution:
    """Aufloesung eines Ziel-Spans durch atomare Geometrie.

    `status` (Confidence-Level, ehrlich):
    - EXACT_WORD:              Ziel in EINEM OCR-Wort-Box
    - VALIDATED_TABLE_CELL:    Ziel in validierter Tabellenzelle
    - EXACT_LINE:              Ziel in (einer) OCR-Zeilen-Box(en)
    - COARSE_FALLBACK:         nur grobe Element-Box (nie still als exakt)
    - UNAVAILABLE:             nichts aufloesbar
    """

    status: str
    boxes: list[BoundingRegion]
    units: list[AtomicUnit] = field(default_factory=list)
    coarse: Optional[WordRegion] = None
    signals: dict = field(default_factory=dict)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower())


_PREC_RANK = {
    GeometryPrecision.WORD: 4,
    GeometryPrecision.TABLE_CELL: 3,
    GeometryPrecision.LINE: 2,
    GeometryPrecision.COARSE_ELEMENT: 1,
    GeometryPrecision.ESTIMATED: 0,
}


def _overlap(u: AtomicUnit, offset: int, end: int) -> bool:
    if u.canonical_offset is None or u.canonical_length is None:
        return False
    return u.canonical_offset < end and u.canonical_offset + u.canonical_length > offset


def resolve_target_atomic(page: Page, offset: int, length: int) -> AtomicResolution:
    """EOF (target-span) -> atomare OCR-/Zell-Boxen MIT ehrlicher Klassifikation.

    Invariante fuer "exakt": der normalisierte Zielttext ist vollstaendig im
    `text` der gewaehlten Einheit(en) enthalten (Containment-Beweis). Fallback
    ist ausnahmslos die grobe Element-Box als COARSE_FALLBACK.
    """
    if length < 1 or offset < 0 or offset + length > len(page.text):
        return AtomicResolution(status="UNAVAILABLE", boxes=[])
    end = offset + length
    target = page.text[offset : offset + length]
    norm_target = _normalise(target)
    if not norm_target:
        return AtomicResolution(status="UNAVAILABLE", boxes=[])

    units = [
        u
        for u in page.atomic_units
        if u.aligned
        and u.bbox.page == page.page_number
        and _overlap(u, offset, end)
    ]
    containing = [u for u in units if norm_target in _normalise(u.text)]

    boxes: list[BoundingRegion] = []
    chosen: list[AtomicUnit] = []
    status = "COARSE_FALLBACK"

    if containing:
        ranked = sorted(containing, key=lambda u: _PREC_RANK.get(u.precision, 0), reverse=True)
        best = ranked[0].precision
        if best == GeometryPrecision.WORD:
            status = "EXACT_WORD"
            chosen = [u for u in ranked if u.precision == GeometryPrecision.WORD]
        elif best == GeometryPrecision.TABLE_CELL:
            status = "VALIDATED_TABLE_CELL"
            chosen = [u for u in ranked if u.precision == GeometryPrecision.TABLE_CELL]
        else:
            status = "EXACT_LINE"
            chosen = [u for u in ranked if u.precision == GeometryPrecision.LINE]
        boxes = [u.bbox for u in chosen]
    else:
        coverage = [u for u in units if _overlap(u, offset, end)]
        joined = " ".join(_normalise(u.text) for u in sorted(coverage, key=lambda u: u.canonical_offset or 0))
        if coverage and norm_target in joined:
            best = max((_PREC_RANK.get(u.precision, 0) for u in coverage), default=0)
            status = "EXACT_LINE" if best >= 2 else "COARSE_FALLBACK"
            chosen = sorted(coverage, key=lambda u: u.canonical_offset or 0)
            boxes = [u.bbox for u in chosen]
        else:
            coarse = _element_overlapping(page, offset, length)
            if coarse:
                status = "COARSE_FALLBACK"
                boxes = [c.region for c in coarse if c.region is not None]
                chosen = []
            else:
                status = "TARGET_NOT_FOUND"

    signals = {
        "target_in_text": norm_target in _normalise(page.text),
        "boxes_count": len(boxes),
        "in_bounds": all(
            b.x0 >= 0 and b.y0 >= 0 and b.x1 <= page.width_pt and b.y1 <= page.height_pt for b in boxes
        ),
        "min_confidence": round(min((u.confidence for u in chosen if u.confidence is not None), default=1.0), 4),
    }
    return AtomicResolution(status=status, boxes=boxes, units=chosen, signals=signals)


# -------------------------------------------------------------- Koordinaten


def page_view_to_mediabox(
    r: BoundingRegion,
    rotation: int,
    *,
    med_w: float,
    med_h: float,
) -> BoundingRegion:
    """View-/kanonische Koordinaten -> Original-PDF-Media-Box (TOPLEFT, y runter).

    Ableitungs-Regel: der gerenderte View entspricht der um `rotation` Grad
    (im Uhrzeigersinn) gedrehten MediaBox. Fuer rotierte Seiten ist die
    MediaBox breiter/höher als der View; hier werden DIE Buchstaben-Boxen
    korrekt zurueckgedreht. Kein Raten: reine, deterministische Geometrie.
    """
    rot = rotation % 360
    if rot == 0:
        x0, y0, x1, y1 = r.x0, r.y0, r.x1, r.y1
    elif rot == 90:
        # (x_v, y_v) = (H_m - y, x); Inverse: (x_m, y_m) = (y_v, H_m - x_v)
        x0 = r.y0
        y0 = med_h - r.x1
        x1 = r.y1
        y1 = med_h - r.x0
    elif rot == 180:
        # Inverse: (x_m, y_m) = (W_m - x_v, H_m - y_v)
        x0 = med_w - r.x1
        y0 = med_h - r.y1
        x1 = med_w - r.x0
        y1 = med_h - r.y0
    elif rot == 270:
        # (x_v, y_v) = (y, W_m - x); Inverse: (x_m, y_m) = (W_m - y_v, x_v)
        x0 = med_w - r.y1
        y0 = r.x0
        x1 = med_w - r.y0
        y1 = r.x1
    else:
        raise ValueError(f"Ununterstuetzte Rotation: {rotation}")
    return _clamp(BoundingRegion(page=r.page, x0=x0, y0=y0, x1=x1, y1=y1), med_w, med_h)


def _clamp(r: BoundingRegion, med_w: float, med_h: float) -> BoundingRegion:
    x0 = max(0.0, min(float(r.x0), med_w))
    x1 = max(0.0, min(float(r.x1), med_w))
    y0 = max(0.0, min(float(r.y0), med_h))
    y1 = max(0.0, min(float(r.y1), med_h))
    return BoundingRegion(page=r.page, x0=x0, y0=y0, x1=x1, y1=y1)


def medibox_to_view(r: BoundingRegion, rotation: int, *, view_w: float, view_h: float) -> BoundingRegion:
    """Rueckweg (Medibox-Fest für Tests/Kreislauf-Verifikation)."""
    rot = rotation % 360
    if rot == 0:
        x0, y0, x1, y1 = r.x0, r.y0, r.x1, r.y1
    elif rot == 90:
        x0 = view_w - r.y1
        y0 = r.x0
        x1 = view_w - r.y0
        y1 = r.x1
    elif rot == 180:
        x0 = view_w - r.x1
        y0 = view_h - r.y1
        x1 = view_w - r.x0
        y1 = view_h - r.y0
    elif rot == 270:
        x0 = r.y0
        y0 = view_h - r.x1
        x1 = r.y1
        y1 = view_h - r.x0
    else:
        raise ValueError(f"Ununterstuetzte Rotation: {rotation}")
    return _clamp(BoundingRegion(page=r.page, x0=x0, y0=y0, x1=x1, y1=y1), view_w, view_h)


# -------------------------------------------------------------- Schutzregel


def guard_oversized(
    boxes: list[WordRegion],
    *,
    page_w: float,
    page_h: float,
    target_text: str = "",
    per_char_max_width: float = 18.0,
    max_line_height: float = 42.0,
    min_width_floor: float = 120.0,
) -> list[dict]:
    """Prueft jede Box deterministisch auf Plausibilitaet (kein Raten, nur Schutz).

    Returns: je Box {"ok": bool, "reasons": [...]}. Nicht ok ist z. B. wenn eine
    9-Zeichen-Spanne eine breite Absatz-Box ergibt (oversized area) oder eine
    Box aus der Seite herausfällt. Element-Boxen sind nur dann exakt, wenn das
    Element praktisch der Zieltext ist (laenge <= Ziel + 8); sonst
    "coarse_element_box" -> dieser Zustand wird in der Navigation explizit als
    EXACT_GEOMETRY_UNAVAILABLE beim Menschen prüfbar markiert, ohne Block.
    """
    target_len = len(target_text.strip()) if target_text.strip() else 1
    results: list[dict] = []
    for wr in boxes:
        reasons: list[str] = []
        r = wr.region
        if r is None:
            reasons.append("no_region")
            results.append({"ok": False, "reasons": reasons})
            continue
        if r.x1 > page_w + 0.5 or r.y1 > page_h + 0.5 or r.x0 < -0.5 or r.y0 < -0.5:
            reasons.append("outside_page")
        if wr.granularity == "element" and len((wr.text or "").strip()) > target_len + 8:
            reasons.append("coarse_element_box")
        if wr.granularity == "element":
            # Nur GroESSEN-Pruefung fuer Element-Fallback (Absatz-/Tabellen-Boxen):
            # Neu sind Segment-/Wort-Boxen Provider-Geometrie und bleiben EXAKT.
            n = max(1, len((wr.text or "").strip()) or len("x"))
            max_w = max(min_width_floor, (n + 1) * per_char_max_width)
            if r.width > max_w + 0.5:
                reasons.append(f"oversized_width({r.width:.0f}>{max_w:.0f})")
            if r.height > max_line_height + 0.5:
                reasons.append(f"oversized_height({r.height:.0f}>{max_line_height:.0f})")
        results.append({"ok": not reasons, "reasons": reasons})
    return results


# -------------------------------------------------------------- Render


def render_transparent_highlights(
    pdf_path: Path,
    page_no: int,
    boxes: list[WordRegion],
    png_path: Path,
    *,
    dpi: int = 160,
    fill_opacity: float = 0.22,
    outline_color=(0.85, 0.08, 0.08),
    fill_color=(0.98, 0.58, 0.18),
) -> dict:
    """Abgeleitetes, transparentes Hervorhebungs-Render (Original bleibt unveraendert).

    Delegiert an `render_transparent_boxes` mit den WordRegion-Boxen.
    """
    regions = [wr.region for wr in boxes if wr.region is not None]
    return render_transparent_boxes(
        pdf_path,
        page_no,
        regions,
        png_path,
        dpi=dpi,
        fill_opacity=fill_opacity,
        outline_color=outline_color,
        fill_color=fill_color,
    )


def render_transparent_boxes(
    pdf_path: Path,
    page_no: int,
    boxes: list[BoundingRegion],
    png_path: Path,
    *,
    dpi: int = 160,
    fill_opacity: float = 0.22,
    outline_color=(0.85, 0.08, 0.08),
    fill_color=(0.98, 0.58, 0.18),
) -> dict:
    """Abgeleitetes, transparentes Hervorhebungs-Render (Original bleibt unveraendert).

    Halbtransparente Fuellung ueber `fill_opacity` (kein RGBA-Trick), duenne
    Umrisslinie; der Text bleibt lesbar. Koordinaten: View -> Medibox unter
    Beachtung von page.rotation.
    Returns: render-Diagnose (Anzahl Boxen, umgewandelte Rects, Datei).
    """
    import fitz

    png_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    rects_med: list = []
    try:
        page = doc.load_page(page_no - 1)
        med = page.mediabox
        med_w, med_h = float(med.width), float(med.height)
        rotation = int(page.rotation or 0)
        shape = page.new_shape()
        for br in boxes:
            if br is None:
                continue
            bm = page_view_to_mediabox(
                BoundingRegion(page=br.page, x0=br.x0, y0=br.y0, x1=br.x1, y1=br.y1),
                rotation,
                med_w=med_w,
                med_h=med_h,
            )
            rects_med.append({"x0": bm.x0, "y0": bm.y0, "x1": bm.x1, "y1": bm.y1})
            rect = fitz.Rect(bm.x0, bm.y0, bm.x1, bm.y1)
            shape.draw_rect(rect)
            shape.finish(
                color=outline_color,
                fill=fill_color,
                width=1.1,
                fill_opacity=max(0.0, min(1.0, fill_opacity)),
                stroke_opacity=0.9,
            )
        shape.commit()
        pix = page.get_pixmap(dpi=dpi)
        pix.save(str(png_path))
    finally:
        doc.close()
    return {
        "rects_mediabox": rects_med,
        "render": str(png_path),
        "box_count": len(rects_med),
        "fill_opacity": float(fill_opacity),
        "dpi": dpi,
        "original_unmodified": True,
    }