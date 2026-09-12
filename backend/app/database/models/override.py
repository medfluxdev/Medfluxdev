"""contract_override – Append-only Protokoll für manuelle Bestätigungs-/Override-
Entscheidungen zu materialen Vertragsfakten (UAT Defect Batch A).

STEP 16 (Authentication/RBAC) ist NICHT implementiert. Daher ist der Akteur
(`actor_id`/`actor_type`) NULLABLE und RBAC-bereit; in Dev wird `is_development`
wahr gesetzt, um die Provenienz ehrlich zu kennzeichnen – es wird NIE eine
Mitarbeiter-Identität erfunden.

Zeilen sind IMMUTABLE (append-only): jede Übernahme/Änderung/Bestätigung/Void
wird als NEUE Zeile geschrieben → vollständige Audit-Historie. Der „aktuelle
wirksame" Wert zu einem `key` ergibt sich als letzte `set`-Zeile je key (nach
created_at); ein `void` legt eine Tombstone-Zeile an (kein wirksamer Override).

Keys (stabil, kodiert in app/contracts/overrides/keys.py):
- cost.tax_basis
- cost.tax_rate_percent
- date.event_start
- fact.confirm
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
    """Append-only Audit-/Override-Zeile für einen Vertragsfakt."""

    __tablename__ = "contract_override"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    # value ist nur bei action='set' gesetzt (JSONB: Zahl/Basis/ISO-Datum/String).
    value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Bei action='confirm': welche extrahierte Feld-Referenz bestätigt wird.
    fact_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # RBAC-bereit; bis STEP 16 NULL + is_development=True (keine erfundene Identität).
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
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
