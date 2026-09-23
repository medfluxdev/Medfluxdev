"""Demospace (Demo-/UAT-Arbeitsbereich) – kleinstes Dev-/UAT-Mechanismus.

Isoliert einen für die Kunden-Demo sichtbaren Arbeitsbereich, ohne Bestand-
Verträge zu löschen oder zu verändern:
- `demo_workspace` (eine Zeile) steuert, ob der Arbeitsbereich aktiv ist.
- `demo_workspace_entry` registriert je während der Demo hochgeladenen
  Vertrag eine Zeile (Vertrag + ggf. Dokumentversion).

Aktiv: Vertragsliste/Dashboard/Detail zeigen NUR diese Demo-Verträge.
Deaktiviert: Normales Portfolio ist unverändert sichtbar.

Dieser Mechanismus ist reine Dev-/UAT-Funktionalität; die Produktions-
Geschäftslogik (Liste/Dashboard) kennt ihn nur über einen optional
übergebenen `workspace_contract_ids`-Predicate.
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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import uuid_pk

# Fester ID der einzigen Workspace-Zeile (Stable-Marker).
DEMO_WORKSPACE_ID = uuid.UUID("01100000-0000-0000-0000-000000000001")


class DemoWorkspace(Base):
    """Eine Zeile: ob der Demo-/UAT-Arbeitsbereich aktiv ist."""

    __tablename__ = "demo_workspace"

    id: Mapped[uuid.UUID] = uuid_pk()
    enabled: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(f"id = '{DEMO_WORKSPACE_ID}'::uuid", name="single_row"),
    )


class DemoWorkspaceEntry(Base):
    """Registriert einen während der Demo hochgeladenen Vertrag im Arbeitsbereich."""

    __tablename__ = "demo_workspace_entry"

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("demo_workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("contract.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    document_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_version.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("contract_id", name="uq_demo_workspace_entry_contract"),
        Index("ix_demo_workspace_entry_workspace", "workspace_id"),
    )