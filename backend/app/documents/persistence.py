"""Einheitliche Produktions-Storage-Grenze (STEP 14) – koordiniert DB + Bytes.

Schliesst die Luecke zwischen der STEP-10-Persistenz (DocumentFile/DocumentVersion
Zeilen) und der eigentlichen Byte-Ablage (DocumentStorage). Vor STEP 14 gab es
KEINEN Produktionspfad, der beides koordiniert; die Zeilen wurden nur in Tests
mit erfundenen `storage_key`s belegt.

Autoritative Kette hier:
    Contract -> ContractDocument -> DocumentVersion -> DocumentFile
        -> storage_key (kanonische Server-Referenz)
        -> DocumentStorage -> Original-Bytes

Regeln:
- `storage_key` = `<document_file_id>/original.<ext>` mit document_file_id =
  UUID.hex (32 Hex, valide fuer DocumentStorage). Server-Referenz, relativ,
  von keinem Client-/Browser-Input abgeleitet.
- `DocumentStorage` ist die EINZIGE Komponente, die eine Referenz in einen
  Dateisystem-Pfad uebersetzt (validate_reference/safe_path/write/read/delete).
- Ordnung: DB-DocumentFile-Flush (ID) -> Bytes schreiben -> DocumentVersion.
- Dateisystem + PostgreSQL sind NICHT ACID-atomar. Explizite Kompensation:
  * FS-Fehler nach DB-Flush -> Aufrufer rollt DB zurueck; ggf. Teil anlegen
    verhindert (write ist alles-oder-nichts via write_bytes).
  * DB-Fehler NACH erfolgreichem FS-Write -> delete_reference (Kompensation).
- Idempotenz: sha256 ist die Duplikat-Identitaet (document_file.sha256 UNIQUE).
- `resolve_original_bytes` liest Bytes fuer gesicherte Auslieferung (org-gebunden),
  KEINE Pfade/Referenzen werden dem Aufrufer zurueckgegeben.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import (
    Contract,
    ContractDocument,
    DocumentArtifact,
    DocumentFile,
    DocumentVersion,
    ProcessingRun,
)
from app.documents.intelligence.canonical import DocumentIntelligenceResult
from app.documents.storage import DocumentStorage, StorageError

# Canonical reference builder (einzig legitimer Ort fuer die Referenz-Struktur).
_CANONICAL_PREFIX = "original"


@dataclass
class StoredDocument:
    """Ergebnis eines koordinierten Import-/Persistenz-Aufrufs."""

    document_file_id: str
    document_version_id: str
    storage_key: str
    sha256: str
    file_extension: str
    mime_type: Optional[str]
    original_filename: str
    file_size_bytes: int
    duplicate: bool = False


def canonical_storage_key(document_file_id, extension: str) -> str:
    """Erzeugt die kanonische Server-Referenz aus der DocumentFile-UUID.

    Prueft die Dokument-ID auf einen unbedenklich re-repräsentierbaren Wert
    (hex) und lehnt alles andere ab – es wird NIE ein Pfad aus clientseitigen
    IDs erraten.
    """
    import uuid as _uuid

    try:
        value = _uuid.UUID(str(document_file_id))
    except (ValueError, TypeError):
        raise StorageError("ungueltige DocumentFile-Id")
    ext = extension.lower() if extension.startswith(".") else f".{extension or ''}"
    if ext not in DocumentStorage.allowed_extensions():
        raise StorageError("nicht unterstuetzte Endung")
    return f"{value.hex}/{_CANONICAL_PREFIX}{ext}"


def canonical_artifact_storage_key(document_file_id, processing_run_id) -> str:
    """Builds the protected canonical-artifact reference from server UUIDs."""

    import uuid as _uuid

    try:
        document_file = _uuid.UUID(str(document_file_id))
        processing_run = _uuid.UUID(str(processing_run_id))
    except (ValueError, TypeError):
        raise StorageError("ungueltige Artifact-Id")
    return (
        f"{document_file.hex}/artifacts/{processing_run.hex}/canonical.json"
    )


class DocumentPersistenceService:
    """Einziger Produktions-Schreib-/Lesepfad fuer Dokument-Bytes + DB-Zeilen."""

    def __init__(
        self,
        storage: Optional[DocumentStorage] = None,
        max_size_mb: Optional[int] = None,
    ) -> None:
        self._storage = storage or DocumentStorage(settings.contracts_dir)
        self._max_size_bytes = (max_size_mb or settings.max_upload_size_mb) * 1024 * 1024

    # ------------------------------------------------------------------
    # Schreiben (koordiniert DB + Bytes mit Kompensation)
    # ------------------------------------------------------------------

    def store_original(
        self,
        session: Session,
        *,
        organization_id,
        original_filename: str,
        content_type: str,
        content: bytes,
        version_no: int = 1,
    ) -> StoredDocument:
        extension, error = self._validate(original_filename, content_type, content)
        if error is not None or extension is None:
            raise StorageError(error or "ungueltige Datei")

        sha256 = hashlib.sha256(content).hexdigest()

        # Idempotenz via SHA-256 (document_file.sha256 UNIQUE).
        existing = session.scalars(
            select(DocumentFile).where(
                (DocumentFile.organization_id == organization_id)
                & (DocumentFile.sha256 == sha256)
            )
        ).first()
        if existing is not None:
            ref = canonical_storage_key(existing.id, existing.file_extension)
            if existing.storage_key != ref:
                raise StorageError("Ungueltige Dokumentreferenz")
            ver = self._version_for_file(session, existing, version_no)
            if ver is not None and ver.storage_key != ref:
                raise StorageError("Ungueltige Dokumentreferenz")
            # Duplicate detection must not mask a lost original. The caller has
            # supplied bytes whose SHA-256 matches this row, so restore the
            # canonical object only after every stored reference was validated.
            if not self._storage.exists_reference(ref):
                self._storage.write_reference(ref, content)
            return StoredDocument(
                document_file_id=str(existing.id),
                document_version_id=str(ver.id) if ver else "",
                storage_key=ref,
                sha256=sha256,
                file_extension=extension,
                mime_type=existing.mime_type,
                original_filename=existing.original_filename,
                file_size_bytes=len(content),
                duplicate=True,
            )

        # (1) DB-Zeile (DocumentFile) anlegen + flush -> UUID fuer Referenz.
        stored_filename = f"original{extension}"
        doc = DocumentFile(
            organization_id=organization_id,
            original_filename=self._storage.sanitize_original_filename(original_filename),
            stored_filename=stored_filename,
            file_extension=extension,
            mime_type=content_type or None,
            file_size_bytes=len(content),
            sha256=sha256,
            storage_key="",  # wird nach Flush gesetzt (Server-Referenz)
            import_status="imported",
            duplicate_detected=False,
        )
        session.add(doc)
        session.flush()  # UUID vergeben

        ref = canonical_storage_key(doc.id, extension)

        try:
            # (2) Bytes ueber die kanoische Referenz schreiben (AFTER DB-Flush).
            self._storage.write_reference(ref, content)
        except StorageError:
            # FS-Fehler: DB-Zeile wird vom Aufrufer zurueckgerollt.
            raise

        doc.storage_key = ref
        try:
            session.flush()
        except Exception:
            # DB-Fehler NACH FS-Write -> Kompensation (Datei entfernen).
            self._storage.delete_reference(ref)
            raise

        # (3) DocumentVersion (gleiche Referenz + sha).
        try:
            ver = self._create_version(session, organization_id, doc, version_no, sha256, ref)
        except Exception:
            self._storage.delete_reference(ref)
            raise

        session.flush()
        return StoredDocument(
            document_file_id=str(doc.id),
            document_version_id=str(ver.id),
            storage_key=ref,
            sha256=sha256,
            file_extension=extension,
            mime_type=content_type or None,
            original_filename=doc.original_filename,
            file_size_bytes=len(content),
            duplicate=False,
        )

    def link_to_contract(
        self,
        session: Session,
        *,
        contract_id,
        document_version_id,
        role: Optional[str] = None,
    ):
        from app.database.services import link_document

        return link_document(
            session, contract_id=contract_id, document_version_id=document_version_id, role=role
        )

    def store_canonical_artifact(
        self,
        session: Session,
        *,
        organization_id,
        document_version_id,
        processing_run_id,
        content: bytes,
        format_version: str,
    ):
        """Coordinates protected canonical bytes and immutable artifact metadata."""

        from app.database.services import save_artifact

        version = session.scalars(
            select(DocumentVersion).where(
                (DocumentVersion.id == document_version_id)
                & (DocumentVersion.organization_id == organization_id)
            )
        ).first()
        if version is None:
            raise StorageError("Dokument nicht gefunden")
        reference = canonical_artifact_storage_key(
            version.document_file_id, processing_run_id
        )
        digest = hashlib.sha256(content).hexdigest()
        self._storage.write_reference(reference, content)
        try:
            artifact = save_artifact(
                session,
                organization_id=organization_id,
                document_version_id=document_version_id,
                artifact_type="canonical",
                storage_key=reference,
                sha256=digest,
                size_bytes=len(content),
                format_version=format_version,
                media_type="application/json",
                processing_run_id=processing_run_id,
            )
            session.flush()
            return artifact
        except Exception:
            self._storage.delete_reference(reference)
            raise

    # ------------------------------------------------------------------
    # Lesen (org-gebundene, sichere Byte-Auslieferung)
    # ------------------------------------------------------------------

    def resolve_bytes_for_version(
        self,
        session: Session,
        *,
        organization_id,
        document_version_id,
        contract_id=None,
    ) -> bytes:
        """Liest Original-Bytes einer DocumentVersion org-gebunden.

        Ohne `contract_id`: nur org + Version-Praesenz. Mit `contract_id`: zusaetzlich
        verifizieren, dass die Version an genau diesen (org-gebundenen) Vertrag
        geknuepft ist. Liefert generisch Not-Found (StorageError) bei jeder
        Nicht-Verfuegbarkeit / Nicht-Bindung.
        """
        ver = session.scalars(
            select(DocumentVersion).where(
                (DocumentVersion.id == document_version_id)
                & (DocumentVersion.organization_id == organization_id)
            )
        ).first()
        if ver is None:
            raise StorageError("Dokument nicht gefunden")
        if contract_id is not None:
            linked = session.scalars(
                select(ContractDocument).where(
                    (ContractDocument.organization_id == organization_id)
                    & (ContractDocument.contract_id == contract_id)
                    & (ContractDocument.document_version_id == ver.id)
                )
            ).first()
            contract = session.scalars(
                select(Contract).where(
                    (Contract.id == contract_id)
                    & (Contract.organization_id == organization_id)
                )
            ).first()
            if linked is None or contract is None:
                raise StorageError("Dokument nicht gefunden")
        if not self._storage.exists_reference(ver.storage_key):
            raise StorageError("Dokument nicht gefunden")
        return self._storage.read_reference(ver.storage_key)

    def resolve_canonical_for_version(
        self,
        session: Session,
        *,
        organization_id,
        document_version_id,
    ) -> Optional[DocumentIntelligenceResult]:
        """Liest das kanonische Analyse-Artefakt einer Version, org-gebunden.

        Returns None (statt Fehler) fuer "kein Artefakt vorhanden" – Aufrufer
        entscheidet ueber Fallback. Nicht-Verfuegbare Speicher-Referenzen
        werden generisch behandelt (keine Pfad-/Referenz-Leaks).
        """
        version = session.scalars(
            select(DocumentVersion).where(
                (DocumentVersion.id == document_version_id)
                & (DocumentVersion.organization_id == organization_id)
            )
        ).first()
        if version is None or version.document_file_id is None:
            return None
        artifacts = session.scalars(
            select(DocumentArtifact)
            .join(
                ProcessingRun,
                DocumentArtifact.processing_run_id == ProcessingRun.id,
            )
            .where(
                (DocumentArtifact.organization_id == organization_id)
                & (DocumentArtifact.document_version_id == version.id)
                & (DocumentArtifact.artifact_type == "canonical")
                & (DocumentArtifact.lifecycle_state == "active")
            )
            .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
        ).all()
        for artifact in artifacts:
            if not artifact.storage_key:
                continue
            try:
                raw = self._storage.read_reference(artifact.storage_key)
                import hashlib as _hashlib

                if artifact.sha256 and _hashlib.sha256(raw).hexdigest() != artifact.sha256:
                    continue
                canonical = DocumentIntelligenceResult.model_validate_json(raw)
            except Exception:
                continue
            if canonical.source_sha256 != version.sha256:
                continue
            return canonical
        return None

    # ------------------------------------------------------------------
    # Intern
    # ------------------------------------------------------------------

    def _validate(self, filename, content_type, content):
        if not content:
            return None, "Datei ist leer"
        if len(content) > self._max_size_bytes:
            return None, "Datei ist zu groß"
        extension = self._storage.normalize_extension(filename)
        if extension is None:
            return None, "Dateityp nicht unterstützt"
        expected = self._storage.expected_mime(extension)
        generic = {"", "application/octet-stream"}
        if content_type not in generic and expected and content_type not in expected:
            return None, "Dateityp nicht unterstützt"
        return extension, None

    @staticmethod
    def _version_for_file(session, doc: DocumentFile, version_no: int):
        return session.scalars(
            select(DocumentVersion)
            .where(
                (DocumentVersion.document_file_id == doc.id)
                & (DocumentVersion.version_no == version_no)
            )
        ).first()

    def _create_version(
        self, session, organization_id, doc: DocumentFile, version_no, sha256, ref
    ):
        ver = DocumentVersion(
            organization_id=organization_id,
            document_file_id=doc.id,
            version_no=version_no,
            sha256=sha256,
            storage_key=ref,
        )
        session.add(ver)
        session.flush()
        return ver
