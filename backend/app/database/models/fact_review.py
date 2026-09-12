from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import uuid_pk

FACT_REVIEW_ACTION_ALLOWED = {"confirmed", "corrected", "voided", "reopened"}
CONTRACT_REVIEW_STATUS_ALLOWED = {"unreviewed", "in_review", "reviewed", "changed_after_review", "manual_review_required"}


class FactReview(Base):
    __tablename__ = "fact_review"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False)
    fact_key: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    original_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    previous_effective_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_effective_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Snapshot fields preserve the historic identity even when the account changes later.
    reviewer_display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewer_identity_type: Mapped[str] = mapped_column(String(32), default="manual_unverified", nullable=False)
    authenticated_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_role_snapshot: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(f"action IN ({', '.join(repr(v) for v in sorted(FACT_REVIEW_ACTION_ALLOWED))})", name="action"),
        Index("ix_fact_review_contract_key_created", "contract_id", "fact_key", "created_at"),
        Index("ix_fact_review_contract_created", "contract_id", "created_at"),
    )


class ContractReview(Base):
    __tablename__ = "contract_review"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unreviewed")
    reviewer_display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewer_identity_type: Mapped[str] = mapped_column(String(32), default="manual_unverified", nullable=False)
    authenticated_actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_role_snapshot: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    change_noted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(f"status IN ({', '.join(repr(v) for v in sorted(CONTRACT_REVIEW_STATUS_ALLOWED))})", name="status"),
    )

    @property
    def is_material_reviewed(self) -> bool:
        return self.status == "reviewed" and self.reviewed_at is not None
