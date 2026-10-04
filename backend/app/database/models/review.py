"""review_action – manuelle Korrektur-/Freigabe-Entscheidungen (Audit).

STEP 10A §12: Korrekturen mutieren das Original-`contract_snapshot` NIE
(immutabel); sie legen einen akzeptierten Zustand/Override an und halten die
Provenienz (original + manuell) sichtbar. `old_value` -> `new_value` + `reason`
und optionaler Link auf Quellen-Evidence werden als Audit-Zeile abgelegt.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

REVIEW_STATUS_ALLOWED = {"approved", "rejected", "needs_review"}


class ReviewAction(OrgOwnedMixin, Base):
    """Audit-Zeile einer Review-/Korrektur-Entscheidung zu einem extrahierten Feld."""

    __tablename__ = "review_action"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
    )
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract_extraction.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("extraction_evidence.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewer: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(repr(v) for v in sorted(REVIEW_STATUS_ALLOWED))})",
            name="status",
        ),
        Index("ix_review_action_contract_id", "contract_id"),
        Index("ix_review_action_extraction_id", "extraction_id"),
    )
