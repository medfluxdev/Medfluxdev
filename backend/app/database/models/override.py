"""Append-only Protokoll fuer manuelle Bestätigungen und Vertrags-Overrides.

STEP 16 bindet bei aktivierter lokaler Authentifizierung `actor_id` an
`app_user.id`, setzt `actor_type=authenticated_local` und markiert die Aktion
nicht als Entwicklung. Ohne Auth bleibt die bisherige ehrliche Dev-Provenienz.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

OVERRIDE_ACTION_ALLOWED = {"set", "void", "confirm"}


class ContractOverride(OrgOwnedMixin, Base):
    """Append-only Audit-/Override-Zeile fuer einen Vertragsfakt."""

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
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("app_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_development: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            f"action IN ({', '.join(repr(v) for v in sorted(OVERRIDE_ACTION_ALLOWED))})",
            name="action",
        ),
        Index("ix_contract_override_contract_key", "contract_id", "key"),
        Index("ix_contract_override_contract_created", "contract_id", "created_at"),
    )
