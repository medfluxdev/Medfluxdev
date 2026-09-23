"""Organisations-/Krankenhaus-Basis-Entitaet (STEP 10 §15, Foundation).

Nur die Ownership-Basis. Vollstaendige Auth-/RBAC-/RLS-Themen sind spaetere
Sicherheits-Arbeit; hier wird nur eine stabile Organisation + future-safe
Organisations-Zugehoerigkeit bereitgestellt.

RLS-Attachment (spaeter): `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + eine
Policy `organization_id = current_setting('app.organization_id')`. Dafuer traegt
jede owned Tabelle direkt eine `organization_id`-Spalte mit Index.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import uuid_pk

import uuid
from datetime import datetime
from sqlalchemy import DateTime, String


class Organization(Base):
    """Eine Organisation (Krankenhaus/Einkaufsverband), die Vertraege besitzt."""

    __tablename__ = "organization"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Organization id={self.id} slug={self.slug}>"
