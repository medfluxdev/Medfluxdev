from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import uuid_pk

ACCOUNT_ROLES = {"admin", "contract_manager", "reviewer", "viewer"}


class Account(Base):
    __tablename__ = "account"

    id: Mapped[uuid.UUID] = uuid_pk()
    login_name: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # PBKDF2-derived material only; plaintext credentials are never persisted.
    credential_digest: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    profile_photo_data_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AccountMembership(Base):
    __tablename__ = "account_membership"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "account_id", name="uq_account_membership_org_account"),
        Index("ix_account_membership_account_active", "account_id", "is_active"),
    )
