"""Enterprise contract-intelligence persistence.

These tables add contract-family graph edges, obligations, policy decisions,
outbox events and auditable action proposals. They keep evidence/provenance as
stable references instead of duplicating raw contract text.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

RELATION_ALLOWED = {"amends","supersedes","references","renews","governs","covers","ordered_by","corroborates","conflicts_with"}
AUTHORITY_ALLOWED = {"primary","secondary","unknown"}
OBLIGATION_STATUS_ALLOWED = {"proposed","active","satisfied","breached","waived","unknown"}
POLICY_OUTCOME_ALLOWED = {"pass","warn","fail","unknown"}
ACTION_STATUS_ALLOWED = {"proposed","approved","rejected","executed","cancelled"}


class ContractRelationRecord(OrgOwnedMixin, Base):
    __tablename__ = "contract_relation"
    id: Mapped[uuid.UUID] = uuid_pk()
    source_contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=True)
    target_contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=True)
    source_document_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_version.id", ondelete="SET NULL"), nullable=True)
    target_document_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_version.id", ondelete="SET NULL"), nullable=True)
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    authority: Mapped[str] = mapped_column(String(16), default="unknown", nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    evidence_refs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (
        CheckConstraint(f"relation_type IN ({', '.join(repr(v) for v in sorted(RELATION_ALLOWED))})", name="relation_type"),
        CheckConstraint(f"authority IN ({', '.join(repr(v) for v in sorted(AUTHORITY_ALLOWED))})", name="authority"),
        Index("ix_contract_relation_source", "source_contract_id"),
        Index("ix_contract_relation_target", "target_contract_id"),
        UniqueConstraint(
            "source_contract_id", "target_contract_id", "relation_type", name="uq_contract_relation_pair_type"
        ),
    )


class ContractObligationRecord(OrgOwnedMixin, Base):
    __tablename__ = "contract_obligation"
    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False)
    obligation_key: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    owner_role: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="proposed", nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    recurrence: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    conditions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    source_field_refs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    evidence_refs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (
        CheckConstraint(f"status IN ({', '.join(repr(v) for v in sorted(OBLIGATION_STATUS_ALLOWED))})", name="status"),
        UniqueConstraint("organization_id","contract_id","obligation_key", name="uq_contract_obligation_key"),
        Index("ix_contract_obligation_contract_status", "contract_id", "status"),
        Index("ix_contract_obligation_due", "due_date"),
    )


class PolicyDecisionRecord(OrgOwnedMixin, Base):
    __tablename__ = "policy_decision"
    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False)
    policy_key: Mapped[str] = mapped_column(String(160), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation: Mapped[str] = mapped_column(String, nullable=False)
    evidence_refs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (
        CheckConstraint(f"outcome IN ({', '.join(repr(v) for v in sorted(POLICY_OUTCOME_ALLOWED))})", name="outcome"),
        Index("ix_policy_decision_contract", "contract_id"),
        Index("ix_policy_decision_outcome", "outcome"),
    )


class IntelligenceEvent(OrgOwnedMixin, Base):
    __tablename__ = "intelligence_event"
    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index("ix_intelligence_event_type", "event_type"),
        Index("ix_intelligence_event_unprocessed", "processed_at"),
    )


class ActionProposalRecord(OrgOwnedMixin, Base):
    __tablename__ = "action_proposal"
    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="proposed", nullable=False)
    assignee_role: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    evidence_refs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __table_args__ = (
        CheckConstraint(f"status IN ({', '.join(repr(v) for v in sorted(ACTION_STATUS_ALLOWED))})", name="status"),
        Index("ix_action_proposal_contract_status", "contract_id", "status"),
    )
