from app.documents.intelligence.canonical import (
    BoundingRegion,
    DocumentIntelligenceResult,
    Element,
    ElementType,
    Method,
    Page,
)
from app.documents.intelligence.hybrid import (
    PageRoute,
    classify_page,
    route_summary,
    visual_candidate_pages,
)


def _page(number: int, text: str, *, method=Method.NATIVE, type_=ElementType.TEXT, metadata=None):
    element = Element(
        element_id=f"p{number}-e1",
        type=type_,
        text=text,
        page=number,
        region=BoundingRegion(page=number, x0=1, y0=1, x1=100, y1=40),
        reading_order=0,
        method=method,
        metadata=metadata or {},
    )
    return Page(page_number=number, width_pt=595, height_pt=842, text=text, elements=[element])


def test_clean_native_page_stays_text_only():
    page = _page(1, "A" * 200)
    assert classify_page(page) == PageRoute.TEXT_NATIVE


def test_sparse_empty_page_routes_to_vision():
    page = Page(page_number=1, width_pt=595, height_pt=842, text="", elements=[])
    assert classify_page(page) == PageRoute.VISION_REQUIRED


def test_ocr_page_with_structure_routes_hybrid():
    page = _page(1, "Service " * 20, method=Method.OCR, type_=ElementType.TABLE)
    assert classify_page(page) == PageRoute.HYBRID_REQUIRED


def test_visual_marker_routes_hybrid_even_with_text():
    page = _page(
        1,
        "Vertragstext " * 20,
        method=Method.OCR,
        metadata={"requires_vision": True},
    )
    assert classify_page(page) == PageRoute.HYBRID_REQUIRED


def test_candidate_pages_exclude_clean_native():
    pages = [
        _page(1, "A" * 200),
        _page(2, "B" * 100, method=Method.OCR, type_=ElementType.TABLE),
        Page(page_number=3, width_pt=595, height_pt=842, text="", elements=[]),
    ]
    assert visual_candidate_pages(pages) == [2, 3]
    assert route_summary(pages) == {
        1: "text_native",
        2: "hybrid_required",
        3: "vision_required",
    }
