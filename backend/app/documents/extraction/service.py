"""Medflux-Text-Extraktion – Orchestrierung (Schritt 5).

Delegiert an PDF-/DOCX-Extraktoren, integriert den STEP-4-Speicher (nur
kontrollierte interne Pfade über document_id) und baut das strukturierte
Ergebnis. Alle Verarbeitung bleibt vollständig lokal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.documents.extraction.docx import extract_docx_units
from app.documents.extraction.ocr import OCRProvider
from app.documents.extraction.pdf import extract_pdf_units
from app.documents.extraction.schemas import (
    ExtractionUnit,
    FileType,
    TextExtractionResult,
    UnitMethod,
)
from app.documents.storage import DocumentStorage
from app.models.enums import ExtractionStatus

ERR_PDF_CORRUPT = "Die PDF-Datei ist beschädigt oder konnte nicht gelesen werden."
ERR_DOCX_CORRUPT = "Die DOCX-Datei ist beschädigt oder konnte nicht gelesen werden."


class TextExtractionService:
    def __init__(
        self,
        storage: Optional[DocumentStorage] = None,
        ocr: Optional[OCRProvider] = None,
    ) -> None:
        self._storage = storage or DocumentStorage(settings.contracts_dir)
        self._ocr = ocr or OCRProvider(
            tesseract_cmd=settings.tesseract_cmd or None,
            lang=settings.ocr_lang,
            enabled=settings.ocr_enabled,
        )

    def extract(self, document_id: str) -> Optional[TextExtractionResult]:
        resolved = self._storage.resolve_document(document_id)
        if resolved is None:
            return None
        extension, path = resolved
        return self.extract_from_path(document_id, extension, path)

    def extract_from_path(
        self, document_id: str, extension: str, path: Path
    ) -> TextExtractionResult:
        """Extrahiert Text aus einer bereits gespeicherten Originaldatei.

        `extension` ist die normalisierte Endung (`.pdf`/`.docx`), `path` der
        tatsaechliche Dateipfad der Originaldatei. Wird fuer den Produktions-
        Pfad (STEP 14, DB+Bytes) genutzt, damit Extraktion direkt auf der
        persistenten Ablage laeuft – identische Provider wie `extract()`.
        """
        if extension == ".pdf":
            return self._extract_pdf(document_id, path)
        return self._extract_docx(document_id, path)

    def _extract_pdf(self, document_id: str, path: Path) -> TextExtractionResult:
        file_type = FileType.PDF
        try:
            units, requires_ocr_remaining, warnings, page_count = extract_pdf_units(
                path, self._ocr
            )
        except Exception:
            return TextExtractionResult(
                document_id=document_id,
                file_type=file_type,
                extraction_status=ExtractionStatus.FAILED,
                page_count=0,
                total_characters=0,
                error=ERR_PDF_CORRUPT,
            )

        return self._compose(
            document_id=document_id,
            file_type=file_type,
            units=units,
            page_count=page_count,
            requires_ocr_remaining=requires_ocr_remaining,
            extra_warnings=warnings,
        )

    def _extract_docx(self, document_id: str, path: Path) -> TextExtractionResult:
        file_type = FileType.DOCX
        try:
            units = extract_docx_units(path)
        except Exception:
            return TextExtractionResult(
                document_id=document_id,
                file_type=file_type,
                extraction_status=ExtractionStatus.FAILED,
                page_count=0,
                total_characters=0,
                error=ERR_DOCX_CORRUPT,
            )

        return self._compose(
            document_id=document_id,
            file_type=file_type,
            units=units,
            page_count=0,  # DOCX hat keine physischen Seiten
            requires_ocr_remaining=False,
            extra_warnings=[],
        )

    def _compose(
        self,
        document_id: str,
        file_type: FileType,
        units: list[ExtractionUnit],
        page_count: int,
        requires_ocr_remaining: bool,
        extra_warnings: list[str],
    ) -> TextExtractionResult:
        total_characters = sum(len(u.text) for u in units)
        text_available = any(bool(u.text) for u in units)
        used_ocr = any(u.method == UnitMethod.OCR for u in units)
        extraction_method = UnitMethod.OCR if used_ocr else UnitMethod.TEXT

        warnings = list(extra_warnings)
        if requires_ocr_remaining or not text_available:
            status = ExtractionStatus.PARTIAL
            if not text_available and not requires_ocr_remaining:
                warnings.append("Kein Text im Dokument gefunden.")
        else:
            status = ExtractionStatus.SUCCESS

        return TextExtractionResult(
            document_id=document_id,
            file_type=file_type,
            extraction_status=status,
            extraction_method=extraction_method,
            page_count=page_count,
            total_characters=total_characters,
            text_available=text_available,
            requires_ocr=requires_ocr_remaining,
            units=units,
            warnings=warnings,
        )
