"""STEP 8B-Haertung: Evidenz-Bruecke, Disparitaet, deutsche Daten,
Token-Sicherheit, Strukturrollen, Provenienz-Manifest (fokussierte Tests).

Nur deterministische, lokalere Tests – keine KI, keine echten Vertraege.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.documents.intelligence.canonical import (
    BoundingRegion,
    CANONICAL_SCHEMA_VERSION,
    Cell,
    Element,
    Method,
    Page,
    ProcessingProvenance,
)
from app.documents.intelligence.dates import find_dates, parse_german_date
from app.documents.intelligence.disparity import (
    DisparityStatus,
    SourceType,
    ValueCandidate,
    classify_values,
)
from app.documents.intelligence.evidence import (
    bounding_box_from_region,
    evidence_from_cell,
    evidence_from_element,
)
from app.documents.intelligence.structure import (
    BODY,
    apply_structural_roles,
    dominant_repeated_lines,
)
from app.documents.intelligence.token_safety import (
    classify_date_token,
    classify_number_token,
    classify_percent_token,
    classify_serial_repetition,
    safe_normalize_money,
    scan_suspicious_numbers,
)
from app.models.enums import ExtractionMethod


def _element(text, page_no, *, x0=0.0, y0=0.0, x1=200.0, y1=20.0, method=Method.OCR,
             confidence=0.87, element_id="e1"):
    return Element(
        element_id=element_id,
        type="text",
        text=text,
        page=page_no,
        region=BoundingRegion(page=page_no, x0=x0, y0=y0, x1=x1, y1=y1),
        reading_order=0,
        method=method,
        confidence=confidence,
    )


# ------------------------------------------------------------- Evidenz (3A)

def test_evidence_from_element_separates_confidence():
    el = _element("Full Service", 1, confidence=0.87)
    ev = evidence_from_element(el)
    assert ev.page == 1
    assert ev.source_type == "page"
    assert ev.source_text == "Full Service"
    assert ev.confidence is None  # semantisch bleibt getrennt
    assert ev.ocr_confidence == 0.87
    assert ev.extraction_method == ExtractionMethod.PROGRAMMATIC
    assert ev.requires_review is False
    assert ev.bounding_box is not None


def test_evidence_from_element_without_region_has_no_box():
    el = Element(element_id="e", page=1, reading_order=0)
    ev = evidence_from_element(el, source_text="x")
    assert ev.bounding_box is None
    assert ev.ocr_confidence is None


def test_evidence_from_cell_empty_is_none():
    c = Cell(row_index=0, column_index=0, text="   ", confidence=None)
    assert evidence_from_cell(c) is None


def test_evidence_from_cell_keeps_ocr_confidence():
    c = Cell(row_index=0, column_index=0, text="13.115,00", confidence=0.91,
             region=BoundingRegion(page=2, x0=0, y0=0, x1=50, y1=10))
    ev = evidence_from_cell(c)
    assert ev is not None
    assert ev.page == 2
    assert ev.ocr_confidence == 0.91
    assert ev.confidence is None


def test_bounding_box_from_region_none():
    assert bounding_box_from_region(None) is None


# ------------------------------------------------------------- Disparitaet (3B)

def _can(value, source_type=SourceType.OCR_TEXT, page=1, conf=0.7):
    return ValueCandidate(value=value, source_type=source_type, page=page, ocr_confidence=conf)


def test_disparity_consistent_money():
    d = classify_values("money", [_can("13.115,00"), _can("13.115,00")])
    assert d.status == DisparityStatus.CONSISTENT
    assert d.review_required is False


def test_disparity_strich_money_consistent():
    d = classify_values("money", [_can("2.419,-"), _can("2.419,00")])
    assert d.status == DisparityStatus.CONSISTENT


def test_disparity_serial_conflict():
    d = classify_values("serial", [_can("21115", SourceType.OCR_TEXT), _can("24445", SourceType.DOCX)])
    assert d.status == DisparityStatus.CONFLICT
    assert d.review_required is True
    assert d.candidates[0].value == "21115"  # Wortlaut unveraendert


def test_disparity_single_no_review():
    d = classify_values("money", [_can("13.115,00")])
    assert d.status == DisparityStatus.SINGLE


def test_disparity_empty_undetermined():
    d = classify_values("money", [])
    assert d.status == DisparityStatus.UNDETERMINED
    assert d.review_required is False


# ------------------------------------------------------------- Deutsche Daten (3C)

def test_parse_german_month_name():
    assert parse_german_date("27. Januar 2018") == date(2018, 1, 27)
    assert parse_german_date("16. April 2025") == date(2025, 4, 16)


def test_parse_german_abbreviation():
    assert parse_german_date("31. Dez. 2027") == date(2027, 12, 31)
    assert parse_german_date("1. Feb. 2026") == date(2026, 2, 1)


def test_parse_numeric_german():
    assert parse_german_date("13.06.2017") == date(2017, 6, 13)
    assert parse_german_date("1.6.17") == date(2017, 6, 1)


def test_parse_invalid_day_none():
    assert parse_german_date("32. Januar 2018") is None


def test_parse_event_based_none():
    # Ereignisbasiert: KEIN Datum wird erfunden
    assert parse_german_date("Beginn ab Übergabedatum") is None
    assert parse_german_date("Vertrag endet am ... Unterzeichnung") is None


def test_parse_missing_day_none():
    assert parse_german_date("März 2028") is None


def test_find_dates_reports_invalid_hits():
    hits = find_dates("32. Januar 2018")
    assert len(hits) >= 1
    assert hits[0].text == "32. Januar 2018"
    assert hits[0].to_date() is None


# ------------------------------------------------------------- Token-Sicherheit (5)

def test_safe_normalize_money_exact():
    m = safe_normalize_money("792.000,00")
    assert m.ok and str(m.amount) == "792000.00"
    assert str(safe_normalize_money("13.115,00").amount) == "13115.00"
    assert str(safe_normalize_money("1.234,-").amount) == "1234.00"


def test_safe_normalize_money_suspicious():
    assert safe_normalize_money("150,480,00").ok is False
    assert safe_normalize_money("5.916.67").ok is False


def test_classify_number_token():
    assert classify_number_token("792,000,00")[0] == "suspicious"
    assert classify_number_token("5.916.67")[0] == "suspicious"
    assert classify_number_token("792.000,00")[0] == "safe"
    assert classify_number_token("13.115,00")[0] == "safe"


def test_classify_percent_token():
    assert classify_percent_token("19,00 %")[0] == "safe"
    assert classify_percent_token("1.234 %")[0] == "suspicious"


def test_classify_date_token():
    assert classify_date_token("27. Januar 2018")[0] == "safe"
    assert classify_date_token("ab Übergabedatum")[0] == "suspicious"


def test_classify_serial_repetition():
    assert classify_serial_repetition(["21115", "24445"])[0] == "suspicious"
    assert classify_serial_repetition(["21115"])[0] == "safe"


def test_scan_suspicious_numbers_detects_dirty_tokens():
    text = "150,480,00 EUR und 792,000,00 bzw. 5.916.67 falsch, aber 792.000,00 korrekt"
    found = scan_suspicious_numbers(text)
    tokens = {t for t, _ in found}
    assert "150,480,00" in tokens
    assert "792,000,00" in tokens
    assert "5.916.67" in tokens
    assert "792.000,00" not in tokens


# ------------------------------------------------------------- Strukturrollen (4)

def _page(pn, elements):
    return Page(page_number=pn, width_pt=595.0, height_pt=842.0, elements=elements)


def test_structural_roles_header_footer_page_number():
    def top(text, id_):
        return _element(text, 1, y0=5.0, y1=25.0, element_id=id_)

    def bottom(text, id_):
        return _element(text, 1, y0=820.0, y1=837.0, element_id=id_)

    p1 = _page(1, [top("Sanitätshaus GmbH", "h1"), bottom("Liefer- und Zahlungsbedingungen", "f1"),
                   bottom(" 3 ", "num1"), _element("Vollwartung Gerät X", 1, y0=400, y1=420, element_id="b1")])
    p2 = _page(2, [top("Sanitätshaus GmbH", "h2"), bottom("Liefer- und Zahlungsbedingungen", "f2"),
                   bottom(" 4 ", "num2"), _element("OCR-Konfidenz prüfen", 2, y0=400, y1=420, element_id="b2")])

    report = apply_structural_roles([p1, p2], min_pages_share=0.5)
    marked = dict(report.marked)
    assert marked.get("h1") == "header"
    assert marked.get("h2") == "header"
    assert marked.get("f1") == "footer"
    assert marked.get("f2") == "footer"
    assert marked.get("num1") == "page_number"
    assert marked.get("b1", BODY) == BODY  # nicht markiert
    # Text bleibt unangetastet
    assert p1.elements[0].text == "Sanitätshaus GmbH"


def test_structural_roles_single_page_not_marked():
    el = _element("Nur einmal Kopf?", 1, y0=5.0, y1=25.0, element_id="x1")
    p = _page(1, [el])
    report = apply_structural_roles([p], min_pages_share=0.5)
    assert not report.marked


def test_dominant_repeated_lines_lists_header():
    el = _element("Dokusign Envelope ID: X", 1, y0=5.0, y1=25.0, element_id="d1")
    p1 = _page(1, [el])
    p2 = _page(2, [_element("Dokusign Envelope ID: X", 2, y0=5.0, y1=25.0, element_id="d2")])
    lines = dominant_repeated_lines([p1, p2])
    assert lines and lines[0]["pages"] == 2
    assert lines[0]["role"] == "header"


# ------------------------------------------------------------- Manifest (8)

def test_provenance_defaults_manifest():
    p = ProcessingProvenance(provider="docling")
    assert p.canonical_schema_version == CANONICAL_SCHEMA_VERSION
    assert p.dpi is None
    assert p.preprocessing is None


# ------------------------------------------------------------- Tabellen-Normalisierung (3D)

from app.documents.intelligence.table_normalize import (  # noqa: E402
    scan_geometry_relations,
    scan_table_relations,
)
from app.documents.intelligence.canonical import TableStructure  # noqa: E402


def _money_el(text, page_no, *, x0, y0, x1, y1, element_id, etype="text"):
    return Element(
        element_id=element_id,
        type=etype,
        text=text,
        page=page_no,
        region=BoundingRegion(page=page_no, x0=x0, y0=y0, x1=x1, y1=y1),
        reading_order=0,
    )


def test_geometry_relation_label_left_unambiguous():
    label = _money_el("Gesamtbetrag Angebot :", 2, x0=78.0, y0=390.0, x1=156.0, y1=399.7, element_id="l1")
    value = _money_el("€ 792.000,00", 2, x0=236.0, y0=390.7, x1=279.3, y1=399.7, element_id="v1")
    rs = scan_geometry_relations([value, label])
    rels = rs.by_trust("geometry")
    assert len(rels) == 1
    rel = rels[0]
    assert rel.label == "Gesamtbetrag Angebot :"
    assert rel.value_token == "792.000,00"
    assert str(rel.normalized_amount) == "792000.00"
    assert rel.label_element_id == "l1"


def test_geometry_relation_ambiguous_two_labels_review():
    l1 = _money_el("Kosten", 2, x0=50.0, y0=390.0, x1=120.0, y1=399.7, element_id="l1")
    l2 = _money_el("Netto", 2, x0=130.0, y0=390.0, x1=200.0, y1=399.7, element_id="l2")
    value = _money_el("€ 792.000,00", 2, x0=236.0, y0=390.7, x1=279.3, y1=399.7, element_id="v1")
    rs = scan_geometry_relations([value, l1, l2])
    review = rs.by_trust("review_required")
    assert review and review[0].reason == "multiple_labels_in_band"
    assert rs.by_trust("geometry") == []


def test_geometry_relation_no_label_review():
    value = _money_el("€ 792.000,00", 2, x0=236.0, y0=390.7, x1=279.3, y1=399.7, element_id="v1")
    rs = scan_geometry_relations([value])
    review = rs.by_trust("review_required")
    assert review and review[0].reason == "0_labels_in_band"


def test_table_relation_structured_and_suspicious():
    t = TableStructure(
        table_id="t1", page=5, num_rows=2, num_cols=2,
        cells=[
            Cell(row_index=0, column_index=0, text="TrueBeam STx - Essentials"),
            Cell(row_index=0, column_index=1, text="€99.000,00"),
            Cell(row_index=1, column_index=0, text="Gesamt"),
            Cell(row_index=1, column_index=1, text="€99,000,00"),
        ],
    )
    rs = scan_table_relations(t)
    structured = rs.by_trust("structured_table")
    review = rs.by_trust("review_required")
    assert len(structured) == 1
    assert structured[0].label == "TrueBeam STx - Essentials"
    assert str(structured[0].normalized_amount) == "99000.00"
    assert len(review) == 1  # "€99,000,00" -> suspicious, nie normalisiert
    assert review[0].value_token == "99,000,00"
    assert review[0].normalized_amount is None


def test_no_supplier_specific_rule():
    # "×9" MUSS unverstanden bleiben: nur Tokens werden beziehungsweise geliefert.
    label = _money_el("Annual Wartung", 5, x0=50.0, y0=282.0, x1=100.0, y1=291.0, element_id="l1")
    value = _money_el("€99.000,00 x9 wie Lieferant", 5, x0=117.0, y0=282.0, x1=200.0, y1=291.0, element_id="v1")
    rs = scan_geometry_relations([value, label])
    rels = rs.by_trust("geometry")
    assert len(rels) == 1
    assert rels[0].value_token == "99.000,00"
    assert str(rels[0].normalized_amount) == "99000.00"
    assert "x9" not in rels[0].label and "x9" not in rels[0].value_token