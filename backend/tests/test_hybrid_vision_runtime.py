from pathlib import Path

import app.documents.intelligence.hybrid_runtime as runtime_module
from app.documents.intelligence.canonical import (
    BoundingRegion,
    DocumentIntelligenceResult,
    Element,
    ElementType,
    Method,
    Page,
    ProcessingProvenance,
)
from app.documents.intelligence.hybrid_runtime import HybridVisionRuntime


def _canonical():
    native = Page(
        page_number=1,
        width_pt=595,
        height_pt=842,
        text="A" * 200,
        elements=[
            Element(
                element_id="p1",
                type=ElementType.TEXT,
                text="A" * 200,
                page=1,
                region=BoundingRegion(page=1, x0=1, y0=1, x1=100, y1=30),
                reading_order=0,
                method=Method.NATIVE,
            )
        ],
    )
    scanned = Page(
        page_number=2,
        width_pt=595,
        height_pt=842,
        text="Service " * 20,
        elements=[
            Element(
                element_id="p2",
                type=ElementType.TABLE,
                text="Service " * 20,
                page=2,
                region=BoundingRegion(page=2, x0=1, y0=1, x1=200, y1=100),
                reading_order=0,
                method=Method.OCR,
            )
        ],
    )
    return DocumentIntelligenceResult(
        source_sha256="a" * 64,
        source_filename="contract.pdf",
        pages=[native, scanned],
        provenance=ProcessingProvenance(provider="test", method=Method.OCR),
    )


def test_runtime_only_renders_visual_candidates(monkeypatch):
    seen = {}

    def fake_page_image(path, page_number, *, longest_side):
        seen["path"] = path
        seen["page"] = page_number
        seen["longest_side"] = longest_side
        return "image64"

    monkeypatch.setattr(runtime_module, "page_image", fake_page_image)

    runtime = HybridVisionRuntime(Path("contract.pdf"), _canonical(), longest_side=1800)
    assert runtime.routes == {1: "text_native", 2: "hybrid_required"}
    assert runtime.visual_pages == [2]
    assert runtime.render_page(2) == "image64"
    assert seen["page"] == 2
    assert seen["longest_side"] == 1800


def test_runtime_rejects_clean_native_page_render():
    runtime = HybridVisionRuntime(Path("contract.pdf"), _canonical())
    try:
        runtime.render_page(1)
    except ValueError as exc:
        assert "does not require visual compute" in str(exc)
    else:
        raise AssertionError("native page render should be rejected")
