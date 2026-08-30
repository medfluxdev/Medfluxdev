"""Fokussierte Tests für lokale Dokument-Intelligence (STEP 8B).

Keine echte Docling-Konvertierung in den Tests – die Mapping-Logik wird mit
gezimmerten Docling-Objekten (Fake-converter) direkt geprüft, damit die Suite
ohne Modell-Downloads/OCR schnell und deterministisch bleibt.
"""

from types import SimpleNamespace as NS

from app.documents.intelligence.canonical import (
    BoundingRegion,
    Cell,
    DocumentIntelligenceResult,
    Element,
    ElementType,
    Method,
    Page,
    ProcessingProvenance,
    TableStructure,
    TextSpan,
    build_canonical_text,
)
from app.documents.intelligence.docling_provider import DoclingDocumentProvider
from app.documents.intelligence.provider import (
    DocumentIntelligenceSettings,
    available_providers,
    get_provider,
)


# ---------------------------------------------------------------- Helfer

def _bb(l, t, r, b, origin="BOTTOMLEFT"):
    return NS(l=l, t=t, r=r, b=b, coord_origin=origin)


def _prov(page_no, l, t, r, b, origin="BOTTOMLEFT", ocr_conf=None):
    return NS(page_no=page_no, bbox=_bb(l, t, r, b, origin), ocr_confidence=ocr_conf)


def _text_item(text, prov, label="text"):
    return NS(text=text, prov=[prov], label=label, content_layer="ocr")


def _table_item(raw_cells, prov, label="table"):
    return NS(text="", prov=[prov], data=NS(table_cells=raw_cells), label=label)


def _raw_cell(row, col, text, row_span=1, col_span=1, header=False, h=842.0):
    l, r = col * 100 + 5, col * 100 + 95
    t = 842 - (row * 20 + 5)
    b = 842 - (row * 20 + 15)
    return NS(
        start_row_offset_idx=row,
        end_row_offset_idx=row + row_span,
        start_col_offset_idx=col,
        end_col_offset_idx=col + col_span,
        row_span=row_span,
        col_span=col_span,
        text=text,
        column_header=header,
        bbox=_bb(l, t, r, b),
    )


def _fake_doc(items_by_page):
    """Baut ein Fake-Docling-Dokument.

    items_by_page: dict[int, list[item]] – Items werden pro Seite in der
    angegebenen Reihenfolge (Lesereihenfolge) besucht.
    """
    ordered: list[tuple] = []
    page_keys = sorted(items_by_page)
    for pn in page_keys:
        for item in items_by_page[pn]:
            ordered.append((item, 1))

    pages = {}
    for pn in page_keys:
        pages[pn] = NS(size=NS(width=595.0, height=842.0), rotation=0)
    fake = NS()
    fake.pages = pages  # dict[int, NS(size, rotation)]
    fake.iterate_items = lambda: iter(ordered)
    return fake


# ---------------------------------------------------------------- Geometrie/Nutzung

def test_bounding_region_props():
    br = BoundingRegion(page=1, x0=10, y0=20, x1=110, y1=120)
    assert br.width == 100
    assert br.height == 100
    rect = br.as_pdf_rect()
    assert rect.x0 == 10 and rect.y1 == 120


def test_canonical_table_linearized_and_cell_lookup():
    t = TableStructure(
        table_id="t1",
        page=1,
        num_rows=2,
        num_cols=2,
        cells=[
            Cell(row_index=0, column_index=0, text="Full Service"),
            Cell(row_index=0, column_index=1, text="5.916,67 EUR"),
            Cell(row_index=1, column_index=0, text="monatlich"),
        ],
    )
    lit = t.linearized_text()
    assert "Full Service | 5.916,67 EUR" in lit
    assert t.cell(0, 1).text == "5.916,67 EUR"
    assert t.cell(1, 0).text == "monatlich"


def test_find_text_case_insensitive():
    page = Page(page_number=1, width_pt=100, height_pt=100, text="Nicht geprüft")
    r = DocumentIntelligenceResult(
        source_sha256="abc123",
        canonical_text=page.text,
        pages_text=[page.text],
        pages=[page],
        provenance=ProcessingProvenance(provider="x", method=Method.NATIVE),
    )
    hits = r.find_text("nicht")
    assert len(hits) == 1
    pg, span = hits[0]
    assert pg.page_number == 1
    assert page.text[span.offset:span.to()] == "Nicht"


def test_build_canonical_text_formfeed_separated():
    p1 = Page(page_number=1, width_pt=100, height_pt=100, text="a")
    p2 = Page(page_number=2, width_pt=100, height_pt=100, text="b")
    assert build_canonical_text([p1, p2]) == "a\fb"


# ---------------------------------------------------------------- Docling-Mapping

def test_mapping_pages_elements_spans_and_bbox():
    doc = _fake_doc(
        {
            1: [
                _text_item("Kaufvertrag", _prov(1, 64, 700, 193, 650), "title"),
                _text_item("Unterstützung", _prov(1, 64, 640, 400, 600)),
            ],
            2: [
                _text_item("nächste Zeile", _prov(2, 64, 700, 300, 650), "page_footer"),
            ],
        }
    )
    provider = DoclingDocumentProvider()
    pages, warnings = provider._map_pages(doc)
    assert warnings == []
    p1 = pages[0]
    assert p1.page_number == 1
    assert p1.width_pt == 595.0
    assert p1.rotation == 0
    assert [e.type for e in p1.elements] == [ElementType.TITLE, ElementType.PARAGRAPH]
    # Lesereihenfolge
    assert [e.reading_order for e in p1.elements] == [0, 1]
    # Seiten-Text deterministisch
    assert p1.text == "Kaufvertrag\nUnterstützung"
    # Spans zeigen auf den bestimmten Text
    e0, e1 = p1.elements
    assert p1.text[e0.spans[0].offset:e0.spans[0].to()] == "Kaufvertrag"
    assert p1.text[e1.spans[0].offset:e1.spans[0].to()] == "Unterstützung"
    # BOTTOMLEFT -> PDF-Punkte (Ursprung oben links) umrechnen: H=842
    assert e0.region.x0 == 64
    assert abs(e0.region.y0 - (842 - 700)) < 1e-6
    assert abs(e0.region.y1 - (842 - 650)) < 1e-6
    # Methode aus content_layer
    assert e0.method == Method.OCR


def test_mapping_table_structure_and_spans():
    cells = [
        _raw_cell(0, 0, "Art.-Nr.", header=True),
        _raw_cell(0, 1, "Servicepaket", header=True),
        _raw_cell(1, 0, "914-000", col_span=1),
        # mehrzeilige Zelle mit Label->Wert Bezug in EINER Zelle
        _raw_cell(1, 1, "Full Service | 5.916,67 EUR", col_span=1),
    ]
    doc = _fake_doc({3: [_text_item("unten", _prov(3, 10, 800, 200, 780)), _table_item(cells, _prov(3, 5, 800, 400, 200))]})
    provider = DoclingDocumentProvider()
    pages, warnings = provider._map_pages(doc)
    p = pages[0]
    assert len(p.tables) == 1
    t = p.tables[0]
    assert t.page == 3
    assert t.num_rows == 2
    assert t.num_cols == 2
    assert t.headers == ["Art.-Nr.", "Servicepaket"]
    # Zellen mit Position, Span und Text
    c00 = t.cell(0, 0)
    assert c00.text == "Art.-Nr." and c00.row_span == 1 and c00.column_span == 1
    assert t.cell(1, 1).text == "Full Service | 5.916,67 EUR"
    # Label->Wert bleibt in der Zelle und im linearisierten Text erhalten
    lit = t.linearized_text()
    assert "Art.-Nr. | Servicepaket" in lit
    assert "Full Service | 5.916,67 EUR" in lit
    # Tabellen-Element mit korrekten children-Referenzen auf Zellen
    te = [e for e in p.elements if e.type == ElementType.TABLE][0]
    assert te.children == [f"cell_{t.table_id}_0_0", f"cell_{t.table_id}_0_1", f"cell_{t.table_id}_1_0", f"cell_{t.table_id}_1_1"]
    # Cell-Region hat die richtige Seitenzahl
    assert c00.region.page == 3
    # Lesereihenfolge: Text vor Tabelle, Spans konsistent
    assert p.elements[0].text == "unten"
    assert p.text[p.elements[0].spans[0].offset:p.elements[0].spans[0].to()] == "unten"


def test_mapping_page_header_footer_and_list():
    doc = _fake_doc(
        {
            1: [
                _text_item("Kopf", _prov(1, 64, 800, 400, 780), "page_header"),
                _text_item("1", _prov(1, 300, 100, 340, 80), "page_number"),
                _text_item("- Punkt", _prov(1, 64, 700, 300, 680), "list_item"),
                _text_item("Fuß", _prov(1, 64, 50, 400, 30), "page_footer"),
            ]
        }
    )
    provider = DoclingDocumentProvider()
    pages, _ = provider._map_pages(doc)
    types = [e.type for e in pages[0].elements]
    assert types == [
        ElementType.HEADER,
        ElementType.PAGE_NUMBER,
        ElementType.LIST_ITEM,
        ElementType.FOOTER,
    ]
    # Reihenfolge: Kopf vor Liste vor Fuß (Lesereihenfolge der Quelle)
    assert pages[0].elements[0].type == ElementType.HEADER
    assert pages[0].elements[-1].type == ElementType.FOOTER


def test_mapping_ocr_confidence_and_provenance():
    doc = _fake_doc(
        {
            1: [
                _text_item("a", _prov(1, 10, 800, 100, 790, ocr_conf=0.87)),
                _text_item("b", _prov(1, 10, 770, 100, 760, ocr_conf=0.91)),
            ]
        }
    )
    provider = DoclingDocumentProvider()
    pages, _ = provider._map_pages(doc)
    confs = [e.confidence for e in pages[0].elements]
    assert confs[0] == 0.87
    assert confs[1] == 0.91


def test_mapping_skips_orphan_items_with_warning():
    doc = _fake_doc({1: [_text_item("falsche Seite", _prov(7, 10, 10, 100, 100))]})
    provider = DoclingDocumentProvider()
    pages, warnings = provider._map_pages(doc)
    assert len(pages) == 1
    assert pages[0].elements == []
    assert any("ohne Seitenmodell" in w for w in warnings)


def test_mapping_span_offsets_survive_empty_elements():
    # Ein Bild (leerer Text) zwischen zwei Absätzen darf die Span-Offsets
    # der folgenden Elemente nicht verschieben (Regression: Separator jedes
    # Elements, auch leerer, muss mitgezaehlt werden).
    doc = _fake_doc(
        {
            1: [
                _text_item("Betriebskosten", _prov(1, 10, 800, 300, 790)),
                _text_item("", _prov(1, 10, 750, 590, 740), "picture"),
                _text_item("13.115,00", _prov(1, 10, 700, 200, 690)),
            ]
        }
    )
    provider = DoclingDocumentProvider()
    pages, _ = provider._map_pages(doc)
    p = pages[0]
    assert p.text == "Betriebskosten\n\n13.115,00"
    assert [e.text for e in p.elements] == ["Betriebskosten", "", "13.115,00"]
    for e in p.elements:
        if not e.text:
            continue
        sp = e.spans[0]
        assert p.text[sp.offset:sp.to()] == e.text


def test_mapping_deduplicates_identical_items():
    # Docling liefert manche Items (Tabellen, OCR-Zeilen) mehrfach (z.B.
    # Body UND Floats); identische Exemplace duerfen nur einmal gemappt werden.
    item = _text_item("Seriennummer", _prov(1, 10, 800, 200, 790))
    doc = _fake_doc({1: [item, item, item]})
    provider = DoclingDocumentProvider()
    pages, _ = provider._map_pages(doc)
    assert len(pages[0].elements) == 1
    assert pages[0].elements[0].text == "Seriennummer"


# ---------------------------------------------------------------- Registry

def test_registry_and_availability():
    caps = {c.name: c for c in available_providers()}
    assert "docling" in caps
    assert "native_pdf" in caps
    assert "paddle" in caps and not caps["paddle"].available
    assert "tesseract" in caps
    p = get_provider("native_pdf")
    assert p.capabilities().supports_pdf
    assert p.is_available()


def test_settings_defaults():
    s = DocumentIntelligenceSettings()
    assert s.ocr_lang == ["de", "en"]
    assert s.table_mode == "accurate"
    assert s.do_table_structure is True