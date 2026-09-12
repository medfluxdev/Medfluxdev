"""Atomare OCR-Geometrie fuer exakte Quell-Navigation (STEP 8B-Korrektur).

RapidOCR (PP-OCRv6, Apache-2.0) liefert direkt auf dem gerenderten Seiten-View
- Zeilen: `to_json()` -> list[{text, box(4-Eck, Pixel), score}]
- Woerter: `return_word_box=True` -> `word_results` je Zeile
  als [(wort_text, score, [[x,y], ...]), ...]

Dieses Modul
1. rendert jede Seite des Original-PDFs als View (fitz, Rotation angewendet),
2. erkennt atomare Zeilen- und Wort-Einheiten (Geometrie-EIGENTUEMER = RapidOCR),
3. aligniert sie DETERMINISTISCH ueber Token-/Text-Matching an den kanonischen
   Seiten-Text `page.text` (offsets, Containment-bewiesen), und
4. ergaenzt validierte Tabellenzellen (table_cells.py) als atomare Einheiten.

Regel: Es wird NIE Geometrie erfunden. Woerter, die keinen deterministischen
kanonischen Offset ergeben, bleiben `aligned=False` und sind fuer die
EXAKT-Klassifikation unbrauchbar (Fallback sauber als grob markiert).
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from app.documents.intelligence.canonical import (
    CANONICAL_SCHEMA_VERSION,
    AtomicUnit,
    BoundingRegion,
    DocumentIntelligenceResult,
    GeometryPrecision,
    Page,
)
from app.documents.intelligence.table_cells import reconcile_table_cells


# Ein gemeinsamer RapidOCR-Prozess reicht je Laufzeit-Prozess.
_OCR_INSTANCE = None


def _get_ocr():
    global _OCR_INSTANCE
    if _OCR_INSTANCE is None:
        from rapidocr import RapidOCR

        _OCR_INSTANCE = RapidOCR()
    return _OCR_INSTANCE


# -------------------------------------------------------------- Text-Normalisierung


def _normalise(text: str) -> str:
    """Kleinschreibung + Whitespace-Buendelung; Satzzeichen bleiben erhalten.

    Nur fuer Vergleichszwecke; nie fuer Offsets.
    """
    return re.sub(r"\s+", " ", (text or "").lower())


def _tokenize_lower(text: str) -> list[tuple[int, int, str]]:
    """Tokens als (start, end, lower) in `text` (Whitespace-getrennt, rohe Offsets)."""
    return [(m.start(), m.end(), m.group().lower()) for m in re.finditer(r"\S+", text)]


# -------------------------------------------------------------- Erkennung


def _poly_to_bbox(polygon, sx: float, sy: float) -> tuple[float, float, float, float]:
    xs = [float(p[0]) / sx for p in polygon]
    ys = [float(p[1]) / sy for p in polygon]
    return round(min(xs), 3), round(min(ys), 3), round(max(xs), 3), round(max(ys), 3)


def _pixel_polygon(box) -> list[list[float]]:
    if not box:
        return []
    return [[float(p[0]), float(p[1])] for p in box]


def recognise_page_units(page: Page, pdf_path: Path, *, dpi: int = 200, ocr=None) -> tuple[list[AtomicUnit], dict]:
    """Erkennt atomare Zeilen- und Wort-Einheiten einer Seite (kanonischer Raum).

    Skalierung FEST aus dem gerenderten View vs. kanonische Seitenabmessung
    (kein Raten): sx = pix.width / page.width_pt, sy = pix.height / page.height_pt.
    Returns (alle Einheiten Zeilen+Woerter, stats).
    """
    import fitz
    import numpy as np
    from PIL import Image

    ocr = ocr or _get_ocr()
    pdf_path = Path(pdf_path)
    doc = fitz.open(pdf_path)
    try:
        page_doc = doc.load_page(page.page_number - 1)
        pix = page_doc.get_pixmap(dpi=dpi)
    finally:
        doc.close()

    arr = np.asarray(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))[:, :, ::-1].copy()
    sx = pix.width / page.width_pt if page.width_pt and page.width_pt > 0 else 1.0
    sy = pix.height / page.height_pt if page.height_pt and page.height_pt > 0 else 1.0

    res = ocr(arr, return_word_box=True)

    line_units: list[AtomicUnit] = []
    for idx, item in enumerate(res.to_json()):
        txt = str(item.get("txt", "") or "").strip()
        if not txt:
            continue
        x0, y0, x1, y1 = _poly_to_bbox(item.get("box", []), sx, sy)
        score = item.get("score")
        line_units.append(
            AtomicUnit(
                unit_id=f"p{page.page_number}_l{idx}",
                kind="ocr_line",
                text=txt,
                page=page.page_number,
                bbox=BoundingRegion(page=page.page_number, x0=x0, y0=y0, x1=x1, y1=y1),
                precision=GeometryPrecision.LINE,
                confidence=float(score) if score is not None else None,
                provider="rapidocr",
                source_ref=f"line[{idx}]",
                extra={"dpi": dpi, "pixel_bbox": _pixel_polygon(item.get("box", []))},
            )
        )

    word_units: list[AtomicUnit] = []
    for line_idx in range(len(line_units)):
        if line_idx >= len(res.word_results):
            continue
        for word_idx, item in enumerate(res.word_results[line_idx]):
            text = str(item[0] or "").strip()
            if not text:
                continue
            x0, y0, x1, y1 = _poly_to_bbox(item[2], sx, sy)
            word_units.append(
                AtomicUnit(
                    unit_id=f"p{page.page_number}_l{line_idx}_w{word_idx}",
                    kind="ocr_word",
                    text=text,
                    page=page.page_number,
                    bbox=BoundingRegion(page=page.page_number, x0=x0, y0=y0, x1=x1, y1=y1),
                    precision=GeometryPrecision.WORD,
                    confidence=float(item[1]) if item[1] is not None else None,
                    provider="rapidocr",
                    parent_line_id=f"p{page.page_number}_l{line_idx}",
                    source_ref=f"word[{line_idx}][{word_idx}]",
                    extra={"dpi": dpi},
                )
            )

    stats = {
        "page": page.page_number,
        "lines": len(line_units),
        "words": len(word_units),
        "view_px": [int(pix.width), int(pix.height)],
        "scale": [round(sx, 4), round(sy, 4)],
    }
    return line_units + word_units, stats


# -------------------------------------------------------------- Alignment


def _tok_equal(a: str, b: str) -> bool:
    """Exakt oder Praefix-tolerant (OCR-Abschneidung, min. 3 Zeichen)."""
    if a == b:
        return True
    if len(a) >= 3 and len(b) >= 3:
        return a.startswith(b) or b.startswith(a)
    return False


def align_line_units(page: Page, line_units: list[AtomicUnit]) -> None:
    """Deterministisches Text-Matching Zeilen -> kanonische Seiten-Offsets.

    SequenceMatcher ueber die Token-Folge des gesamten Seiten-Texts gegen die
    Token-Folge aller Zeilen (Lesereihenfolge: erst nach (y0, x0) sortiert).
    Zeilen ohne getroffene Tokens bleiben `aligned=False`.
    """
    canonical_toks = _tokenize_lower(page.text)
    if not canonical_toks:
        for u in line_units:
            u.aligned = False
        return

    ordered = sorted(line_units, key=lambda u: (u.bbox.y0, u.bbox.x0))
    if not ordered:
        return

    # (unit, toks je Zeile)
    line_entries: list[tuple[AtomicUnit, list[tuple[int, int, str]]]] = []
    for u in ordered:
        toks = _tokenize_lower(u.text)
        if toks:
            line_entries.append((u, toks))

    ocr_tokens: list[str] = []
    ocr_owner: list[tuple[int, int]] = []  # ocr token index -> (entry index, local index)
    for entry_idx, (_, toks) in enumerate(line_entries):
        ocr_owner.extend((entry_idx, local) for local in range(len(toks)))
        ocr_tokens.extend(t[2] for t in toks)

    matcher = SequenceMatcher(None, ocr_tokens, [t[2] for t in canonical_toks], autojunk=False)

    line_ranges: dict[str, list[tuple[int, int]]] = {}
    for i, j, n in matcher.get_matching_blocks():
        if n == 0:
            continue
        for k in range(n):
            if i + k >= len(ocr_owner):
                break
            entry_idx, _local = ocr_owner[i + k]
            unit = line_entries[entry_idx][0]
            start, end, _ = canonical_toks[j + k]
            line_ranges.setdefault(unit.unit_id, []).append((start, end))

    for u in line_units:
        ranges = line_ranges.get(u.unit_id)
        if not ranges:
            u.aligned = False
            continue
        u.canonical_offset = min(r[0] for r in ranges)
        u.canonical_length = max(r[1] for r in ranges) - u.canonical_offset
        u.aligned = True
        u.extra["matched_tokens"] = len(ranges)


def align_line_units_local(page: Page, line_units: list[AtomicUnit]) -> None:
    """Lokaler, deterministischer Fallback fuer noch unalignierte Zeilen.

    Grund: der globale SequenceMatcher verliert isolierte/am Rand liegende
    Zeilen (z. B. '13.06.2017' als letztes kanonisches Token) und Zeilen
    innerhalb eines Scrambles. Der Fallback sucht je Zeile (sortiert nach
    Lesereihenfolge) den erssten passenden kanonischen Token-Anker OHNE
    starr aufsteigenden Cursor – bei rotierten Seiten ist die y-Achse nicht
    die Lesereihenfolge. Verlangt >= 60 % der Zeilen-Tokens in Reihenfolge
    (Praefix-tolerant fuer OCR-Abschneidungen) und vermeidet Ueberschneidung
    mit bereits belegten Texten. Kein Raten: Offsets stammen aus dem
    gefundenen kanonischen Ausschnitt.
    """
    canonical_toks = _tokenize_lower(page.text)
    if not canonical_toks:
        return
    n_can = len(canonical_toks)

    def matched_span(unit_text: str) -> Optional[tuple[int, int]]:
        toks = _tokenize_lower(unit_text)
        if not toks:
            return None
        target = toks[0][2]
        best: Optional[tuple[int, int, int]] = None  # (covered, first, after)
        for si in range(n_can):
            if not _tok_equal(canonical_toks[si][2], target):
                continue
            j = si
            pos = 0
            misses = 0
            while pos < len(toks) and j < n_can:
                if _tok_equal(canonical_toks[j][2], toks[pos][2]):
                    pos += 1
                    j += 1
                else:
                    j += 1
                    misses += 1
                    if misses > max(3 * len(toks) + 10, 24):
                        break
            if pos < max(1, int(0.6 * len(toks))):
                continue
            start = canonical_toks[si][0]
            end = canonical_toks[j - 1][1]
            covered = end - start
            if best is None or covered > best[0]:
                best = (covered, start, end)
        return (best[1], best[2]) if best else None

    for u in sorted(line_units, key=lambda x: (x.bbox.y0, x.bbox.x0)):
        if u.aligned:
            continue
        span = matched_span(u.text)
        if span is None:
            u.aligned = False
            continue
        start, end = span
        u.canonical_offset = start
        u.canonical_length = end - start
        u.aligned = True
        u.extra["matched_tokens"] = max(1, int(0.6 * len(_tokenize_lower(u.text))))
        u.extra["alignment"] = "local_anchor"


def align_word_units(page: Page, line_units: list[AtomicUnit], word_units: list[AtomicUnit]) -> None:
    """Wort-Offsets INNERHALB der alignierten Zeilen-Slices (deterministisch).

    Bindung: das normalisierte Wort muss im Zeilen-Slice enthalten sein –
    sonst `aligned=False` (kein Erraten). Offsets werden im ROHEM Seiten-Text
    bestimmt (case-insensitives `find`), da Normalisierung die Laenge aendern kann.
    """
    line_by_id = {u.unit_id: u for u in line_units}
    for u in sorted(word_units, key=lambda w: (w.bbox.y0, w.bbox.x0)):
        parent = line_by_id.get(u.parent_line_id or "")
        if parent is None or not parent.aligned or parent.canonical_offset is None or parent.canonical_length is None:
            u.aligned = False
            continue
        slice_lo = parent.canonical_offset
        slice_hi = slice_lo + parent.canonical_length
        if slice_hi > len(page.text):
            slice_hi = len(page.text)
        hay = page.text[slice_lo:slice_hi].lower()
        needle = (u.text or "").lower()
        if not needle:
            u.aligned = False
            continue
        rel = hay.find(needle)
        if rel < 0:
            u.aligned = False
            u.extra["alignment_note"] = "wort nicht im alignierten Zeilenslice"
            continue
        u.canonical_offset = slice_lo + rel
        u.canonical_length = len(u.text)
        u.aligned = True


# -------------------------------------------------------------- API


def augment_with_atomic_geometry(
    result: DocumentIntelligenceResult,
    pdf_path: Path,
    *,
    dpi: int = 200,
    ocr=None,
) -> tuple[DocumentIntelligenceResult, dict]:
    """Refresht atomare Geometrie in einem (bereits kanonisierten) Ergebnis.

    Nur Geometrie-Erfassung + Alignment; der kanonische Text/Layout bleibt
    unveraendert, damit der fachliche Cache-INHALT gleich bleibt. Persistiert
    wird erst durch den Aufrufer (Skript schreibt canonical JSON zurueck).
    """
    pdf_path = Path(pdf_path)
    stats: dict = {"provider": "rapidocr", "pages": []}
    for page in result.pages:
        units, page_stats = recognise_page_units(page, pdf_path, dpi=dpi, ocr=ocr)
        line_units = [u for u in units if u.kind == "ocr_line"]
        word_units = [u for u in units if u.kind == "ocr_word"]
        align_line_units(page, line_units)
        align_line_units_local(page, line_units)
        align_word_units(page, line_units, word_units)
        cell_units = reconcile_table_cells(page, word_units)
        combined: list[AtomicUnit] = []
        combined.extend(cell_units)
        combined.extend(line_units)
        combined.extend(word_units)
        page.atomic_units = combined
        page_stats["aligned"] = sum(1 for u in combined if u.aligned)
        page_stats["cells"] = len(cell_units)
        stats["pages"].append(page_stats)

    result.provenance.geometry_provider = "rapidocr"
    result.provenance.canonical_schema_version = CANONICAL_SCHEMA_VERSION
    result.provenance.config = {**result.provenance.config, "atomic_geometry": {"dpi": dpi}}
    return result, stats