"""Nativer PDF-Provider (STEP 8B).

Nutzt die vorhandene, getestete Schritt-5-Extraktion (PyMuPDF, native
Textschicht) und liefert sie als kanonische Dokument-Repraesentation.
Weder OCR noch Layout-/Tabellenanalyse – reiner nativer Fallback, der fuer
gemischte PDFs (eingebettete Textschicht) und als native Baseline dient.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from app.documents.extraction.pdf import extract_pdf_units
from app.documents.intelligence.canonical import (
    BoundingRegion,
    DocumentIntelligenceResult,
    Element,
    ElementType,
    Method,
    Page,
    ProcessingProvenance,
    TextSpan,
)
from app.documents.intelligence.provider import (
    DocumentIntelligenceProvider,
    DocumentIntelligenceSettings,
    IntelligenceProviderError,
    IntelligenceProviderUnavailableError,
    ProviderCapabilities,
)


class NativePdfDocumentProvider(DocumentIntelligenceProvider):
    """Provider fuer die eingebettete PDF-Textschicht (PyMuPDF)."""

    name = "native_pdf"

    def __init__(self) -> None:
        try:
            import fitz  # noqa: F401
        except Exception as exc:
            raise IntelligenceProviderUnavailableError(
                f"PyMuPDF (fitz) ist nicht installiert: {exc}"
            )
        self._ready = True

    def is_available(self) -> bool:
        return self._ready

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.name,
            available=True,
            supports_pdf=True,
            supports_ocr=False,
            supports_tables=False,
            supports_layout=False,
            supports_reading_order=False,
            offline_after_setup=True,
        )

    def process(
        self,
        path: Path,
        settings: Optional[DocumentIntelligenceSettings] = None,
    ) -> DocumentIntelligenceResult:
        path = Path(path)
        if not path.is_file():
            raise IntelligenceProviderError(f"Datei nicht gefunden: {path}")

        try:
            units, requires_ocr, warnings, page_count = extract_pdf_units(path, ocr=None)
        except Exception as exc:
            raise IntelligenceProviderError(f"Native PDF-Extraktion fehlgeschlagen: {exc}")

        try:
            dims = self._page_dims(path)
        except Exception as exc:
            raise IntelligenceProviderError(f"Seitenmaße nicht lesbar: {exc}")

        pages: list[Page] = []
        for unit in units:
            text = unit.text
            element = Element(
                element_id=f"elem_p{unit.index}_0",
                type=ElementType.PARAGRAPH,
                text=text,
                page=unit.index,
                region=_region(unit.index, unit.bbox),
                spans=[TextSpan(offset=0, length=len(text))] if text else [],
                reading_order=0,
                method=Method.NATIVE,
            )
            w, h = dims.get(unit.index, (0.0, 0.0))
            pages.append(
                Page(
                    page_number=unit.index,
                    width_pt=w,
                    height_pt=h,
                    text=text,
                    elements=[element],
                    tables=[],
                )
            )

        return DocumentIntelligenceResult(
            source_sha256=_sha256(path),
            source_filename=path.name,
            source_path=str(path),
            canonical_text="\f".join(p.text for p in pages),
            pages_text=[p.text for p in pages],
            pages=pages,
            provenance=ProcessingProvenance(
                provider=self.name,
                method=Method.NATIVE,
                do_ocr=False,
                do_table_structure=False,
                config={"engine": "pymupdf"},
            ),
            warnings=list(warnings),
        )

    @staticmethod
    def _page_dims(path: Path) -> dict[int, tuple[float, float]]:
        import fitz

        doc = fitz.open(path)
        try:
            return {
                i + 1: (float(doc.load_page(i).rect.width), float(doc.load_page(i).rect.height))
                for i in range(len(doc))
            }
        finally:
            doc.close()


def _region(page: int, box) -> Optional[BoundingRegion]:
    if box is None:
        return None
    return BoundingRegion(page=page, x0=box.x0, y0=box.y0, x1=box.x1, y1=box.y1)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()