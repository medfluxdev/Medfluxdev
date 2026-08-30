"""Datenmodelle für den Medflux-Dokumentimport (Schritt 4).

Diese Modelle beschreiben importierte Dateien und die strukturierten
Ergebnisse eines Importvorgangs. Es geht hier NUR um Datei-/Speicher-Aspekte,
nicht um Vertragsinhalte (diese folgen in späteren Schritten).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ImportStatus(str, Enum):
    """Status eines einzelnen importierten Dokuments."""

    IMPORTED = "imported"
    REJECTED = "rejected"
    FAILED = "failed"
    DUPLICATE = "duplicate"


class DocumentFile(BaseModel):
    """Metadaten einer lokal gespeicherten Vertragsdatei."""

    document_id: str
    original_filename: str
    stored_filename: str
    file_extension: str
    mime_type: Optional[str] = None
    file_size_bytes: int = Field(ge=0)
    sha256: str
    storage_path: str
    imported_at: datetime
    import_status: ImportStatus = ImportStatus.IMPORTED
    duplicate_detected: bool = False
    duplicate_of_document_id: Optional[str] = None


class ImportFileResult(BaseModel):
    """Ergebnis für ein einzelnes Dokument innerhalb einer Import-Anfrage."""

    document_id: Optional[str] = None
    original_filename: str
    status: ImportStatus
    size: int = Field(ge=0)
    sha256: Optional[str] = None
    duplicate_of_document_id: Optional[str] = None
    message: Optional[str] = None


class ImportBatchResponse(BaseModel):
    """Antwort einer Mehrfachdatei-Import-Anfrage."""

    total: int = Field(ge=0)
    successful: int = Field(ge=0)
    failed: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    documents: list[ImportFileResult]
