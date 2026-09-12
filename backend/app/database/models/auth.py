"""Lokale Benutzer- und Audit-Entitaeten (STEP 16)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, TimestampMixin, org_id_col, uuid_pk


class User(Base, OrgOwnedMixin):
    """Lokaler, organisationsgebundener MedFlux-Benutzer."""

    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("organization_id", "username", name="uq_app_user_org_username"),
        CheckConstraint("role IN ('admin','reviewer','viewer')", name="app_user_role"),
        Index("ix_app_user_org_active", "organization_id", "active"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False, server_default="viewer")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    """Append-only Sicherheits-/Benutzer-Audit.

    Es gibt absichtlich keinen Updated-at-Zeitstempel: Audit-Zeilen werden nie
    fachlich mutiert. Korrekturen entstehen als neue Events.
    """

    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_org_created", "organization_id", "created_at"),
        Index("ix_audit_event_entity", "entity_type", "entity_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID] = org_id_col()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
