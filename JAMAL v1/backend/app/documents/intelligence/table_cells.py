"""Validierte Tabellenzell-Geometrie (STEP 8B-Korrektur).

Docling-Zell-BBoxes koennen gegenueber der Seite Y-gespiegelt sein (bekannter
Befund am Vision-RFD-Test: Zellen y=538-623, Element-Region y=208-359).
Dieses Modul prueft DETERMINISTISCH, welche Koordinatenraum-Transformation
(Identitaet vs. Y-Spiegel an der Seitenhoehe) die Zell-BBoxes mit der ECHTEN
Geometrie kohärent macht – belegt durch atomare OCR-Wort-Boxen (RapidOCR),
deren Mittelpunkte in den Zellen liegen.

Ausgabe: NUR validierte `docling_cell`-Einheiten (precision=TABLE_CELL).
Zellen ohne OCR-Belegerzeugung oder nicht in-bounds werden verworfen; eine
Gesamt-Tabellen-Box wird NIEMALS als exakt markiert.
"""

from __future__ import annotations

from typing import Optional

from app.documents.intelligence.canonical import (
    AtomicUnit,
    BoundingRegion,
    GeometryPrecision,
    Page,
)


def _mirror_y(r: BoundingRegion, height_pt: float) -> BoundingRegion:
    """Y-Spiegel: BottomLeft->TopLeft-Koordinaten normalisiert auf Seitenhoehe."""
    return BoundingRegion(
        page=r.page,
        x0=r.x0,
        y0=height_pt - r.y1,
        x1=r.x1,
        y1=height_pt - r.y0,
    )


def _in_bounds(r: BoundingRegion, page_w: float, page_h: float, tol: float = 1.0) -> bool:
    return r.x0 >= -tol and r.y0 >= -tol and r.x1 <= page_w + tol and r.y1 <= page_h + tol


def _word_counts(table, word_units, transform, page_w: float, page_h: float) -> tuple[int, list[int]]:
    """Anzahl OCR-Wort-Mittelpunkte innerhalb der (transformierten) Zell-BBoxes."""
    counts: list[int] = []
    total = 0
    for cell in table.cells:
        r = cell.region
        if r is None:
            counts.append(0)
            continue
        tb = transform(r, page_h)
        if not _in_bounds(tb, page_w, page_h):
            counts.append(0)
            continue
        inside = 0
        for w in word_units:
            cx = (w.bbox.x0 + w.bbox.x1) / 2.0
            cy = (w.bbox.y0 + w.bbox.y1) / 2.0
            if tb.x0 <= cx <= tb.x1 and tb.y0 <= cy <= tb.y1:
                inside += 1
        counts.append(inside)
        total += inside
    return total, counts


def _cell_to_canonical_offset(page: Page, table, cell_text: str) -> tuple[Optional[int], Optional[int]]:
    """Bindet den Zelltext deterministisch an den kanonischen Seiten-Text.

    Suchfenster = Span des Elementes, das diese Tabelle traegt (Lesereihen-
    folge), damit der Zelltext nicht in einer fernen Seite auftauchen kann.
    """
    if not cell_text.strip():
        return None, None
    for e in page.elements:
        if e.table is not None and e.table.table_id == table.table_id:
            if e.spans and e.text.strip():
                sp = e.spans[0]
                if sp.offset <= len(page.text):
                    hay = page.text[sp.offset : min(sp.offset + (sp.to() - sp.offset), len(page.text))]
                    rel = hay.lower().find(cell_text.lower())
                    if rel >= 0:
                        return sp.offset + rel, len(cell_text)
            break
    return None, None


def reconcile_table_cells(page: Page, word_units: Optional[list[AtomicUnit]] = None) -> list[AtomicUnit]:
    """Erzeugt validierte `docling_cell`-Einheiten fuer alle Tabellen der Seite."""
    if not page.tables:
        return []
    words = word_units or [u for u in page.atomic_units if u.kind == "ocr_word"]
    words = [w for w in words if w.bbox.page == page.page_number]
    page_w = page.width_pt
    page_h = page.height_pt
    out: list[AtomicUnit] = []

    for table in page.tables:
        cells_with_bbox = [c for c in table.cells if c.region is not None]
        if not cells_with_bbox:
            continue

        id_total, id_counts = _word_counts(table, words, lambda r, h: r, page_w, page_h)
        mi_total, mi_counts = _word_counts(table, words, _mirror_y, page_w, page_h)

        if id_total >= mi_total:
            transform = None  # Identitaet
            counts = id_counts
            transform_label = "identity"
        else:
            transform = _mirror_y
            counts = mi_counts
            transform_label = "y_mirror"

        for cell, inside in zip(cells_with_bbox, counts):
            r = cell.region
            if transform is not None:
                r = transform(r, page_h)
            if not _in_bounds(r, page_w, page_h):
                continue
            if inside < 1:
                continue
            off, length = _cell_to_canonical_offset(page, table, cell.text)
            out.append(
                AtomicUnit(
                    unit_id=f"cell_{table.table_id}_{cell.row_index}_{cell.column_index}",
                    kind="docling_cell",
                    text=cell.text.strip(),
                    page=page.page_number,
                    bbox=r,
                    precision=GeometryPrecision.TABLE_CELL,
                    confidence=cell.confidence if cell.confidence is not None else table.confidence,
                    provider="docling",
                    canonical_offset=off,
                    canonical_length=length,
                    aligned=off is not None,
                    source_ref=f"cell[{cell.row_index}][{cell.column_index}]",
                    extra={
                        "row": cell.row_index,
                        "column": cell.column_index,
                        "transform": transform_label,
                        "ocr_words_inside": inside,
                    },
                )
            )
    return out