"""PDF-Text-Extraktion für Medflux (Schritt 5).

- Extrahiert Text Seite für Seite mit PyMuPDF, erhält die echte Seitennummer.
- Erkennt deterministisch leere/texthaltige bzw. gescannte Seiten.
- Rastert nur Seiten, die OCR benötigen, und bleibt dabei lokal.
- Quell-Navigation: native Wort-Boxen (PDF-Punkte) und OCR-Wort-Boxen (über die
  bekannte Rasterauflösung deterministisch in PDF-Punkte umgerechnet) werden an
  den ExtractionUnits mitgeführt, damit später keine Neuverarbeitung/Re-OCR
  erforderlich ist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import fitz

from app.documents.extraction.schemas import (
    ExtractionUnit,
    SourceBox,
    SourceType,
    UnitMethod,
)
from app.documents.extraction.ocr import OCRProvider
from app.documents.geometry import PdfRect, ocr_pixels_to_pdf_rect

# Unterhalb dieser Anzahl an substantiven Zeichen gilt eine Seite als
# textarm (möglicherweise gescannt/Bild) und benötigt OCR.
TEXT_POOR_THRESHOLD = 50

# Auflösung, mit der Seiten für OCR gerastert werden (wird für die
# deterministische Pixel->Punkt-Umrechnung der OCR-Boxen benötigt).
OCR_DPI = 300

_OCR_PAGE_MSG = "Seite {n} ist textarm/gescannt; OCR ist nicht verfügbar."


def _substantive_count(text: str) -> int:
    """Zählt nicht-leere, nicht-Whitespace-Zeichen eines Texts."""
    return sum(1 for ch in text if not ch.isspace())


def _box_union(boxes: list[SourceBox]) -> Optional[SourceBox]:
    if not boxes:
        return None
    page = boxes[0].page
    return SourceBox(
        page=page,
        x0=min(b.x0 for b in boxes),
        y0=min(b.y0 for b in boxes),
        x1=max(b.x1 for b in boxes),
        y1=max(b.y1 for b in boxes),
    )


def _mean_conf(confs: list[Optional[float]]) -> Optional[float]:
    vals = [c for c in confs if c is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 3)


def page_words(page: fitz.Page, page_number: int) -> list[SourceBox]:
    """Native Wort-Boxen einer Seite in PDF-Punkten (Quell-Navigation)."""
    boxes = []
    for w in page.get_text("words"):
        x0, y0, x1, y1, word, *_ = w
        boxes.append(SourceBox(page=page_number, x0=x0, y0=y0, x1=x1, y1=y1, text=word))
    return boxes


def _rasterize(page: fitz.Page):
    """Rastert eine Seite für OCR; liefert (PIL-Bild, Breite_px, Höhe_px)."""
    pix = page.get_pixmap(dpi=OCR_DPI)
    from PIL import Image

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return img, pix.width, pix.height


def _ocr_word_boxes(page, image, width_px, height_px, page_number, ocr) -> tuple[list[SourceBox], Optional[float]]:
    """OCR-Wort-Boxen (Pixel -> PDF-Punkte) + mittlere Konfidenz."""
    boxes = []
    confidences: list[Optional[float]] = []
    for w in ocr.image_to_word_data(image):
        conf = w["confidence"]
        if conf is not None and conf < 0:
            conf = None
        rect = ocr_pixels_to_pdf_rect(
            PdfRect(x0=w["left"], y0=w["top"], x1=w["left"] + w["width"], y1=w["top"] + w["height"]),
            dpi=OCR_DPI,
            page_width_pt=page.rect.width,
            page_height_pt=page.rect.height,
            image_width_px=width_px,
            image_height_px=height_px,
        )
        boxes.append(
            SourceBox(
                page=page_number,
                x0=rect.x0,
                y0=rect.y0,
                x1=rect.x1,
                y1=rect.y1,
                text=w["text"],
                confidence=conf,
            )
        )
        confidences.append(conf)
    return boxes, _mean_conf(confidences)


def extract_pdf_units(
    pdf_path: Path,
    ocr: Optional[OCRProvider] = None,
) -> tuple[list[ExtractionUnit], bool, list[str], int]:
    """Extrahiert Texteinheiten aus einem PDF.

    Liefert (units, requires_ocr_remaining, warnings, page_count).
    Wirft Exception bei korruptem PDF (Aufrufer behandelt das).
    """
    units: list[ExtractionUnit] = []
    warnings: list[str] = []
    requires_ocr_remaining = False

    ocr_ok = bool(ocr and ocr.is_available())

    doc = fitz.open(pdf_path)
    try:
        page_count = len(doc)
        for page_index in range(page_count):
            page = doc.load_page(page_index)
            page_number = page_index + 1
            text = page.get_text("text").strip()
            # Nicht-unterbrechende Leerzeichen als normale Leerzeichen normalisieren
            # (häufig bei Preisen/Datum in deutschen Verträgen).
            text = text.replace("\xa0", " ")

            if _substantive_count(text) >= TEXT_POOR_THRESHOLD:
                boxes = page_words(page, page_number)
                units.append(
                    ExtractionUnit(
                        source_type=SourceType.PAGE,
                        index=page_number,
                        text=text,
                        method=UnitMethod.TEXT,
                        boxes=boxes,
                        bbox=_box_union(boxes),
                    )
                )
                continue

            # Textarme/gescannte Seite → OCR versuchen.
            if ocr_ok:
                image = _rasterize(page)
                ocr_text = ocr.image_to_text(image).strip()
                word_boxes, conf = _ocr_word_boxes(page, image[0], image[1], image[2], page_number, ocr)
                units.append(
                    ExtractionUnit(
                        source_type=SourceType.PAGE,
                        index=page_number,
                        text=ocr_text,
                        method=UnitMethod.OCR,
                        boxes=word_boxes,
                        bbox=_box_union(word_boxes),
                        ocr_confidence=conf,
                    )
                )
            else:
                requires_ocr_remaining = True
                warnings.append(_OCR_PAGE_MSG.format(n=page_number))
                units.append(
                    ExtractionUnit(
                        source_type=SourceType.PAGE,
                        index=page_number,
                        text="",
                        method=UnitMethod.TEXT,
                    )
                )
    finally:
        doc.close()

    return units, requires_ocr_remaining, warnings, page_count