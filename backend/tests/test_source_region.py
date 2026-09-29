"""Focused PR-5 UAT-D tests: narrowest trustworthy source geometry."""

import fitz

from app.documents.intelligence.canonical import (
    AtomicUnit,
    BoundingRegion,
    DocumentIntelligenceResult,
    GeometryPrecision,
    Method,
    Page,
    ProcessingProvenance,
)
from app.documents.source_region import resolve_narrowest_region


def _pdf(text: str, *, repeat: bool = False) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    if repeat:
        for y in range(60, 800, 22):
            for x in range(10, 590, 30):
                page.insert_text((x, y), "kW", fontsize=16)
    else:
        for i, line in enumerate(text.splitlines()):
            page.insert_text((40, 60 + i * 24), line, fontsize=12)
    return doc.tobytes()


def _canonical(page: Page) -> DocumentIntelligenceResult:
    return DocumentIntelligenceResult(
        source_sha256="abc",
        pages=[page],
        canonical_text=page.text,
        provenance=ProcessingProvenance(provider="test"),
    )


def test_text_layer_exact_word():
    result = resolve_narrowest_region(
        "Mindestvertragslaufzeit",
        pdf_bytes=_pdf("Mindestvertragslaufzeit: 2 Jahre"),
    )
    assert result["status"] == "exact"
    assert result["page"] == 1
    assert result["method"] == "pdf_text_layer"
    assert result["bbox"] is not None
    x0, y0, x1, y1 = result["bbox"]
    assert 0 <= x0 < x1 <= 600
    assert 0 <= y0 < y1 <= 800


def test_text_layer_token_fallback_for_split_snippet():
    result = resolve_narrowest_region(
        "Mindestvertragslaufzeit 2 Jahre",
        pdf_bytes=_pdf("Mindestvertragslaufzeit:\n2 Jahre"),
        page_hint=1,
    )
    assert result["status"] == "coarse"
    assert result["method"] == "pdf_text_layer"


def test_absent_snippet_is_none_not_invented():
    result = resolve_narrowest_region(
        "Kündigungsfrist-ABC-9999",
        pdf_bytes=_pdf("Mindestvertragslaufzeit"),
    )
    assert result["status"] == "none"
    assert result["bbox"] is None
    assert result["page"] is None


def test_oversize_region_downgraded_to_coarse():
    result = resolve_narrowest_region(
        "kW",
        pdf_bytes=_pdf("", repeat=True),
        page_hint=1,
    )
    assert result["status"] == "coarse"
    assert result["bbox"] is not None


def test_canonical_atomic_fallback_when_text_layer_empty():
    snippet = "Vertragsnummer-VK-2026-X1"
    page = Page(
        page_number=1,
        width_pt=600.0,
        height_pt=800.0,
        pdf_rotation=0,
        text=snippet,
        atomic_units=[
            AtomicUnit(
                unit_id="u1",
                kind="ocr_word",
                text=snippet,
                page=1,
                bbox=BoundingRegion(page=1, x0=40, y0=40, x1=230, y1=60),
                precision=GeometryPrecision.WORD,
                confidence=1.0,
                canonical_offset=0,
                canonical_length=len(snippet),
                aligned=True,
            )
        ],
    )
    result = resolve_narrowest_region(
        snippet,
        pdf_bytes=_pdf("Gänzlich unpassender Vertragstext ohne Snippet"),
        canonical=_canonical(page),
    )
    assert result["status"] == "exact"
    assert result["method"] == "canonical_atomic"
    assert result["page"] == 1
    x0, y0, x1, y1 = result["bbox"]
    assert (x0, y0, x1, y1) == (40, 40, 230, 60)


def test_rotation_not_required_for_unrotated_canonical():
    snippet = "Nur hier im OCR"
    page = Page(
        page_number=1,
        width_pt=600.0,
        height_pt=800.0,
        pdf_rotation=0,
        text=f"versehen {snippet} mehr",
        atomic_units=[
            AtomicUnit(
                unit_id="u1",
                kind="ocr_word",
                text=snippet,
                page=1,
                bbox=BoundingRegion(page=1, x0=100, y0=100, x1=300, y1=130),
                precision=GeometryPrecision.WORD,
                canonical_offset=8,
                canonical_length=len(snippet),
                aligned=True,
            )
        ],
    )
    pdf_bytes = _pdf("versehen ABC 123 def Test")
    result = resolve_narrowest_region(
        snippet,
        pdf_bytes=pdf_bytes,
        canonical=_canonical(page),
    )
    assert result["status"] == "exact"
    assert result["method"] == "canonical_atomic"


def test_pdf_garbage_bytes_returns_none():
    result = resolve_narrowest_region(
        "irgendwas",
        pdf_bytes=b"keine echte pdf datei",
    )
    assert result["status"] == "none"

def test_repeated_token_does_not_produce_misleading_highlight():
    result = resolve_narrowest_region(
        "Die Vertragsnummer 2026 ist maßgeblich",
        pdf_bytes=_pdf("Vertragsnummer: 2026\\nVertragsnummer: 2027"),
        page_hint=1,
    )
    assert result["status"] == "none"
    assert result["bbox"] is None


def test_unique_partial_token_is_only_coarse():
    result = resolve_narrowest_region(
        "Vertragsnummer 2026",
        pdf_bytes=_pdf("Vertragsnummer: 2026"),
        page_hint=1,
    )
    assert result["status"] == "coarse"
    assert result["bbox"] is not None


def test_repeated_exact_phrase_is_not_a_unique_location():
    result = resolve_narrowest_region(
        "Vertragsnummer",
        pdf_bytes=_pdf("Vertragsnummer: A\\nVertragsnummer: B"),
        page_hint=1,
    )
    assert result["status"] == "coarse"


def test_invalid_page_hint_returns_none():
    result = resolve_narrowest_region("Mindestvertragslaufzeit", pdf_bytes=_pdf("Mindestvertragslaufzeit"), page_hint=999)
    assert result["status"] == "none"
    assert result["bbox"] is None


def test_unique_phrase_with_text_layer_is_exact():
    result = resolve_narrowest_region("Mindestvertragslaufzeit", pdf_bytes=_pdf("Mindestvertragslaufzeit: 2 Jahre"), page_hint=1)
    assert result["status"] == "exact"


def test_repeated_phrase_is_not_exact_even_when_search_rectangles_are_narrow():
    result = resolve_narrowest_region("Vertragsnummer", pdf_bytes=_pdf("Vertragsnummer A\nVertragsnummer B"), page_hint=1)
    assert result["status"] == "coarse"
