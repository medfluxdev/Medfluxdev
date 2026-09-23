"""Lokale Speicherung importierter Dokumente für Medflux (Schritt 4).

Verantwortlich für:
- feste, vorhersagbare Ablagestruktur data/contracts/<document_id>/original.<ext>
- sichere Pfadbehandlung (original_filename wird NIE als Pfad verwendet)
- JSON-basierten Manifest-Index für Duplikat-Erkennung über SHA-256
- sauberes Aufräumen fehlgeschlagener/imkompletter Dateien

Der physikalische Dateiname wird ausschließlich von Medflux bestimmt.
Der ursprüngliche Dateiname dient nur als Metadatum.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx"}

_EXPECTED_MIME: dict[str, list[str]] = {
    ".pdf": ["application/pdf"],
    ".docx": [
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    ],
}

_INDEX_FILENAME = ".index.json"


class StorageError(Exception):
    """Fehler beim Speichern eines Dokuments."""


class DocumentStorage:
    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def allowed_extensions() -> set[str]:
        return set(_ALLOWED_EXTENSIONS)

    @staticmethod
    def expected_mime(extension: str) -> list[str]:
        return _EXPECTED_MIME.get(extension, [])

    @staticmethod
    def normalize_extension(filename: str) -> Optional[str]:
        """Liefert die normalisierte Endung (.pdf/.docx) oder None.

        Unbekannte Endungen, ungültige Zeichen und Path-Traversal werden
        abgelehnt. Der Dateiname wird nicht als Pfad verwendet.
        """
        name = filename.replace("\\", "/").split("/")[-1]
        if not name:
            return None
        suffix = Path(name).suffix.lower()
        if suffix not in _ALLOWED_EXTENSIONS:
            return None
        return suffix

    @staticmethod
    def sanitize_original_filename(filename: str) -> str:
        """Bereinigt den Originaldateinamen für die Anzeige (Metadatum)."""
        name = filename.replace("\\", "/").split("/")[-1]
        return name.replace("\x00", "").strip() or "unbenannt"

    def _new_document_id(self) -> str:
        return uuid.uuid4().hex

    def _index_path(self) -> Path:
        return self._base_dir / _INDEX_FILENAME

    def _load_index(self) -> dict[str, dict[str, Any]]:
        path = self._index_path()
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return {}

    def _save_index(self, index: dict[str, dict[str, Any]]) -> None:
        tmp = self._index_path().with_suffix(".json.tmp")
        tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._index_path())

    def find_by_sha256(self, sha256: str) -> Optional[dict[str, Any]]:
        return self._load_index().get(sha256)

    @staticmethod
    def is_valid_document_id(document_id: str) -> bool:
        """Nur kontrollierte, sichere IDs (Hex-Zeichen) sind erlaubt.

        Verhindert Path-Traversal über die document_id.
        """
        return bool(document_id) and all(c in "0123456789abcdef" for c in document_id)

    def find_by_document_id(self, document_id: str) -> Optional[dict[str, Any]]:
        if not self.is_valid_document_id(document_id):
            return None
        for rec in self._load_index().values():
            if rec.get("document_id") == document_id:
                return rec
        return None

    def resolve_document(self, document_id: str) -> Optional[tuple[str, Path]]:
        """Löst eine document_id zu (Endung, Dateipfad) der Originaldatei auf.

        Liefert None, wenn das Dokument nicht existiert oder die ID unsicher ist.
        Es werden ausschließlich kontrollierte Speicherpfade verwendet –
        niemals Nutzereingaben als Pfad.
        """
        if not self.is_valid_document_id(document_id):
            return None
        document_dir = self._base_dir / document_id
        if not document_dir.is_dir():
            return None
        for ext in sorted(_ALLOWED_EXTENSIONS):
            candidate = document_dir / f"original{ext}"
            if candidate.is_file():
                return ext, candidate
        return None

    # ------------------------------------------------------------------
    # Kanonische Storage-Referenz (STEP 14)
    #
    # `storage_key` (Server-Referenz) ist IMMER ein relativer, kontrollierter
    # Original- oder Artifact-Schluessel. Der Browser/API erfaehrt ihn NIE. Nur
    # `DocumentStorage` uebersetzt eine kanonische Referenz in einen Pfad.
    # ------------------------------------------------------------------

    _ORIGINAL_REF_RE = re.compile(r"^[0-9a-f]{32}/original\.(pdf|docx)$")
    _ARTIFACT_REF_RE = re.compile(
        r"^[0-9a-f]{32}/artifacts/[0-9a-f]{32}/canonical\.json$"
    )

    @staticmethod
    def validate_reference(reference: str) -> None:
        """Prueft eine kanonische Storage-Referenz strikt.

        Regeln: nur relativ, eine der explizit erlaubten Medflux-Strukturen,
        kein '..', kein absoluter Pfad, kein Laufwerks-/UNC-Escape.
        """
        if not isinstance(reference, str) or not reference:
            raise StorageError("ungueltige Storage-Referenz")
        if reference.startswith(("/", "\\")):
            raise StorageError("absoluter Pfad nicht erlaubt")
        if re.search(r"[:]", reference):
            raise StorageError("Laufwerks-/scheme-Anteil nicht erlaubt")
        parts = reference.replace("\\", "/").split("/")
        if ".." in parts or "." in parts:
            raise StorageError("Pfad-Traversal nicht erlaubt")
        if any(not p for p in parts):
            raise StorageError("leere Pfadteile nicht erlaubt")
        if not (
            DocumentStorage._ORIGINAL_REF_RE.fullmatch(reference)
            or DocumentStorage._ARTIFACT_REF_RE.fullmatch(reference)
        ):
            raise StorageError("unerwartete Storage-Referenz-Struktur")

    def legacy_records(
        self,
        *,
        document_ids: Optional[list[str]] = None,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Lists legacy-manifest records for explicit reconciliation only.

        This read-only method does not rewrite the manifest or original files.
        Callers must still resolve each opaque document_id through
        ``resolve_document``; the historical ``storage_path`` value is never a
        trusted input to the production orchestrator.
        """

        requested = set(document_ids or [])
        if any(not self.is_valid_document_id(value) for value in requested):
            raise StorageError("ungueltige Legacy-Dokument-ID")
        records = [
            dict(record)
            for record in self._load_index().values()
            if not requested or record.get("document_id") in requested
        ]
        records.sort(key=lambda record: str(record.get("imported_at") or ""))
        if limit is not None:
            if limit < 1:
                raise StorageError("limit muss positiv sein")
            records = records[:limit]
        return records

    def safe_path(self, reference: str) -> Path:
        """Uebersetzt eine KANONISCHE REFERENZ in einen Pfad unter dem Root.

        Einziger Uebersetzungspunkt Referenz -> Dateisystempfad. Validierung + 
        Containment-Check; bei Verletzung wirft es StorageError (nie selbst-gebauter
        Pfad aus Client-Input ohne Validierung).
        """
        DocumentStorage.validate_reference(reference)
        # containment via resolve(): Ziel muss innerhalb des Roots bleiben.
        root = self._base_dir.resolve()
        target = (root / reference.replace("\\", "/")).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            raise StorageError("Referenz verlaesst den Storage-Root")
        return target

    def write_reference(self, reference: str, content: bytes) -> None:
        """Schreibt Bytes ueber eine kanonische Referenz (Compatibility-Check)."""
        target = self.safe_path(reference)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.write_bytes(content)
        except OSError:
            raise StorageError("Datei konnte nicht geschrieben werden")

    def exists_reference(self, reference: str) -> bool:
        try:
            return self.safe_path(reference).is_file()
        except StorageError:
            return False

    def read_reference(self, reference: str) -> bytes:
        target = self.safe_path(reference)
        if not target.is_file():
            raise StorageError("Datei nicht gefunden")
        try:
            return target.read_bytes()
        except OSError:
            raise StorageError("Datei konnte nicht gelesen werden")

    def delete_reference(self, reference: str) -> None:
        """Entfernt eine referenzierte Datei (Kompensation nach DB-Fehler)."""
        try:
            target = self.safe_path(reference)
        except StorageError:
            return
        if target.is_file():
            try:
                target.unlink()
            except OSError:
                pass
            try:
                target.parent.rmdir()
            except OSError:
                pass

    def save(
        self,
        original_filename: str,
        file_extension: str,
        mime_type: str,
        content: bytes,
        sha256: str,
    ) -> dict[str, Any]:
        """Speichert ein Dokument und trägt es in den Manifest-Index ein.

        Wirft StorageError, wenn das Schreiben auf die Festplatte fehlschlägt.
        Bei Fehlern wird die unvollständige Ablage wieder entfernt.
        """
        document_id = self._new_document_id()
        stored_filename = f"original{file_extension}"
        document_dir = self._base_dir / document_id
        document_dir.mkdir(parents=True, exist_ok=False)

        target = document_dir / stored_filename
        try:
            target.write_bytes(content)
        except OSError:
            shutil.rmtree(document_dir, ignore_errors=True)
            raise StorageError("Datei konnte nicht geschrieben werden")

        record = {
            "document_id": document_id,
            "original_filename": self.sanitize_original_filename(original_filename),
            "stored_filename": stored_filename,
            "file_extension": file_extension,
            "mime_type": mime_type,
            "file_size_bytes": len(content),
            "sha256": sha256,
            "storage_path": str(target),
            "imported_at": datetime.now(timezone.utc).isoformat(),
            "import_status": "imported",
        }

        index = self._load_index()
        index[sha256] = record
        try:
            self._save_index(index)
        except OSError:
            shutil.rmtree(document_dir, ignore_errors=True)
            raise StorageError("Metadaten konnten nicht gespeichert werden")

        return record

    def remove(self, document_id: str) -> None:
        """Entfernt eine Ablage und zugehörige Indexeinträge (Aufräumen)."""
        document_dir = self._base_dir / document_id
        index = self._load_index()
        index = {sha: rec for sha, rec in index.items() if rec.get("document_id") != document_id}
        self._save_index(index)
        shutil.rmtree(document_dir, ignore_errors=True)
