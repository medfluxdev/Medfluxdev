from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import uuid_pk


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    display_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    role_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    event_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    context_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_activity_log_org_created", "organization_id", "created_at"),
        Index("ix_activity_log_object_created", "object_type", "object_id", "created_at"),
    )
