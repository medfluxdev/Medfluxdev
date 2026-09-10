"""contract_extraction & extraction_evidence – KI-Extraktionslauf + relationale Belege.

STEP 10A §6/§9/§10 „Evidence-Ownership":
- `contract_extraction.contract_snapshot` (JSONB) = IMMUTABLER ExtractionSnapshot
  (Lauf-Wahrheit). Gross/voluminoes → `contract_snapshot_artifact_id` →
  `document_artifact` (Protected Storage). KEIN BLANKETT-JSONB.
- `extraction_evidence` = relationale, abfragbare Quell-Navigations-Projektion.
  Atomar im selben Lauf geschrieben + `field_ref`-Bindung (Integritaets-Schnelltest).

Quell-Navigation (STEP 8B, darf nicht brechen): Contract.Feld → extraction_evidence
→ contract_extraction → document_version → canonical/atomic source → Seite →
Geometrie → Original-PDF. Geometrie NIE erfinden; `bounding_box`/Geometrie nur
uebernehmen, wenn sie die Quelle liefert (§10).

OCR-Konfidenz (`ocr_confidence`) bleibt STRENG getrennt von semantischer
`confidence` (Konvention aus app/documents/intelligence/evidence.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

EXTRACTION_STATUS_ALLOWED = {"success", "partial", "failed"}
VALIDATION_STATUS_ALLOWED = {"valid", "invalid", "unknown"}
SOURCE_TYPE_ALLOWED = {"page", "paragraph", "table"}
EXTRACTION_METHOD_ALLOWED = {"ai", "manual", "programmatic"}


class ContractExtraction(OrgOwnedMixin, Base):
    """Ein vollstaendiger strukturierter KI-Extraktions-Lauf + immutabler Snapshot."""

    __tablename__ = "contract_extraction"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_version.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    validation_status: Mapped[str] = mapped_column(
        String(16), default="unknown", nullable=False
    )
    requires_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processing_duration: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    timeout_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    truncated_chunks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_call_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    groups_processed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    evidence_issues: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    verifier_issues: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    normalization_issues: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Immutabler Contract-Snapshot: klein → JSONB; gross → Artifact-Referenz.
    contract_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    contract_snapshot_artifact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_artifact.id", ondelete="SET NULL", name="fk_extraction_snapshot_artifact_id_docartifact"),
        nullable=True,
    )
    snapshot_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    evidence_rows: Mapped[list["ExtractionEvidence"]] = relationship(
        back_populates="extraction",
        cascade="all, delete-orphan",
        order_by="ExtractionEvidence.field_ref",
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(repr(v) for v in sorted(EXTRACTION_STATUS_ALLOWED))})",
            name="status",
        ),
        CheckConstraint(
            f"validation_status IN ({', '.join(repr(v) for v in sorted(VALIDATION_STATUS_ALLOWED))})",
            name="validation_status",
        ),
        Index("ix_contract_extraction_version_id", "document_version_id"),
    )


class ExtractionEvidence(OrgOwnedMixin, Base):
    """Relationaler, abfragbarer Beleg fuer ein extrahiertes Feld (Quell-Navigation)."""

    __tablename__ = "extraction_evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract_extraction.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # DOCX has no authoritative physical pages.  Such evidence is addressed by
    # paragraph_index/table_index and deliberately persists page=NULL.
    page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    table_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bounding_box: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    requires_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    extraction_method: Mapped[str] = mapped_column(
        String(16), default="ai", nullable=False
    )

    extraction: Mapped["ContractExtraction"] = relationship(back_populates="evidence_rows")

    __table_args__ = (
        CheckConstraint(
            f"source_type IN ({', '.join(repr(v) for v in sorted(SOURCE_TYPE_ALLOWED))})",
            name="source_type",
        ),
        CheckConstraint(
            f"extraction_method IN ({', '.join(repr(v) for v in sorted(EXTRACTION_METHOD_ALLOWED))})",
            name="method",
        ),
        CheckConstraint("page IS NULL OR page > 0", name="page_positive"),
        CheckConstraint(
            "page IS NOT NULL OR paragraph_index IS NOT NULL OR table_index IS NOT NULL",
            name="source_address_present",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
        CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 1)",
            name="ocr_confidence_range",
        ),
        UniqueConstraint(
            "extraction_id", "field_ref", "paragraph_index", "table_index",
            name="uq_extraction_evidence_source",
        ),
        Index("ix_extraction_evidence_extraction_id", "extraction_id"),
        Index("ix_extraction_evidence_page", "page"),
        Index("ix_extraction_evidence_field_ref", "field_ref"),
    )
