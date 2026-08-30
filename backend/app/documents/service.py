"""Import-Service für Medflux-Dokumente (Schritt 4).

Enthält die eigentliche Importlogik: Validierung (Endung, MIME, Größe,
Leere Datei), SHA-256-Berechnung, Duplikat-Erkennung und Speicherung.

Die API-Route bleibt dünn und delegiert hierher.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from app.core.config import settings
from app.documents.schemas import ImportBatchResponse, ImportFileResult, ImportStatus
from app.documents.storage import DocumentStorage, StorageError

MSG_SUCCESS = "Dokument erfolgreich importiert"
MSG_UNSUPPORTED_TYPE = "Dateityp nicht unterstützt"
MSG_TOO_LARGE = "Datei ist zu groß"
MSG_DUPLICATE = "Duplikat erkannt"
MSG_IMPORT_FAILED = "Import fehlgeschlagen"
MSG_EMPTY = "Datei ist leer"

# MIME-Typen, die eine zuverlässige Zuordnung zur Endung ermöglichen.
_MATCHABLE_MIME = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument"
    ".wordprocessingml.document": ".docx",
}

# Generische/fehlende Content-Typen werden nicht für die Prüfung herangezogen.
_GENERIC_TYPES = {"", "application/octet-stream"}


class DocumentImportService:
    def __init__(
        self,
        storage: Optional[DocumentStorage] = None,
        max_size_mb: Optional[int] = None,
    ) -> None:
        self._storage = storage or DocumentStorage(settings.contracts_dir)
        self._max_size_bytes = (max_size_mb or settings.max_upload_size_mb) * 1024 * 1024

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _validate(
        self, filename: str, content_type: str, content: bytes
    ) -> tuple[Optional[str], Optional[str]]:
        """Gibt (endung_oder_None, fehlermeldung_oder_None) zurück."""
        extension = self._storage.normalize_extension(filename)
        if extension is None:
            return None, MSG_UNSUPPORTED_TYPE

        if not content:
            return None, MSG_EMPTY

        if len(content) > self._max_size_bytes:
            return None, MSG_TOO_LARGE

        if content_type not in _GENERIC_TYPES:
            expected = self._storage.expected_mime(extension)
            if expected and content_type not in expected:
                return None, MSG_UNSUPPORTED_TYPE

        return extension, None

    def import_file(
        self, filename: str, content_type: str, content: bytes
    ) -> ImportFileResult:
        extension, error = self._validate(filename, content_type, content)
        if error is not None or extension is None:
            return ImportFileResult(
                original_filename=filename,
                status=ImportStatus.REJECTED,
                size=len(content),
                message=error or MSG_UNSUPPORTED_TYPE,
            )

        sha256 = self.compute_sha256(content)

        existing = self._storage.find_by_sha256(sha256)
        if existing is not None:
            return ImportFileResult(
                original_filename=filename,
                status=ImportStatus.DUPLICATE,
                size=len(content),
                sha256=sha256,
                duplicate_of_document_id=existing["document_id"],
                message=MSG_DUPLICATE,
            )

        try:
            record = self._storage.save(
                original_filename=filename,
                file_extension=extension,
                mime_type=content_type or None,
                content=content,
                sha256=sha256,
            )
        except StorageError:
            return ImportFileResult(
                original_filename=filename,
                status=ImportStatus.FAILED,
                size=len(content),
                sha256=sha256,
                message=MSG_IMPORT_FAILED,
            )

        return ImportFileResult(
            document_id=record["document_id"],
            original_filename=record["original_filename"],
            status=ImportStatus.IMPORTED,
            size=record["file_size_bytes"],
            sha256=record["sha256"],
            message=MSG_SUCCESS,
        )

    def import_many(self, files: list[tuple[str, str, bytes]]) -> ImportBatchResponse:
        """Importiert mehrere Dateien unabhängig voneinander als Batch."""
        results: list[ImportFileResult] = []
        for filename, content_type, content in files:
            results.append(self.import_file(filename, content_type, content))

        successful = sum(1 for r in results if r.status == ImportStatus.IMPORTED)
        failed = sum(1 for r in results if r.status != ImportStatus.IMPORTED)
        duplicates = sum(1 for r in results if r.status == ImportStatus.DUPLICATE)

        return ImportBatchResponse(
            total=len(results),
            successful=successful,
            failed=failed,
            duplicates=duplicates,
            documents=results,
        )
