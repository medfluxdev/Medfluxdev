"""Erneute Erfassung aus dem Vertragsdokument (Plan ERNEUT_ERFASSEN_PLAN_20261011).

Ein Lauf ("Analyse #N") erzeugt nur eine *Kandidaten*-Extraktion und daraus
Vorschlaege (`ContractReextractionProposal`). Die Vertragswahrheit
(`contract.accepted_extraction_id`) aendert sich erst, wenn eine Person einen
Vorschlag uebernimmt; bis dahin bleibt alles unveraendert. Jeder Vorschlag haelt
den alten Wert samt Nachweisen fest, damit sich ein Stand zuruecknehmen laesst.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

REEXTRACTION_STATUS_ALLOWED = ("queued", "running", "ready", "failed", "applied", "discarded", "cancelled")
REEXTRACTION_ACTIVE = ("queued", "running")
# supplement = nur leere/nicht gefundene Angaben, sections = gewaehlte Bereiche, full = alles,
# rollback = Eintrag fuer "Auf diesen Stand zurueck" (kein Modelllauf).
REEXTRACTION_MODE_ALLOWED = ("supplement", "sections", "full", "rollback")
PROPOSAL_KIND_ALLOWED = ("new", "deviating", "missing", "unchanged")
PROPOSAL_DECISION_ALLOWED = ("pending", "accepted", "kept_old", "manual", "rejected", "rolled_back")


class ContractReextraction(OrgOwnedMixin, Base):
    __tablename__ = "contract_reextraction"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_version.id", ondelete="CASCADE"), nullable=False
    )
    # Laufende Nummer je Vertrag (#1 = Erstanalyse beim Import, ohne eigene Zeile).
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    sections: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    hint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    protect_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    reset_confirmations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # Fortschritt waehrend des Laufs: {"step", "steps", "label", "found"}.
    progress: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
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
        CheckConstraint("mode IN ('supplement', 'sections', 'full', 'rollback')", name="mode_allowed"),
        UniqueConstraint("contract_id", "number", name="uq_contract_reextraction_number"),
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


class ContractReextractionProposal(OrgOwnedMixin, Base):
    """Ein Vorschlag einer Analyse fuer eine Angabe: alt gegen neu, mit Entscheidung."""

    __tablename__ = "contract_reextraction_proposal"

    id: Mapped[uuid.UUID] = uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract_reextraction.id", ondelete="CASCADE"), nullable=False
    )
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    # Von Hand gepflegt und geschuetzt: kein Vorschlag, gilt als unveraendert.
    protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    old_display: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_display: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Schnappschuss des Fakts (JSON) und seiner Nachweise vor bzw. aus der Analyse.
    old_value: Mapped[Optional[dict | list | str | int | float | bool]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[dict | list | str | int | float | bool]] = mapped_column(JSONB, nullable=True)
    old_evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    new_evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    decision: Mapped[str] = mapped_column(String(12), nullable=False, default="pending", server_default="pending")
    decided_by_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    decided_by_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("kind IN ('new', 'deviating', 'missing', 'unchanged')", name="kind_allowed"),
        CheckConstraint(
            "decision IN ('pending', 'accepted', 'kept_old', 'manual', 'rejected', 'rolled_back')",
            name="decision_allowed",
        ),
        UniqueConstraint("run_id", "field_key", name="uq_contract_reextraction_proposal_run_field"),
        Index("ix_contract_reextraction_proposal_run", "organization_id", "run_id"),
    )
