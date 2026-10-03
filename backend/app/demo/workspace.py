"""Demo-/UAT-Arbeitsbereich – Service (Enable/Disable/Track/Include).

Kleinster Mechanismus für eine saubere Kunden-Demo:
- Aktiv ⇒ Vertragsliste/Dashboard/Detail zeigen NUR während der Demo
  hochgeladene Verträge (`workspace_contract_ids`).
- Deaktivieren stellt das normale Portfolio wieder her; es wird nichts
  gelöscht oder verändert.
- `track_contract` registriert während der Demo hochgeladene Verträge
  ausschließlich im aktiven Modus.

Der Workspace ist reine Dev-/UAT-Ebene: Die Produktionsabfragen erhalten
lediglich einen optionalen `workspace_contract_ids`-Predicate.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import Contract, DemoWorkspace, DemoWorkspaceEntry
from app.database.models.demo import DEMO_WORKSPACE_ID


def workspace_enabled(session: Session) -> bool:
    # Demo/UAT filtering must never influence pilot or production portfolios,
    # even if a stale enabled row exists from an earlier development run.
    if settings.app_env.strip().casefold() not in {"development", "test"}:
        return False
    row = session.get(DemoWorkspace, DEMO_WORKSPACE_ID)
    return bool(row and row.enabled)


def set_workspace_enabled(session: Session, *, enabled: bool) -> None:
    if settings.app_env.strip().casefold() not in {"development", "test"}:
        raise RuntimeError("Demo-Arbeitsbereich ist nur in Entwicklung/Test erlaubt.")
    row = session.get(DemoWorkspace, DEMO_WORKSPACE_ID)
    if row is None:
        row = DemoWorkspace(id=DEMO_WORKSPACE_ID, enabled=enabled)
        session.add(row)
    else:
        row.enabled = enabled
    session.flush()


def workspace_contract_ids(session: Session) -> Optional[set]:
    """Aktive Workspace-Verträge; None = Workspace aus (kein Filter)."""
    if not workspace_enabled(session):
        return None
    rows = session.scalars(select(DemoWorkspaceEntry.contract_id)).all()
    return set(rows)


def track_contract(
    session: Session,
    *,
    contract_id: uuid.UUID,
    document_version_id: Optional[uuid.UUID] = None,
) -> bool:
    """Registriert den Vertrag IM aktiven Modus (idempotent)."""
    if not workspace_enabled(session):
        return False
    existing = session.scalars(
        select(DemoWorkspaceEntry).where(
            DemoWorkspaceEntry.contract_id == contract_id
        )
    ).first()
    if existing is None:
        session.add(
            DemoWorkspaceEntry(
                workspace_id=DEMO_WORKSPACE_ID,
                contract_id=contract_id,
                document_version_id=document_version_id,
            )
        )
        session.flush()
    return True


def workspace_status(session: Session) -> dict:
    enabled = workspace_enabled(session)
    ids = workspace_contract_ids(session) if enabled else set()
    return {
        "enabled": enabled,
        "contract_ids": sorted(str(i) for i in (ids or set())),
        "contract_count": len(ids or set()),
    }
