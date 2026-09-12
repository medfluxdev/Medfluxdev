"""Deterministische Koordinaten-Mappings für die Quell-Navigation (Medflux).

Die Medflux-Quellnavigation referenziert Positionen IMMER im Koordinatensystem
der ORIGINAL-PDF-Seite (Punkte, 72/inch, Ursprung oben links, y wächst nach
unten – identisch zum PyMuPDF-Standard `page.rect`).

- Native Textschicht: PyMuPDF liefert Wort-/Block-Boxen bereits in PDF-Punkten.
- OCR-Spur: Tesseract/pytesseract liefert Boxen in BILD-PIXELN (Ursprung oben
  links). Die Umrechnung Pixel → PDF-Punkte ist deterministisch, weil Medflux
  die Seite selbst mit bekanntem DPI rastet (Standard: 300 dpi):
      pdf_pt = pixel * (72 / dpi)
  Sollte die gerasterte Bildgröße unerwartet abweichen (Clip/Skala), wird
  zusätzlich über das echte Seitenrechteck korrigiert: scale = rect / pixmap.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PdfRect(BaseModel):
    """Rechteck in PDF-Punkten der Original-Seite (oben-links-Ursprung)."""

    x0: float = Field(ge=0.0)
    y0: float = Field(ge=0.0)
    x1: float = Field(ge=0.0)
    y1: float = Field(ge=0.0)

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    def union(self, other: "PdfRect") -> "PdfRect":
        return PdfRect(
            x0=min(self.x0, other.x0),
            y0=min(self.y0, other.y0),
            x1=max(self.x1, other.x1),
            y1=max(self.y1, other.y1),
        )


PT_PER_INCH = 72.0


def ocr_pixels_to_pdf_rect(
    rect: PdfRect,
    *,
    dpi: float,
    page_width_pt: Optional[float] = None,
    page_height_pt: Optional[float] = None,
    image_width_px: Optional[float] = None,
    image_height_px: Optional[float] = None,
) -> PdfRect:
    """Pixel-Rechteck → PDF-Punkte mit optionaler Seitenrechteck-Korrektur.

    Ohne Seitenrechteck gilt die reine DPI-Skala (72/dpi). Werden die echten
    Seiten- und Bildmaße mitgegeben, wird über diese skaliert (robust gegen
    Clips/Skalierung). So bleiben Koordinaten IMMER auf die Original-PDF-Seite
    abbildbar.
    """
    sx = sy = PT_PER_INCH / dpi
    if (page_width_pt and page_height_pt and image_width_px and image_height_px
            and image_width_px > 0 and image_height_px > 0):
        sx = page_width_pt / image_width_px
        sy = page_height_pt / image_height_px

    return PdfRect(x0=rect.x0 * sx, y0=rect.y0 * sy, x1=rect.x1 * sx, y1=rect.y1 * sy)