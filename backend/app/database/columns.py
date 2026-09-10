"""Gemeinsame Spalten-/Mixin-Definitionen der Medflux-DB-ORM-Modelle."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

# Server-seitige uuidv7()-Erzeugung (PostgreSQL 18, STEP 10A §2A).
UUIDV7_SERVER_DEFAULT = text("uuidv7()")


def uuid_pk() -> Mapped[uuid.UUID]:
    """PostgreSQL-UUID-Primary-Key, server-seitig per uuidv7() generiert."""
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=UUIDV7_SERVER_DEFAULT,
    )


def org_id_col() -> Mapped[uuid.UUID]:
    """Organisations-Zugehoerigkeit (future-safe fuer spaetere RLS-Isolation)."""
    return mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="RESTRICT"),
        nullable=False,
    )


class TimestampMixin:
    """Technische Zeitstempel (TIMESTAMPTZ, UTC-Semantik)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class OrgOwnedMixin(TimestampMixin):
    """Technische Zeitstempel + Organisations-Zugehoerigkeit."""

    organization_id: Mapped[uuid.UUID] = org_id_col()
