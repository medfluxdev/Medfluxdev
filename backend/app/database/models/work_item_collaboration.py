"""Human collaboration metadata for canonical Work Queue items.

Derived WorkItem rows remain authoritative operational tasks. Assignment,
reminders and comments live separately so reconcile can never overwrite human
collaboration state.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk


class WorkItemCollaboration(OrgOwnedMixin, Base):
    __tablename__ = "work_item_collaboration"

    id: Mapped[uuid.UUID] = uuid_pk()
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("work_item.id", ondelete="CASCADE"), nullable=False
    )
    assignee_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    owner_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remind_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("work_item_id", name="uq_work_item_collaboration_item"),
        Index("ix_work_item_collaboration_assignee", "assignee_account_id"),
        Index("ix_work_item_collaboration_remind_at", "remind_at"),
    )


class WorkItemComment(OrgOwnedMixin, Base):
    __tablename__ = "work_item_comment"

    id: Mapped[uuid.UUID] = uuid_pk()
    work_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("work_item.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    display_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_work_item_comment_item_created", "work_item_id", "created_at"),
    )
