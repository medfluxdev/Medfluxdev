"""document_file & document_version – immutablable Quelldatei + erkannte Versionen.

STEP 10A §5/§6/§14/§8:
- `document_file` = eine eingelesene, UNVERAENDERBARE Quelldatei (Original-BLOB
  als relativer `storage_key` im Protected Artifact-Storage + `sha256`).
  `sha256` UNIQUE → SHA-256 ist die Duplikat-Identitaet (Dateinamens-Gleichheit
  ist KEINE Identitaet).
- `document_version` = eine erkannte Version einer Datei (Re-Import mit neuem
  Hash → neue Version; kein In-Place-Overwrite).

WICHTIG (§2A Kompatibilitaet): Bereits von der App erzeugte `document_id`s
bleiben gueltige Werte; es gibt KEINE Konvertierungs-Migration auf UUIDv7.
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
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

IMPORT_STATUS_ALLOWED = {"imported", "rejected", "failed", "duplicate"}


class DocumentFile(OrgOwnedMixin, Base):
    """Eine eingelesene, unveraenderbare Quelldatei (Original-BLOB-Referenz)."""

    __tablename__ = "document_file"

    id: Mapped[uuid.UUID] = uuid_pk()
    external_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    stored_filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_extension: Mapped[str] = mapped_column(String(16), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    import_status: Mapped[str] = mapped_column(String(16), nullable=False)
    duplicate_detected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    duplicate_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_file.id", ondelete="SET NULL"),
        nullable=True,
    )

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document_file",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            f"import_status IN ({', '.join(repr(v) for v in sorted(IMPORT_STATUS_ALLOWED))})",
            name="import_status",
        ),
        UniqueConstraint(
            "organization_id", "sha256", name="uq_document_file_org_sha256"
        ),
        Index("ix_document_file_imported_at", "imported_at"),
    )


class DocumentVersion(OrgOwnedMixin, Base):
    """Eine erkannte Version einer Quelle (Re-Import / neuer Hash)."""

    __tablename__ = "document_version"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_file_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_file.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document_file: Mapped["DocumentFile"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "sha256", name="uq_document_version_org_sha256"
        ),
        Index("ix_document_version_document_file_id", "document_file_id"),
    )
