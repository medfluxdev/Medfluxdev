"""Tests fuer die atomare OCR-Geometrie (STEP 8B-Korrektur).

Abgedeckt (synthetisch, deterministisch – KEIN RapidOCR/PDF-Zwang):
- Modell: AtomicUnit/GeometryPrecision JSON-Roundtrip, Schema 1.3.0
- Alignment: Zeilen (SequenceMatcher) + Woerter (casefold find) -> kanonische
  Offsets; nie erfundene Offsets
- Aufloeser: EXACT_WORD / EXACT_LINE / VALIDATED_TABLE_CELL / COARSE_FALLBACK /
  TARGET_NOT_FOUND; Containment-Invariante; keine falsche Exaktheit aus
  groben Element-Boxen
- Tabellenzellen: Y-Spiegel-Reconciliation mit OCR-Wort-Belegen
"""

import json

import pytest

from app.documents.intelligence.canonical import (
    AtomicUnit,
    BoundingRegion,
    DocumentIntelligenceResult,
    Element,
    ElementType,
    GeometryPrecision,
    TextSpan,
    TableStructure,
    Cell,
    Page,
    ProcessingProvenance,
    CANONICAL_SCHEMA_VERSION,
)
from app.documents.intelligence.highlight import resolve_target_atomic
from app.documents.intelligence.table_cells import reconcile_table_cells
from app.documents.intelligence.atomic_ocr import align_line_units, align_word_units, align_line_units_local


def _page(text: str, w: float = 600.0, h: float = 800.0, page_number: int = 1) -> Page:
    return Page(page_number=page_number, width_pt=w, height_pt=h, text=text)


def _line(pid: str, text: str, off: int, lo: float, top: float, hi: float, bottom: float) -> AtomicUnit:
    return AtomicUnit(
        unit_id=pid,
        kind="ocr_line",
        text=text,
        page=1,
        bbox=BoundingRegion(page=1, x0=lo, y0=top, x1=hi, y1=bottom),
        precision=GeometryPrecision.LINE,
        confidence=0.99,
        provider="rapidocr",
    )


def _word(pid: str, text: str, off: int, lo: float, top: float, hi: float, bottom: float) -> AtomicUnit:
    return AtomicUnit(
        unit_id=pid,
        kind="ocr_word",
        text=text,
        page=1,
        bbox=BoundingRegion(page=1, x0=lo, y0=top, x1=hi, y1=bottom),
        precision=GeometryPrecision.WORD,
        confidence=0.95,
        provider="rapidocr",
        parent_line_id=pid.rsplit("_", 1)[0],
    )


# ================================================== Modell


class TestModel:
    def test_schema_version_is_130(self):
        assert CANONICAL_SCHEMA_VERSION == "1.3.0"

    def test_atomic_unit_json_roundtrip(self):
        u = AtomicUnit(
            unit_id="p1_l0_w0",
            kind="ocr_word",
            text="942.480,00",
            page=1,
            bbox=BoundingRegion(page=1, x0=10, y0=20, x1=90, y1=35),
            precision=GeometryPrecision.WORD,
            confidence=0.99,
            canonical_offset=5,
            canonical_length=10,
            aligned=True,
        )
        du = AtomicUnit.model_validate_json(u.model_dump_json())
        assert du == u
        assert du.precision is GeometryPrecision.WORD

    def test_atomic_units_default_empty(self):
        p = _page("x")
        assert p.atomic_units == []
        assert "atomic_units" in Page.model_json_schema()["properties"]


# ================================================== Alignment


class TestAlignment:
    def test_line_and_word_alignment(self):
        page = _page("Vertragsbeginn: 27. Januar 2018\nMwSt. 19,00 %\nGesamtbetrag 942.480,00 EUR")
        lines = [
            _line("p1_l0", "Vertragsbeginn: 27. Januar 2018", -1, 0, 0, 590, 14),
            _line("p1_l1", "MwSt. 19,00 %", -1, 0, 15, 590, 29),
            _line("p1_l2", "Gesamtbetrag 942.480,00 EUR", -1, 0, 30, 590, 44),
        ]
        for u in lines:
            u.canonical_offset = None
        align_line_units(page, lines)
        assert all(u.aligned for u in lines)
        assert page.text[lines[2].canonical_offset : lines[2].to()].lower() == "gesamtbetrag 942.480,00 eur"

        words = [
            _word("p1_l2_w0", "Gesamtbetrag", -1, 0, 30, 120, 44),
            _word("p1_l2_w1", "942.480,00", -1, 130, 30, 230, 44),
            _word("p1_l2_w2", "EUR", -1, 240, 30, 300, 44),
        ]
        align_word_units(page, lines, words)
        assert all(w.aligned for w in words)
        assert page.text[words[1].canonical_offset : words[1].to()].lower() == "942.480,00"

    def test_no_alignment_without_match_stays_false(self):
        page = _page("nur a b c")
        line = _line("p1_l0", "Komplett anderer Text", -1, 0, 0, 10, 5)
        align_line_units(page, [line])
        assert not line.aligned
        assert line.canonical_offset is None

    def test_local_fallback_anchors_isolated_tail_token(self):
        page = _page("Anlagen\n13.06.2017")
        l0 = _line("p1_l0", "13.06.2017", -1, 0, 0, 10, 5)
        l0.aligned = False  # simuliert: globaler Matcher hat Zeile verworfen
        align_line_units_local(page, [l0])
        assert l0.aligned
        assert page.text[l0.canonical_offset : l0.to()].lower() == "13.06.2017"

    def test_local_fallback_prefix_tolerance_for_truncated_token(self):
        page = _page("unter Einhaltung einer Kündigungsfrist von drei")
        l0 = _line("p1_l0", "unter Einhaltung einer Kündigungsfr", -1, 0, 0, 10, 5)
        align_line_units_local(page, [l0])
        assert l0.aligned
        assert page.text[l0.canonical_offset : l0.to()].lower().startswith("unter einhaltung einer kündig")
        assert "kündigungsfrist" in page.text[l0.canonical_offset : l0.to()].lower()

    def test_local_fallback_split_tokens(self):
        # OCR liest "EUR 942.480,00", kanonisch mit Euro getrennt liefert trotzdem
        # den korrekten Ausschnitt, der den Betrag enthaelt.
        page = _page("Gesamtbetrag: 942.480,00 EUR")
        l0 = _line("p1_l0", "942.480,00 EUR", -1, 0, 0, 10, 5)
        align_line_units_local(page, [l0])
        assert l0.aligned
        assert "942.480,00" in page.text[l0.canonical_offset : l0.to()]

    def test_local_fallback_rotated_euro_line(self):
        # Rotierte Seite: y-Ordnung ist NICHT Lesereihenfolge. Eine Zeile mit
        # "€ 942.480,00" muss exakt auf den Betrag zeigen.
        page = _page("MwSt.\n€ 942.480,00\nGeschäftsbedingungen")
        l0 = _line("p1_l0", "€ 942.480,00", -1, 452, 0, 475, 5)
        align_line_units(page, [l0])  # global verfehlt evtl.
        l0.aligned = False
        l0.canonical_offset = None
        align_line_units_local(page, [l0])
        assert l0.aligned
        assert page.text[l0.canonical_offset : l0.to()].lower() == "€ 942.480,00"


# ================================================== Aufloeser


class TestResolver:
    def _page_with_units(self):
        page = _page("Vertragsbeginn: 27. Januar 2018\nGesamtbetrag 942.480,00 EUR")
        s = page.text
        o_date, o_betrag, o_line = s.find("27. Januar 2018"), s.find("942.480,00"), s.find("Gesamtbetrag 942.480,00")
        l0 = _line("p1_l0", "Vertragsbeginn: 27. Januar 2018", 0, 0, 0, 590, 14)
        l0.canonical_offset, l0.canonical_length, l0.aligned = 0, len(l0.text), True
        w_datum = _word("p1_l0_w0", "27. Januar 2018", 0, 100, 0, 200, 14)
        w_datum.canonical_offset, w_datum.canonical_length, w_datum.aligned = o_date, len(w_datum.text), True
        l1 = _line("p1_l1", "Gesamtbetrag 942.480,00 EUR", 0, 0, 15, 590, 29)
        l1.canonical_offset, l1.canonical_length, l1.aligned = o_line, len(l1.text), True
        w_betrag = _word("p1_l1_w0", "942.480,00", 0, 130, 15, 230, 29)
        w_betrag.canonical_offset, w_betrag.canonical_length, w_betrag.aligned = o_betrag, len(w_betrag.text), True
        page.atomic_units = [l0, w_datum, l1, w_betrag]
        return page

    def test_exact_word_german_date(self):
        page = self._page_with_units()
        off = page.text.find("27. Januar 2018")
        res = resolve_target_atomic(page, off, len("27. Januar 2018"))
        assert res.status == "EXACT_WORD"
        assert len(res.boxes) == 1

    def test_exact_word_monetary(self):
        page = self._page_with_units()
        off = page.text.find("942.480,00")
        res = resolve_target_atomic(page, off, len("942.480,00"))
        assert res.status == "EXACT_WORD"

    def test_exact_line_for_phrase_across_two_words(self):
        page = self._page_with_units()
        off = page.text.find("Gesamtbetrag 942.480,00")
        # Phrase spannt zwei Woerter, aber innerhalb EINER Zeile
        res = resolve_target_atomic(page, off, len("Gesamtbetrag 942.480,00"))
        assert res.status == "EXACT_LINE"
        assert len(res.boxes) == 1

    def test_coarse_fallback_never_exact(self):
        page = _page("Elementtext irgendwo")
        element = Element(
            element_id="el_p1_0",
            type=ElementType.PARAGRAPH,
            text="Elementtext irgendwo",
            page=1,
            region=BoundingRegion(page=1, x0=0, y0=0, x1=590, y1=60),
            spans=[TextSpan(offset=0, length=20)],
            reading_order=0,
        )
        page.elements = [element]
        # keine atomaren Units -> grosse Element-Box nur als COARSE_FALLBACK
        res = resolve_target_atomic(page, 0, 11)
        assert res.status == "COARSE_FALLBACK"
        assert res.units == []

    def test_unavailable_for_missing_text(self):
        page = _page("nichts hier")
        res = resolve_target_atomic(page, 0, 6)
        assert res.status == "TARGET_NOT_FOUND"

    def test_out_of_bounds_span_unavailable(self):
        page = _page("kurz")
        assert resolve_target_atomic(page, 2, 99).status == "UNAVAILABLE"

    def test_unaligned_unit_excluded(self):
        page = _page("gestern 123")
        w = _word("p1_l0_w0", "123", 0, 10, 0, 30, 10)
        w.canonical_offset, w.canonical_length = 8, 3
        w.aligned = False
        page.atomic_units = [w]
        res = resolve_target_atomic(page, 8, 3)
        assert res.status == "TARGET_NOT_FOUND"


# ================================================== Tabellenzellen


class TestTableCellReconciliation:
    def _word(self, pid, text, x0, y0, x1, y1, off=None, aligned=True):
        u = _word(pid, text, 0, x0, y0, x1, y1)
        u.aligned = aligned
        if off is not None:
            u.canonical_offset, u.canonical_length = off, len(text)
        return u

    def _table_page(self, cell_mirrored: bool):
        h = 800.0
        page = _page("Beschreibung 123,45 EUR", w=600.0, h=800.0)
        # docling-Zelle (Strukturwert im BottomLeft-Rohformat): y 185..200
        # entspricht WAHR y 600..615 (Y-Spiegel an der Seitenhoehe 800)
        cf = Cell(
            row_index=0, column_index=1, text="123,45",
            region=BoundingRegion(page=1, x0=100, y0=185 if cell_mirrored else 600,
                                  x1=160, y1=200 if cell_mirrored else 615),
        )
        table = TableStructure(
            table_id="table_p1_0", page=1,
            region=BoundingRegion(page=1, x0=50, y0=150, x1=300, y1=700),
            num_rows=1, num_cols=2, cells=[cf],
        )
        element = Element(
            element_id="el_p1_0", type=ElementType.TABLE, text="Beschreibung 123,45 EUR",
            page=1, region=BoundingRegion(page=1, x0=50, y0=600, x1=300, y1=700),
            spans=[TextSpan(offset=0, length=len("Beschreibung 123,45 EUR"))],
            reading_order=0, table=table,
        )
        page.elements = [element]
        page.tables = [table]
        return page

    def test_y_mirror_transform_chosen_when_docling_bottomleft(self):
        page = self._table_page(cell_mirrored=True)
        words = [self._word("p1_l0_w0", "123,45", 104, 607, 156, 613)]
        cells = reconcile_table_cells(page, words)
        assert len(cells) == 1
        assert cells[0].precision is GeometryPrecision.TABLE_CELL
        assert cells[0].kind == "docling_cell"
        assert cells[0].extra["transform"] == "y_mirror"
        assert cells[0].aligned
        assert page.text[cells[0].canonical_offset : cells[0].to()] == "123,45"

    def test_identity_kept_when_cells_already_topleft(self):
        page = self._table_page(cell_mirrored=False)
        words = [self._word("p1_l0_w0", "123,45", 104, 604, 156, 611)]
        cells = reconcile_table_cells(page, words)
        assert len(cells) == 1
        assert cells[0].extra["transform"] == "identity"

    def test_no_unit_without_ocr_words_inside(self):
        page = self._table_page(cell_mirrored=True)
        cells = reconcile_table_cells(page, [])
        assert cells == []

    def test_cell_wins_over_line_in_resolver(self):
        page = self._table_page(cell_mirrored=True)
        words = [self._word("p1_l0_w0", "123,45", 104, 607, 156, 613)]
        cells = reconcile_table_cells(page, words)
        line = _line("p1_l0", "Beschreibung 123,45 EUR", 0, 0, 605, 500, 615)
        line.canonical_offset, line.canonical_length, line.aligned = 0, len(line.text), True
        page.atomic_units = cells + [line]
        res = resolve_target_atomic(page, page.text.find("123,45"), 6)
        assert res.status == "VALIDATED_TABLE_CELL"


# ================================================== Schema-/Ergebnis-Rundum


class TestDocumentContainer:
    def test_page_accepts_atomic_units(self):
        page = _page("ein test")
        page.atomic_units = [
            _word("p1_l0_w0", "test", 0, 0, 0, 10, 5),
        ]
        result = DocumentIntelligenceResult(
            source_sha256="x" * 64,
            pages=[page],
            provenance=ProcessingProvenance(provider="test"),
        )
        du = DocumentIntelligenceResult.model_validate_json(result.model_dump_json())
        assert len(du.pages[0].atomic_units) == 1
        assert du.pages[0].atomic_units[0].text == "test"
        assert json.loads(result.model_dump_json()) is not None