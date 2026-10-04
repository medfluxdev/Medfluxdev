"""Lokaler OCR-Provider für Medflux (Schritt 5).

Bevorzugt Tesseract mit deutscher Sprachunterstützung. Wenn Tesseract nicht
verfügbar ist, wird OCRUnavailableError geworfen, damit der Aufrufer elegant
mit einer deutschen Warnung antworten kann – ohne Absturz.
"""

from __future__ import annotations

from typing import Optional

from PIL import Image

import pytesseract

OCR_UNAVAILABLE_MSG = (
    "OCR ist nicht verfügbar (Tesseract nicht installiert). "
    "Der Text konnte nicht erkannt werden."
)


class OCRUnavailableError(Exception):
    """Wird geworfen, wenn Tesseract/OCR nicht verfügbar ist."""


class OCRProvider:
    def __init__(
        self,
        tesseract_cmd: str | None = None,
        lang: str = "deu",
        enabled: bool = True,
    ) -> None:
        self._lang = lang
        self._enabled = enabled
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def is_available(self) -> bool:
        """Prüft, ob OCR aktiviert und Tesseract ausführbar ist."""
        if not self._enabled:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def image_to_text(self, image: Image.Image) -> str:
        """OCR einer bereits gerasterten Bildseite (lokal, Tesseract)."""
        if not self.is_available():
            raise OCRUnavailableError(OCR_UNAVAILABLE_MSG)
        return pytesseract.image_to_string(image, lang=self._lang)

    def image_to_word_data(self, image: Image.Image) -> list[dict]:
        """Wort-Level-Daten einer Bildseite für die Quell-Navigation.

        Liefert pro Wort: `text`, `confidence` (0..1, NaN/negativ -> None) und
        das Rechteck `left/top/width/height` in **BILD-PIXELN** (Ursprung oben
        links). Die Umrechnung in PDF-Punkte erfolgt deterministisch im Aufrufer
        (app/documents/geometry.py) mit der bekannten Rasterauflösung.

        Gibt leere Liste zurück, wenn OCR nicht verfügbar ist oder keine
        Wort-Daten geliefert werden – der Textpfad funktioniert dann weiter
        (nur ohne Boxen/Konfidenz, NIE mit falschen Koordinaten).
        """
        if not self.is_available():
            return []
        try:
            data = pytesseract.image_to_data(
                image, lang=self._lang, output_type=pytesseract.Output.DICT
            )
        except Exception:
            return []

        words: list[dict] = []
        n = len(data.get("text", []))
        for i in range(n):
            text = (data.get("text")[i] or "").strip()
            if not text:
                continue
            raw_conf = data.get("conf", [0])[i]
            try:
                conf = float(raw_conf) / 100.0
            except (TypeError, ValueError):
                conf = None
            if conf is not None and conf < 0:
                conf = None
            words.append(
                {
                    "text": text,
                    "confidence": conf,
                    "left": int(data.get("left", [0])[i]),
                    "top": int(data.get("top", [0])[i]),
                    "width": int(data.get("width", [0])[i]),
                    "height": int(data.get("height", [0])[i]),
                }
            )
        return words
