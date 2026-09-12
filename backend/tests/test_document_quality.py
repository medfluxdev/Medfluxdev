"""Fokussierte Tests der Dokumentqualitäts-Klassifikation (Schritt 5/Benchmark v2).

Keine PDF-, keine KI-, keine OCR-Abhängigkeit – reine, deterministische
Schwellwert-Logik aus app/documents/quality.py.
"""

from app.documents.quality import (
    DOC_NATIVE,
    DOC_PARTIAL,
    DOC_SCANNED,
    DOC_UNREADABLE,
    classify_pages,
    page_stat_from_text,
    recommended_path,
)


def _pages(data: list[tuple[int, int]]) -> list:
    # (Seite, substantive_chars) -> PageStat (ohne Bilder/Blöcke)
    return [page_stat_from_text(n, "x" * chars) for n, chars in data]


def test_native_text_high_coverage_and_density():
    pages = _pages([(n, 1200) for n in range(1, 11)])
    q = classify_pages("a.pdf", pages)
    assert q.classification == DOC_NATIVE
    assert q.recommended_processing_path == "native_extraction"
    assert q.coverage_ratio == 1.0
    assert q.native_text_char_count == 10 * 1200


def test_single_rich_page_of_many_is_not_native():
    # 15 Seiten, nur 1 Seite mit 1000 Zeichen -> NICHT native_text
    pages = [page_stat_from_text(n, "y" * 5) for n in range(1, 16)]
    pages[0] = page_stat_from_text(1, "y" * 1000)
    q = classify_pages("big.pdf", pages)
    assert q.classification == DOC_PARTIAL
    assert q.coverage_ratio < 0.35
    assert len(q.pages_needing_ocr) == 14


def test_sparse_full_coverage_is_partial():
    # 16 Seiten, alle mit etwas Text, aber nur ~110 Zeichen -> Teiltext
    pages = _pages([(n, 110) for n in range(1, 17)])
    q = classify_pages("bd.pdf", pages)
    assert q.classification == DOC_PARTIAL
    assert "geringe Textdichte" in "; ".join(q.extraction_warnings)
    assert q.recommended_processing_path == "native_plus_ocr_fallback"


def test_tiny_but_textrich_doc_is_partial():
    # 1 Seite, 1324 Zeichen: hohe Dichte, aber zu wenig Gesamttext
    pages = _pages([(1, 1324)])
    q = classify_pages("cche.pdf", pages)
    assert q.classification == DOC_PARTIAL
    assert any("zu wenig Gesamttext" in w for w in q.extraction_warnings)


def test_empty_pages_scanned():
    pages = _pages([(n, 0) for n in range(1, 6)])
    q = classify_pages("scan.pdf", pages)
    assert q.classification == DOC_SCANNED
    assert q.recommended_processing_path == "full_ocr_required"
    assert len(q.pages_needing_ocr) == 5


def test_low_total_with_meaningful_page_is_scanned_not_native():
    pages = _pages([(1, 10), (2, 8), (3, 12)])
    q = classify_pages("low.pdf", pages)
    assert q.classification == DOC_SCANNED


def test_unreadable_on_runtime_error():
    q = classify_pages("bad.pdf", [], open_error="korrupt")
    assert q.classification == DOC_UNREADABLE
    assert q.recommended_processing_path == "manual_review"


def test_recommended_path_mapping():
    assert recommended_path(DOC_NATIVE) == "native_extraction"
    assert recommended_path(DOC_PARTIAL) == "native_plus_ocr_fallback"
    assert recommended_path(DOC_SCANNED) == "full_ocr_required"
    assert recommended_path(DOC_UNREADABLE) == "manual_review"


def test_pages_needing_ocr_exact_positions():
    pages = _pages([(1, 600), (2, 4), (3, 900), (4, 0)])
    q = classify_pages("mix.pdf", pages)
    assert q.pages_needing_ocr == [2, 4]