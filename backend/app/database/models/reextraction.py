"""Erneute Erfassung aus dem Vertragsdokument (Plan ERNEUT_ERFASSEN_PLAN_20261011).

Ein Lauf erzeugt nur eine *Kandidaten*-Extraktion. Die Vertragswahrheit
(`contract.accepted_extraction_id`) aendert sich erst, wenn eine Person im
Vergleich ausgewaehlte Angaben uebernimmt; bis dahin bleibt alles unveraendert.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

REEXTRACTION_STATUS_ALLOWED = ("queued", "running", "ready", "failed", "applied", "discarded", "cancelled")
REEXTRACTION_ACTIVE = ("queued", "running")
REEXTRACTION_MODE_ALLOWED = ("full", "missing_fields")


class ContractReextraction(OrgOwnedMixin, Base):
    __tablename__ = "contract_reextraction"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_version.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    page_hint: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    reread_document: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    provider_id: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    model_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Stand der Vertragswahrheit beim Start: Uebernahme nur, wenn er noch gilt.
    base_extraction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract_extraction.id", ondelete="SET NULL", name="fk_contract_reextraction_base_extraction"),
        nullable=True,
    )
    candidate_extraction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract_extraction.id", ondelete="SET NULL", name="fk_contract_reextraction_candidate_extraction"),
        nullable=True,
    )
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    applied_keys: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    requested_by_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    requested_by_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'ready', 'failed', 'applied', 'discarded', 'cancelled')",
            name="status_allowed",
        ),
        CheckConstraint("mode IN ('full', 'missing_fields')", name="mode_allowed"),
        Index("ix_contract_reextraction_contract", "organization_id", "contract_id", "created_at"),
        Index("ix_contract_reextraction_status", "status"),
        # Hoechstens ein wartender/laufender Lauf je Vertrag.
        Index(
            "uq_contract_reextraction_active",
            "contract_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )
