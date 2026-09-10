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
    """Status eines einzelnen importierten Dokuments (Import + Verarbeitung)."""

    IMPORTED = "imported"          # Ablage + Vertrag erstellt (Analyse evtl. partial)
    REJECTED = "rejected"          # Organisation/Datei abgelehnt
    FAILED = "failed"              # Verarbeitung fehlgeschlagen
    DUPLICATE = "duplicate"        # bereits vorhandene Bytes
    ANALYSIS_FAILED = "analysis_failed"  # importiert, aber keine Analyse moeglich


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
    document_version_id: Optional[str] = None
    original_filename: str
    status: ImportStatus
    size: int = Field(ge=0)
    sha256: Optional[str] = None
    duplicate_of_document_id: Optional[str] = None
    # Verarbeitungs-/Vertrags-Ergebnis (nach der end-to-end-Pipeline)
    analysis_status: Optional[str] = None  # success | partial | failed | None
    requires_review: bool = False
    contract_id: Optional[str] = None
    message: Optional[str] = None


class ImportBatchResponse(BaseModel):
    """Antwort einer Mehrfachdatei-Import-Anfrage."""

    total: int = Field(ge=0)
    successful: int = Field(ge=0)
    failed: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    documents: list[ImportFileResult]
