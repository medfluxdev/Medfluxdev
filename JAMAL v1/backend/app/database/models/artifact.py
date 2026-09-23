"""document_artifact – immutables, externes Artefakt im Protected Artifact-Storage.

STEP 10A §6/§7B/§13: Original-PDFs, grosse kanonische Payloads, OCR-/Layout-
Diagnosen, Rendered/Debug und grosse Snapshots liegen im Protected
Artifact-Storage; die DB haelt nur Metadaten + `storage_key` (RELATIV, nie
maschinenabhaengiger absoluter Pfad) + `sha256`.

Loesch-Lebenszyklus (§13): `lifecycle_state` (active|orphan|pending_deletion|
deleted) + `deletion_owner` sind die einzige Loesch-Freigabe-Quelle.
Eine referenzierte Datei wird NIE ohne Klaerung der DB-Zeile geloescht.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

ARTIFACT_TYPE_ALLOWED = {
    "canonical",
    "ocr_diagnostics",
    "layout_diagnostics",
    "rendered",
    "preview",
    "debug",
    "original_file",
    "contract_snapshot",
    "other",
}

LIFECYCLE_STATE_ALLOWED = {
    "active",
    "orphan",
    "pending_deletion",
    "deleted",
}


class DocumentArtifact(OrgOwnedMixin, Base):
    """Metadaten-Referenz auf einen im Artifact-Storage liegenden Payload."""

    __tablename__ = "document_artifact"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    processing_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_processing_result.id", ondelete="SET NULL", name="fk_artifact_processing_run_id_result"),
        nullable=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    format_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    media_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(
        String(24), default="active", nullable=False
    )
    deletion_owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            f"artifact_type IN ({', '.join(repr(v) for v in sorted(ARTIFACT_TYPE_ALLOWED))})",
            name="type",
        ),
        CheckConstraint(
            f"lifecycle_state IN ({', '.join(repr(v) for v in sorted(LIFECYCLE_STATE_ALLOWED))})",
            name="lifecycle_state",
        ),
        Index("ix_document_artifact_version_id", "document_version_id"),
        Index("ix_document_artifact_type", "artifact_type"),
    )
