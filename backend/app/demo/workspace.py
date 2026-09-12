"""Demo-/UAT-Arbeitsbereich und request scope filtering."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.scope_context import current_scope_context
from app.database.models import DemoWorkspace, DemoWorkspaceEntry, Organization
from app.database.models.demo import DEMO_WORKSPACE_ID
from app.database.scope_queries import intersect_ids, scoped_contract_ids


def workspace_enabled(session: Session) -> bool:
    row = session.get(DemoWorkspace, DEMO_WORKSPACE_ID)
    return bool(row and row.enabled)


def set_workspace_enabled(session: Session, *, enabled: bool) -> None:
    row = session.get(DemoWorkspace, DEMO_WORKSPACE_ID)
    if row is None:
        row = DemoWorkspace(id=DEMO_WORKSPACE_ID, enabled=enabled)
        session.add(row)
    else:
        row.enabled = enabled
    session.flush()


def workspace_contract_ids(session: Session) -> Optional[set]:
    demo_ids: Optional[set] = None
    if workspace_enabled(session):
        demo_ids = set(session.scalars(select(DemoWorkspaceEntry.contract_id)).all())

    scope = current_scope_context()
    if not scope.organization_slug:
        return demo_ids
    organization = session.scalar(select(Organization).where(Organization.slug == scope.organization_slug))
    if organization is None:
        return demo_ids
    scope_ids = scoped_contract_ids(session, organization.id, scope.hospital_id, scope.department_id)
    return intersect_ids(demo_ids, scope_ids)


def track_contract(
    session: Session,
    *,
    contract_id: uuid.UUID,
    document_version_id: Optional[uuid.UUID] = None,
) -> bool:
    if not workspace_enabled(session):
        return False
    existing = session.scalars(select(DemoWorkspaceEntry).where(DemoWorkspaceEntry.contract_id == contract_id)).first()
    if existing is None:
        session.add(DemoWorkspaceEntry(
            workspace_id=DEMO_WORKSPACE_ID,
            contract_id=contract_id,
            document_version_id=document_version_id,
        ))
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
