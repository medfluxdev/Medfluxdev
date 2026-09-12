"""Append-only contract override history with authenticated actor provenance."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

OVERRIDE_ACTION_ALLOWED = {"set", "void", "confirm"}


class ContractOverride(OrgOwnedMixin, Base):
    __tablename__ = "contract_override"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    fact_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    actor_display_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor_role_snapshot: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_development: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            f"action IN ({', '.join(repr(v) for v in sorted(OVERRIDE_ACTION_ALLOWED))})",
            name="action",
        ),
        Index("ix_contract_override_contract_key", "contract_id", "key"),
        Index("ix_contract_override_contract_created", "contract_id", "created_at"),
    )
