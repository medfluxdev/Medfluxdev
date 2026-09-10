"""document_processing_result & processing_summary – kanonische Verarbeitungslaeufe.

STEP 10A §6/§9: Je (document_version, Konfig/Provider/OCR) ein eigener Lauf als
eigene Zeile, keine Ueberschreibung. `schema_version` + Provider machen Ergebnisse
reproduzierbar. Das grosse kanonische Payload liegt immutabel im Protected
Artifact-Storage (kein BLANKETT-JSONB); die DB haelt Header/Metadaten.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

PROCESSING_STATUS_ALLOWED = {"running", "succeeded", "failed", "partial"}


class ProcessingRun(OrgOwnedMixin, Base):
    """Document-Intelligence-Verarbeitung (kanonische Struktur) je (Version, Config)."""

    __tablename__ = "document_processing_result"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_version.id", ondelete="CASCADE", name="fk_result_document_version_id_docversion"),
        nullable=False,
    )
    schema_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    provider_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ocr_engine: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ocr_engine_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    do_ocr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    do_table_structure: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    dpi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geometry_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    processing_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    canonical_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_artifact.id", ondelete="SET NULL", name="fk_result_canonical_artifact_id_docartifact"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(repr(v) for v in sorted(PROCESSING_STATUS_ALLOWED))})",
            name="status",
        ),
        Index("ix_document_processing_result_version_id", "document_version_id"),
    )


class ProcessingSummary(OrgOwnedMixin, Base):
    """Kanonische, fortlaufende Verarbeitungs-Uebersicht (Verlauf je Version).

    Design §5: `processing_summary` ist Statistick/Pathfeld eines Laufs; hier als
    flache, fortlaufende Summen-Sicht pro Dokument-Version (eine Zeile je Version,
    UNIQUE) mit Zeiger auf den letzten erfolgreichen Lauf.
    """

    __tablename__ = "processing_summary"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_version.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    file_key: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    doc_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_success_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_processing_result.id", ondelete="SET NULL", name="fk_summary_last_success_run_id_docresult"),
        nullable=True,
    )
