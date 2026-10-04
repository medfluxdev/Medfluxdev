"""Fokussierte Tests zur Quell-Navigations-Metadaten (Schritt 5/8B-Semantik).

PrÃ¼ft: deterministische Pixelâ†’Punkt-Umrechnung, native Wort-Boxen aus
PyMuPDF, OCR-Wort-Box-Mapping (ohne Tesseract-Binary!) sowie RÃ¼ckwÃ¤rts-
KompatibilitÃ¤t der erweiterten Modelle.
"""

import pytest
import fitz

from app.documents.geometry import PdfRect, ocr_pixels_to_pdf_rect
from app.documents.extraction import pdf
from app.documents.extraction.ocr import OCRProvider, OCRUnavailableError
from app.documents.extraction.pdf import _ocr_word_boxes, _mean_conf, page_words
from app.ai.groups.evidence import verify_evidence
from app.documents.extraction.schemas import (
    ExtractionUnit,
    SourceBox,
    SourceType,
    UnitMethod,
)
from app.models.evidence import BoundingBox, SourceEvidence


# ------------------------------------------------------------------ geometry

def test_pixel_to_point_scale_300dpi():
    r = ocr_pixels_to_pdf_rect(
        PdfRect(x0=100, y0=100, x1=200, y1=150), dpi=300
    )
    # 72/300 = 0.24
    assert (r.x0, r.y0, r.x1, r.y1) == pytest.approx((24.0, 24.0, 48.0, 36.0))


def test_pixel_to_point_with_page_rect_correction():
    # A4 @300 dpi: 595.32 x 841.92 pt entspricht 2480 x 3508 px (glatt)
    r = ocr_pixels_to_pdf_rect(
        PdfRect(x0=0, y0=0, x1=2480, y1=3508),
        dpi=300,
        page_width_pt=595.32,
        page_height_pt=841.92,
        image_width_px=2480,
        image_height_px=3508,
    )
    assert r.x1 == pytest.approx(595.32, abs=0.2)
    assert r.y1 == pytest.approx(841.92, abs=0.2)


def test_bounding_box_model_validates_ranges():
    bb = BoundingBox(x0=0, y0=0, x1=10, y1=20)
    assert bb.x1 == 10


# --------------------------------------------------- native word boxes (fitz)

def test_page_words_on_synthetic_pdf():
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((72, 100), "KÃ¼ndigungsfrist: 3 Monate", fontsize=12)
    boxes = page_words(page, page_number=1)
    doc.close()
    assert len(boxes) >= 3
    assert any(b.text == "KÃ¼ndigungsfrist:" for b in boxes)
    for b in boxes:
        assert b.page == 1
        assert b.x1 > b.x0 and b.y1 > b.y0
        assert b.x0 >= 0 and b.y0 >= 0 and b.x1 <= 600 and b.y1 <= 800


# ------------------------------------------- OCR word boxes (ohne Tesseract!)

class _FakeOcr:
    def __init__(self, words):
        self._words = words

    def image_to_word_data(self, image):
        return self._words


def test_ocr_word_boxes_converted_to_pdf_points():
    doc = fitz.open()
    page = doc.new_page(width=595.32, height=841.92)
    fake = _FakeOcr([
        {"text": "Monate", "confidence": 0.92,
         "left": 100, "top": 100, "width": 200, "height": 50},
        {"text": "null", "confidence": -1.0,
         "left": 320, "top": 100, "width": 60, "height": 50},
    ])
    boxes, conf = _ocr_word_boxes(
        page, image=object(), width_px=2480, height_px=3508,
        page_number=3, ocr=fake,
    )
    doc.close()
    assert len(boxes) == 2
    assert boxes[0].page == 3
    assert boxes[0].text == "Monate"
    assert boxes[0].x1 > boxes[0].x0
    # -1-er-Konfidenz wird zu None; Mittel nur Ã¼ber gÃ¼ltige Werte
    assert boxes[1].confidence is None
    assert conf == pytest.approx(0.92)


def test_mean_conf_ignores_none():
    assert _mean_conf([0.9, None, 0.7]) == pytest.approx(0.8)
    assert _mean_conf([None, None]) is None
    assert _mean_conf([]) is None


# ------------------------------------------------- OCR provider ist Lokalfall

def test_ocr_word_data_empty_when_unavailable():
    provider = OCRProvider(enabled=True)
    assert not provider.is_available()  # Tesseract-Binary fehlt auf dieser Box
    assert provider.image_to_word_data(None) == []
    try:
        provider.image_to_text(None)  # type: ignore
        raise AssertionError("sollte OCRUnavailableError werfen")
    except OCRUnavailableError:
        pass


# ----------------------------------------------- RÃ¼ckwÃ¤rts-KompatibilitÃ¤t

def test_extraction_unit_legacy_constructor_backwards_compatible():
    u = ExtractionUnit(source_type=SourceType.PAGE, index=2, text="x")
    assert u.method == UnitMethod.TEXT
    assert u.bbox is None
    assert u.boxes == []
    assert u.ocr_confidence is None
    assert u.model_dump()["boxes"] == []


def test_extraction_unit_carries_boxes():
    u = ExtractionUnit(
        source_type=SourceType.PAGE, index=1, text="x",
        boxes=[SourceBox(page=1, x0=0, y0=0, x1=5, y1=5, text="x")],
        ocr_confidence=0.88,
    )
    assert u.bbox is None
    assert len(u.boxes) == 1
    assert u.ocr_confidence == 0.88


def test_source_evidence_legacy_constructor_backwards_compatible():
    ev = SourceEvidence(page=1, source_text="3 Monate", confidence=0.8)
    assert ev.document_id is None
    assert ev.bounding_box is None
    assert ev.ocr_confidence is None


def test_source_evidence_accepts_navigation_metadata():
    ev = SourceEvidence(
        page=2,
        source_text="Kündigungsfrist",
        document_id="doc-1",
        bounding_box=BoundingBox(x0=10, y0=20, x1=90, y1=40),
        ocr_confidence=0.91,
    )
    assert ev.document_id == "doc-1"
    assert ev.bounding_box.x1 == 90
    assert ev.ocr_confidence == 0.91


# ------------------------------------- Enrichment in verify_evidence (PDF)

def _pdf_unit(page, text, boxes=None, bbox=None, ocr_confidence=None):
    return ExtractionUnit(
        source_type=SourceType.PAGE,
        index=page,
        text=text,
        method=UnitMethod.TEXT if boxes is not None and ocr_confidence is None else UnitMethod.OCR,
        boxes=boxes or [],
        bbox=bbox,
        ocr_confidence=ocr_confidence,
    )


def test_verify_evidence_attaches_bbox_from_word_boxes():
    units = [
        _pdf_unit(
            1,
            "Kündigungsfrist: 3 Monate",
            boxes=[
                SourceBox(page=1, x0=72, y0=100, x1=130, y1=116, text="Monate"),
                SourceBox(page=1, x0=140, y0=100, x1=180, y1=116, text="Kündigungsfrist:"),
            ],
        )
    ]
    ev = SourceEvidence(page=1, source_text="3 Monate", confidence=0.9)
    verified, issues = verify_evidence(ev, units)
    assert issues == []
    assert verified.bounding_box is not None
    # nur das "Monate"-Wort (x0=72) trägt zum belegten Fragment bei;
    # Kündigungsfrist: ist NICHT im source_text
    assert verified.bounding_box.x0 == 72
    assert verified.bounding_box.y1 == 116


def test_verify_evidence_falls_back_to_unit_bbox():
    unit = _pdf_unit(
        1, "fragment text",
        bbox=SourceBox(page=1, x0=10, y0=20, x1=200, y1=300),
    )
    ev = SourceEvidence(page=1, source_text="fragment", confidence=0.8)
    verified, _ = verify_evidence(ev, [unit])
    assert verified.bounding_box is not None
    assert verified.bounding_box.x0 == 10
    assert verified.bounding_box.x1 == 200


def test_verify_evidence_attaches_ocr_confidence():
    unit = _pdf_unit(
        1, "Wartung 9,50 EUR",
        boxes=[SourceBox(page=1, x0=0, y0=0, x1=50, y1=20, text="Wartung")],
        ocr_confidence=0.84,
    )
    ev = SourceEvidence(page=1, source_text="Wartung", confidence=0.8)
    verified, _ = verify_evidence(ev, [unit])
    assert verified.ocr_confidence == 0.84
    assert verified.bounding_box is not None
